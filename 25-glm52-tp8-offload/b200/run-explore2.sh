#!/usr/bin/env bash
# Step 25 exploration, second thunder config (2026-10-11): thunder-gpu-l10 (GPU-pool
# capacity read from vLLM, idle lease 10 s) on server B at c=24 and c=32, with the
# no-router arm on server A. The no-router c=24 point was already running (started by
# run-explore-resume.sh, whose thunder-cputier arm was stopped); this waits for it.
# 900 s per point, RESET=1 (both KV tiers emptied, EPP restarted), no restarts.
# Usage: nohup caffeinate -i ./run-explore2.sh <direct-c24-run-point-pid> > results/explore2.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
DIRECT24=${1:?pid of the running no-router c=24 run-point.sh}

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
    "$SCRIPTS/run-point.sh" "$1" explore-thunder-gpu-l10 > "$RESULTS/explore-thunder-gpu-l10-c$1.log" 2>&1
}

echo "=== c=24 thunder-gpu-l10 ($(date -u +%H:%M:%S)); no router c=24 already running"
thunder 24 || FAILED="$FAILED thunder/c24"
while kill -0 "$DIRECT24" 2>/dev/null; do sleep 20; done
grep -q "job succeeded" "$RESULTS/explore-direct-c24.log" || FAILED="$FAILED direct/c24"
echo "=== c=24 done ($(date -u +%H:%M:%S))"

echo "=== c=32: both arms in parallel ($(date -u +%H:%M:%S))"
direct 32 & pd=$!
sleep 5
thunder 32 & pt=$!
wait $pd || FAILED="$FAILED direct/c32"
wait $pt || FAILED="$FAILED thunder/c32"
echo "=== c=32 done ($(date -u +%H:%M:%S))"

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore/report" "$RESULTS"/explore-direct/c* "$RESULTS"/explore-thunder-gpu-l10/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
