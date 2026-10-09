#!/usr/bin/env bash
# Step 24 phase 2 finish. Replaces the ends of run-offload.sh and run-offload-rerun.sh,
# which were stopped at 17:05 UTC so the three failed offload-thunder points can rerun
# while offloading is still on, on each lane as soon as its offload-baseline point ends
# (saves an offload off/on cycle and about 2 h):
#   lane d after baseline c32 -> thunder c128, lane c after c96 -> c64, lane b after c128 -> c32
# Then it waits for the baseline run-lanes.sh (c192 on lane a), builds the reports,
# restores the original vLLM deployment and removes the lane EPPs.
# Usage: run-offload-finish.sh <pid of the offload-baseline run-lanes.sh>
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube
pin_kube
export CLIENT_CPU=4
BASE_PID=${1:?pid of the offload-baseline run-lanes.sh}
LOG="$RESULTS/run-offload.log"   # the baseline run-lanes.sh still writes its progress here
ts() { date -u +%H:%M:%S; }

echo "=== archiving the failed offload-thunder points ($(ts))"
mkdir -p "$RESULTS/offload-thunder-60m-invalid"
for c in 128 64 32; do
  [ -d "$RESULTS/offload-thunder-60m/c$c" ] && mv "$RESULTS/offload-thunder-60m/c$c" "$RESULTS/offload-thunder-60m-invalid/c$c"
done
kubectl -n "$NS" delete job agentx-c128-offload-thunder-60m --ignore-not-found --wait=true

rerun_on() {
  local lane=$1 after=$2 conc=$3
  until grep -qE "offload-baseline-60m lane $lane: c$after (done|did not succeed)" "$LOG"; do sleep 60; done
  echo "=== lane $lane free after baseline c$after: thunder c$conc ($(ts))"
  if LANE=$lane LANE_EPP=1 MODE=lane "$SKILL/scripts/run-point.sh" "$conc" offload-thunder-60m \
      > "$RESULTS/offload-thunder-60m-$lane-c$conc-rerun.log" 2>&1; then
    echo "=== thunder c$conc on lane $lane done ($(ts))"
  else
    echo "=== thunder c$conc on lane $lane did not succeed or is invalid ($(ts))"
  fi
}
rerun_on d 32 128 &
rerun_on c 96 64 &
rerun_on b 128 32 &
wait

echo "=== waiting for offload-baseline c192 (run-lanes.sh pid $BASE_PID) ($(ts))"
while kill -0 "$BASE_PID" 2>/dev/null; do sleep 60; done

restore() {
  echo "=== restoring the original vLLM deployment ($(ts))"
  kubectl replace -f "$RESULTS/vllm-deploy-before.json"
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=45m
}
trap restore EXIT

echo "=== reports ($(ts))"
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/offload-thunder-60m/report" "$RESULTS"/offload-thunder-60m/c*
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-all/report" \
  "$RESULTS"/thunder-60m/c* "$RESULTS"/baseline-60m/c* "$RESULTS"/offload-thunder-60m/c* "$RESULTS"/offload-baseline-60m/c*
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare-all/report" --baseline baseline-60m \
  --name baseline-60m="no router" --name thunder-60m="thunder gate (PR3)" \
  --name offload-baseline-60m="no router + 400 GiB offload" --name offload-thunder-60m="thunder + 400 GiB offload" \
  "$RESULTS/compare-all/report/summary.csv"

echo "=== removing the lane EPPs ($(ts))"
for l in a b c d; do kubectl delete -f "$RESULTS/lane-epp-$l.yaml" --ignore-not-found >/dev/null; done
echo "=== done ($(ts))"
