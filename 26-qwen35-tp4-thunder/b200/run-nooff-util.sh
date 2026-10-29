#!/usr/bin/env bash
# Step 26 part 2, gate capacity sweep (2026-10-29): llm-d thunder with utilThreshold 0.7 and 0.6
# (gate admits up to 70% / 60% of the server's kv_cache_size_tokens), Qwen3.5 TP=4 WITHOUT the CPU KV
# tier, c = 24, 28, 32, 36, 40. Lease 10 s, forced admission 1800 s, MAX_NUM_SEQS 2x concurrency,
# 3600 s per point, RESET=1. Baselines: part 2's qwen35-nooff-direct, -thunder-l10 and -thunder-u08.
# 10 points at once, one server and one lane each (server qwen35-nooff-<lane>, lane u<util><c>);
# the 0.7 and 0.6 servers of one c share a node and start their 3600 s points together after both
# pass a c=4 120 s smoke:
#   c=24 13z6   c=28 gw0s   c=32 p3mf   c=36 1g50   c=40 3v40
# Node pool pool-1: clients request 1.5 CPU / 8Gi (no CPU limit), lane EPPs 250m / 1Gi per container.
# Usage: ./run-nooff-util.sh 2>&1 | tee results/run-nooff-util.log
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
export CLIENT_CPU=1.5 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=8Gi
export RESTART=0 RESET=1
export EPP_SMALL_REQUESTS=1
BASE_EXTRA="--tokenizer-trust-remote-code"
kc() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
ts() { date -u +%H:%M:%S; }

kv_tokens() {
  local v
  v=$(kc exec "deploy/$1" -- curl -s -m 10 localhost:8000/metrics 2>/dev/null \
      | grep -oE 'kv_cache_size_tokens="[0-9.eE+]+"' | head -1 | grep -oE '[0-9.eE+]+' | tail -1)
  [ -n "$v" ] || v=$(kc logs "deploy/$1" 2>/dev/null | grep -oE 'GPU KV cache size: [0-9,]+ tokens' | tail -1 | grep -oE '[0-9,]+' | tr -d ,)
  [ -n "$v" ] && python3 -c "print(int(float('$v')))"
}

run1() {  # run1 <lane> <c> <label> <duration> <extra args>
  local lane=$1 c=$2 label=$3 dur=$4 extra=$5 dep=qwen35-nooff-$1
  DURATION=$dur EXTRA_ARGS="$extra" MODE=pool URL=http://agentx-epp-$lane-epp:80 EPP_DEPLOY=agentx-epp-$lane-epp DEPLOY=$dep \
    DECODE_SELECTOR=app=$dep LANE=$lane "$SCRIPTS/run-point.sh" "$c" "$label" > "$RESULTS/$label-c$c.log" 2>&1
}

prep() {  # prep <lane> <util> <label>: server up, lane EPP, smoke c=4 120 s, verify
  local lane=$1 util=$2 label=$3-smoke-$1 dep=qwen35-nooff-$1 ip cap try
  kc rollout status "deploy/$dep" --timeout=90m > /dev/null || { echo "=== $dep not available ($(ts))"; return 1; }
  ip=$(kc get svc "$dep" -o jsonpath='{.spec.clusterIP}'); cap=$(kv_tokens "$dep")
  [ -n "$ip" ] && [ -n "$cap" ] || { echo "=== $dep: no ClusterIP or kv tokens"; return 1; }
  echo "=== $dep: capacityTokens $cap, utilThreshold $util, endpoint $ip ($(ts))"
  "$HERE/render-nooff-epp.py" "$lane" "$dep" "$ip" "$cap" "$util" > "$HERE/lane-epp-$lane.yaml" || return 1
  for i in 1 2 3; do kc apply -f "$HERE/lane-epp-$lane.yaml" > /dev/null && break; sleep 10; done
  kc rollout status "deploy/agentx-epp-$lane-epp" --timeout=15m > /dev/null || return 1
  for try in "$label" "$label-retry"; do
    if run1 "$lane" 4 "$try" 120 "$BASE_EXTRA --unsafe-override --num-dataset-entries 8 --warmup-requests-per-lane 1" \
       && "$SCRIPTS/verify-point.sh" "$RESULTS/$try/c4" > "$RESULTS/$try-verify.txt" 2>&1 \
       && ! grep -qv '^  ok' "$RESULTS/$try-verify.txt"; then
      echo "=== $dep: smoke ok ($(ts))"; return 0
    fi
    echo "=== $dep: smoke $try failed ($(ts))"; kc delete job "agentx-c4-$try" --ignore-not-found > /dev/null 2>&1
  done
  return 1
}

pair() {  # pair <c>: the u07 and u06 servers of one concurrency
  local c=$1 rc=0 p1 p2 pids="" lane label
  prep "u07c$c" 0.7 qwen35-nooff-thunder-u07 & p1=$!; prep "u06c$c" 0.6 qwen35-nooff-thunder-u06 & p2=$!
  wait $p1 || rc=1; wait $p2 || rc=1
  [ $rc = 0 ] || { echo "=== c=$c: a smoke failed, pair not started ($(ts))"; return 1; }
  echo "=== c=$c: both smokes ok, starting the 3600 s points ($(ts))"
  for lu in "u07c$c:qwen35-nooff-thunder-u07" "u06c$c:qwen35-nooff-thunder-u06"; do
    lane=${lu%%:*}; label=${lu##*:}
    ( for try in "$label" "$label-retry"; do
        run1 "$lane" "$c" "$try" 3600 "$BASE_EXTRA" && { echo "=== qwen35-nooff-$lane done $try c=$c ($(ts))"; exit 0; }
        echo "=== $try/c$c on qwen35-nooff-$lane failed ($(ts))"; kc delete job "agentx-c$c-$try" --ignore-not-found > /dev/null 2>&1
      done; exit 1 ) & pids="$pids $!"
    sleep 5
  done
  for p in $pids; do wait $p || rc=1; done
  return $rc
}

FAILED="" GP=""
for c in 40 36 32 28 24; do pair $c & GP="$GP $!:$c"; sleep 10; done
for g in $GP; do wait "${g%%:*}" || FAILED="$FAILED c${g##*:}"; done

"$SCRIPTS/verify-point.sh" "$RESULTS"/qwen35-nooff-thunder-u0{7,6}/c{24,28,32,36,40}
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/report-nooff" \
  "$RESULTS"/qwen35-nooff-direct/c* "$RESULTS"/qwen35-nooff-thunder-{l10,u08,u07,u06}/c*
[ -z "$FAILED" ] || { echo "concurrencies with a failure:$FAILED"; exit 1; }
echo "=== all done ($(ts))"
