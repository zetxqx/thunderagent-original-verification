#!/usr/bin/env bash
# Tail of run-1h-l30-nooff.sh, rebalanced (2026-10-12): without offload the warmup of a
# no-router point takes about 50 min instead of 10, so chain A (c=24, 32, 16 in a row)
# was stopped after c=24 and its last two points split:
#   A: no router c=32 once the c=24 point (pid in $1) exits
#   B: no router c=16 once chain B of run-1h-l30-nooff.sh is done (B is already
#      without offload)
# Incident: run-1h-l30-nooff.sh ends with `rm -f results/bobbm.kubeconfig`, which this
# script's run-point.sh calls still used; they waited 11 h on "kubectl cannot reach the
# cluster" until the file was recreated (lib.sh pin_kube), then fetched normally.
# Usage: nohup caffeinate -i ./run-1h-nooff-tail.sh <pid> > results/run-1h-nooff-tail.log 2>&1 &
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
LABEL=explore1h-direct-nooff

point() {  # point <server> <concurrency>; no router, one retry
  local srv=$1 c=$2 dep=glm52-tp8 try
  [ "$srv" = a ] || dep=glm52-tp8-$srv
  echo "=== $srv: $LABEL c=$c ($(date -u +%H:%M:%S))"
  for try in "$LABEL" "$LABEL-retry"; do
    MODE=direct URL=http://$dep:8000 DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$srv \
      "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    echo "=== $try/c$c on $srv failed ($(date -u +%H:%M:%S))"
  done
  return 1
}

FAILED=""
( while kill -0 "$1" 2>/dev/null; do sleep 30; done; point a 32 ) & pa=$!
( until grep -q "^=== b done" "$RESULTS/run-1h-l30-nooff.log"; do sleep 30; done; point b 16 ) & pb=$!
wait $pa || FAILED="$FAILED A"
wait $pb || FAILED="$FAILED B"
echo "=== tail done ($(date -u +%H:%M:%S))"
[ -z "$FAILED" ] || { echo "failed:$FAILED"; exit 1; }
