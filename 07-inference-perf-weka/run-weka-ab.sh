#!/usr/bin/env bash
# Weka trace replay A/B sweep through the original ThunderAgent router.
# PARALLEL layout: each concurrency pair (default-cN then tr-decay-cN,
# sequential WITHIN the pair on the SAME dedicated vLLM pod) runs as one
# lane; the three lanes (c8, c16, c24) run in parallel on three vLLM pods
# on DISTINCT nodes. Wall time ~= 2 x 45 min + overhead.
#
# Usage:
#   ./run-weka-ab.sh smoke   # 1 cell: tr-decay c3, 3 traces, 5-min stage
#   ./run-weka-ab.sh         # full sweep: 3 parallel lanes x (default, tr-decay)
set -euo pipefail

NS=llm-d-program-aware-scheduling
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-full}"

AB_ID="weka-$(date +%Y%m%d-%H%M%S)-$MODE"
OUT_ROOT="$SCRIPT_DIR/results/$AB_ID"
mkdir -p "$OUT_ROOT"
echo "run id: $AB_ID"

# --- pick one Running decode pod per DISTINCT node (up to 3 lanes) ---------
PODS=() IPS=()
while read -r name node ip; do
  for n in "${NODES[@]:-}"; do [ "$n" = "$node" ] && continue 2; done
  NODES+=("$node"); PODS+=("$name"); IPS+=("$ip")
done < <(kubectl get pods -n "$NS" -l llm-d.ai/role=decode \
  --field-selector=status.phase=Running \
  -o jsonpath='{range .items[*]}{.metadata.name} {.spec.nodeName} {.status.podIP}{"\n"}{end}' | sort)
echo "lane pods: ${PODS[*]} (nodes: ${NODES[*]})"
[ "${#PODS[@]}" -ge 1 ] || { echo "no running decode pods" >&2; exit 1; }

cat > "$OUT_ROOT/manifest-global.json" <<EOF
{
  "ab_id": "$AB_ID",
  "started": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "kubectl_context": "$(kubectl config current-context)",
  "lane_pods": "$(IFS=,; echo "${PODS[*]}")",
  "lane_pod_ips": "$(IFS=,; echo "${IPS[*]}")",
  "lane_nodes": "$(IFS=,; echo "${NODES[*]}")",
  "inference_perf": "quay.io/inference-perf/inference-perf:v0.7.0@sha256:d247e6ad725dc5bb56df71d115abc8ca455bba9f0ccd4110e14bbb56504250ec",
  "thunderagent_source_commit": "7ddc861",
  "thunderagent_image": "us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/thunderagent-original:7ddc861",
  "base_seed": 20260915,
  "config_template_sha256": "$(shasum -a 256 "$SCRIPT_DIR/config-tmpl.yaml" | cut -d' ' -f1)",
  "filter_traces_sha256": "$(shasum -a 256 "$SCRIPT_DIR/filter_traces.py" | cut -d' ' -f1)",
  "prober_sha256": "$(shasum -a 256 "$SCRIPT_DIR/prober.py" | cut -d' ' -f1)"
}
EOF

kubectl create configmap weka-bench-scripts \
  --from-file=filter_traces.py="$SCRIPT_DIR/filter_traces.py" \
  --from-file=prober.py="$SCRIPT_DIR/prober.py" \
  -n "$NS" --dry-run=client -o yaml | kubectl apply -f -

retry() { # retry <cmd...> - 5 attempts, 20s apart (network blips, laptop naps)
  local n=0
  until "$@"; do
    n=$((n + 1))
    [ "$n" -ge 5 ] && return 1
    echo "retry $n/5: $*" >&2
    sleep 20
  done
}

reset_cache() { # reset_cache <vllm_pod>
  kubectl exec "$1" -n "$NS" -c modelserver -- python3 -c "
import urllib.request
r = urllib.request.urlopen(urllib.request.Request(
    'http://localhost:8000/reset_prefix_cache', method='POST'))
print('reset_prefix_cache:', r.status)"
}

deploy_router() { # deploy_router <router_name> <mode> <router_extra> <backend_ip>
  local RN=$1 RM=$2 RX=$3 BIP=$4
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
  [ "$READY" = "$RM" ] || { echo "FATAL: $RN mode $RM not ready (got $READY)" >&2; return 1; }
  echo "[$RN] ready: mode=$READY"
}

run_cell() { # run_cell <cell> <router_name> <router_mode> <router_extra> <vllm_pod> <backend_ip> <concurrency> <timeout> <max_traces>
  local CELL=$1 RN=$2 RM=$3 RX=$4 VP=$5 BIP=$6 C=$7 TMO=$8 MAXTR=$9
  local RUN_ID="$AB_ID-$CELL" CELL_DIR="$OUT_ROOT/$CELL"
  echo "===== cell $CELL (router=$RN mode=$RM pod=$VP c=$C timeout=${TMO}s) ====="
  mkdir -p "$CELL_DIR"

  # Spot preemption guard: pin the backend by UID, not name. If the node is
  # reclaimed mid-cell the replacement pod gets a new UID and IP, the router's
  # static backend address goes dead, and the pair is no longer same-hardware.
  # Detect it rather than silently producing an uncomparable arm.
  local VUID
  VUID=$(kubectl get pod "$VP" -n "$NS" -o jsonpath='{.metadata.uid}' 2>/dev/null)
  [ -n "$VUID" ] || { echo "FATAL [$CELL]: target pod $VP is gone before start" >&2; return 1; }

  reset_cache "$VP"
  deploy_router "$RN" "$RM" "$RX" "$BIP"

  sed -e "s/__CONCURRENCY__/$C/" -e "s/__STAGE_TIMEOUT__/$TMO/" \
      -e "s/__ROUTER__/$RN/" "$SCRIPT_DIR/config-tmpl.yaml" > "$CELL_DIR/config.yml"
  kubectl create configmap "weka-bench-config-$CELL" \
    --from-file=config.yml="$CELL_DIR/config.yml" \
    -n "$NS" --dry-run=client -o yaml | kubectl apply -f -

  kubectl delete job "weka-bench-$CELL" -n "$NS" --ignore-not-found
  kubectl wait --for=delete pod -l cell="$CELL" -n "$NS" --timeout=120s 2>/dev/null || true
  sed -e "s/__CELL__/$CELL/g" -e "s/__RUN_ID__/$RUN_ID/" -e "s/__ROUTER__/$RN/" \
      -e "s/__BACKEND_IP__/$BIP/" -e "s/__MAX_TRACES__/$MAXTR/" \
      -e "s/__RUN_BUDGET__/$((TMO + 1800))/" -e "s/__PROBE_MAX_SECONDS__/$((TMO + 900))/" \
    "$SCRIPT_DIR/job-weka.yaml" | kubectl apply -f -
  kubectl wait pod -l cell="$CELL" -n "$NS" --for=condition=Ready --timeout=600s
  local POD T0
  POD=$(kubectl get pod -l cell="$CELL" -n "$NS" \
    --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  T0=$(date +%s)

  local PREEMPTED=false
  while ! kubectl exec "$POD" -n "$NS" -c bench -- test -f /results/DONE 2>/dev/null; do
    local NOWUID
    NOWUID=$(kubectl get pod "$VP" -n "$NS" -o jsonpath='{.metadata.uid}' 2>/dev/null)
    if [ "$NOWUID" != "$VUID" ]; then
      echo "PREEMPTED [$CELL]: backend pod $VP changed (uid $VUID -> ${NOWUID:-gone}); aborting cell" >&2
      PREEMPTED=true
      break
    fi
    local H
    H=$(kubectl exec "deploy/$RN" -n "$NS" -- python -c "import urllib.request,json;h=json.load(urllib.request.urlopen('http://localhost:8300/health'));print(h['programs_count'],h['paused_count'])" 2>/dev/null || echo "n/a")
    echo "$(date +%H:%M:%S) [$CELL] programs/paused: $H"
    sleep 30
  done

  # Router + prober logs FIRST (per-cell filenames), before any teardown.
  kubectl logs "deploy/$RN" -n "$NS" --tail=200000 > "$CELL_DIR/router.log" 2>/dev/null || true
  kubectl logs "$POD" -n "$NS" -c prober --tail=2000 > "$CELL_DIR/prober.log" 2>/dev/null || true
  retry kubectl cp "$NS/$POD:/results" "$CELL_DIR/results" -c bench >/dev/null

  cat > "$CELL_DIR/manifest.json" <<EOF
{
  "cell": "$CELL", "run_id": "$RUN_ID",
  "router": "$RN", "router_mode": "$RM", "router_extra": "$RX",
  "vllm_pod": "$VP", "vllm_pod_ip": "$BIP",
  "concurrency": $C, "stage_timeout_s": $TMO, "max_traces": $MAXTR,
  "vllm_pod_uid": "$VUID", "preempted": $PREEMPTED,
  "started_epoch": $T0, "finished_epoch": $(date +%s),
  "config_sha256": "$(shasum -a 256 "$CELL_DIR/config.yml" | cut -d' ' -f1)",
  "router_image_id": "$(kubectl get pod -l app="$RN" -n "$NS" -o jsonpath='{.items[0].status.containerStatuses[0].imageID}')",
  "bench_pod": "$POD"
}
EOF
  kubectl delete job "weka-bench-$CELL" -n "$NS"
  tail -4 "$CELL_DIR/results/bench-stdout.log" 2>/dev/null || true
  if [ "$PREEMPTED" = true ]; then
    mv "$CELL_DIR" "$CELL_DIR-PREEMPTED"
    echo "[$CELL] marked PREEMPTED; rerun this lane with rerun-lane.sh" >&2
    return 1
  fi
}

run_lane() { # run_lane <concurrency> <vllm_pod> <backend_ip>   (default then tr-decay, same pod)
  local C=$1 VP=$2 BIP=$3 RN="thunderagent-ab-c$1"
  run_cell "default-c$C"  "$RN" default ""                         "$VP" "$BIP" "$C" 2700 0
  run_cell "tr-decay-c$C" "$RN" tr      "--use-acting-token-decay" "$VP" "$BIP" "$C" 2700 0
  kubectl delete "deploy/$RN" "svc/$RN" -n "$NS" --ignore-not-found
}

if [ "$MODE" = "smoke" ]; then
  RN="thunderagent-ab-smoke"
  run_cell "smoke-tr-decay-c3" "$RN" tr "--use-acting-token-decay" \
    "${PODS[0]}" "${IPS[0]}" 3 300 3
  kubectl delete "deploy/$RN" "svc/$RN" -n "$NS" --ignore-not-found
else
  [ "${#PODS[@]}" -ge 3 ] || { echo "need 3 pods on distinct nodes, have ${#PODS[@]}" >&2; exit 1; }
  # Saturated regime, from calibration (cal-20260916-134154 and -103627):
  # at these concurrencies the baseline hit rate collapses to 0.10-0.41 with
  # KV at 100% and engine preemptions. The earlier 8/16/24 sweep sat in the
  # unsaturated regime (hit rate 0.90) where no scheduler can help.
  CS=(${SWEEP_CONCURRENCIES:-96 128 192})
  LANE_PIDS=()
  for i in 0 1 2; do
    run_lane "${CS[$i]}" "${PODS[$i]}" "${IPS[$i]}" \
      > >(sed "s/^/[lane-c${CS[$i]}] /") 2>&1 &
    LANE_PIDS+=($!)
  done
  FAIL=0
  for p in "${LANE_PIDS[@]}"; do wait "$p" || FAIL=1; done
  [ "$FAIL" = 0 ] || { echo "one or more lanes failed" >&2; exit 1; }
fi

echo; echo "all artifacts: $OUT_ROOT"
