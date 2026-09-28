#!/usr/bin/env bash
# Step 16 replicates: two more cells per arm (thunder-min, thunder-min-hl10) at
# c=128, so each arm has three cells like step 13's origin-only reference. The
# first cell of each arm is the one already in the run (epp-<arm>-c128); these
# are epp-<arm>-c128-r2 and -r3, in ABBA order to spread drift over both arms.
# The main EPP release is switched per cell by run-pool.sh and restored at the
# end to the manifest saved at the start (restore-main-release.sh).
# Usage: ./run-replicates.sh    (appends to AB_ID, default the step 16 run)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
POOL="$HERE/../12-llm-d-router-pool/run-pool.sh"
export AB_ID="${AB_ID:-rep-20260927-195200-c128-t1900}" OUT_BASE="$HERE/results" SKIP_ANALYSIS=1 EPP_IMAGE_TAG=thunder-agent-min-33dde5d2
SAVED="$HERE/results/main-release-now.yaml"
helm get manifest program-aware-scheduling -n llm-d-program-aware-scheduling > "$SAVED"
PLAN="thunder-min:2 thunder-min-hl10:2 thunder-min-hl10:3 thunder-min:3"
for item in $PLAN; do
  IFS=: read -r ARM R <<< "$item"
  echo "===== replicate: $ARM r$R ====="
  CELL_TAG="c128-r$R" "$POOL" 128 1 1800 "$ARM" 1900 || echo "WARNING: $ARM r$R failed"
done
echo "===== restore the main release to its state before this run ====="
"$HERE/restore-main-release.sh" "$SAVED" || echo "WARNING: main release NOT restored; see restore-main-release.sh"
echo "===== analysis ====="
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze.py" "$OUT_BASE/$AB_ID" || true
echo "artifacts: $OUT_BASE/$AB_ID"
