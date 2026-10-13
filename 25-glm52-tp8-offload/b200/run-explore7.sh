#!/usr/bin/env bash
# Step 25 exploration batch 7 (2026-10-11): the forced-admission fix. EPP image
# thunder-agent-pr3-a025437b-forced-7ae26276 = a025437b + PR zetxqx/llm-d-router#14
# (forced admission pauses reclaimable idle sessions first; Produces() fix). Same
# thunder config as batches 5 and 6 (GPU capacity, lease 10 s), backstop 300 s then
# 60 s; c=24 on server A (agentx-epp-b), c=32 on server B (agentx-epp-a), in
# parallel, 900 s, RESET=1. A failed point is retried once.
# Usage: nohup caffeinate -i ./run-explore7.sh > results/explore7.log 2>&1 &
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
round() {  # round <backstop name s300|s60>
  local label=explore-thunder-gpu-l10-$1-forced
  echo "=== $1: deploying EPPs ($(date -u +%H:%M:%S))"
  KUBECONFIG=$KUBECONFIG_SOURCE kubectl apply -f "$HERE/lane-epp-a-gpu-l10-$1-b-forced.yaml" -f "$HERE/lane-epp-b-gpu-l10-$1-a-forced.yaml"
  for d in agentx-epp-a-epp agentx-epp-b-epp; do
    KUBECONFIG=$KUBECONFIG_SOURCE kubectl rollout status deploy/$d -n "$NS" --timeout=10m
  done
  echo "=== $1: c=24 on A and c=32 on B ($(date -u +%H:%M:%S))"
  point a "$label" 24 & pa=$!
  sleep 5
  point b "$label" 32 & pb=$!
  wait $pa || FAILED="$FAILED $1/c24"
  wait $pb || FAILED="$FAILED $1/c32"
  echo "=== $1 done ($(date -u +%H:%M:%S))"
}

round s300
round s60

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore/report" "$RESULTS"/explore-direct*/c* "$RESULTS"/explore-thunder-gpu-l*/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
