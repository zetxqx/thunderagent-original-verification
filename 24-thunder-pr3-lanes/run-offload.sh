#!/usr/bin/env bash
# Step 24 phase 2: 400 GiB CPU KV offloading on every vLLM pod (one pod per node),
# thunder lanes then no-router lanes at c = 192 128 96 64 32, then the four-arm
# comparison; the original deployment is restored on every exit path.
# Waits for run-all.sh (phase 1) to finish first.
#   nohup caffeinate -i ./run-offload.sh > results/run-offload.log 2>&1 &
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube, vllm_get
pin_kube
CONCS="192 128 96 64 32"
export CLIENT_CPU=4
ts() { date -u +%H:%M:%S; }

echo "=== waiting for phase 1 ($(ts))"
until grep -q "=== done" "$RESULTS/run-all.log" 2>/dev/null; do
  pgrep -f "run-all.sh" >/dev/null || { echo "phase 1 stopped without finishing; phase 2 not started"; exit 1; }
  sleep 120
done
pin_kube

restore() {
  echo "=== restoring the original vLLM deployment ($(ts))"
  kubectl replace -f "$RESULTS/vllm-deploy-before.json"
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=45m
}
trap restore EXIT

echo "=== offloading on: $RESULTS/vllm-deploy-offload400.json ($(ts))"
kubectl replace -f "$RESULTS/vllm-deploy-offload400.json"
kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=60m \
  || echo "not every replica became ready (a node may be missing); running on the ready ones"
READY=$(kubectl -n "$NS" get pods -l llm-d.ai/role=decode \
  -o jsonpath='{range .items[?(@.status.containerStatuses[0].ready==true)]}{.metadata.name}{"\n"}{end}')
N=$(echo "$READY" | grep -c . || true)
[ "$N" -ge 1 ] || { echo "no ready vLLM pod with offloading"; exit 1; }
LANES=$(echo "a b c d" | cut -d' ' -f1-"$N")
export LANES
echo "ready pods: $N, lanes: $LANES"
for p in $READY; do
  echo "$p $(vllm_get "$p" /metrics | grep -E '^vllm:cache_config_info' | grep -oE 'kv_offloading_size="[^"]*"|num_cpu_blocks="[^"]*"' | tr '\n' ' ')"
done | tee "$RESULTS/offload-cache-config.txt"

echo "=== offload thunder ($(ts))"
LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" offload-thunder-60m $CONCS

echo "=== offload baseline ($(ts))"
LANE_EPP=0 "$SKILL/scripts/run-lanes.sh" offload-baseline-60m $CONCS

echo "=== four-arm comparison ($(ts))"
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-all/report" \
  "$RESULTS"/thunder-60m/c* "$RESULTS"/baseline-60m/c* "$RESULTS"/offload-thunder-60m/c* "$RESULTS"/offload-baseline-60m/c*
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare-all/report" --baseline baseline-60m \
  --name baseline-60m="no router" --name thunder-60m="thunder gate (PR3)" \
  --name offload-baseline-60m="no router + 400 GiB offload" --name offload-thunder-60m="thunder + 400 GiB offload" \
  "$RESULTS/compare-all/report/summary.csv"

echo "=== removing the lane EPPs ($(ts))"
for l in a b c d; do kubectl delete -f "$RESULTS/lane-epp-$l.yaml" --ignore-not-found >/dev/null; done
echo "=== done ($(ts))"
