#!/usr/bin/env bash
# Step 13 extension: the epp-thunder-origin arm (resumePlacement: origin-only,
# thunder-agent-v4) at the levels where the port pauses and resumes programs,
# appended to the existing sweep run directory, plus one same-day control cell
# (epp-thunder at c=192 on v4, cell tag c192-v4ctl) to check that today's
# cluster matches yesterday's thunder-c192 (1342 tok/s, hit 0.301).
# Usage: AB_ID=<existing run id> ./run-origin.sh [levels]   default levels "96 128 192 256 338"
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
POOL="$HERE/../12-llm-d-router-pool/run-pool.sh"
: "${AB_ID:?set AB_ID to the sweep run id to append to}"
LEVELS="${1:-96 128 192 256 338}"
export AB_ID OUT_BASE="$HERE/results" SKIP_ANALYSIS=1 EPP_IMAGE_TAG=thunder-agent-v4
echo "origin arm run id: $AB_ID  levels: $LEVELS  image: $EPP_IMAGE_TAG"
for C in $LEVELS; do
  if [ "$C" = 192 ]; then
    echo "===== control: thunder (most-room) on v4 at c=192 ====="
    CELL_TAG="c192-v4ctl" "$POOL" 192 1 1800 thunder 1900 || echo "WARNING: control cell failed"
  fi
  echo "===== level c=$C (thunder-origin) ====="
  CELL_TAG="c$C" "$POOL" "$C" 1 1800 thunder-origin 1900 || echo "WARNING: level c=$C had a failed cell"
done
echo "===== analysis ====="
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze_sweep.py" "$OUT_BASE/$AB_ID" || true
echo "artifacts: $OUT_BASE/$AB_ID"
