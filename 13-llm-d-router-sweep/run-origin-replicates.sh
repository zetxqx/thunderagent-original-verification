#!/usr/bin/env bash
# Step 13 replicates: two more cells per arm (thunder = most-room, thunder-origin)
# at c=96 and c=128, so that with the sweep's own cell as replicate 1 each arm has
# three replicates at both levels. Both arms run thunder-agent-v4 (identical to
# v3 under most-room, shown by the v4 control cell) and the session-id bench
# image, so these cells also support the session-level metrics of proposal
# Part 7. Cells are named epp-<arm>-c<C>-r<N>; analyze_sweep.py ignores them
# (its level regex needs the name to end in -c<C>), analyze_replicates.py reads them.
# Order alternates arm and level so neither arm always follows the other.
# Usage: AB_ID=<existing sweep run id> ./run-origin-replicates.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
POOL="$HERE/../12-llm-d-router-pool/run-pool.sh"
: "${AB_ID:?set AB_ID to the sweep run id to append to}"
export AB_ID OUT_BASE="$HERE/results" SKIP_ANALYSIS=1 EPP_IMAGE_TAG=thunder-agent-v4
PLAN="thunder-origin:96:2 thunder:96:2 thunder:128:2 thunder-origin:128:2 thunder:96:3 thunder-origin:96:3 thunder-origin:128:3 thunder:128:3"
echo "replicates run id: $AB_ID  image: $EPP_IMAGE_TAG  bench: $(cat "$HERE/../12-llm-d-router-pool/results/inference-perf-image.txt")"
for item in $PLAN; do
  IFS=: read -r ARM C R <<< "$item"
  echo "===== replicate: $ARM c=$C r$R ====="
  CELL_TAG="c$C-r$R" "$POOL" "$C" 1 1800 "$ARM" 1900 || echo "WARNING: $ARM c=$C r$R failed"
done
echo "===== analysis ====="
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze_replicates.py" "$OUT_BASE/$AB_ID" || true
echo "artifacts: $OUT_BASE/$AB_ID"
