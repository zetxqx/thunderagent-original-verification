#!/usr/bin/env bash
# Step 27, experiment C (user request, 2026-10-15): DEP=8 with llm-d-thunder-agent-simplified at c=96 and
# c=128, one point on each server at the same time, 3600 s, both KV tiers emptied before each point.
#   glm52-dep8-c, EPP agentx-epp-gc (lane-epp-gc.yaml)        -> dep8-thunder-l10 c=96
#   glm52-dep8-b, EPP agentx-epp-gb (lane-epp-gb-thunder.yaml) -> dep8-thunder-l10 c=128
# Server b's EPP changes from session affinity to the same thunder config as server c (capacity 818,175 for
# each rank; both servers have this pool on all 8 ranks). The client memory limit is 64 GiB, not 32 GiB:
# three clients were OOMKilled at c=64 while they exported the server metrics.
# TP=8 references: step 25 explore1h-direct and explore1h-thunder-gpu-l10 at c=96 and 128.
# Usage: nohup caffeinate -i ./run-dep8-highc.sh > results/run-dep8-highc.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
export RESULTS="$HERE/results" CTX=gke_supercomputer-testing_europe-west4_a4-pr KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=64Gi CLIENT_MEM_REQUEST=16Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
RANK_PORTS="8000 8001 8002 8003 8004 8005 8006 8007"
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }

point() {  # point <server b|c> <lane file> <concurrency>; one retry
  local srv=$1 c=$3 dep=glm52-dep8-$1 epp=agentx-epp-g$1-epp try
  k apply -f "$HERE/$2" >/dev/null && k rollout status "deploy/$epp" --timeout=10m >/dev/null || return 1
  echo "=== $srv: thunder c=$c ($(date -u +%H:%M:%S))"
  for try in dep8-thunder-l10 dep8-thunder-l10-retry; do
    MODE=pool URL=http://$epp:80 EPP_DEPLOY=$epp DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=g$srv \
      VLLM_PORTS="$RANK_PORTS" "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 \
      && { echo "=== $try/c$c on $srv done ($(date -u +%H:%M:%S))"; return 0; }
    echo "=== $try/c$c on $srv failed ($(date -u +%H:%M:%S))"
  done
  return 1
}

point c lane-epp-gc.yaml 96 & pc=$!
sleep 5
point b lane-epp-gb-thunder.yaml 128 & pb=$!
rc=0; wait $pc || rc=1; wait $pb || rc=1
exit $rc
