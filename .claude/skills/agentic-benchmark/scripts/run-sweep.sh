#!/usr/bin/env bash
# Run an AgentX concurrency sweep (one fresh server per point), then build the report.
#
# Usage: RESULTS=<step>/results run-sweep.sh <run-label> <concurrency> [<concurrency> ...]
# Example: RESULTS=$PWD/results run-sweep.sh lane-vllm-20261009 8 16 32 64 128
# MODE, DURATION, EXTRA_ARGS and the other run-point.sh settings pass through.
#   nohup caffeinate -i run-sweep.sh <label> ... > results/<label>.log 2>&1 &
set -uo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
export RESULTS=${RESULTS:-$PWD/results}
LABEL=${1:?usage: run-sweep.sh <run-label> <concurrency>...}
shift
[ $# -gt 0 ] || { echo "give at least one concurrency" >&2; exit 1; }

FAILED=""
for c in "$@"; do
  echo "=== $LABEL: concurrency $c ($(date -u +%H:%M:%S))"
  if ! "$SCRIPTS/run-point.sh" "$c" "$LABEL"; then
    FAILED="$FAILED $c"
    echo "=== concurrency $c did not succeed or is invalid; artifacts kept, continuing"
  fi
done

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/$LABEL/report" "$RESULTS/$LABEL"/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
