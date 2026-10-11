#!/usr/bin/env bash
# Step 24, 400 GiB offload: end of the 2026-10-11 runs. Replaces run-more.sh's parent
# (stopped with SIGKILL, no restore, at about 10:40 UTC); run-more.sh's four lane queues keep
# running as their own processes. Adds one rerun:
#   offload-baseline-60m c80 failed at 10:34 UTC in warmup: one direct request got
#   "Connection reset by peer" (vLLM closes idle connections after 5 s; aiohttp reused one),
#   and a failed root warmup request aborts an AgentX run. The vLLM pod did not restart.
# It reruns c80 on lane c when lane c's c48 ends, waits for the given processes, restores the
# original vLLM deployment, removes the lane EPPs and rebuilds the reports and the bundle.
# Usage: run-final.sh <pid> [...]
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube
pin_kube
export CLIENT_CPU=4
PIDS=("$@")
[ ${#PIDS[@]} -gt 0 ] || { echo "give the pids to wait for" >&2; exit 1; }
ts() { date -u +%H:%M:%S; }

restore() {
  echo "=== restoring the original vLLM deployment ($(ts))"
  kubectl replace -f "$RESULTS/vllm-deploy-before.json"
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=45m
}
trap restore EXIT

echo "=== archiving the failed no-router c80 ($(ts))"
mkdir -p "$RESULTS/offload-baseline-60m-invalid"
[ -d "$RESULTS/offload-baseline-60m/c80" ] && mv "$RESULTS/offload-baseline-60m/c80" "$RESULTS/offload-baseline-60m-invalid/c80"
kubectl -n "$NS" delete job agentx-c80-offload-baseline-60m --ignore-not-found --wait=true

until grep -qE "offload-thunder-60m lane c: c48 (done|did not succeed)" "$RESULTS/run-more.log"; do sleep 60; done
echo "=== offload-baseline-60m lane c: c80 rerun start ($(ts))"
if LANE=c LANE_EPP=0 MODE=lane "$SKILL/scripts/run-point.sh" 80 offload-baseline-60m \
    > "$RESULTS/offload-baseline-60m-c-c80-rerun.log" 2>&1; then
  echo "=== offload-baseline-60m lane c: c80 rerun done ($(ts))"
else
  echo "=== offload-baseline-60m lane c: c80 rerun did not succeed or is invalid ($(ts))"
fi

echo "=== waiting for ${PIDS[*]} ($(ts))"
for p in "${PIDS[@]}"; do while kill -0 "$p" 2>/dev/null; do sleep 60; done; done

restore
trap - EXIT
echo "=== removing the lane EPPs ($(ts))"
for l in a b c d; do kubectl delete -f "$RESULTS/lane-epp-$l.yaml" --ignore-not-found >/dev/null; done

echo "=== reports and dashboard bundle ($(ts))"
LABELS=(thunder-60m baseline-60m offload-thunder-60m offload-thunder-lease10-60m offload-baseline-60m)
POINTS=()
for l in "${LABELS[@]}"; do POINTS+=("$RESULTS/$l"/c*); done
NAMES=(--name baseline-60m="no router" --name thunder-60m="thunder gate (PR3)"
       --name offload-baseline-60m="no router + 400 GiB offload" --name offload-thunder-60m="thunder + 400 GiB offload"
       --name offload-thunder-lease10-60m="thunder lease 10 s + 400 GiB offload")
for l in offload-thunder-lease10-60m offload-thunder-60m offload-baseline-60m; do
  uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/$l/report" "$RESULTS/$l"/c* > "$RESULTS/report-$l.log" 2>&1
done
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-all/report" "${POINTS[@]}"
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare-all/report" --baseline baseline-60m "${NAMES[@]}" \
  "$RESULTS/compare-all/report/summary.csv"
uv run "$SKILL/scripts/export_bundle.py" --out "$STEP/../dashboard/data/step24-thunder-pr3-lanes.json" \
  --title "Step 24: thunder PR3 gate vs no router, 400 GiB CPU offload" \
  --description "One vLLM pod per lane (Qwen3-Coder-30B-A3B FP8, TP=2, 2 H100), AgentX Weka trace replay, 60 min per point, 2026-10-09 to 11." \
  --baseline baseline-60m "${NAMES[@]}" "${POINTS[@]}"
echo "=== done ($(ts))"
