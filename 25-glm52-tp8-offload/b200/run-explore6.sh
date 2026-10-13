#!/usr/bin/env bash
# Step 25 exploration batch 6 (2026-10-11): thunder-gpu-l10-s300 (lease 10 s,
# forced-admission backstop 300 s) at c=24 on server A (agentx-epp-b) and c=32 on
# server B (agentx-epp-a), in parallel; 900 s, RESET=1. Both servers have the same
# settings and GPU pool (1,572,864 tokens). A failed point is retried once.
# Usage: nohup caffeinate -i ./run-explore6.sh > results/explore6.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd MODE=pool
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=900 RESTART=0 RESET=1

LABEL=explore-thunder-gpu-l10-s300
FAILED=""
point() {  # point <server a|b> <concurrency>; one retry under $LABEL-retry
  local srv=$1 c=$2 try
  for try in "$LABEL" "$LABEL-retry"; do
    if [ "$srv" = a ]; then
      URL=http://agentx-epp-b-epp:80 EPP_DEPLOY=agentx-epp-b-epp DEPLOY=glm52-tp8 \
        DECODE_SELECTOR=app=glm52-tp8 LANE=a \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    else
      URL=http://agentx-epp-a-epp:80 EPP_DEPLOY=agentx-epp-a-epp DEPLOY=glm52-tp8-b \
        DECODE_SELECTOR=app=glm52-tp8-b LANE=b \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    fi
    echo "=== $try/c$c failed; $( [ "$try" = "$LABEL" ] && echo retrying || echo giving up ) ($(date -u +%H:%M:%S))"
  done
  return 1
}

echo "=== c=24 on A and c=32 on B ($(date -u +%H:%M:%S))"
point a 24 & pa=$!
sleep 5
point b 32 & pb=$!
wait $pa || FAILED="$FAILED c24"
wait $pb || FAILED="$FAILED c32"
echo "=== done ($(date -u +%H:%M:%S))"

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore/report" "$RESULTS"/explore-direct*/c* "$RESULTS"/explore-thunder-gpu-l*/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
