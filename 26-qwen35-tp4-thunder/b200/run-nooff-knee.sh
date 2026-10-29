#!/usr/bin/env bash
# Step 26 part 2, knee points (2026-10-29): Qwen3.5 TP=4 WITHOUT the CPU KV tier at c = 28, 36, 40, 44,
# where the no-router working set crosses the GPU KV pool (part 2 measured 0.86x peak at c=24, 1.07x at
# c=32, 1.65x at c=48). Three arms per concurrency, as in part 2: no-router (qwen35-nooff-direct),
# llm-d thunder at 100% capacity (qwen35-nooff-thunder-l10, utilThreshold 1.0) and at 80%
# (qwen35-nooff-thunder-u08, utilThreshold 0.8); lease 10 s, forced admission 1800 s, capacity = the
# server's kv_cache_size_tokens. MAX_NUM_SEQS 2x concurrency, 3600 s per point, RESET=1.
# All 12 points at once, one server and one lane (k<x>) each:
#   c=44: g p3mf direct,  h p3mf thunder 100%,  i 13z6 thunder 80%
#   c=40: j gw0s direct,  k 1g50 thunder 100%,  l 1g50 thunder 80%
#   c=36: m 9r8s direct,  n dkvh thunder 100%,  o 3v40 thunder 80%
#   c=28: p mzl3 direct,  q q2b8 thunder 100%,  r xfxp thunder 80%
# Per server: wait for it, (thunder) render its lane EPP, run a c=4 120 s smoke and verify it. The three
# arms of one concurrency start their 3600 s points together once all three smokes pass.
# Node pool pool-1 (clients, EPPs) had about 28 free CPU of requests: clients request 1.5 CPU / 8Gi
# (no CPU limit; earlier clients used well under 1 core) and lane EPPs 250m / 1Gi per container.
# Usage: ./run-nooff-knee.sh 2>&1 | tee results/run-nooff-knee.log
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

run1() {  # run1 <server letter> <arm: direct|l10|u08> <c> <label> <duration> <extra args>
  local s=$1 arm=$2 c=$3 label=$4 dur=$5 extra=$6 dep=qwen35-nooff-$1 lane=k$1
  if [ "$arm" = direct ]; then
    DURATION=$dur EXTRA_ARGS="$extra" MODE=direct URL=http://$dep:8000 DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$lane \
      "$SCRIPTS/run-point.sh" "$c" "$label" > "$RESULTS/$label-c$c.log" 2>&1
  else
    DURATION=$dur EXTRA_ARGS="$extra" MODE=pool URL=http://agentx-epp-$lane-epp:80 EPP_DEPLOY=agentx-epp-$lane-epp DEPLOY=$dep \
      DECODE_SELECTOR=app=$dep LANE=$lane "$SCRIPTS/run-point.sh" "$c" "$label" > "$RESULTS/$label-c$c.log" 2>&1
  fi
}

label_of() { case $1 in direct) echo qwen35-nooff-direct ;; l10) echo qwen35-nooff-thunder-l10 ;; u08) echo qwen35-nooff-thunder-u08 ;; esac; }

prep() {  # prep <server letter> <arm>: server up, lane EPP (thunder), smoke c=4 120 s, verify
  local s=$1 arm=$2 dep=qwen35-nooff-$1 lane=k$1 ip cap util label try
  kc rollout status "deploy/$dep" --timeout=90m > /dev/null || { echo "=== $dep not available ($(ts))"; return 1; }
  if [ "$arm" != direct ]; then
    util=1.0; [ "$arm" = u08 ] && util=0.8
    ip=$(kc get svc "$dep" -o jsonpath='{.spec.clusterIP}'); cap=$(kv_tokens "$dep")
    [ -n "$ip" ] && [ -n "$cap" ] || { echo "=== $dep: no ClusterIP or kv tokens"; return 1; }
    echo "=== $dep: capacityTokens $cap, utilThreshold $util, endpoint $ip ($(ts))"
    "$HERE/render-nooff-epp.py" "$lane" "$dep" "$ip" "$cap" "$util" > "$HERE/lane-epp-$lane.yaml" || return 1
    for i in 1 2 3; do kc apply -f "$HERE/lane-epp-$lane.yaml" > /dev/null && break; sleep 10; done
    kc rollout status "deploy/agentx-epp-$lane-epp" --timeout=15m > /dev/null || return 1
  fi
  label="$(label_of "$arm")-smoke-$s"
  for try in "$label" "$label-retry"; do
    if run1 "$s" "$arm" 4 "$try" 120 "$BASE_EXTRA --unsafe-override --num-dataset-entries 8 --warmup-requests-per-lane 1" \
       && "$SCRIPTS/verify-point.sh" "$RESULTS/$try/c4" > "$RESULTS/$try-verify.txt" 2>&1 \
       && ! grep -qv '^  ok' "$RESULTS/$try-verify.txt"; then
      echo "=== $dep: smoke ok ($(ts))"; return 0
    fi
    echo "=== $dep: smoke $try failed ($(ts))"; kc delete job "agentx-c4-$try" --ignore-not-found > /dev/null 2>&1
  done
  return 1
}

group() {  # group <c> <direct server> <l10 server> <u08 server>
  local c=$1 d=$2 t=$3 u=$4 rc=0 p1 p2 p3 s arm label try
  prep "$d" direct & p1=$!; prep "$t" l10 & p2=$!; prep "$u" u08 & p3=$!
  wait $p1 || rc=1; wait $p2 || rc=1; wait $p3 || rc=1
  [ $rc = 0 ] || { echo "=== c=$c: a smoke failed, group not started ($(ts))"; return 1; }
  echo "=== c=$c: all three smokes ok, starting the 3600 s points ($(ts))"
  pids=""
  for sa in "$d:direct" "$t:l10" "$u:u08"; do
    s=${sa%%:*}; arm=${sa##*:}; label=$(label_of "$arm")
    ( for try in "$label" "$label-retry"; do
        run1 "$s" "$arm" "$c" "$try" 3600 "$BASE_EXTRA" && { echo "=== qwen35-nooff-$s done $try c=$c ($(ts))"; exit 0; }
        echo "=== $try/c$c on qwen35-nooff-$s failed ($(ts))"; kc delete job "agentx-c$c-$try" --ignore-not-found > /dev/null 2>&1
      done; exit 1 ) & pids="$pids $!"
    sleep 5
  done
  for p in $pids; do wait $p || rc=1; done
  return $rc
}

FAILED=""
group 44 g h i & G1=$!; sleep 10
group 40 j k l & G2=$!; sleep 10
group 36 m n o & G3=$!; sleep 10
group 28 p q r & G4=$!
wait $G1 || FAILED="$FAILED c44"; wait $G2 || FAILED="$FAILED c40"; wait $G3 || FAILED="$FAILED c36"; wait $G4 || FAILED="$FAILED c28"

"$SCRIPTS/verify-point.sh" "$RESULTS"/qwen35-nooff-{direct,thunder-l10,thunder-u08}/c{28,36,40,44}
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/report-nooff" \
  "$RESULTS"/qwen35-nooff-direct/c* "$RESULTS"/qwen35-nooff-thunder-l10/c* "$RESULTS"/qwen35-nooff-thunder-u08/c*
[ -z "$FAILED" ] || { echo "groups with a failure:$FAILED"; exit 1; }
echo "=== all done ($(ts))"
