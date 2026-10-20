#!/usr/bin/env bash
# Step 30: llm-d-router v1.0.0 turn-priority on Qwen3.5-397B-A17B-FP8, vLLM TP=4 + 387 GiB offload
# (step 26's servers qwen35-tp4-b, -d, -f: MAX_NUM_SEQS 64, 96, 128 = 2x concurrency), 1-hour points at
# c = 32, 48, 64, one per server, all three at once; same method as step 26's run-1h.sh (RESET=1
# empties both KV tiers and restarts the EPP before every point, no server restart, 3600 s).
#   1. wait until the three servers are available (scaled to 1 by hand before this script, on free
#      nodes 000v (b, d) and 14rm (f); step 26's nodes hold step 27's DEP=8 servers);
#   2. deploy one v1.0.0 lane EPP per server (agentx-epp-u{b,d,f}) and check image and config;
#   3. smoke test: c = 4 for 120 s through agentx-epp-ub; stop if it fails;
#   4. the three points (b: c32, d: c48, f: c64), each retried once on failure;
#   5. delete the EPPs and scale the servers back to 0 (also on any early exit), then analyze the
#      new points alone and together with step 26's qwen35-direct and qwen35-thunder-gpu-l10.
# Usage: setsid nohup ./run-turn-priority.sh > results/run-turn-priority.log 2>&1 < /dev/null &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
STEP26="$HERE/../../26-qwen35-tp4-thunder/b200/results"
export PATH="$HOME/.local/bin:$PATH"   # uv

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=Qwen/Qwen3.5-397B-A17B-FP8 DATASET=semianalysis_cc_traces_weka_062126_256k
export CLIENT_POOL=pool-1 GPUS_PER_POD=4 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=3 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=12Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" RESTART=0 RESET=1
LABEL=qwen35-turn-priority
SERVERS="b d f"
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
dep_of() { echo "qwen35-tp4-$1"; }
epp_of() { echo "agentx-epp-u$1-epp"; }
mkdir -p "$RESULTS"

teardown() {
  echo "=== teardown: delete the lane EPPs, scale the servers back to 0 ($(ts))"
  for s in $SERVERS; do
    [ -f "$RESULTS/lane-epp-u$s.yaml" ] && k delete -f "$RESULTS/lane-epp-u$s.yaml" --ignore-not-found >/dev/null
    k scale "deploy/$(dep_of "$s")" --replicas=0
  done
}
trap teardown EXIT

# The API server can throttle applies ("ENHANCE_YOUR_CALM", step 24).
apply_retry() {
  local i
  for i in 1 2 3 4 5 6; do k apply -f "$1" >/dev/null && return 0; sleep 15; done
  return 1
}

echo "=== removing leftover jobs of this label ($(ts))"
for c in 4 32 48 64; do
  k delete job "agentx-c$c-$LABEL" "agentx-c$c-$LABEL-retry" "agentx-c$c-$LABEL-smoke" --ignore-not-found --wait=true >/dev/null
done

echo "=== 1. waiting for the three servers ($(ts))"
for s in $SERVERS; do
  k rollout status "deploy/$(dep_of "$s")" --timeout=120m || { echo "server $s did not become available; stopping"; exit 1; }
  echo "server $s available ($(ts)): $(k get pods -l "app=$(dep_of "$s")" -o wide --no-headers | awk '{print $1, $7}')"
done

echo "=== 2. lane EPPs, llm-d-router v1.0.0 turn-priority ($(ts))"
for s in $SERVERS; do
  "$HERE/render-epp.sh" "u$s" "$s" > "$RESULTS/lane-epp-u$s.yaml" || { echo "render for $s failed; stopping"; exit 1; }
  apply_retry "$RESULTS/lane-epp-u$s.yaml" || { echo "EPP apply for $s failed; stopping"; exit 1; }
done
for s in $SERVERS; do
  k rollout status "deploy/$(epp_of "$s")" --timeout=10m || { echo "EPP $s did not become ready; stopping"; exit 1; }
  img=$(k get "deploy/$(epp_of "$s")" -o jsonpath='{.spec.template.spec.containers[*].image}')
  cm=$(k get configmap "$(epp_of "$s")" -o yaml)
  strat=$(grep -oE 'strategy: [a-z_-]+' <<<"$cm" | sort -u | tr '\n' ' ')
  ep=$(grep -oE 'address: "[0-9.]+"' <<<"$cm" | head -1)
  echo "EPP $s: $strat; endpoint $ep; images: $img"
  [[ "$img" == *"llm-d-router-endpoint-picker:v1.0.0"* ]] && [ "$strat" = "strategy: turn-priority " ] \
    || { echo "EPP $s is not v1.0.0 with turn-priority; stopping"; exit 1; }
done

run_one() {  # run_one <server> <concurrency> <label> [extra env...]
  local s=$1 c=$2 label=$3; shift 3
  env "$@" MODE=pool URL="http://$(epp_of "$s"):80" EPP_DEPLOY="$(epp_of "$s")" DEPLOY="$(dep_of "$s")" \
    DECODE_SELECTOR="app=$(dep_of "$s")" LANE="q$s" \
    "$SCRIPTS/run-point.sh" "$c" "$label" > "$RESULTS/$label-c$c.log" 2>&1
}

echo "=== 3. smoke test: c = 4, 120 s, server b ($(ts))"
if run_one b 4 "$LABEL-smoke" DURATION=120 EXTRA_ARGS="$EXTRA_ARGS --unsafe-override"; then
  echo "smoke test passed ($(ts))"
else
  echo "smoke test failed; see $RESULTS/$LABEL-smoke-c4.log; stopping ($(ts))"; exit 1
fi
"$SCRIPTS/verify-point.sh" "$RESULTS/$LABEL-smoke/c4" || { echo "smoke point did not pass verify-point.sh; stopping ($(ts))"; exit 1; }
grep -c '"severity_text":"ERROR"' "$RESULTS"/$LABEL-smoke/c4/epp-*.log 2>/dev/null | sed 's/^/EPP error lines in the smoke test: /'
if [ -f "$RESULTS/$LABEL-smoke/c4/epp/raw-epp-metrics.txt.gz" ]; then
  zcat "$RESULTS/$LABEL-smoke/c4/epp/raw-epp-metrics.txt.gz" | grep -E 'flow_control_(stale_endpoints|pool_saturation)[ {]' | tail -3 \
    | sed 's/^/smoke EPP gauge: /'
fi
[ "${SMOKE_ONLY:-0}" = 1 ] && { echo "SMOKE_ONLY=1: stopping after the smoke test ($(ts))"; exit 0; }

point() {  # point <server> <concurrency>; one retry
  local s=$1 c=$2 try
  echo "=== $LABEL c$c on server $s start ($(ts))"
  for try in "$LABEL" "$LABEL-retry"; do
    if run_one "$s" "$c" "$try" DURATION=3600; then
      echo "=== $LABEL c$c on server $s done ($(ts))"; return 0
    fi
    echo "=== $try c$c on server $s did not succeed ($(ts))"
  done
  return 1
}
echo "=== 4. points ($(ts))"
point b 32 & p1=$!; sleep 20
point d 48 & p2=$!; sleep 20
point f 64 & p3=$!
rc=0; for p in $p1 $p2 $p3; do wait $p || rc=1; done

teardown
trap - EXIT
echo "=== 5. reports ($(ts))"
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --out "$RESULTS/$LABEL/report" "$RESULTS"/$LABEL/c* "$RESULTS"/$LABEL-retry/c* 2>/dev/null
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/compare-step26/report" \
  "$RESULTS"/$LABEL/c* "$RESULTS"/$LABEL-retry/c* \
  "$STEP26"/qwen35-direct/c32 "$STEP26"/qwen35-direct/c48 "$STEP26"/qwen35-direct/c64 \
  "$STEP26"/qwen35-thunder-gpu-l10/c32 "$STEP26"/qwen35-thunder-gpu-l10/c48 "$STEP26"/qwen35-thunder-gpu-l10/c64 \
  > "$RESULTS/compare-step26-analyze.log" 2>&1
echo "=== done, rc=$rc ($(ts))"
exit $rc
