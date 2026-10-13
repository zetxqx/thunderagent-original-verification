#!/usr/bin/env bash
# Tail of run-1h-highc.sh, rebalanced (2026-10-12): no router c=128 warms up for about
# 3.5 h (1422 warmup requests), so chain A was stopped after c=128 and its second point,
# no router c=48, runs on server C once chain C of run-1h-highc.sh is done (C keeps its
# offload flags; no EPP is needed).
# Usage: nohup caffeinate -i ./run-1h-highc-tail.sh > results/run-1h-highc-tail.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=48Gi CLIENT_MEM_REQUEST=24Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
LABEL=explore1h-direct

until grep -q "^=== c done" "$RESULTS/run-1h-highc.log"; do sleep 60; done
echo "=== c: $LABEL c=48 ($(date -u +%H:%M:%S))"
for try in "$LABEL" "$LABEL-retry"; do
  MODE=direct URL=http://glm52-tp8-c:8000 DEPLOY=glm52-tp8-c DECODE_SELECTOR=app=glm52-tp8-c LANE=c \
    "$SCRIPTS/run-point.sh" 48 "$try" > "$RESULTS/$try-c48.log" 2>&1 && { echo "=== tail done ($(date -u +%H:%M:%S))"; exit 0; }
  echo "=== $try/c48 failed ($(date -u +%H:%M:%S))"
done
echo "=== tail done, failed ($(date -u +%H:%M:%S))"
exit 1
