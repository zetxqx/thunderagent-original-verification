#!/usr/bin/env bash
# Single-node A/B: original ThunderAgent `default` (pure proxy) vs `tr`
# (program-aware admission control) against the SAME single vLLM pod.
#
# Sequence per arm: reset the pod's prefix cache -> (re)deploy the AB router
# in that mode -> run the in-cluster benchmark job -> collect results.
# Arms run sequentially (default first, then tr) so they never share load.
# Finally runs compare.py (use VIZ_PYTHON for a python with matplotlib).
set -euo pipefail

NS=llm-d-program-aware-scheduling
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AB_ID="ab-$(date +%Y%m%d-%H%M%S)"
OUT_ROOT="$SCRIPT_DIR/results/$AB_ID"
mkdir -p "$OUT_ROOT"
echo "A/B id: $AB_ID"

# Pick the target vLLM pod (name-sorted first, recorded for reproducibility).
VLLM_POD=$(kubectl get pods -n "$NS" -l llm-d.ai/role=decode \
  --field-selector=status.phase=Running -o name | sort | head -1 | cut -d/ -f2)
BACKEND_IP=$(kubectl get pod "$VLLM_POD" -n "$NS" -o jsonpath='{.status.podIP}')
echo "target vLLM pod: $VLLM_POD ($BACKEND_IP)" | tee "$OUT_ROOT/target-pod.txt"

reset_cache() {
  echo "resetting prefix cache on $VLLM_POD"
  kubectl exec "$VLLM_POD" -n "$NS" -c modelserver -- python3 -c "
import urllib.request
r = urllib.request.urlopen(urllib.request.Request(
    'http://localhost:8000/reset_prefix_cache', method='POST'))
print('reset_prefix_cache:', r.status)"
}

# Shared ConfigMaps (idempotent).
kubectl create configmap thunderagent-bench-script \
  --from-file=benchmark.py="$SCRIPT_DIR/../04-benchmark/benchmark.py" \
  -n "$NS" --dry-run=client -o yaml | kubectl apply -f -

run_arm() { # run_arm <arm_name> <router_mode> <router_extra> <bench_extra>
  local ARM=$1 MODE=$2 ROUTER_EXTRA=$3 EXTRA=$4
  local RUN_ID="$AB_ID-$ARM"
  echo; echo "===== arm: $ARM (mode=$MODE router_extra='$ROUTER_EXTRA') ====="

  reset_cache

  sed -e "s/MODE_PLACEHOLDER/$MODE/g" -e "s/BACKEND_IP_PLACEHOLDER/$BACKEND_IP/g" \
      -e "s|ROUTER_EXTRA_PLACEHOLDER|$ROUTER_EXTRA|g" \
    "$SCRIPT_DIR/router-ab.yaml" | kubectl apply -f -
  kubectl rollout restart deploy/thunderagent-ab -n "$NS" >/dev/null 2>&1 || true
  kubectl rollout status deploy/thunderagent-ab -n "$NS" --timeout=180s

  # Confirm the router answers in the requested mode before starting the job.
  local READY=""
  for _ in $(seq 1 30); do
    READY=$(kubectl exec deploy/thunderagent-ab -n "$NS" -- python -c "import urllib.request,json;print(json.load(urllib.request.urlopen('http://localhost:8300/health'))['router_mode'])" 2>/dev/null || true)
    [ "$READY" = "$MODE" ] && break
    sleep 2
  done
  if [ "$READY" != "$MODE" ]; then
    echo "FATAL: router did not come up in mode $MODE (got: $READY)" >&2
    exit 1
  fi
  echo "router ready in mode: $READY"

  kubectl delete job thunderagent-ab-bench -n "$NS" --ignore-not-found
  kubectl wait --for=delete pod -l app=thunderagent-ab-bench -n "$NS" --timeout=120s 2>/dev/null || true
  sed -e "s/RUN_ID_PLACEHOLDER/$RUN_ID/" -e "s|EXTRA_FLAGS_PLACEHOLDER|$EXTRA|" \
    "$SCRIPT_DIR/job-ab.yaml" | kubectl apply -f -
  kubectl wait pod -l app=thunderagent-ab-bench -n "$NS" \
    --for=condition=Ready --timeout=300s
  local POD
  POD=$(kubectl get pod -l app=thunderagent-ab-bench -n "$NS" \
    --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}')

  while ! kubectl exec "$POD" -n "$NS" -- test -f /results/DONE 2>/dev/null; do
    local H
    H=$(kubectl exec deploy/thunderagent-ab -n "$NS" -- python -c "import urllib.request,json;h=json.load(urllib.request.urlopen('http://localhost:8300/health'));print(h['programs_count'],h['paused_count'])" 2>/dev/null || echo "n/a")
    echo "$(date +%H:%M:%S) [$ARM] programs/paused: $H"
    sleep 15
  done

  kubectl cp "$NS/$POD:/results/$RUN_ID" "$OUT_ROOT/$ARM" >/dev/null
  kubectl cp "$NS/$POD:/results/stdout.log" "$OUT_ROOT/$ARM/stdout.log" >/dev/null
  kubectl delete job thunderagent-ab-bench -n "$NS"
  tail -12 "$OUT_ROOT/$ARM/stdout.log"
}

# All arms run WITHOUT release: realistic clients never signal completion.
# tr-decay is upstream's supported answer for that (idle ACTING footprints
# decay 2^-t); tr-nodecay shows the failure mode (capacity only frees via
# the 1800s forced-resume timeout).
run_arm default    default ""                        "--expect-mode default --no-release --request-timeout 1200"
run_arm tr-decay   tr      "--use-acting-token-decay" "--expect-mode tr --expect-pauses --no-release --request-timeout 1200"
run_arm tr-nodecay tr      ""                        "--expect-mode tr --expect-pauses --no-release --request-timeout 2400"

# Teardown the AB router (the main 02-deploy router is untouched).
kubectl delete deploy/thunderagent-ab svc/thunderagent-ab -n "$NS"

echo; echo "===== comparison ====="
"${VIZ_PYTHON:-python3}" "$SCRIPT_DIR/compare.py" "$OUT_ROOT" default tr-decay tr-nodecay
echo "all artifacts: $OUT_ROOT"
