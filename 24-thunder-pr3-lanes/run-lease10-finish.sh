#!/usr/bin/env bash
# Step 24, finish of run-lease10.sh, which was stopped (SIGKILL, no restore) at about
# 08:35 UTC on 2026-10-11 so offloading stays on for one rerun:
#   offload-thunder-lease10-60m c32 failed at 08:06 UTC: vLLM hit "CUDA error: an illegal
#   memory access was encountered" (Cloud Logging, pod ...-b7d5j), restarted, and could not
#   start again because the old 400 GiB offload file still filled /dev/shm; aiperf stopped
#   at its 10% failed-request threshold. No GPU Xid on the node.
# It reruns c32 on lane a when lane a's c20 ends, waits for the run-lanes.sh workers of
# run-lease10.sh, then restores the original vLLM deployment, removes the lane EPPs and
# rebuilds the five-arm report and the dashboard bundle (the end of run-lease10.sh).
# Usage: run-lease10-finish.sh <run-lanes pid> [<run-lanes pid> ...]
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube
pin_kube
export CLIENT_CPU=4
LOG="$RESULTS/run-lease10.log"   # the run-lanes.sh workers still write their progress here
PIDS=("$@")
[ ${#PIDS[@]} -gt 0 ] || { echo "give the run-lanes.sh pids" >&2; exit 1; }
ts() { date -u +%H:%M:%S; }

restore() {
  echo "=== restoring the original vLLM deployment ($(ts))"
  kubectl replace -f "$RESULTS/vllm-deploy-before.json"
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=45m
}
trap restore EXIT

echo "=== archiving the failed lease 10 s c32 ($(ts))"
mkdir -p "$RESULTS/offload-thunder-lease10-60m-invalid"
[ -d "$RESULTS/offload-thunder-lease10-60m/c32" ] && \
  mv "$RESULTS/offload-thunder-lease10-60m/c32" "$RESULTS/offload-thunder-lease10-60m-invalid/c32"
kubectl -n "$NS" delete job agentx-c32-offload-thunder-lease10-60m --ignore-not-found --wait=true

until grep -qE "offload-thunder-lease10-60m lane a: c20 (done|did not succeed)" "$LOG"; do sleep 60; done
echo "=== lane a free: rerun lease 10 s c32 ($(ts))"
if LANE=a LANE_EPP=1 MODE=lane "$SKILL/scripts/run-point.sh" 32 offload-thunder-lease10-60m \
    > "$RESULTS/offload-thunder-lease10-60m-a-c32-rerun.log" 2>&1; then
  echo "=== lease 10 s c32 rerun done ($(ts))"
else
  echo "=== lease 10 s c32 rerun did not succeed or is invalid ($(ts))"
fi

echo "=== waiting for the run-lanes.sh workers (${PIDS[*]}) ($(ts))"
for p in "${PIDS[@]}"; do while kill -0 "$p" 2>/dev/null; do sleep 60; done; done

restore
trap - EXIT
echo "=== removing the lane EPPs ($(ts))"
for l in a b c; do kubectl delete -f "$RESULTS/lane-epp-$l.yaml" --ignore-not-found >/dev/null; done

echo "=== five-arm report and dashboard bundle ($(ts))"
LABELS=(thunder-60m baseline-60m offload-thunder-60m offload-thunder-lease10-60m offload-baseline-60m)
POINTS=()
for l in "${LABELS[@]}"; do POINTS+=("$RESULTS/$l"/c*); done
NAMES=(--name baseline-60m="no router" --name thunder-60m="thunder gate (PR3)"
       --name offload-baseline-60m="no router + 400 GiB offload" --name offload-thunder-60m="thunder + 400 GiB offload"
       --name offload-thunder-lease10-60m="thunder lease 10 s + 400 GiB offload")
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/offload-thunder-lease10-60m/report" "$RESULTS"/offload-thunder-lease10-60m/c*
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-all/report" "${POINTS[@]}"
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare-all/report" --baseline baseline-60m "${NAMES[@]}" \
  "$RESULTS/compare-all/report/summary.csv"
uv run "$SKILL/scripts/export_bundle.py" --out "$STEP/../dashboard/data/step24-thunder-pr3-lanes.json" \
  --title "Step 24: thunder PR3 gate vs no router, 400 GiB CPU offload" \
  --description "One vLLM pod per lane (Qwen3-Coder-30B-A3B FP8, TP=2, 2 H100), AgentX Weka trace replay, 60 min per point, 2026-10-09 to 11." \
  --baseline baseline-60m "${NAMES[@]}" "${POINTS[@]}"
echo "=== done ($(ts))"
