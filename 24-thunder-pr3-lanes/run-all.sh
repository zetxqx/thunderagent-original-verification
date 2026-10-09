#!/usr/bin/env bash
# Step 24 driver: thunder PR3 gate on one lane EPP per vLLM pod, then the no-router
# baseline, 60 min points at c = 32 24 20 16 12, then the comparison report.
#   nohup caffeinate -i ./run-all.sh > results/run-all.log 2>&1 &
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, pin_kube
pin_kube
CONCS="32 24 20 16 12"
# Each lane's PVC is zonal and each zone has one default-pool node, so two lanes can
# share a client node; 4 CPUs requested (no CPU limit) leaves room for both.
export CLIENT_CPU=4
# PR3 a025437b plus the missing Produces() (thunder-produces.patch): a025437b alone
# fails every request ("wrote undeclared request attribute").
EPP_TAG=thunder-agent-pr3-a025437b-produces

echo "=== deploy lane EPPs ($(date -u +%H:%M:%S))"
kubectl apply -f "$SKILL/manifests/lane-epp-rbac.yaml"
for l in a b c d; do
  "$SKILL/scripts/render-lane-epp.sh" "$l" "$SKILL/manifests/epp/thunder-pr3-plugins.yaml" "$EPP_TAG" > "$RESULTS/lane-epp-$l.yaml"
  kubectl apply -f "$RESULTS/lane-epp-$l.yaml" >/dev/null
  kubectl -n "$NS" rollout status "deploy/agentx-epp-$l-epp" --timeout=10m
done

echo "=== thunder ($(date -u +%H:%M:%S))"
LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" thunder-60m $CONCS

echo "=== baseline ($(date -u +%H:%M:%S))"
LANE_EPP=0 "$SKILL/scripts/run-lanes.sh" baseline-60m $CONCS

echo "=== comparison ($(date -u +%H:%M:%S))"
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare/report" \
  "$RESULTS"/thunder-60m/c* "$RESULTS"/baseline-60m/c*
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare/report" --baseline baseline-60m \
  --name baseline-60m="no router" --name thunder-60m="thunder gate (PR3)" "$RESULTS/compare/report/summary.csv"
echo "=== done ($(date -u +%H:%M:%S))"
