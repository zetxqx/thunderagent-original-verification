#!/usr/bin/env bash
# Step 25 B200 grid on cluster a4-pr: a 900 s calibration point at c=1, then
# c=1, 4, 8 at 3600 s, one fresh server per point. --max-num-seqs follows the
# InferenceX recipe's max-running-requests (2x concurrency) and is set in the
# same rollout as the restart (run-point.sh MODE=direct, SERVER_ENV).
#
# Usage: nohup caffeinate -i ./run-grid.sh > results/grid.log 2>&1 &
# FIRST_RESTART=0 skips the restart before the first point when the server
# was just (re)deployed and has served nothing.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd DEPLOY=glm52-tp8 DECODE_SELECTOR=app=glm52-tp8
export MODE=direct URL=http://glm52-tp8:8000
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export EXTRA_ARGS="--tokenizer-trust-remote-code"

FAILED=""
run() {  # run <label> <concurrency> <duration> <restart>
  echo "=== $1: concurrency $2, $3 s ($(date -u +%H:%M:%S))"
  if ! RESTART=$4 DURATION=$3 SERVER_ENV="MAX_NUM_SEQS=$(($2 * 2))" "$SCRIPTS/run-point.sh" "$2" "$1"; then
    FAILED="$FAILED $1/c$2"
    echo "=== $1/c$2 did not succeed or is invalid; artifacts kept, continuing"
  fi
}

run calib 1 900 "${FIRST_RESTART:-1}"
for c in 1 4 8; do
  run r1 "$c" 3600 1
done

for label in calib r1; do
  uv run "$SCRIPTS/analyze.py" --out "$RESULTS/$label/report" "$RESULTS/$label"/c*
done
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
