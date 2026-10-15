#!/usr/bin/env bash
# Step 27: c=24 and c=48 on the three DEP=8 servers (user request, 2026-10-15), after the c=32 and c=64
# points. Each chain waits until its server has finished: a and c when run-dep8.sh logs "=== <srv> done",
# b when run-dep8-b32.sh has finished its c=32 point. Same settings and labels as run-dep8.sh.
# Usage: nohup caffeinate -i ./run-dep8-more.sh > results/run-dep8-more.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
export RESULTS="$HERE/results" CTX=gke_supercomputer-testing_europe-west4_a4-pr KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=16Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
RANK_PORTS="8000 8001 8002 8003 8004 8005 8006 8007"

point() {  # point <server a|b|c> <concurrency>; one retry
  local srv=$1 c=$2 dep=glm52-dep8-$1 label try
  case $srv in a) label=dep8-direct ;; b) label=dep8-affinity ;; c) label=dep8-thunder-l10 ;; esac
  for try in "$label" "$label-retry"; do
    if [ "$srv" = a ]; then
      MODE=direct URL=http://$dep:8000 DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$srv \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    else
      local epp=agentx-epp-g$srv-epp
      MODE=pool URL=http://$epp:80 EPP_DEPLOY=$epp DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=g$srv \
        VLLM_PORTS="$RANK_PORTS" "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    fi
    echo "=== $try/c$c on $srv failed; $( [ "$try" = "$label" ] && echo retrying || echo giving up ) ($(date -u +%H:%M:%S))"
  done
  return 1
}
chain() {  # chain <server> <log> <pattern>: wait for the pattern in the log, then c=24 and c=48
  local srv=$1 rc=0 c
  until grep -qE "$3" "$RESULTS/$2" 2>/dev/null; do sleep 60; done
  for c in 24 48; do
    echo "=== $srv: c=$c ($(date -u +%H:%M:%S))"; point "$srv" "$c" || rc=1
  done
  echo "=== $srv done ($(date -u +%H:%M:%S))"
  return $rc
}

chain a run-dep8.log "=== a done" & pa=$!
chain b run-dep8-b32.log "r2/c32 done|r3/c32 (done|failed)" & pb=$!
chain c run-dep8.log "=== c done" & pc=$!
rc=0; wait $pa || rc=1; wait $pb || rc=1; wait $pc || rc=1
exit $rc
