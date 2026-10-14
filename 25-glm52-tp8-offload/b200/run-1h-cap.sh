#!/usr/bin/env bash
# Step 25, 1-hour points (2026-10-13, user request): llm-d-thunder-agent-simplified with the
# gate capacity above the GPU KV pool, so the CPU tier (about 18.2M tokens) holds the extra
# admitted sessions: capacity 3.15M (2x the pool) and 6.29M (4x), lease 10 s, backstop
# 1800 s, at c=32 and 48. Compare with explore1h-thunder-gpu-l10 (capacity = GPU pool) and
# explore1h-direct at the same concurrency. Same method as run-1h.sh: no server restart,
# RESET=1 empties both KV tiers and restarts the EPP, 3600 s, MAX_NUM_SEQS 64, offload on.
# Four servers, one point each, paired by concurrency:
#   A glm52-tp8   (EPP agentx-epp-e, new): cap 3.15M, c=48
#   B glm52-tp8-b (EPP agentx-epp-a):      cap 6.29M, c=48
#   C glm52-tp8-c (EPP agentx-epp-c):      cap 3.15M, c=32
#   D glm52-tp8-d (EPP agentx-epp-d):      cap 6.29M, c=32
# Clients request 4 CPU and 16 GiB (limit 32 GiB) so four fit next to four EPPs on the one
# usable pool-1 node.
# Usage: nohup caffeinate -i ./run-1h-cap.sh > results/run-1h-cap.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=16Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1

k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }

point() {  # point <deploy> <epp lane> <lane file> <label> <concurrency> <client lane>; one retry
  local dep=$1 epp=agentx-epp-$2-epp lane_file=$3 label=$4 c=$5 lane=$6 try
  k apply -f "$HERE/$lane_file" >/dev/null || return 1
  k rollout status "deploy/$epp" --timeout=15m >/dev/null || return 1
  echo "=== $dep: $label c=$c ($(date -u +%H:%M:%S))"
  for try in "$label" "$label-retry"; do
    MODE=pool URL=http://$epp:80 EPP_DEPLOY=$epp DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$lane \
      "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && { echo "=== $dep done ($(date -u +%H:%M:%S))"; return 0; }
    echo "=== $try/c$c on $dep failed; $( [ "$try" = "$label" ] && echo retrying || echo giving up ) ($(date -u +%H:%M:%S))"
  done
  return 1
}

FAILED=""
point glm52-tp8   e lane-epp-e-cap3m-a.yaml explore1h-thunder-cap3m-l10 48 a & pa=$!
sleep 5
point glm52-tp8-b a lane-epp-a-cap6m-b.yaml explore1h-thunder-cap6m-l10 48 b & pb=$!
sleep 5
point glm52-tp8-c c lane-epp-c-cap3m-c.yaml explore1h-thunder-cap3m-l10 32 c & pc=$!
sleep 5
point glm52-tp8-d d lane-epp-d-cap6m-d.yaml explore1h-thunder-cap6m-l10 32 d & pd=$!
wait $pa || FAILED="$FAILED A"
wait $pb || FAILED="$FAILED B"
wait $pc || FAILED="$FAILED C"
wait $pd || FAILED="$FAILED D"

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore1h-cap/report" \
  "$RESULTS"/explore1h-thunder-cap3m-l10/c* "$RESULTS"/explore1h-thunder-cap6m-l10/c*
[ -z "$FAILED" ] || { echo "points that failed:$FAILED"; exit 1; }
