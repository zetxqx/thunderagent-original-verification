#!/usr/bin/env bash
# Step 27: dep8-affinity c=32 again. Both tries in run-dep8.sh failed at the cache reset on a transient
# Kubernetes API error ("the server is currently unable to handle the request", 2026-10-15 08:44).
# Waits until run-dep8.sh has finished server b's chain, then runs the point on glm52-dep8-b.
# Usage: nohup caffeinate -i ./run-dep8-b32.sh > results/run-dep8-b32.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
export RESULTS="$HERE/results" CTX=gke_supercomputer-testing_europe-west4_a4-pr KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=16Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
until grep -q "=== b done" "$RESULTS/run-dep8.log"; do sleep 60; done
echo "=== b: c=32 again ($(date -u +%H:%M:%S))"
for try in dep8-affinity-r2 dep8-affinity-r3; do
  MODE=pool URL=http://agentx-epp-gb-epp:80 EPP_DEPLOY=agentx-epp-gb-epp DEPLOY=glm52-dep8-b DECODE_SELECTOR=app=glm52-dep8-b LANE=gb \
    VLLM_PORTS="8000 8001 8002 8003 8004 8005 8006 8007" "$SCRIPTS/run-point.sh" 32 "$try" > "$RESULTS/$try-c32.log" 2>&1 \
    && { echo "=== $try/c32 done ($(date -u +%H:%M:%S))"; exit 0; }
  echo "=== $try/c32 failed ($(date -u +%H:%M:%S))"
done
exit 1
