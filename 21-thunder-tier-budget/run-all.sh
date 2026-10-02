#!/usr/bin/env bash
# Step 21 driver, unattended: the three tier budget arms in parallel on the
# step 20 phase B setup (3 single replicas, 400 GiB CPU tier), using step 20's
# scripts with this step's results folder and image.
#   1. refuse unless the model server is the saved original and no GPU pod is
#      pending (the saved original is step 20's, copied here)
#   2. offloading on, lanes, smoke test; stop if a check fails
#   3. phase T, one run per replicate given (default: replicate 1 only)
#   4. remove the lanes, restore the model server, check the main release, analysis
# The restore runs on every exit path.
#   nohup caffeinate -i ./run-all.sh > results/driver.log 2>&1 &
# Usage: run-all.sh [replicate ...]
set -uo pipefail
STEP21="$(cd "$(dirname "$0")" && pwd)"
export STEP_RESULTS="$STEP21/results"
export EPP_IMAGE_TAG="${EPP_IMAGE_TAG:-thunder-agent-lease-tier-a13a87ed}"
source "$STEP21/../20-cpu-offload-pool/lib.sh"
pin_kube
REPS="${*:-1}"
echo "step 21 replicates $REPS start $(date)  EPP $EPP_IMAGE_TAG  context $(kubectl config current-context)"

echo; echo "##### 1. checks ($(date))"
for f in vllm-deploy-before.json vllm-deploy-before-clean.json vllm-deploy-before.yaml main-release-before.yaml; do
  [ -f "$RESULTS/$f" ] || cp "$STEP20/results/$f" "$RESULTS/$f"
done
"$STEP20/offload.sh" check-original || { echo "FATAL: the model server is not the saved original; nothing was changed"; exit 1; }
PENDING=$(kubectl get pods -A --field-selector=status.phase=Pending -o json | python3 -c '
import json, sys
print(" ".join(p["metadata"]["namespace"] + "/" + p["metadata"]["name"] for p in json.load(sys.stdin)["items"]
  if any("nvidia.com/gpu" in (c.get("resources", {}).get("requests") or {}) for c in p["spec"]["containers"])))')
[ -z "$PENDING" ] || { echo "FATAL: GPU pods are pending: $PENDING; nothing was changed"; exit 1; }

RESTORED=0
restore_all() {
  [ "$RESTORED" = 0 ] || return 0; RESTORED=1
  echo; echo "##### teardown and restore ($(date))"
  "$STEP20/lanes.sh" teardown || echo "WARNING: lane teardown failed"
  "$STEP20/offload.sh" restore || echo "WARNING: vLLM deployment NOT restored; apply results/vllm-deploy-before-clean.json by hand"
  "$STEP20/../16-thunder-minimal-pool/restore-main-release.sh" "$RESULTS/main-release-before.yaml" || echo "WARNING: main release differs from main-release-before.yaml"
}
trap restore_all EXIT

echo; echo "##### 2. offloading on, smoke test ($(date))"
"$STEP20/offload.sh" on || exit 1
SMOKE_LANE_ARMS="a:thunder-lease-budget30 b:thunder-lease-budget5 c:thunder-lease-main5" "$STEP20/smoke-test.sh"; SMOKE=$?
[ "$SMOKE" = 0 ] || { echo "FATAL: $SMOKE smoke check(s) failed; runs skipped (results/smoke-test-output.txt)"; exit 1; }

for R in $REPS; do
  echo; echo "##### 3. phase T replicate $R ($(date))"
  REP="$R" "$STEP20/run-cells.sh" T || echo "WARNING: phase T replicate $R had a failed lane"
done

restore_all
echo; echo "##### 4. analysis ($(date))"
uv run --quiet --with matplotlib --with numpy python "$STEP20/analyze.py" > /dev/null || echo "WARNING: analysis failed"
rm -f "$RESULTS/bobbm.kubeconfig"
echo "step 21 done $(date)"
