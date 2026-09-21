#!/usr/bin/env bash
# Step 13 Option B experiment: origin-only plus the urgent tier (urgentWaitMs 15 s),
# with and without the forced-admission backstop lowered to 25 s, at c=128:
# two 30-minute cells per arm (comparable with the most-room and origin-only
# replicates) and one 90-minute cell per arm (the deep-session regime where the
# origin-only tail was longest). thunder-agent-v5, session-id bench image.
# Usage: AB_ID=<existing sweep run id> ./run-optionb.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
POOL="$HERE/../12-llm-d-router-pool/run-pool.sh"
: "${AB_ID:?set AB_ID to the sweep run id to append to}"
export AB_ID OUT_BASE="$HERE/results" SKIP_ANALYSIS=1 EPP_IMAGE_TAG=thunder-agent-v5
PLAN="thunder-origin-u15:1800:c128-r2 thunder-origin-u15-f25:1800:c128-r2 thunder-origin-u15-f25:1800:c128-r3 thunder-origin-u15:1800:c128-r3 thunder-origin-u15:5400:c128-w90 thunder-origin-u15-f25:5400:c128-w90"
echo "option B run id: $AB_ID  image: $EPP_IMAGE_TAG  bench: $(cat "$HERE/../12-llm-d-router-pool/results/inference-perf-image.txt")"
for item in $PLAN; do
  IFS=: read -r ARM WINDOW TAG <<< "$item"
  echo "===== option B: $ARM window=${WINDOW}s tag=$TAG ====="
  CELL_TAG="$TAG" "$POOL" 128 1 "$WINDOW" "$ARM" 1900 || echo "WARNING: $ARM $TAG failed"
done
echo "===== analysis ====="
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze_replicates.py" "$OUT_BASE/$AB_ID" || true
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze_long.py" "$OUT_BASE/$AB_ID" || true
echo "artifacts: $OUT_BASE/$AB_ID"
