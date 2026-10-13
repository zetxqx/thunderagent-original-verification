#!/usr/bin/env bash
# Step 25 exploration on cluster a4-pr: no router (server A, glm52-tp8) and the
# thunder-cputier gate (server B, glm52-tp8-b, lane EPP agentx-epp-a-epp) in
# parallel at c=24 and c=32, 900 s each. No server restart between points:
# RESET=1 empties both KV tiers (and restarts the EPP) before each point. Both
# servers run MAX_NUM_SEQS=64. Not AgentX's fresh-server rule: exploration only.
#
# Usage: nohup caffeinate -i ./run-explore.sh > results/explore.log 2>&1 &
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=900 RESTART=0 RESET=1

FAILED=""
direct() {
  MODE=direct URL=http://glm52-tp8:8000 DEPLOY=glm52-tp8 DECODE_SELECTOR=app=glm52-tp8 LANE=a \
    "$SCRIPTS/run-point.sh" "$1" explore-direct > "$RESULTS/explore-direct-c$1.log" 2>&1
}
thunder() {
  MODE=pool URL=http://agentx-epp-a-epp:80 EPP_DEPLOY=agentx-epp-a-epp DEPLOY=glm52-tp8-b \
    DECODE_SELECTOR=app=glm52-tp8-b LANE=b \
    "$SCRIPTS/run-point.sh" "$1" explore-thunder-cputier > "$RESULTS/explore-thunder-c$1.log" 2>&1
}
for c in 24 32; do
  echo "=== concurrency $c: both arms in parallel ($(date -u +%H:%M:%S))"
  direct "$c" & pd=$!
  thunder "$c" & pt=$!
  wait $pd || FAILED="$FAILED direct/c$c"
  wait $pt || FAILED="$FAILED thunder/c$c"
  echo "=== concurrency $c done ($(date -u +%H:%M:%S))"
done

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore/report" "$RESULTS"/explore-direct/c* "$RESULTS"/explore-thunder-cputier/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
