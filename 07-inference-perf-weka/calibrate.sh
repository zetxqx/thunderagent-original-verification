#!/usr/bin/env bash
# Saturation calibration: baseline (default/pure-proxy) arm only, three
# concurrencies in parallel on three pods on distinct nodes, 10 min each.
#
# Answers, before committing hours to the full sweep:
#   1. does this regime actually create cache pressure?  (baseline hit rate)
#   2. is effective concurrency sustained, or does it decay?
#   3. does the bigger corpus compile within the job's memory/time budget?
#   4. does the report now carry per-request cached_tokens?
#
# Usage: ./calibrate.sh [concurrency ...]    (default: 40 64 96)
set -euo pipefail

NS=llm-d-program-aware-scheduling
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONCS=("${@:-}")
[ -z "${CONCS[0]:-}" ] && CONCS=(64 128 192)
WINDOW=600
CAL_TRACES=0     # no cap: c=192 over 10 min needs >= 192 x 1.5 = 288 traces

AB_ID="cal-$(date +%Y%m%d-%H%M%S)"
OUT_ROOT="$SCRIPT_DIR/results/$AB_ID"
mkdir -p "$OUT_ROOT"
echo "calibration id: $AB_ID  concurrencies: ${CONCS[*]}"

# one Running decode pod per distinct node
PODS=() IPS=() NODES=()
while read -r name node ip; do
  skip=""
  for n in "${NODES[@]:-}"; do [ "$n" = "$node" ] && skip=1; done
  [ -n "$skip" ] && continue
  NODES+=("$node"); PODS+=("$name"); IPS+=("$ip")
done < <(kubectl get pods -n "$NS" -l llm-d.ai/role=decode --field-selector=status.phase=Running \
  -o jsonpath='{range .items[*]}{.metadata.name} {.spec.nodeName} {.status.podIP}{"\n"}{end}' | sort)
echo "pods: ${PODS[*]}"
[ "${#PODS[@]}" -ge "${#CONCS[@]}" ] || { echo "need ${#CONCS[@]} pods on distinct nodes, have ${#PODS[@]}" >&2; exit 1; }

cat > "$OUT_ROOT/manifest-global.json" <<EOF
{"ab_id":"$AB_ID","kind":"calibration","started":"$(date -u +%Y-%m-%dT%H:%M:%SZ)",
 "window_s":$WINDOW,"max_traces":$CAL_TRACES,"arms":"default only",
 "concurrencies":"$(IFS=,; echo "${CONCS[*]}")",
 "pods":"$(IFS=,; echo "${PODS[*]}")","nodes":"$(IFS=,; echo "${NODES[*]}")",
 "inference_perf":"quay.io/inference-perf/inference-perf:v0.7.0@sha256:d247e6ad725dc5bb56df71d115abc8ca455bba9f0ccd4110e14bbb56504250ec",
 "filter_traces_sha256":"$(shasum -a 256 "$SCRIPT_DIR/filter_traces.py" | cut -d' ' -f1)",
 "config_template_sha256":"$(shasum -a 256 "$SCRIPT_DIR/config-tmpl.yaml" | cut -d' ' -f1)"}
EOF

kubectl create configmap weka-bench-scripts \
  --from-file=filter_traces.py="$SCRIPT_DIR/filter_traces.py" \
  --from-file=prober.py="$SCRIPT_DIR/prober.py" \
  -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep 20; done; }

run_cal() { # run_cal <concurrency> <pod> <ip>
  local C=$1 VP=$2 BIP=$3 CELL="cal-c$1" RN="thunderagent-cal-c$1"
  local CELL_DIR="$OUT_ROOT/$CELL"
  mkdir -p "$CELL_DIR"
  echo "[$CELL] pod=$VP ip=$BIP"

  kubectl exec "$VP" -n "$NS" -c modelserver -- python3 -c "
import urllib.request
print('reset_prefix_cache:', urllib.request.urlopen(urllib.request.Request(
    'http://localhost:8000/reset_prefix_cache', method='POST')).status)"

  sed -e "s/__NAME__/$RN/g" -e "s/__MODE__/default/g" -e "s|__ROUTER_EXTRA__||g" \
      -e "s/__BACKEND_IP__/$BIP/g" "$SCRIPT_DIR/router-weka.yaml" | kubectl apply -f - >/dev/null
  kubectl rollout status "deploy/$RN" -n "$NS" --timeout=180s >/dev/null
  echo "[$CELL] router up"

  sed -e "s/__CONCURRENCY__/$C/" -e "s/__STAGE_TIMEOUT__/$WINDOW/" -e "s/__ROUTER__/$RN/" \
    "$SCRIPT_DIR/config-tmpl.yaml" > "$CELL_DIR/config.yml"
  kubectl create configmap "weka-bench-config-$CELL" --from-file=config.yml="$CELL_DIR/config.yml" \
    -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

  kubectl delete job "weka-bench-$CELL" -n "$NS" --ignore-not-found >/dev/null
  kubectl wait --for=delete pod -l cell="$CELL" -n "$NS" --timeout=180s 2>/dev/null || true
  sed -e "s/__CELL__/$CELL/g" -e "s/__RUN_ID__/$AB_ID-$CELL/" -e "s/__ROUTER__/$RN/" \
      -e "s/__BACKEND_IP__/$BIP/" -e "s/__MAX_TRACES__/$CAL_TRACES/" \
      -e "s/__RUN_BUDGET__/$((WINDOW + 1800))/" \
      -e "s/__PROBE_MAX_SECONDS__/$((WINDOW + 900))/" \
    "$SCRIPT_DIR/job-weka.yaml" | kubectl apply -f - >/dev/null
  kubectl wait pod -l cell="$CELL" -n "$NS" --for=condition=Ready --timeout=900s
  local POD
  POD=$(kubectl get pod -l cell="$CELL" -n "$NS" --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}')
  local T0=$(date +%s)

  while ! kubectl exec "$POD" -n "$NS" -c bench -- test -f /results/DONE 2>/dev/null; do
    echo "$(date +%H:%M:%S) [$CELL] $(kubectl exec "deploy/$RN" -n "$NS" -- python -c "import urllib.request,json;h=json.load(urllib.request.urlopen('http://localhost:8300/health'));print('progs',h['programs_count'],'reasoning',h['reasoning_count'])" 2>/dev/null || echo n/a)"
    sleep 30
  done

  kubectl logs "$POD" -n "$NS" -c prober --tail=500 > "$CELL_DIR/prober.log" 2>/dev/null || true
  retry kubectl cp "$NS/$POD:/results" "$CELL_DIR/results" -c bench >/dev/null
  local BNODE
  BNODE=$(kubectl get pod "$POD" -n "$NS" -o jsonpath='{.spec.nodeName}' 2>/dev/null)
  local VNODE
  VNODE=$(kubectl get pod "$VP" -n "$NS" -o jsonpath='{.spec.nodeName}' 2>/dev/null)
  echo "{\"cell\":\"$CELL\",\"concurrency\":$C,\"pod\":\"$VP\",\"vllm_node\":\"$VNODE\",\"bench_pod\":\"$POD\",\"bench_node\":\"$BNODE\",\"window_s\":$WINDOW,\"max_traces\":$CAL_TRACES,\"started_epoch\":$T0,\"finished_epoch\":$(date +%s)}" > "$CELL_DIR/manifest.json"
  kubectl delete job "weka-bench-$CELL" -n "$NS" >/dev/null
  kubectl delete "deploy/$RN" "svc/$RN" -n "$NS" --ignore-not-found >/dev/null
  echo "[$CELL] collected"
}

PIDS=()
for i in "${!CONCS[@]}"; do
  run_cal "${CONCS[$i]}" "${PODS[$i]}" "${IPS[$i]}" > >(sed "s/^/[c${CONCS[$i]}] /") 2>&1 &
  PIDS+=($!)
done
FAIL=0
for p in "${PIDS[@]}"; do wait "$p" || FAIL=1; done

echo; echo "===== calibration verdict ====="
"${VIZ_PYTHON:-python3}" "$SCRIPT_DIR/verdict.py" "$OUT_ROOT"
[ "$FAIL" = 0 ] || echo "WARNING: at least one cell reported a failure"
echo "artifacts: $OUT_ROOT"
