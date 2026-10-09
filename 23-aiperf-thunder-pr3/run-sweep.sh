#!/usr/bin/env bash
# Run an AgentX concurrency sweep (one fresh server per point), then build the report.
#
# Usage: ./run-sweep.sh <run-label> <concurrency> [<concurrency> ...]
# Example: ./run-sweep.sh lane-vllm-20261009 2 4 8 16 32 64
# MODE, DURATION, EXTRA_ARGS and the other run-point.sh settings pass through.
#   nohup caffeinate -i ./run-sweep.sh <label> ... > results/<label>.log 2>&1 &
set -uo pipefail

STEP23="$(cd "$(dirname "$0")" && pwd)"
LABEL=${1:?usage: run-sweep.sh <run-label> <concurrency>...}
shift
[ $# -gt 0 ] || { echo "give at least one concurrency" >&2; exit 1; }

FAILED=""
for c in "$@"; do
  echo "=== $LABEL: concurrency $c ($(date -u +%H:%M:%S))"
  if ! "$STEP23/run-point.sh" "$c" "$LABEL"; then
    FAILED="$FAILED $c"
    echo "=== concurrency $c did not succeed or is invalid; artifacts kept, continuing"
  fi
done

uv run "$STEP23/analyze.py" --out "$STEP23/results/$LABEL/report" "$STEP23/results/$LABEL"/c*
[ -z "$FAILED" ] || { echo "points that did not succeed or are invalid:$FAILED"; exit 1; }
