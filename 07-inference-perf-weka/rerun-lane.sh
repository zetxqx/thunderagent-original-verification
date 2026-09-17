#!/usr/bin/env bash
# Rerun ONE lane (default then tr-decay at a given concurrency) into an
# existing results root. Used to redo a lane whose spot vLLM pod was
# preempted mid-sweep, and as a kill-safe restartable unit: cluster-side
# Jobs keep results for 8h after DONE, so re-invoking this script skips
# nothing but can always re-collect via collect-lane.sh.
#
# Usage: rerun-lane.sh <results_root> <concurrency> <vllm_pod> <backend_ip>
set -euo pipefail

NS=llm-d-program-aware-scheduling
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_ROOT=$1 C=$2 VP=$3 BIP=$4
RN="thunderagent-ab-c$C"
AB_ID="$(basename "$OUT_ROOT")"

echo "lane c$C on pod $VP ($BIP), results -> $OUT_ROOT"

kubectl create configmap weka-bench-scripts \
  --from-file=filter_traces.py="$SCRIPT_DIR/filter_traces.py" \
  --from-file=prober.py="$SCRIPT_DIR/prober.py" \
  -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep 20; done; }

run_cell() { # run_cell <cell> <mode> <router_extra>
  local CELL=$1 RM=$2 RX=$3
  local RUN_ID="$AB_ID-$CELL" CELL_DIR="$OUT_ROOT/$CELL"
  echo "===== cell $CELL (mode=$RM) ====="
  mkdir -p "$CELL_DIR"

  kubectl exec "$VP" -n "$NS" -c modelserver -- python3 -c "
import urllib.request
print('reset_prefix_cache:', urllib.request.urlopen(urllib.request.Request(
    'http://localhost:8000/reset_prefix_cache', method='POST')).status)"

  sed -e "s/__NAME__/$RN/g" -e "s/__MODE__/$RM/g" \
      -e "s|__ROUTER_EXTRA__|$RX|g" -e "s/__BACKEND_IP__/$BIP/g" \
    "$SCRIPT_DIR/router-weka.yaml" | kubectl apply -f -
  kubectl rollout restart "deploy/$RN" -n "$NS" >/dev/null 2>&1 || true
  kubectl rollout status "deploy/$RN" -n "$NS" --timeout=180s
  local READY=""
  for _ in $(seq 1 30); do
    READY=$(kubectl exec "deploy/$RN" -n "$NS" -- python -c "import urllib.request,json;print(json.load(urllib.request.urlopen('http://localhost:8300/health'))['router_mode'])" 2>/dev/null || true)
    [ "$READY" = "$RM" ] && break
    sleep 2
  done
  [ "$READY" = "$RM" ] || { echo "FATAL: $RN not in mode $RM (got $READY)" >&2; exit 1; }
  echo "[$RN] ready: mode=$READY"

  sed -e "s/__CONCURRENCY__/$C/" -e "s/__STAGE_TIMEOUT__/2700/" \
      -e "s/__ROUTER__/$RN/" "$SCRIPT_DIR/config-tmpl.yaml" > "$CELL_DIR/config.yml"
  kubectl create configmap "weka-bench-config-$CELL" \
    --from-file=config.yml="$CELL_DIR/config.yml" \
    -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

  kubectl delete job "weka-bench-$CELL" -n "$NS" --ignore-not-found
  kubectl wait --for=delete pod -l cell="$CELL" -n "$NS" --timeout=180s 2>/dev/null || true
  sed -e "s/__CELL__/$CELL/g" -e "s/__RUN_ID__/$RUN_ID/" -e "s/__ROUTER__/$RN/" \
      -e "s/__BACKEND_IP__/$BIP/" -e "s/__MAX_TRACES__/0/" \
      -e "s/__RUN_BUDGET__/4500/" -e "s/__PROBE_MAX_SECONDS__/3600/" \
    "$SCRIPT_DIR/job-weka.yaml" | kubectl apply -f -
  kubectl wait pod -l cell="$CELL" -n "$NS" --for=condition=Ready --timeout=600s
  local POD T0
  POD=$(kubectl get pod -l cell="$CELL" -n "$NS" --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}')
  T0=$(date +%s)

  while ! kubectl exec "$POD" -n "$NS" -c bench -- test -f /results/DONE 2>/dev/null; do
    echo "$(date +%H:%M:%S) [$CELL] $(kubectl exec "deploy/$RN" -n "$NS" -- python -c "import urllib.request,json;h=json.load(urllib.request.urlopen('http://localhost:8300/health'));print('programs',h['programs_count'],'paused',h['paused_count'])" 2>/dev/null || echo n/a)"
    sleep 30
  done

  kubectl logs "deploy/$RN" -n "$NS" --tail=200000 > "$CELL_DIR/router.log" 2>/dev/null || true
  kubectl logs "$POD" -n "$NS" -c prober --tail=2000 > "$CELL_DIR/prober.log" 2>/dev/null || true
  retry kubectl cp "$NS/$POD:/results" "$CELL_DIR/results" -c bench >/dev/null
  cat > "$CELL_DIR/manifest.json" <<EOF
{
  "cell": "$CELL", "run_id": "$RUN_ID", "router": "$RN", "router_mode": "$RM",
  "router_extra": "$RX", "vllm_pod": "$VP", "vllm_pod_ip": "$BIP",
  "concurrency": $C, "stage_timeout_s": 2700,
  "started_epoch": $T0, "finished_epoch": $(date +%s),
  "config_sha256": "$(shasum -a 256 "$CELL_DIR/config.yml" | cut -d' ' -f1)",
  "bench_pod": "$POD", "note": "lane rerun after spot preemption of the original pod"
}
EOF
  kubectl delete job "weka-bench-$CELL" -n "$NS"
  tail -4 "$CELL_DIR/results/bench-stdout.log" 2>/dev/null || true
}

run_cell "default-c$C"  default ""
run_cell "tr-decay-c$C" tr      "--use-acting-token-decay"
kubectl delete "deploy/$RN" "svc/$RN" -n "$NS" --ignore-not-found
echo "lane c$C complete"
