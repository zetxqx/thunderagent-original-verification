#!/usr/bin/env bash
# Step 29: llm-d-router v1.0.0 turn-priority on GLM-5.2 DEP=8 (step 27's servers glm52-dep8-b
# and -c, one API server per rank, 8 x 102.5 GiB offload), 1-hour points at c = 24, 32, 48, 64,
# two at a time (one per server); same method as steps 27 and 28 (RESET=1 empties both KV tiers
# on all 8 rank ports and restarts the EPP before every point, no server restart, 3600 s).
#   1. check the two servers are available (they stay up from step 27; nothing is scaled here);
#   2. deploy one v1.0.0 lane EPP per server (agentx-epp-pb-epp, agentx-epp-pc-epp) and check
#      image, strategy and the detector headroom;
#   3. smoke test: c = 4 for 120 s through agentx-epp-pb; stop if it fails;
#   4. two chains, each point retried once on failure: b: c64 then c32; c: c48 then c24;
#   5. delete the two EPPs (also on any early exit; the servers stay up), then analyze the new
#      points together with step 27's dep8-direct, dep8-affinity and dep8-thunder-l10 points.
# Usage: nohup ./run-dep8-turn-priority.sh > results/run-dep8-turn-priority.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
STEP27="$HERE/../../27-glm52-dep8/b200/results"
export PATH="$HOME/.local/bin:$PATH"   # uv

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=48Gi CLIENT_MEM_REQUEST=24Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" RESTART=0 RESET=1
export VLLM_PORTS="8000 8001 8002 8003 8004 8005 8006 8007"
LABEL=dep8-turn-priority
SERVERS="b c"
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
dep_of() { echo "glm52-dep8-$1"; }
epp_of() { echo "agentx-epp-p$1-epp"; }
mkdir -p "$RESULTS"

teardown() {
  echo "=== teardown: delete the lane EPPs; the servers stay up ($(ts))"
  for s in $SERVERS; do
    [ -f "$RESULTS/lane-epp-p$s.yaml" ] && k delete -f "$RESULTS/lane-epp-p$s.yaml" --ignore-not-found >/dev/null
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
for c in 4 24 32 48 64; do
  k delete job "agentx-c$c-$LABEL" "agentx-c$c-$LABEL-retry" "agentx-c$c-$LABEL-smoke" --ignore-not-found --wait=true >/dev/null
done

echo "=== 1. the two DEP=8 servers ($(ts))"
for s in $SERVERS; do
  k rollout status "deploy/$(dep_of "$s")" --timeout=2m || { echo "server $s is not available; stopping"; exit 1; }
  k get pods -l "app=$(dep_of "$s")" -o wide --no-headers
done

echo "=== 2. lane EPPs, llm-d-router v1.0.0 turn-priority + session affinity ($(ts))"
for s in $SERVERS; do
  "$HERE/render-epp.sh" "p$s" "$s" > "$RESULTS/lane-epp-p$s.yaml" || { echo "render for $s failed; stopping"; exit 1; }
  apply_retry "$RESULTS/lane-epp-p$s.yaml" || { echo "EPP apply for $s failed; stopping"; exit 1; }
done
for s in $SERVERS; do
  k rollout status "deploy/$(epp_of "$s")" --timeout=10m || { echo "EPP $s did not become ready; stopping"; exit 1; }
  img=$(k get "deploy/$(epp_of "$s")" -o jsonpath='{.spec.template.spec.containers[*].image}')
  cm=$(k get configmap "$(epp_of "$s")" -o yaml)
  strat=$(grep -oE 'strategy: [a-z_-]+' <<<"$cm" | sort -u | tr '\n' ' ')
  headroom=$(grep -oE 'headroom: [0-9]+' <<<"$cm" | sort -u)
  nep=$(grep -c 'rank[0-9]$' <<<"$cm")
  echo "EPP $s: $strat; $headroom; $nep rank endpoints; images: $img"
  [[ "$img" == *"llm-d-router-endpoint-picker:v1.0.0"* ]] && [[ "$strat" == *"strategy: turn-priority"* ]] \
    && [[ "$strat" == *"strategy: session_id"* ]] && [ "$headroom" = "headroom: 100" ] && [ "$nep" = 8 ] \
    || { echo "EPP $s is not v1.0.0 with turn-priority, session_id, headroom 100 and 8 endpoints; stopping"; exit 1; }
done

run_one() {  # run_one <server> <concurrency> <label> [extra env...]
  local s=$1 c=$2 label=$3; shift 3
  env "$@" MODE=pool URL="http://$(epp_of "$s"):80" EPP_DEPLOY="$(epp_of "$s")" DEPLOY="$(dep_of "$s")" \
    DECODE_SELECTOR="app=$(dep_of "$s")" LANE="g$s" \
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
# The EPP's flow-control gauges at the end of the smoke test: stale endpoints must be 0, or the
# detector's Filter would be moving sessions between ranks for staleness.
if [ -f "$RESULTS/$LABEL-smoke/c4/epp/raw-epp-metrics.txt.gz" ]; then
  zcat "$RESULTS/$LABEL-smoke/c4/epp/raw-epp-metrics.txt.gz" | grep -E 'flow_control_(stale_endpoints|pool_saturation)[ {]' | tail -4 \
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
chain() {  # chain <server> <concurrency...>
  local s=$1 rc=0 c; shift
  for c in "$@"; do point "$s" "$c" || rc=1; done
  echo "=== chain $s done ($(ts))"; return $rc
}
echo "=== 4. points ($(ts))"
chain b 64 32 & pb=$!
sleep 20
chain c 48 24 & pc=$!
rc=0; wait $pb || rc=1; wait $pc || rc=1

teardown
trap - EXIT
echo "=== 5. reports ($(ts))"
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --out "$RESULTS/$LABEL/report" "$RESULTS"/$LABEL/c* "$RESULTS"/$LABEL-retry/c* 2>/dev/null
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/compare-step27/report" \
  "$RESULTS"/$LABEL/c* "$RESULTS"/$LABEL-retry/c* \
  "$STEP27"/dep8-direct/c24 "$STEP27"/dep8-direct/c32 "$STEP27"/dep8-direct/c48 "$STEP27"/dep8-direct/c64 \
  "$STEP27"/dep8-affinity/c24 "$STEP27"/dep8-affinity-r2/c32 "$STEP27"/dep8-affinity/c48 "$STEP27"/dep8-affinity-retry/c64 \
  "$STEP27"/dep8-thunder-l10/c24 "$STEP27"/dep8-thunder-l10/c32 "$STEP27"/dep8-thunder-l10/c48 "$STEP27"/dep8-thunder-l10/c64 \
  > "$RESULTS/compare-step27-analyze.log" 2>&1
echo "=== done, rc=$rc ($(ts))"
exit $rc
