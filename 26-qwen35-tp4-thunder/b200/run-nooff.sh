#!/usr/bin/env bash
# Step 26 part 2 (2026-10-28): Qwen3.5-397B-A17B-FP8 on vLLM v0.31, TP=4, WITHOUT the CPU KV tier
# (vllm-qwen35-nooff.yaml.tmpl), MAX_NUM_SEQS 2x concurrency. no-router vs llm-d thunder (step 26's
# settings: utilThreshold 1.0, capacity = the server's vLLM kv_cache_size_tokens, idle lease 10 s,
# forced admission after 1800 s), 3600 s per point, RESET=1 (KV cache emptied and EPP restarted per point).
# Both arms of one concurrency run at the same time on the two servers of one node; each node runs its
# own queue of concurrencies, so the three nodes never wait for each other:
#   13z6: qwen35-nooff-a no-router, qwen35-nooff-b thunder (EPP agentx-epp-nb): c=96
#   gw0s: qwen35-nooff-c no-router, qwen35-nooff-d thunder (EPP agentx-epp-nd): c=48, then c=32
#   p3mf: qwen35-nooff-e no-router, qwen35-nooff-f thunder (EPP agentx-epp-nf): c=64, then c=24
# Between two points of a node, both servers restart with the next MAX_NUM_SEQS and the thunder EPP gets
# the new kv_cache_size_tokens. SMOKE=1 runs only a c=4, 120 s smoke on all six lanes.
# Usage: nohup ./run-nooff.sh > results/run-nooff.log 2>&1 &
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
DIRECT=qwen35-nooff-direct THUNDER=qwen35-nooff-thunder-l10
SMOKE=${SMOKE:-0}
if [ "$SMOKE" = 1 ]; then
  export DURATION=120
  EXTRA="$EXTRA --unsafe-override --num-dataset-entries 8 --warmup-requests-per-lane 1"
  DIRECT=qwen35-nooff-direct-smoke THUNDER=qwen35-nooff-thunder-l10-smoke
fi
export EXTRA_ARGS="$EXTRA"
kc() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
ts() { date -u +%H:%M:%S; }

kv_tokens() {  # kv_cache_size_tokens of deploy/$1: label of vLLM's cache config metric, else the start log
  local v
  v=$(kc exec "deploy/$1" -- curl -s -m 10 localhost:8000/metrics 2>/dev/null \
      | grep -oE 'kv_cache_size_tokens="[0-9.eE+]+"' | head -1 | grep -oE '[0-9.eE+]+' | tail -1)
  [ -n "$v" ] || v=$(kc logs "deploy/$1" 2>/dev/null | grep -oE 'GPU KV cache size: [0-9,]+ tokens' | tail -1 | grep -oE '[0-9,]+' | tr -d ,)
  [ -n "$v" ] && python3 -c "print(int(float('$v')))"
}

refresh_epp() {  # refresh_epp <thunder server letter>: render and apply the lane EPP with the server's capacity
  local s=$1 dep=qwen35-nooff-$1 lane=n$1 ip cap
  ip=$(kc get svc "$dep" -o jsonpath='{.spec.clusterIP}')
  cap=$(kv_tokens "$dep")
  [ -n "$ip" ] && [ -n "$cap" ] || { echo "=== $dep: no ClusterIP or kv tokens (ip=$ip cap=$cap)"; return 1; }
  echo "=== $dep: thunder capacity $cap tokens, endpoint $ip ($(ts))"
  "$HERE/render-nooff-epp.py" "$lane" "$dep" "$ip" "$cap" > "$HERE/lane-epp-$lane.yaml" || return 1
  for i in 1 2 3; do kc apply -f "$HERE/lane-epp-$lane.yaml" > /dev/null && break; sleep 10; done
  kc rollout status "deploy/agentx-epp-$lane-epp" --timeout=15m > /dev/null
}

set_seqs() {  # set_seqs <server letter> <MAX_NUM_SEQS>: restart the server only if the value changes
  local dep=qwen35-nooff-$1 cur
  cur=$(kc get "deploy/$dep" -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="MAX_NUM_SEQS")].value}')
  if [ "$cur" != "$2" ]; then
    echo "=== $dep: MAX_NUM_SEQS $cur -> $2 ($(ts))"
    kc set env "deploy/$dep" "MAX_NUM_SEQS=$2" > /dev/null
  fi
}

point() {  # point <server letter> <direct|thunder> <concurrency>; one retry
  local srv=$1 arm=$2 c=$3 dep=qwen35-nooff-$1 label try
  if [ "$arm" = direct ]; then label=$DIRECT; else label=$THUNDER; fi
  [ "$SMOKE" = 1 ] && label="$label-$srv"  # smoke points share c=4: one label per server
  echo "=== $dep: $label c=$c ($(ts))"
  for try in "$label" "$label-retry"; do
    if [ "$arm" = direct ]; then
      MODE=direct URL=http://$dep:8000 DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=n$srv \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && { echo "=== $dep done c=$c ($(ts))"; return 0; }
    else
      MODE=pool URL=http://agentx-epp-n$srv-epp:80 EPP_DEPLOY=agentx-epp-n$srv-epp DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=n$srv \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && { echo "=== $dep done c=$c ($(ts))"; return 0; }
    fi
    echo "=== $try/c$c on $dep failed; $( [ "$try" = "$label" ] && echo retrying || echo giving up ) ($(ts))"
    kc delete job "agentx-c$c-$try" --ignore-not-found > /dev/null 2>&1
  done
  return 1
}

node_queue() {  # node_queue <direct letter> <thunder letter> <c1> [c2 ...]
  local d=$1 t=$2 c rc=0 pd pt; shift 2
  for c in "$@"; do
    if [ "$SMOKE" = 1 ]; then c=4; else set_seqs "$d" $((2 * c)); set_seqs "$t" $((2 * c)); fi
    kc rollout status "deploy/qwen35-nooff-$d" --timeout=90m > /dev/null || return 1
    kc rollout status "deploy/qwen35-nooff-$t" --timeout=90m > /dev/null || return 1
    refresh_epp "$t" || return 1
    point "$d" direct "$c" & pd=$!; sleep 5
    point "$t" thunder "$c" & pt=$!
    wait $pd || rc=1; wait $pt || rc=1
    [ "$SMOKE" = 1 ] && break
  done
  return $rc
}

FAILED=""
NODES=${NODES:-"13z6 gw0s p3mf"}  # subset to (re)run, e.g. NODES="gw0s p3mf"
q1=""; q2=""; q3=""
case " $NODES " in *" 13z6 "*) node_queue a b 96 & q1=$!; sleep 10 ;; esac
case " $NODES " in *" gw0s "*) node_queue c d 48 32 & q2=$!; sleep 10 ;; esac
case " $NODES " in *" p3mf "*) node_queue e f 64 24 & q3=$! ;; esac
[ -z "$q1" ] || wait $q1 || FAILED="$FAILED 13z6"
[ -z "$q2" ] || wait $q2 || FAILED="$FAILED gw0s"
[ -z "$q3" ] || wait $q3 || FAILED="$FAILED p3mf"

if [ "$SMOKE" = 1 ]; then
  "$SCRIPTS/verify-point.sh" "$RESULTS"/qwen35-nooff-*-smoke-?/c4
else
  uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/report-nooff" \
    "$RESULTS"/qwen35-nooff-direct/c* "$RESULTS"/qwen35-nooff-thunder-l10/c*
fi
[ -z "$FAILED" ] || { echo "nodes with a failed point:$FAILED"; exit 1; }
echo "=== all done ($(ts))"
