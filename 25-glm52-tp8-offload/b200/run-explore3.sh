#!/usr/bin/env bash
# Step 25 exploration, queued after run-explore2.sh (2026-10-11): separate the lease
# effect and measure run-to-run noise. Server B: thunder-gpu-l30 (thunder-plugins.yaml:
# GPU-pool capacity from vLLM, idle lease 30 s) at c=24 and c=32, against
# run-explore2's thunder-gpu-l10. Server A: a second no-router run (label
# explore-direct-r2) at the same points. Same settings as run-explore2 (900 s, RESET=1,
# MAX_NUM_SEQS 64). A failed point is retried once under <label>-retry.
# Usage: nohup caffeinate -i ./run-explore3.sh <run-explore2-pid> > results/explore3.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
PREV=${1:?pid of run-explore2.sh}

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=900 RESTART=0 RESET=1

FAILED=""
point() {  # point <arm> <label> <concurrency>; one retry under <label>-retry
  local arm=$1 label=$2 c=$3 try
  for try in "$label" "$label-retry"; do
    if [ "$arm" = direct ]; then
      MODE=direct URL=http://glm52-tp8:8000 DEPLOY=glm52-tp8 DECODE_SELECTOR=app=glm52-tp8 LANE=a \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    else
      MODE=pool URL=http://agentx-epp-a-epp:80 EPP_DEPLOY=agentx-epp-a-epp DEPLOY=glm52-tp8-b \
        DECODE_SELECTOR=app=glm52-tp8-b LANE=b \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    fi
    echo "=== $try/c$c failed; $( [ "$try" = "$label" ] && echo retrying || echo giving up ) ($(date -u +%H:%M:%S))"
  done
  return 1
}

while kill -0 "$PREV" 2>/dev/null; do sleep 30; done
echo "=== run-explore2 finished; switching the thunder EPP to lease 30 s ($(date -u +%H:%M:%S))"
KUBECONFIG=$KUBECONFIG_SOURCE kubectl apply -f "$HERE/lane-epp-a-gpu-l30-b.yaml"
KUBECONFIG=$KUBECONFIG_SOURCE kubectl rollout status deploy/agentx-epp-a-epp -n "$NS" --timeout=10m

for c in 24 32; do
  echo "=== c=$c: thunder-gpu-l30 on B and no-router r2 on A ($(date -u +%H:%M:%S))"
  point direct explore-direct-r2 "$c" & pd=$!
  sleep 5
  point thunder explore-thunder-gpu-l30 "$c" & pt=$!
  wait $pd || FAILED="$FAILED direct-r2/c$c"
  wait $pt || FAILED="$FAILED thunder-gpu-l30/c$c"
  echo "=== c=$c done ($(date -u +%H:%M:%S))"
done

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore/report" "$RESULTS"/explore-direct*/c* "$RESULTS"/explore-thunder-gpu-l*/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
