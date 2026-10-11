#!/usr/bin/env bash
# Step 24, 400 GiB offload: the 300 s forced admission with the reclaim fix, image
# thunder-agent-pr3-a025437b-forced-7ae26276 (a025437b + b9a70488 "forced admission reclaims
# idle sessions" + 7ae26276 Produces()). Same plugin file as offload-thunder-fa300-60m
# (300 s forced admission, lease 30 s, GPU-sized capacity), label
# offload-thunder-fa300-reclaim-60m, at c = 96 64 32.
# Replaces run-fa300.sh's parent (stopped with SIGKILL, no restore, at about 19:05 UTC on
# 2026-10-11); its three lane queues keep running. When a lane's queue ends, its EPP is
# re-rendered with the new image and the lane runs its point:
#   a: c96, b: c64, c: c32
# Then it restores the original vLLM deployment, removes the lane EPPs and rebuilds the
# reports and the dashboard bundle.
# Usage: run-reclaim.sh <lane a pid> <lane b pid> <lane c pid>
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube
pin_kube
export CLIENT_CPU=4
NEW_TAG=thunder-agent-pr3-a025437b-forced-7ae26276
FA300="$SKILL/manifests/epp/thunder-pr3-fa300-plugins.yaml"
LABEL=offload-thunder-fa300-reclaim-60m
PID_A=${1:?lane a pid}; PID_B=${2:?lane b pid}; PID_C=${3:?lane c pid}
ts() { date -u +%H:%M:%S; }

apply_retry() {
  local i
  for i in 1 2 3 4 5 6; do kubectl apply -f "$1" >/dev/null && return 0; sleep 15; done
  return 1
}
restore() {
  echo "=== restoring the original vLLM deployment ($(ts))"
  kubectl replace -f "$RESULTS/vllm-deploy-before.json"
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=45m
}
trap restore EXIT

echo "=== removing leftover jobs of this label ($(ts))"
for c in 96 64 32; do kubectl -n "$NS" delete job "agentx-c$c-$LABEL" --ignore-not-found --wait=true; done

# lane_run <lane> <pid of its current queue> <conc>
lane_run() {
  local lane=$1 pid=$2 conc=$3
  while kill -0 "$pid" 2>/dev/null; do sleep 60; done
  echo "=== lane $lane free: EPP with $NEW_TAG ($(ts))"
  "$SKILL/scripts/render-lane-epp.sh" "$lane" "$FA300" "$NEW_TAG" > "$RESULTS/lane-epp-$lane.yaml"
  if ! apply_retry "$RESULTS/lane-epp-$lane.yaml"; then
    echo "=== $LABEL lane $lane: c$conc did not succeed or is invalid (EPP apply failed) ($(ts))"; return
  fi
  kubectl -n "$NS" rollout status "deploy/agentx-epp-$lane-epp" --timeout=10m
  local img cm hw il
  img=$(kubectl -n "$NS" get deploy "agentx-epp-$lane-epp" -o jsonpath='{.spec.template.spec.containers[*].image}')
  cm=$(kubectl -n "$NS" get configmap "agentx-epp-$lane-epp" -o yaml)
  hw=$(grep -oE 'headWaitStarvationMs: [0-9]+' <<< "$cm" | sort -u)
  il=$(grep -oE 'idleLeaseSeconds: [0-9]+' <<< "$cm" | sort -u)
  echo "lane $lane: $hw, $il, images: $img"
  if [[ "$img" != *"$NEW_TAG"* ]] || [ "$hw" != "headWaitStarvationMs: 300000" ] || [ "$il" != "idleLeaseSeconds: 30" ]; then
    echo "=== $LABEL lane $lane: c$conc did not succeed or is invalid (EPP image or config check failed) ($(ts))"; return
  fi
  echo "=== $LABEL lane $lane: c$conc start ($(ts))"
  if LANE=$lane LANE_EPP=1 MODE=lane "$SKILL/scripts/run-point.sh" "$conc" "$LABEL" \
      > "$RESULTS/$LABEL-$lane-c$conc.log" 2>&1; then
    echo "=== $LABEL lane $lane: c$conc done ($(ts))"
  else
    echo "=== $LABEL lane $lane: c$conc did not succeed or is invalid ($(ts))"
  fi
}
lane_run a "$PID_A" 96 &
lane_run b "$PID_B" 64 &
lane_run c "$PID_C" 32 &
wait

restore
trap - EXIT
echo "=== removing the lane EPPs ($(ts))"
for l in a b c; do kubectl delete -f "$RESULTS/lane-epp-$l.yaml" --ignore-not-found >/dev/null; done

echo "=== reports and dashboard bundle ($(ts))"
LABELS=(thunder-60m baseline-60m offload-thunder-60m offload-thunder-lease10-60m offload-thunder-fa300-60m
        offload-thunder-fa300-reclaim-60m offload-baseline-60m)
POINTS=()
for l in "${LABELS[@]}"; do POINTS+=("$RESULTS/$l"/c*); done
NAMES=(--name baseline-60m="no router" --name thunder-60m="thunder gate (PR3)"
       --name offload-baseline-60m="no router + 400 GiB offload" --name offload-thunder-60m="thunder + 400 GiB offload"
       --name offload-thunder-lease10-60m="thunder lease 10 s + 400 GiB offload"
       --name offload-thunder-fa300-60m="thunder FA 300 s + 400 GiB offload"
       --name offload-thunder-fa300-reclaim-60m="thunder FA 300 s + reclaim + 400 GiB offload")
for l in offload-thunder-fa300-60m offload-thunder-fa300-reclaim-60m; do
  uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/$l/report" "$RESULTS/$l"/c* > "$RESULTS/report-$l.log" 2>&1
done
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-all/report" "${POINTS[@]}"
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare-all/report" --baseline baseline-60m "${NAMES[@]}" \
  "$RESULTS/compare-all/report/summary.csv"
uv run "$SKILL/scripts/export_bundle.py" --out "$STEP/../dashboard/data/step24-thunder-pr3-lanes.json" \
  --title "Step 24: thunder PR3 gate vs no router, 400 GiB CPU offload" \
  --description "One vLLM pod per lane (Qwen3-Coder-30B-A3B FP8, TP=2, 2 H100), AgentX Weka trace replay, 60 min per point, 2026-10-09 to 12." \
  --baseline baseline-60m "${NAMES[@]}" "${POINTS[@]}"
echo "=== done ($(ts))"
