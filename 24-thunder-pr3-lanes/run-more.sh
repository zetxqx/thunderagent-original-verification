#!/usr/bin/env bash
# Step 24, 400 GiB offload, more points while offloading is on. Replaces
# run-lease10-finish.sh (stopped with SIGKILL, no restore, at about 08:50 UTC on 2026-10-11)
# and keeps its job: the lease 10 s c32 rerun on lane a. Each lane starts its queue when
# its current point ends:
#   a: lease 10 s c32 (rerun), lease 10 s c128
#   b: lease 10 s c192, no router c48
#   c: no router c80, lease 30 s c48
#   d: lease 10 s c64 (lane d gets a lease 10 s EPP first)
# Lease 10 s at c64 to c192 is where the gate is full and pauses sessions, so where the lease
# matters; c48 and c80 fill the c32 to c64 gap and the no-router cliff between c64 and c96.
# Then it waits for the run-lanes.sh workers still running, restores the original vLLM
# deployment, removes the lane EPPs and rebuilds the reports and the dashboard bundle.
# Usage: run-more.sh <run-lanes pid> [...]
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube
pin_kube
export CLIENT_CPU=4
EPP_TAG=thunder-agent-pr3-a025437b-produces
LEASE10="$SKILL/manifests/epp/thunder-pr3-lease10-plugins.yaml"
PIDS=("$@")
ts() { date -u +%H:%M:%S; }

restore() {
  echo "=== restoring the original vLLM deployment ($(ts))"
  kubectl replace -f "$RESULTS/vllm-deploy-before.json"
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=45m
}
trap restore EXIT

# apply_retry <file>: the API server throttled applies on 2026-10-11 ("ENHANCE_YOUR_CALM").
apply_retry() {
  local i
  for i in 1 2 3 4 5 6; do
    kubectl apply -f "$1" >/dev/null && return 0
    sleep 15
  done
  return 1
}

echo "=== lane d EPP, lease 10 s ($(ts))"
"$SKILL/scripts/render-lane-epp.sh" d "$LEASE10" "$EPP_TAG" > "$RESULTS/lane-epp-d.yaml"
apply_retry "$RESULTS/lane-epp-d.yaml" || { echo "lane d EPP apply failed"; exit 1; }
kubectl -n "$NS" rollout status deploy/agentx-epp-d-epp --timeout=10m
got=$(kubectl -n "$NS" get configmap agentx-epp-d-epp -o yaml | grep -oE 'idleLeaseSeconds: [0-9]+' | sort -u)
echo "lane d: $got"
[ "$got" = "idleLeaseSeconds: 10" ] || { echo "lane d EPP config is not idleLeaseSeconds 10; stopping"; exit 1; }

# run_one <lane> <label> <conc> <lane_epp 0|1> [log suffix]
run_one() {
  local lane=$1 label=$2 conc=$3 epp=$4 suffix=${5:-}
  echo "=== $label lane $lane: c$conc start ($(ts))"
  if LANE=$lane LANE_EPP=$epp MODE=lane "$SKILL/scripts/run-point.sh" "$conc" "$label" \
      > "$RESULTS/$label-$lane-c$conc$suffix.log" 2>&1; then
    echo "=== $label lane $lane: c$conc done ($(ts))"
  else
    echo "=== $label lane $lane: c$conc did not succeed or is invalid ($(ts))"
  fi
}

# wait_for <log> <pattern>: until the lane's current point has ended.
wait_for() { until grep -qE "$2" "$1" 2>/dev/null; do sleep 60; done; }

L10=offload-thunder-lease10-60m; L30=offload-thunder-60m; NR=offload-baseline-60m
{ wait_for "$RESULTS/run-lease10.log" "$L10 lane a: c20 (done|did not succeed)"
  run_one a $L10 32 1 -rerun; run_one a $L10 128 1; } &
A=$!
{ wait_for "$RESULTS/run-lease10.log" "$L10 lane b: c16 (done|did not succeed)"
  run_one b $L10 192 1; run_one b $NR 48 0; } &
B=$!
{ wait_for "$RESULTS/run-lease10.log" "$L30 lane c: c20 (done|did not succeed)"
  run_one c $NR 80 0; run_one c $L30 48 1; } &
C=$!
{ wait_for "$RESULTS/run-offload-baseline-c24-c20.log" "$NR lane d: c20 (done|did not succeed)"
  run_one d $L10 64 1; } &
D=$!
wait $A $B $C $D

echo "=== waiting for the run-lanes.sh workers (${PIDS[*]}) ($(ts))"
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
