#!/usr/bin/env bash
# Step 18 driver, unattended, in order:
#   1. single vLLM pod (lane a, one EPP pinned to one pod), c=32, 30 min:
#      thunder-lease-main (lease 30 s), then thunder-lease-main10 (lease 10 s)
#   2. remove the lane
#   3. 4-pod pool through the main EPP release, c=128, 30 min:
#      thunder-lease-main10, then thunder-lease-main (reverse order to the lane)
#   4. restore the main release to results/main-release-before.yaml, analysis
# c=32 on one pod is the pool's per-pod load at c=128. Both setups use the
# fixed load generator (session-id image) and a 1900 s client timeout.
# kubectl and helm use a kubeconfig pinned to the bobbm context. Run under
# caffeinate, with nohup.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
STEP10="$HERE/../10-llm-d-router-replicates"
POOL="$HERE/../12-llm-d-router-pool/run-pool.sh"
CTX=gke_bobzetian-gke-dev_us-central1_bobbm
KCFG="$HERE/results/bobbm.kubeconfig"
kubectl config view --minify --context="$CTX" --flatten > "$KCFG" && chmod 600 "$KCFG"
export KUBECONFIG="$KCFG"
[ "$(kubectl config current-context)" = "$CTX" ] || { echo "FATAL: kubeconfig is not pinned to $CTX" >&2; exit 1; }
IMAGE="${EPP_IMAGE_TAG:-thunder-agent-lease-1a98a6c5}"
BENCH="$(cat "$HERE/../12-llm-d-router-pool/results/inference-perf-image.txt")"
echo "step 18 start $(date)  image $IMAGE  bench $BENCH  context $(kubectl config current-context)"

echo "===== single pod: lane a, c=32 ====="
"$HERE/deploy-lane.sh" thunder-lease-main "$IMAGE" || { echo "FATAL: lane deploy failed" >&2; exit 1; }
RESULTS_DIR="$HERE/results" EPP_IMAGE_TAG="$IMAGE" BENCH_IMAGE="$BENCH" \
  "$STEP10/run-replicates.sh" 32 1 1800 thunder-lease-main,thunder-lease-main10 1900 || echo "WARNING: single-pod run failed"
"$HERE/teardown-lane.sh"

echo "===== pool: 4 pods, c=128 ====="
export AB_ID="rep-$(date +%Y%m%d-%H%M%S)-c128-t1900" OUT_BASE="$HERE/results" SKIP_ANALYSIS=1 EPP_IMAGE_TAG="$IMAGE"
for ARM in thunder-lease-main10 thunder-lease-main; do
  echo "===== $ARM c128 ====="
  CELL_TAG=c128 "$POOL" 128 1 1800 "$ARM" 1900 || echo "WARNING: $ARM c128 failed"
done

echo "===== restore the main release to its state before step 18 ====="
"$HERE/../16-thunder-minimal-pool/restore-main-release.sh" "$HERE/results/main-release-before.yaml" || echo "WARNING: main release NOT restored; see restore-main-release.sh"
echo "===== analysis ====="
uv run --quiet --with matplotlib --with numpy python "$HERE/analyze.py" > /dev/null || echo "WARNING: analysis failed"
rm -f "$KCFG"
echo "step 18 done $(date)"
