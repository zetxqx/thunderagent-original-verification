#!/usr/bin/env bash
# Step 26 (2026-10-14): Qwen3.5-397B-A17B-FP8 on vLLM v0.31, TP=4 (InferenceX run 442369 setup in
# vLLM), CPU offload 387 GiB, MAX_NUM_SEQS 2x concurrency. no-router and llm-d-thunder-agent-simplified
# (capacity = the server's vLLM kv_cache_size_tokens, lease 10 s, forced admission after 1800 s; EPP image upstream main 907c5fe8,
# ghcr.io/llm-d/llm-d-router-endpoint-picker:main@sha256:c0d60804...) at c=32, 48, 64, 3600 s, all six
# points at once, one server each, the two arms of one concurrency on the same node:
#   5qjv: qwen35-tp4-a no-router c=32   qwen35-tp4-b thunder c=32 (EPP agentx-epp-qb)
#   13z6: qwen35-tp4-c no-router c=48   qwen35-tp4-d thunder c=48 (EPP agentx-epp-qd)
#   0x6t: qwen35-tp4-e no-router c=64   qwen35-tp4-f thunder c=64 (EPP agentx-epp-qf)
# Trace set: the 256k-capped Weka corpus, as InferenceX uses for qwen3.5. RESET=1 empties both KV
# tiers (and restarts the EPP) before each point. Clients request 3 CPU and 12 GiB (limit 32 GiB) so
# six fit next to three EPPs on the one usable pool-1 node.
# Usage: nohup caffeinate -i ./run-1h.sh > results/run-1h.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=Qwen/Qwen3.5-397B-A17B-FP8 DATASET=semianalysis_cc_traces_weka_062126_256k
export CLIENT_POOL=pool-1 GPUS_PER_POD=4 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=3 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=12Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
DIRECT=qwen35-direct THUNDER=qwen35-thunder-gpu-l10

point() {  # point <server letter> <direct|thunder> <concurrency> [epp lane]; one retry
  local srv=$1 arm=$2 c=$3 lane=${4:-} dep=qwen35-tp4-$1 label try
  if [ "$arm" = direct ]; then label=$DIRECT; else label=$THUNDER; fi
  echo "=== $dep: $label c=$c ($(date -u +%H:%M:%S))"
  for try in "$label" "$label-retry"; do
    if [ "$arm" = direct ]; then
      MODE=direct URL=http://$dep:8000 DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=q$srv \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && { echo "=== $dep done ($(date -u +%H:%M:%S))"; return 0; }
    else
      MODE=pool URL=http://agentx-epp-$lane-epp:80 EPP_DEPLOY=agentx-epp-$lane-epp DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$lane \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && { echo "=== $dep done ($(date -u +%H:%M:%S))"; return 0; }
    fi
    echo "=== $try/c$c on $dep failed; $( [ "$try" = "$label" ] && echo retrying || echo giving up ) ($(date -u +%H:%M:%S))"
  done
  return 1
}

for s in a b c d e f; do
  KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" wait --for=condition=Available "deploy/qwen35-tp4-$s" --timeout=90m || exit 1
done
echo "=== all six servers available ($(date -u +%H:%M:%S))"

FAILED=""
point a direct 32 & p1=$!; sleep 5
point b thunder 32 qb & p2=$!; sleep 5
point c direct 48 & p3=$!; sleep 5
point d thunder 48 qd & p4=$!; sleep 5
point e direct 64 & p5=$!; sleep 5
point f thunder 64 qf & p6=$!
for p in $p1 $p2 $p3 $p4 $p5 $p6; do wait $p || FAILED="$FAILED $p"; done

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/report" "$RESULTS"/qwen35-*/c*
[ -z "$FAILED" ] || { echo "points that failed (pids):$FAILED"; exit 1; }
