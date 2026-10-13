#!/usr/bin/env bash
# Step 25 thunder comparison on cluster a4-pr: thunder gate (lane EPP, file
# discovery) against no router at c=12 and c=16, 3600 s each, a fresh server per
# point, arms alternated. MAX_NUM_SEQS = 2x concurrency as in the grid.
# No-router points use label r1, so they extend run-grid.sh's sweep.
#
# Usage: nohup caffeinate -i ./run-thunder.sh > results/thunder.log 2>&1 &
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd DEPLOY=glm52-tp8 DECODE_SELECTOR=app=glm52-tp8
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=1 ROLLOUT_TIMEOUT=60m

FAILED=""
run() {  # run <arm> <concurrency>
  local label
  if [ "$1" = thunder ]; then
    label=thunder-r1
    export MODE=pool URL=http://agentx-epp-a-epp:80 EPP_DEPLOY=agentx-epp-a-epp
  else
    label=r1
    export MODE=direct URL=http://glm52-tp8:8000
  fi
  echo "=== $label: concurrency $2 ($(date -u +%H:%M:%S))"
  if ! SERVER_ENV="MAX_NUM_SEQS=$(($2 * 2))" "$SCRIPTS/run-point.sh" "$2" "$label"; then
    FAILED="$FAILED $label/c$2"
    echo "=== $label/c$2 did not succeed or is invalid; artifacts kept, continuing"
  fi
}

run thunder 12
run direct 12
run thunder 16
run direct 16

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/r1/report" "$RESULTS/r1"/c*
uv run "$SCRIPTS/analyze.py" --out "$RESULTS/thunder-r1/report" "$RESULTS/thunder-r1"/c*
uv run "$SCRIPTS/analyze.py" --out "$RESULTS/compare/report" "$RESULTS/r1"/c1[26] "$RESULTS/thunder-r1"/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
