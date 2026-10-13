#!/usr/bin/env bash
# Step 25 exploration batch 5 (2026-10-11): does a 60 s forced-admission backstop cut
# thunder's long waits, and how much does thunder vary run to run? In parallel at
# c=24 and c=32, 900 s each, RESET=1 (both KV tiers emptied, EPP restarted):
#   server B behind agentx-epp-a: thunder-gpu-l10-s60 (lease 10 s, backstop 60 s)
#   server A behind agentx-epp-b: thunder-gpu-l10, a second run (backstop 1800 s)
# A failed point is retried once under <label>-retry.
# Usage: nohup caffeinate -i ./run-explore5.sh > results/explore5.log 2>&1 &
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

FAILED=""
point() {  # point <server a|b> <label> <concurrency>; one retry under <label>-retry
  local srv=$1 label=$2 c=$3 try
  for try in "$label" "$label-retry"; do
    if [ "$srv" = a ]; then
      URL=http://agentx-epp-b-epp:80 EPP_DEPLOY=agentx-epp-b-epp DEPLOY=glm52-tp8 \
        DECODE_SELECTOR=app=glm52-tp8 LANE=a \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    else
      URL=http://agentx-epp-a-epp:80 EPP_DEPLOY=agentx-epp-a-epp DEPLOY=glm52-tp8-b \
        DECODE_SELECTOR=app=glm52-tp8-b LANE=b \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    fi
    echo "=== $try/c$c failed; $( [ "$try" = "$label" ] && echo retrying || echo giving up ) ($(date -u +%H:%M:%S))"
  done
  return 1
}

for c in 24 32; do
  echo "=== c=$c: thunder-gpu-l10-s60 on B, thunder-gpu-l10 2nd run on A ($(date -u +%H:%M:%S))"
  point b explore-thunder-gpu-l10-s60 "$c" & pb=$!
  sleep 5
  point a explore-thunder-gpu-l10-r2 "$c" & pa=$!
  wait $pb || FAILED="$FAILED l10-s60/c$c"
  wait $pa || FAILED="$FAILED l10-r2/c$c"
  echo "=== c=$c done ($(date -u +%H:%M:%S))"
done

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore/report" "$RESULTS"/explore-direct*/c* "$RESULTS"/explore-thunder-gpu-l*/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
