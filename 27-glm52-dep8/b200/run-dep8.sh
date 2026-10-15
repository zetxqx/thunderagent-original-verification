#!/usr/bin/env bash
# Step 27: GLM-5.2 with DEP=8 (README.md). Three servers at once, c=32 then c=64 on each, 3600 s,
# no restart: RESET=1 empties both KV tiers of every rank (and restarts the EPP) before each point.
# Client settings as step 25's run-1h.sh, so the points compare with its TP=8 points.
#   A glm52-dep8-a: no router, vLLM's internal DP load balancer      -> label dep8-direct
#   B glm52-dep8-b: EPP agentx-epp-gb (session affinity), 8 ports    -> label dep8-affinity
#   C glm52-dep8-c: EPP agentx-epp-gc (thunder, lease 10 s), 8 ports -> label dep8-thunder-l10
# Each chain waits until its server is Available. A failed point is retried once under <label>-retry.
# Usage: nohup caffeinate -i ./run-dep8.sh > results/run-dep8.log 2>&1 &
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
RANK_PORTS="8000 8001 8002 8003 8004 8005 8006 8007"
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }

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
chain() {  # chain <server>: c=32, then c=64
  local srv=$1 rc=0 c
  k wait --for=condition=Available "deploy/glm52-dep8-$srv" --timeout=90m || return 1
  if [ "$srv" != a ]; then
    k apply -f "$HERE/lane-epp-g$srv.yaml" >/dev/null && k rollout status "deploy/agentx-epp-g$srv-epp" --timeout=10m >/dev/null || return 1
  fi
  echo "=== server $srv available ($(date -u +%H:%M:%S))"
  for c in 32 64; do
    echo "=== $srv: c=$c ($(date -u +%H:%M:%S))"; point "$srv" "$c" || rc=1
  done
  echo "=== $srv done ($(date -u +%H:%M:%S))"
  return $rc
}

mkdir -p "$RESULTS"
chain a & pa=$!
sleep 5
chain b & pb=$!
sleep 5
chain c & pc=$!
rc=0; wait $pa || rc=1; wait $pb || rc=1; wait $pc || rc=1
exit $rc
