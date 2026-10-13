#!/usr/bin/env bash
# One-off resume of run-explore.sh on 2026-10-11: at c=24 the no-router arm died at
# start (both arms' pin_kube moved the same temp kubeconfig; fixed in lib.sh), while
# the thunder arm ran on. This starts the no-router c=24 point (about 2 min after
# thunder), waits for both c=24 points, then runs c=32 with both arms and analyzes.
# Usage: nohup caffeinate -i ./run-explore-resume.sh <thunder-c24-run-point-pid> > results/explore-resume.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
THUNDER24=${1:?pid of the running thunder c=24 run-point.sh}

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

echo "=== c=24 no router, late start ($(date -u +%H:%M:%S))"
direct 24 || FAILED="$FAILED direct/c24"
while kill -0 "$THUNDER24" 2>/dev/null; do sleep 20; done
grep -q "job succeeded" "$RESULTS/explore-thunder-c24.log" || FAILED="$FAILED thunder/c24"
echo "=== c=24 done ($(date -u +%H:%M:%S))"

echo "=== c=32: both arms in parallel ($(date -u +%H:%M:%S))"
direct 32 & pd=$!
sleep 5
thunder 32 & pt=$!
wait $pd || FAILED="$FAILED direct/c32"
wait $pt || FAILED="$FAILED thunder/c32"
echo "=== c=32 done ($(date -u +%H:%M:%S))"

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore/report" "$RESULTS"/explore-direct/c* "$RESULTS"/explore-thunder-cputier/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
