#!/usr/bin/env bash
# Rerun of no-router c=64 (2026-10-14): both attempts in run-1h.sh failed in warmup with "Connection reset
# by peer" (vLLM's 5 s HTTP keep-alive, see vllm-qwen35.yaml.tmpl). qwen35-tp4-e now runs with
# VLLM_HTTP_TIMEOUT_KEEP_ALIVE=1800; same settings otherwise.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
export RESULTS="$HERE/results" CTX=gke_supercomputer-testing_europe-west4_a4-pr KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig NS=bobzetian-llmd
export MODEL=Qwen/Qwen3.5-397B-A17B-FP8 DATASET=semianalysis_cc_traces_weka_062126_256k
export CLIENT_POOL=pool-1 GPUS_PER_POD=4 MODEL_SERVER_COLLECT=0 CLIENT_CPU=3 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=12Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" rollout status deploy/qwen35-tp4-e --timeout=60m || exit 1
echo "=== qwen35-tp4-e: qwen35-direct c=64 ($(date -u +%H:%M:%S))"
for try in qwen35-direct qwen35-direct-retry; do
  MODE=direct URL=http://qwen35-tp4-e:8000 DEPLOY=qwen35-tp4-e DECODE_SELECTOR=app=qwen35-tp4-e LANE=qe \
    "$SCRIPTS/run-point.sh" 64 "$try" > "$RESULTS/$try-c64.log" 2>&1 && { echo "=== done ($(date -u +%H:%M:%S))"; exit 0; }
  echo "=== $try/c64 failed ($(date -u +%H:%M:%S))"
done
exit 1
