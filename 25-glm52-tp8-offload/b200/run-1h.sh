#!/usr/bin/env bash
# Step 25 exploration, 1-hour points (2026-10-11, user request): thunder-gpu-l10 (GPU
# capacity from vLLM, lease 10 s, backstop 1800 s, image -produces) at c=12, 16, 20,
# 24, 32 and no router at c=20, 24, 32 (c=12 and 16 no router: formal r1 points).
# No server restart: RESET=1 empties both KV tiers (and restarts the EPP) before every
# point; 3600 s; MAX_NUM_SEQS 64 on every server. Four servers, one chain each:
#   A glm52-tp8   (lane a): no router c=24, then no router c=20
#   B glm52-tp8-b (lane b, agentx-epp-a): thunder c=24, then thunder c=20
#   C glm52-tp8-c (lane c, agentx-epp-c): thunder c=32, then thunder c=12
#   D glm52-tp8-d (lane d, agentx-epp-d): no router c=32, then thunder c=16
# C and D start cold; their chains wait until the server is Available. A failed point
# is retried once under <label>-retry. Clients request 4 CPU and 16 GiB (limit 32 GiB)
# so four fit on node pool pool-1.
# Usage: nohup caffeinate -i ./run-1h.sh > results/run-1h.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=16Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
DIRECT=explore1h-direct THUNDER=explore1h-thunder-gpu-l10

point() {  # point <server a|b|c|d> <direct|thunder> <concurrency>; one retry
  local srv=$1 arm=$2 c=$3 dep=glm52-tp8 label try
  [ "$srv" = a ] || dep=glm52-tp8-$srv
  if [ "$arm" = direct ]; then label=$DIRECT; else label=$THUNDER; fi
  local epp=agentx-epp-$srv-epp
  [ "$srv" = b ] && epp=agentx-epp-a-epp
  for try in "$label" "$label-retry"; do
    if [ "$arm" = direct ]; then
      MODE=direct URL=http://$dep:8000 DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$srv \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    else
      MODE=pool URL=http://$epp:80 EPP_DEPLOY=$epp DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$srv \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    fi
    echo "=== $try/c$c on $srv failed; $( [ "$try" = "$label" ] && echo retrying || echo giving up ) ($(date -u +%H:%M:%S))"
  done
  return 1
}
chain() {  # chain <server> <arm> <conc> <arm> <conc>
  local srv=$1 rc=0
  if [ "$srv" = c ] || [ "$srv" = d ]; then
    KUBECONFIG=$KUBECONFIG_SOURCE kubectl wait --for=condition=Available deploy/glm52-tp8-$srv -n "$NS" --timeout=90m || return 1
    echo "=== server $srv available ($(date -u +%H:%M:%S))"
  fi
  echo "=== $srv: $2 c=$3 ($(date -u +%H:%M:%S))"; point "$srv" "$2" "$3" || rc=1
  echo "=== $srv: $4 c=$5 ($(date -u +%H:%M:%S))"; point "$srv" "$4" "$5" || rc=1
  echo "=== $srv done ($(date -u +%H:%M:%S))"
  return $rc
}

FAILED=""
chain a direct 24 direct 20 & pa=$!
sleep 5
chain b thunder 24 thunder 20 & pb=$!
sleep 5
chain c thunder 32 thunder 12 & pc=$!
sleep 5
chain d direct 32 thunder 16 & pd=$!
wait $pa || FAILED="$FAILED A"
wait $pb || FAILED="$FAILED B"
wait $pc || FAILED="$FAILED C"
wait $pd || FAILED="$FAILED D"

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore1h/report" "$RESULTS"/explore1h-*/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "chains with a failed point:$FAILED"; exit 1; }
