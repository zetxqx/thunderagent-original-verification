#!/usr/bin/env bash
# Step 20 phase B replicates, unattended (asked on 2026-10-01): phase B again
# as replicates 2 and 3, each moving every arm one lane over, so that with the
# first run every arm has run once on every pod at every concurrency.
#   1. refuse unless the model server is the saved original and no GPU pod is pending
#   2. 3 replicas with the 400 GiB CPU tier, lanes, smoke test; stop if a check fails
#   3. phase B replicate 2, then replicate 3 (about 4 h each)
#   4. remove the lanes, restore the model server, check the main release,
#      run the analysis and the figures
# State and smoke-test files get the suffix "-replicates", so the first run's
# records stay as they are. The restore runs on every exit path.
#   nohup caffeinate -i ./run-replicates-B.sh > results/driver-replicates.log 2>&1 &
# Usage: run-replicates-B.sh [replicate ...]   (default: 2 3)
set -uo pipefail
source "$(dirname "$0")/lib.sh"
pin_kube
REPS="${*:-2 3}"
export STATE_SUFFIX=-replicates SMOKE_SUFFIX=-replicates
echo "step 20 phase B replicates $REPS start $(date)  EPP $EPP_IMAGE_TAG  context $(kubectl config current-context)"

echo; echo "##### 1. checks ($(date))"
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
"$STEP20/smoke-test.sh"; SMOKE=$?
[ "$SMOKE" = 0 ] || { echo "FATAL: $SMOKE smoke check(s) failed; replicates skipped (results/smoke-test-output-replicates.txt)"; exit 1; }

for R in $REPS; do
  echo; echo "##### 3. phase B replicate $R ($(date))"
  REP="$R" "$STEP20/run-cells.sh" B || echo "WARNING: phase B replicate $R had a failed lane"
done

restore_all
echo; echo "##### 4. analysis and figures ($(date))"
uv run --quiet --with matplotlib --with numpy python "$STEP20/analyze.py" > /dev/null || echo "WARNING: analysis failed"
rm -f "$RESULTS/figure-data.json"
uv run --quiet --with matplotlib --with numpy python "$STEP20/make_figures.py" > /dev/null || echo "WARNING: figures failed"
rm -f "$RESULTS/bobbm.kubeconfig"
echo "step 20 phase B replicates done $(date)"
