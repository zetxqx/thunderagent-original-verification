#!/usr/bin/env bash
# Step 26 test (2026-10-14): does free space in llm-d-thunder-agent-simplified's capacity keep the admitted
# sessions on the GPU? Same as the c=48 thunder point (qwen35-thunder-gpu-l10/c48: capacity = vLLM
# kv_cache_size_tokens 4,780,827, utilThreshold 1.0), with utilThreshold 0.8 and 0.6, both at c=48, at once:
#   qwen35-tp4-d (EPP agentx-epp-qd): utilThreshold 0.8 -> label qwen35-thunder-u08
#   qwen35-tp4-c (EPP agentx-epp-qc): utilThreshold 0.6 -> label qwen35-thunder-u06
# Both servers run --max-num-seqs 96 (same pool, 4,780,827 tokens). 3600 s, cache reset per point.
# Usage: nohup caffeinate -i ./run-util.sh > results/run-util.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
export RESULTS="$HERE/results" CTX=gke_supercomputer-testing_europe-west4_a4-pr KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig NS=bobzetian-llmd
export MODEL=Qwen/Qwen3.5-397B-A17B-FP8 DATASET=semianalysis_cc_traces_weka_062126_256k
export CLIENT_POOL=pool-1 GPUS_PER_POD=4 MODEL_SERVER_COLLECT=0 CLIENT_CPU=3 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=12Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }

point() {  # point <server> <lane> <lane file> <label>
  local dep=qwen35-tp4-$1 epp=agentx-epp-$2-epp try
  k apply -f "$HERE/$3" >/dev/null && k rollout status "deploy/$epp" --timeout=10m >/dev/null || return 1
  echo "=== $dep: $4 c=48 ($(date -u +%H:%M:%S))"
  for try in "$4" "$4-retry"; do
    MODE=pool URL=http://$epp:80 EPP_DEPLOY=$epp DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$2 \
      "$SCRIPTS/run-point.sh" 48 "$try" > "$RESULTS/$try-c48.log" 2>&1 && { echo "=== $dep done ($(date -u +%H:%M:%S))"; return 0; }
    echo "=== $try/c48 on $dep failed ($(date -u +%H:%M:%S))"
  done
  return 1
}
point d qd lane-epp-qd-u8.yaml qwen35-thunder-u08 & p1=$!
sleep 5
point c qc lane-epp-qc-u6.yaml qwen35-thunder-u06 & p2=$!
rc=0; wait $p1 || rc=1; wait $p2 || rc=1
uv run "$SCRIPTS/analyze.py" --out "$RESULTS/report-util" "$RESULTS"/qwen35-thunder-gpu-l10/c48 "$RESULTS"/qwen35-thunder-u0*/c48 "$RESULTS"/qwen35-direct/c48
exit $rc
