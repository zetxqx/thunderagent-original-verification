#!/usr/bin/env bash
# Step 26 part 2, arm 3 (2026-10-28): llm-d thunder with capacity at 80% of the GPU KV pool
# (utilThreshold 0.8; otherwise part 2's settings: idle lease 10 s, forced admission 1800 s,
# capacityTokens = the server's vLLM kv_cache_size_tokens), Qwen3.5 TP=4 WITHOUT the CPU KV tier,
# MAX_NUM_SEQS 2x concurrency, 3600 s per point, RESET=1. The no-router baseline is part 2's
# qwen35-nooff-direct points (2026-10-28 02:49 to 05:53 UTC, same nodes for c=48/64/96).
# One server and one lane EPP (agentx-epp-t<x>) per queue; the three queues run at the same time.
# Nodes 13z6, gw0s and p3mf each had one GPU taken by another team at start, so they hold one
# server each (d213 was tried for c=32/24 but evicted the servers for low ephemeral storage):
#   a (13z6) c=96   c (gw0s) c=48 then c=32   e (p3mf) c=64 then c=24
# Before a server's second point it restarts with the next MAX_NUM_SEQS, and its EPP gets the new
# kv_cache_size_tokens. SMOKE=1 runs only a c=4, 120 s smoke on the three lanes.
# Usage: ./run-nooff-u08.sh 2>&1 | tee results/run-nooff-u08.log
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
export PATH="$HOME/.local/bin:$PATH"  # uv

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=Qwen/Qwen3.5-397B-A17B-FP8 DATASET=semianalysis_cc_traces_weka_062126_256k
export CLIENT_POOL=pool-1 GPUS_PER_POD=4 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=3 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=12Gi
export DURATION=3600 RESTART=0 RESET=1
EXTRA="--tokenizer-trust-remote-code"
LABEL=qwen35-nooff-thunder-u08
UTIL=0.8
SMOKE=${SMOKE:-0}
if [ "$SMOKE" = 1 ]; then
  export DURATION=120
  EXTRA="$EXTRA --unsafe-override --num-dataset-entries 8 --warmup-requests-per-lane 1"
  LABEL=$LABEL-smoke
fi
export EXTRA_ARGS="$EXTRA"
kc() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
ts() { date -u +%H:%M:%S; }

kv_tokens() {  # kv_cache_size_tokens of deploy/$1 (label of vLLM's cache config metric, else the start log)
  local v
  v=$(kc exec "deploy/$1" -- curl -s -m 10 localhost:8000/metrics 2>/dev/null \
      | grep -oE 'kv_cache_size_tokens="[0-9.eE+]+"' | head -1 | grep -oE '[0-9.eE+]+' | tail -1)
  [ -n "$v" ] || v=$(kc logs "deploy/$1" 2>/dev/null | grep -oE 'GPU KV cache size: [0-9,]+ tokens' | tail -1 | grep -oE '[0-9,]+' | tr -d ,)
  [ -n "$v" ] && python3 -c "print(int(float('$v')))"
}

lane_point() {  # lane_point <server letter> <concurrency>: lane EPP agentx-epp-t<x>, one retry
  local s=$1 c=$2 dep=qwen35-nooff-$1 lane=t$1 label=$LABEL ip cap try
  [ "$SMOKE" = 1 ] && { c=4; label="$LABEL-$s"; }
  kc rollout status "deploy/$dep" --timeout=90m > /dev/null || { echo "=== $dep not available"; return 1; }
  ip=$(kc get svc "$dep" -o jsonpath='{.spec.clusterIP}'); cap=$(kv_tokens "$dep")
  [ -n "$ip" ] && [ -n "$cap" ] || { echo "=== $dep: no ClusterIP or kv tokens (ip=$ip cap=$cap)"; return 1; }
  echo "=== $dep: capacityTokens $cap, utilThreshold $UTIL (gate admits up to $((cap * 8 / 10))), endpoint $ip ($(ts))"
  "$HERE/render-nooff-epp.py" "$lane" "$dep" "$ip" "$cap" "$UTIL" > "$HERE/lane-epp-$lane.yaml" || return 1
  for i in 1 2 3; do kc apply -f "$HERE/lane-epp-$lane.yaml" > /dev/null && break; sleep 10; done
  kc rollout status "deploy/agentx-epp-$lane-epp" --timeout=15m > /dev/null || return 1
  echo "=== $dep: $label c=$c ($(ts))"
  for try in "$label" "$label-retry"; do
    MODE=pool URL=http://agentx-epp-$lane-epp:80 EPP_DEPLOY=agentx-epp-$lane-epp DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$lane \
      "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && { echo "=== $dep done c=$c ($(ts))"; return 0; }
    echo "=== $try/c$c on $dep failed; $( [ "$try" = "$label" ] && echo retrying || echo giving up ) ($(ts))"
    kc delete job "agentx-c$c-$try" --ignore-not-found > /dev/null 2>&1
  done
  return 1
}

set_seqs() {  # set_seqs <server letter> <MAX_NUM_SEQS>: restart the server only if the value changes
  local dep=qwen35-nooff-$1 cur
  cur=$(kc get "deploy/$dep" -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="MAX_NUM_SEQS")].value}')
  if [ "$cur" != "$2" ]; then echo "=== $dep: MAX_NUM_SEQS $cur -> $2 ($(ts))"; kc set env "deploy/$dep" "MAX_NUM_SEQS=$2" > /dev/null; fi
}

queue() {  # queue <server letter> <c1> [c2 ...]
  local s=$1 c rc=0; shift
  for c in "$@"; do
    [ "$SMOKE" = 1 ] || set_seqs "$s" $((2 * c))
    lane_point "$s" "$c" || rc=1
    [ "$SMOKE" = 1 ] && break
  done
  return $rc
}

FAILED="" PIDS=""
for q in "a 96" "c 48 32" "e 64 24"; do
  queue $q & PIDS="$PIDS $!:${q%% *}"; sleep 10
done
for p in $PIDS; do wait "${p%%:*}" || FAILED="$FAILED ${p##*:}"; done

if [ "$SMOKE" = 1 ]; then
  "$SCRIPTS/verify-point.sh" "$RESULTS"/$LABEL-?/c4
else
  "$SCRIPTS/verify-point.sh" "$RESULTS"/$LABEL/c*
  uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/report-nooff" \
    "$RESULTS"/qwen35-nooff-direct/c* "$RESULTS"/qwen35-nooff-thunder-l10/c* "$RESULTS"/$LABEL/c*
fi
[ -z "$FAILED" ] || { echo "servers with a failed point:$FAILED"; exit 1; }
echo "=== all done ($(ts))"
