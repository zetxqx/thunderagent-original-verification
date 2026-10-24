#!/usr/bin/env bash
# Step 37: after the c=96 point (the first run-baseline.sh, PID given as $1) finishes, run the other
# 2P1D concurrencies on the same servers: c=144 first (the high-load question), then 64, 48, 32.
# No smoke (same servers and proxy as the c=96 run). Then analyze all 2P1D points together.
#   setsid nohup ./run-more.sh <pid of the running run-baseline.sh> > results/run-more.log 2>&1 < /dev/null &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
export PATH="$HOME/.local/bin:$PATH"
WAIT_PID=${1:-}
if [ -n "$WAIT_PID" ]; then
  echo "=== waiting for PID $WAIT_PID (the c=96 run) ($(date -u +%H:%M:%S))"
  while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 60; done
fi
echo "=== starting c=144 64 48 32 ($(date -u +%H:%M:%S))"
SMOKE=0 CONCS="144 64 48 32" "$HERE/run-baseline.sh"
echo "=== analyze all 2P1D points ($(date -u +%H:%M:%S))"
pts=(); for c in 32 48 64 96 144; do for d in "$HERE"/results/glm52-2p1d-baseline/c$c "$HERE"/results/glm52-2p1d-baseline-retry/c$c; do [ -d "$d" ] && pts+=("$d"); done; done
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$HERE/results/glm52-2p1d-baseline/report" "${pts[@]}"
echo "=== all done ($(date -u +%H:%M:%S))"
