#!/usr/bin/env bash
# Step 13: concurrency sweep on the 4-pod pool, two arms (epp-baseline vs
# epp-thunder). Each level is one cell per arm through step 12's driver; the
# arm order alternates per level to cancel drift. All cells land in one run
# directory; analyze_sweep.py draws the gain-versus-load curves.
# Usage: ./run-sweep.sh [levels] [window_s]   defaults: "48 96 128 192 256 338" 1800
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
POOL="$HERE/../12-llm-d-router-pool/run-pool.sh"
LEVELS="${1:-48 96 128 192 256 338}"; WINDOW="${2:-1800}"
export AB_ID="sweep-$(date +%Y%m%d-%H%M%S)-t1900" OUT_BASE="$HERE/results" SKIP_ANALYSIS=1
echo "sweep run id: $AB_ID  levels: $LEVELS  window: ${WINDOW}s"
i=0
for C in $LEVELS; do
  ARMS="baseline,thunder"; [ $((i % 2)) -eq 1 ] && ARMS="thunder,baseline"
  echo "===== level c=$C (order $ARMS) ====="
  CELL_TAG="c$C" "$POOL" "$C" 1 "$WINDOW" "$ARMS" 1900 || echo "WARNING: level c=$C had a failed cell"
  i=$((i+1))
done
echo "===== analysis ====="
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze_sweep.py" "$OUT_BASE/$AB_ID" || true
echo "artifacts: $OUT_BASE/$AB_ID"
