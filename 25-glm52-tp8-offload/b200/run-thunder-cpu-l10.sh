#!/usr/bin/env bash
# Step 25 thunder variant thunder-cpu-l10 at c=16 on cluster a4-pr: the gate's
# capacity counts the CPU tier (3909360 tokens) and the idle lease is 10 s
# (thunder-cpu-l10-plugins.yaml, deployed with ./render-epp.sh). Same point
# settings as run-thunder.sh; compared with r1/c16 and thunder-r1/c16.
#
# Usage: nohup caffeinate -i ./run-thunder-cpu-l10.sh > results/thunder-cpu-l10.log 2>&1 &
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
export MODE=pool URL=http://agentx-epp-a-epp:80 EPP_DEPLOY=agentx-epp-a-epp

rc=0
SERVER_ENV="MAX_NUM_SEQS=32" "$SCRIPTS/run-point.sh" 16 thunder-cpu-l10-r1 || rc=$?

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/compare-c16/report" \
  "$RESULTS/r1/c16" "$RESULTS/thunder-r1/c16" "$RESULTS/thunder-cpu-l10-r1/c16"
rm -f "$RESULTS/bobbm.kubeconfig"
exit $rc
