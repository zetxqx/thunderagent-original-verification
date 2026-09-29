#!/usr/bin/env bash
# Step 19 driver: runs the given cells in order with step 12's run-pool.sh
# (c=128, 30 min, client timeout 1900 s), all into one run directory, then
# restores the main EPP release to results/main-release-before.yaml and runs
# the analysis. kubectl and helm use a kubeconfig pinned to the bobbm context,
# so a context switch in another terminal cannot redirect the run. Run under
# caffeinate, with nohup.
# Usage: run-cells.sh <arm:cell-tag> ...   e.g. thunder-lease-main:c128
#   env AB_ID appends to an existing run directory.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
POOL="$HERE/../12-llm-d-router-pool/run-pool.sh"
CTX=gke_bobzetian-gke-dev_us-central1_bobbm
KCFG="$HERE/results/bobbm.kubeconfig"
kubectl config view --minify --context="$CTX" --flatten > "$KCFG" && chmod 600 "$KCFG"
export KUBECONFIG="$KCFG"
[ "$(kubectl config current-context)" = "$CTX" ] || { echo "FATAL: kubeconfig is not pinned to $CTX" >&2; exit 1; }
export AB_ID="${AB_ID:-rep-$(date +%Y%m%d-%H%M%S)-c128-t1900}" OUT_BASE="$HERE/results" SKIP_ANALYSIS=1
export EPP_IMAGE_TAG="${EPP_IMAGE_TAG:-thunder-agent-lease-44544c04}"
echo "step 19 start $(date)  run $AB_ID  image $EPP_IMAGE_TAG  context $(kubectl config current-context)  cells $*"
for SPEC in "$@"; do
  ARM="${SPEC%%:*}" TAG="${SPEC#*:}"
  echo "===== $ARM $TAG ====="
  CELL_TAG="$TAG" "$POOL" 128 1 1800 "$ARM" 1900 || echo "WARNING: $ARM $TAG failed"
done
echo "===== restore the main release to its state before step 19 ====="
"$HERE/../16-thunder-minimal-pool/restore-main-release.sh" "$HERE/results/main-release-before.yaml" || echo "WARNING: main release NOT restored; see restore-main-release.sh"
echo "===== analysis ====="
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze.py" "$OUT_BASE/$AB_ID" > /dev/null || echo "WARNING: analysis failed"
rm -f "$KCFG"
echo "step 19 done $(date)  artifacts: $OUT_BASE/$AB_ID"
