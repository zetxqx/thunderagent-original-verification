#!/usr/bin/env bash
# Step 25 exploration, queued after run-explore3.sh (2026-10-11, user request): the
# thunder-gpu-l10 gate (GPU-pool capacity from vLLM, idle lease 10 s) on server B at
# c=12, 16, 20, 28 and 36; no router on server A only at c=20, in parallel with the
# thunder c=20 point. Same settings as
# run-explore2 (900 s, RESET=1, MAX_NUM_SEQS 64, labels explore-direct and
# explore-thunder-gpu-l10), so these points extend that series. A failed point is
# retried once under <label>-retry.
# Usage: nohup caffeinate -i ./run-explore4.sh <run-explore3-pid> > results/explore4.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
PREV=${1:?pid of run-explore3.sh}

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
echo "=== run-explore3 finished; switching the thunder EPP to lease 10 s ($(date -u +%H:%M:%S))"
KUBECONFIG=$KUBECONFIG_SOURCE kubectl apply -f "$HERE/lane-epp-a-gpu-l10-b.yaml"
KUBECONFIG=$KUBECONFIG_SOURCE kubectl rollout status deploy/agentx-epp-a-epp -n "$NS" --timeout=10m

for c in 12 16 20 28 36; do
  pd=""
  if [ "$c" = 20 ]; then
    echo "=== c=$c: thunder-gpu-l10 on B and no router on A ($(date -u +%H:%M:%S))"
    point direct explore-direct "$c" & pd=$!
    sleep 5
  else
    echo "=== c=$c: thunder-gpu-l10 on B ($(date -u +%H:%M:%S))"
  fi
  point thunder explore-thunder-gpu-l10 "$c" & pt=$!
  if [ -n "$pd" ]; then wait $pd || FAILED="$FAILED direct/c$c"; fi
  wait $pt || FAILED="$FAILED thunder-gpu-l10/c$c"
  echo "=== c=$c done ($(date -u +%H:%M:%S))"
done

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore/report" "$RESULTS"/explore-direct*/c* "$RESULTS"/explore-thunder-gpu-l*/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
