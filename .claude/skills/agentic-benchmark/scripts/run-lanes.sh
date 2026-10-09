#!/usr/bin/env bash
# Run concurrency points in parallel, one lane (vLLM pod) each, then build the report.
# Every lane takes the next concurrency from a shared queue when its point ends, so
# more points than pods still keep every pod busy. Give the largest concurrency
# first: its warmup is the longest.
#
# Usage: RESULTS=<step>/results [LANES="a b c d"] [LANE_EPP=1] run-lanes.sh <label> <conc>...
# Other run-point.sh settings (DURATION, RESTART, EXTRA_ARGS, ...) pass through.
#   nohup caffeinate -i run-lanes.sh <label> 32 24 20 16 12 > results/<label>.log 2>&1 &
# Per point log: $RESULTS/<label>-<lane>-c<N>.log
set -uo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
export RESULTS=${RESULTS:-$PWD/results}
LABEL=${1:?usage: run-lanes.sh <label> <concurrency>...}
shift
[ $# -gt 0 ] || { echo "give at least one concurrency" >&2; exit 1; }
LANES=${LANES:-a b c d}
mkdir -p "$RESULTS"

QUEUE=$(mktemp -d)
trap 'rm -rf "$QUEUE"' EXIT
i=0
for c in "$@"; do echo "$c" > "$QUEUE/$(printf %03d $i)"; i=$((i + 1)); done

# next <lane>: take the first queued concurrency; mv is atomic, so two lanes never get the same one.
next() {
  local f
  for f in "$QUEUE"/[0-9][0-9][0-9]; do
    [ -e "$f" ] || return 1
    mv "$f" "$f.$1" 2>/dev/null && { cat "$f.$1"; return 0; }
  done
  return 1
}

worker() {
  local lane=$1 c
  while c=$(next "$lane"); do
    echo "=== $LABEL lane $lane: c$c start ($(date -u +%H:%M:%S))"
    if LANE=$lane MODE=lane "$SCRIPTS/run-point.sh" "$c" "$LABEL" > "$RESULTS/$LABEL-$lane-c$c.log" 2>&1; then
      echo "=== $LABEL lane $lane: c$c done ($(date -u +%H:%M:%S))"
    else
      echo "=== $LABEL lane $lane: c$c did not succeed or is invalid ($(date -u +%H:%M:%S)); see $LABEL-$lane-c$c.log"
    fi
  done
}

for lane in $LANES; do
  worker "$lane" &
  sleep 5   # claims are atomic anyway; spacing keeps the logs readable
done
wait

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/$LABEL/report" "$RESULTS/$LABEL"/c*
echo "=== $LABEL all points done ($(date -u +%H:%M:%S))"
