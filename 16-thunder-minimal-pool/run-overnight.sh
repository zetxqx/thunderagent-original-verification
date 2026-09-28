#!/usr/bin/env bash
# Step 16 overnight run, unattended:
#   1. thunder-min-hl10-s1 (half-life 10 s, pause sweep 1 s), c=128, 30 min, three cells
#   2. thunder-min (half-life 1 s, sweep 5 s), c=128, one 90-minute cell (-w90), against step 13's w90 cells
# then the main EPP release is restored to its state before the run and both analyses run.
# kubectl and helm use a kubeconfig pinned to the bobbm context, so a context
# switch in another terminal cannot redirect the run. Run under caffeinate.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
POOL="$HERE/../12-llm-d-router-pool/run-pool.sh"
CTX=gke_bobzetian-gke-dev_us-central1_bobbm
KCFG="$HERE/results/bobbm.kubeconfig"
kubectl config view --minify --context="$CTX" --flatten > "$KCFG" && chmod 600 "$KCFG"
export KUBECONFIG="$KCFG"
[ "$(kubectl config current-context)" = "$CTX" ] || { echo "FATAL: kubeconfig is not pinned to $CTX" >&2; exit 1; }
export AB_ID="${AB_ID:-rep-20260927-195200-c128-t1900}" OUT_BASE="$HERE/results" SKIP_ANALYSIS=1 EPP_IMAGE_TAG=thunder-agent-min-33dde5d2
SAVED="$HERE/results/main-release-now.yaml"
helm get manifest program-aware-scheduling -n llm-d-program-aware-scheduling > "$SAVED"
echo "overnight start $(date)  run $AB_ID  context $(kubectl config current-context)"
for R in 1 2 3; do
  TAG="c128"; [ "$R" -gt 1 ] && TAG="c128-r$R"
  echo "===== thunder-min-hl10-s1 $TAG ====="
  CELL_TAG="$TAG" "$POOL" 128 1 1800 thunder-min-hl10-s1 1900 || echo "WARNING: thunder-min-hl10-s1 $TAG failed"
done
echo "===== thunder-min c128-w90 ====="
CELL_TAG="c128-w90" "$POOL" 128 1 5400 thunder-min 1900 || echo "WARNING: thunder-min c128-w90 failed"
echo "===== restore the main release to its state before this run ====="
"$HERE/restore-main-release.sh" "$SAVED" || echo "WARNING: main release NOT restored; see restore-main-release.sh"
echo "===== analysis ====="
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze.py" "$OUT_BASE/$AB_ID" > /dev/null || true
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze_long.py" "$OUT_BASE/$AB_ID" > /dev/null || true
rm -f "$KCFG"
echo "overnight done $(date)  artifacts: $OUT_BASE/$AB_ID"
