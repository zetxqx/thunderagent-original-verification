#!/usr/bin/env bash
# Step 28: llm-d-router v1.0.0 turn-priority on GLM-5.2, vLLM TP=8 + 820 GiB offload (step 25's
# servers), 1-hour points at c = 24, 32, 48, 64, one per server, all at once; same method as
# step 25's run-1h-highc.sh (RESET=1 empties both KV tiers and restarts the EPP before every
# point, no server restart, MAX_NUM_SEQS 64, 3600 s).
#   1. scale glm52-tp8, -b, -c, -d from 0 to 1 and wait until they are available;
#   2. deploy one v1.0.0 lane EPP per server (agentx-epp-ta..td) and check image and config;
#   3. smoke test: c = 4 for 120 s through agentx-epp-ta; stop if it fails;
#   4. the four points (a: c64, b: c48, c: c32, d: c24), each retried once on failure;
#   5. delete the EPPs and scale the servers back to 0 (also on any early exit), then report.
# Usage: nohup caffeinate -i ./run-turn-priority.sh > results/run-turn-priority.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=48Gi CLIENT_MEM_REQUEST=24Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" RESTART=0 RESET=1
LABEL=turn-priority-v1
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
dep_of() { [ "$1" = a ] && echo glm52-tp8 || echo "glm52-tp8-$1"; }
epp_of() { echo "agentx-epp-t$1-epp"; }
SERVERS="a b c d"

teardown() {
  echo "=== teardown: delete the lane EPPs, scale the servers back to 0 ($(ts))"
  for s in $SERVERS; do
    [ -f "$RESULTS/lane-epp-t$s.yaml" ] && k delete -f "$RESULTS/lane-epp-t$s.yaml" --ignore-not-found >/dev/null
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
for c in 4 24 32 48 64; do
  k delete job "agentx-c$c-$LABEL" "agentx-c$c-$LABEL-retry" "agentx-c$c-$LABEL-smoke" --ignore-not-found --wait=true >/dev/null
done

echo "=== 1. scaling the four servers to 1 ($(ts))"
# Step 25 pinned each server to a node with the checkpoint cached on local SSD; step 27's
# glm52-dep8-a/b/c now hold the nodes of a, b and c, so those three move to free nodes (the
# first start downloads the 465 GB checkpoint there). d keeps its node.
for sn in a:000v b:14rm c:21nl; do
  k patch "deploy/$(dep_of "${sn%%:*}")" --type merge -p "{\"spec\":{\"template\":{\"spec\":{\"nodeSelector\":
    {\"kubernetes.io/hostname\":\"gke-a4-pr-a4-highgpu-8g-a4-pool-1-13a7a362-${sn#*:}\"}}}}}"
done
for s in $SERVERS; do k scale "deploy/$(dep_of "$s")" --replicas=1; done
for s in $SERVERS; do
  k rollout status "deploy/$(dep_of "$s")" --timeout=90m || { echo "server $s did not become available; stopping"; exit 1; }
  echo "server $s available ($(ts))"
done

echo "=== 2. lane EPPs, llm-d-router v1.0.0 turn-priority ($(ts))"
for s in $SERVERS; do
  "$HERE/render-epp.sh" "t$s" "$s" > "$RESULTS/lane-epp-t$s.yaml" || { echo "render for $s failed; stopping"; exit 1; }
  apply_retry "$RESULTS/lane-epp-t$s.yaml" || { echo "EPP apply for $s failed; stopping"; exit 1; }
done
for s in $SERVERS; do
  k rollout status "deploy/$(epp_of "$s")" --timeout=10m || { echo "EPP $s did not become ready; stopping"; exit 1; }
  img=$(k get "deploy/$(epp_of "$s")" -o jsonpath='{.spec.template.spec.containers[*].image}')
  strat=$(k get configmap "$(epp_of "$s")" -o yaml | grep -oE 'strategy: [a-z-]+' | sort -u)
  echo "EPP $s: $strat; images: $img"
  [[ "$img" == *"llm-d-router-endpoint-picker:v1.0.0"* ]] && [ "$strat" = "strategy: turn-priority" ] \
    || { echo "EPP $s is not v1.0.0 with turn-priority; stopping"; exit 1; }
done

run_one() {  # run_one <server> <concurrency> <label> [extra env...]
  local s=$1 c=$2 label=$3; shift 3
  env "$@" MODE=pool URL="http://$(epp_of "$s"):80" EPP_DEPLOY="$(epp_of "$s")" DEPLOY="$(dep_of "$s")" \
    DECODE_SELECTOR="app=$(dep_of "$s")" LANE="$s" \
    "$SCRIPTS/run-point.sh" "$c" "$label" > "$RESULTS/$label-c$c.log" 2>&1
}

echo "=== 3. smoke test: c = 4, 120 s, server a ($(ts))"
if run_one a 4 "$LABEL-smoke" DURATION=120 EXTRA_ARGS="$EXTRA_ARGS --unsafe-override"; then
  echo "smoke test passed ($(ts))"
else
  echo "smoke test failed; see $RESULTS/$LABEL-smoke-c4.log; stopping ($(ts))"; exit 1
fi
grep -c '"severity_text":"ERROR"' "$RESULTS"/$LABEL-smoke/c4/epp-*.log 2>/dev/null | sed 's/^/EPP error lines in the smoke test: /'

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
point a 64 & sleep 20
point b 48 & sleep 20
point c 32 & sleep 20
point d 24 &
wait

teardown
trap - EXIT
echo "=== 5. report ($(ts))"
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --out "$RESULTS/$LABEL/report" "$RESULTS"/$LABEL/c* "$RESULTS"/$LABEL-retry/c* 2>/dev/null
echo "=== done ($(ts))"
