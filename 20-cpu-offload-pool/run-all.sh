#!/usr/bin/env bash
# Step 20 driver, unattended, in order (offloading first, as asked on 2026-09-30):
#   1. save the original vLLM deployment and main EPP release (refuses if GPU
#      pods are pending or the deployment is not the manifests' base). Skipped
#      when results/ already holds a saved original: re-saving after a switch
#      would overwrite the original with a step 20 state.
#   2. 3 replicas with the 400 GiB CPU tier, lanes, smoke test; if any smoke
#      check fails, stop (and restore)
#   3. phase B (about 4.3 h)
#   4. 3 replicas without offloading, lanes, phase A (about 2.6 h)
#   5. remove the lanes, restore the vLLM deployment, check the main release,
#      run the analysis
# The restore runs on every exit path, so a failure does not leave the model
# server at 3 replicas. Run under caffeinate, with nohup:
#   nohup caffeinate -i ./run-all.sh > results/driver.log 2>&1 &
set -uo pipefail
source "$(dirname "$0")/lib.sh"
pin_kube
echo "step 20 start $(date)  EPP $EPP_IMAGE_TAG  bench $BENCH_IMAGE  context $(kubectl config current-context)"

RESTORED=0
restore_all() {
  [ "$RESTORED" = 0 ] || return 0; RESTORED=1
  echo; echo "##### teardown and restore ($(date))"
  "$STEP20/lanes.sh" teardown || echo "WARNING: lane teardown failed"
  if [ -f "$RESULTS/vllm-deploy-before-clean.json" ]; then
    "$STEP20/offload.sh" restore || echo "WARNING: vLLM deployment NOT restored; apply results/vllm-deploy-before-clean.json by hand"
  fi
  if [ -f "$RESULTS/main-release-before.yaml" ]; then
    "$STEP20/../16-thunder-minimal-pool/restore-main-release.sh" "$RESULTS/main-release-before.yaml" || echo "WARNING: main release differs from main-release-before.yaml"
  fi
}
trap restore_all EXIT

echo; echo "##### 1. save ($(date))"
if [ -f "$RESULTS/vllm-deploy-before-clean.json" ] && [ -f "$RESULTS/main-release-before.yaml" ]; then
  echo "original already saved ($(ls -l "$RESULTS/vllm-deploy-before-clean.json" | awk '{print $6, $7, $8}')); keeping it"
else
  "$STEP20/offload.sh" save-before || { echo "FATAL: save-before failed; nothing was changed"; RESTORED=1; exit 1; }
fi

echo; echo "##### 2. offloading on, smoke test ($(date))"
"$STEP20/offload.sh" on || exit 1
"$STEP20/smoke-test.sh"; SMOKE=$?
if [ "$SMOKE" != 0 ]; then
  echo "FATAL: $SMOKE smoke check(s) failed; phase B skipped (results/smoke-test-output.txt)"; exit 1
fi

echo; echo "##### 3. phase B: offloading 400 GiB ($(date))"
"$STEP20/run-cells.sh" B || echo "WARNING: phase B had a failed lane"

echo; echo "##### 4. phase A: offloading off ($(date))"
"$STEP20/offload.sh" off || exit 1
"$STEP20/lanes.sh" deploy || exit 1
"$STEP20/run-cells.sh" A || echo "WARNING: phase A had a failed lane"

restore_all
echo; echo "##### 5. analysis ($(date))"
uv run --quiet --with matplotlib --with numpy python "$STEP20/analyze.py" > /dev/null || echo "WARNING: analysis failed"
rm -f "$RESULTS/bobbm.kubeconfig"
echo "step 20 done $(date)"
