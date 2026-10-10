#!/usr/bin/env bash
# Step 24 extra points for complete Pareto curves (same images and configs as phases 1 and 2):
#   phase 1, no offload, one wave on 4 pods:  thunder-60m c8 c4 (lanes a b, lane EPPs),
#                                             baseline-60m c8 c4 (lanes c d, direct)
#   phase 2, 400 GiB offload, one wave:       offload-thunder-60m c256 c16, offload-baseline-60m c16
# Then it restores the original vLLM deployment (on every exit path once phase 2 starts),
# removes the lane EPPs, rebuilds the four-arm report and the dashboard bundle.
#   nohup caffeinate -i ./run-extra.sh > results/run-extra.log 2>&1 &
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube
pin_kube
export CLIENT_CPU=4
EPP_TAG=thunder-agent-pr3-a025437b-produces
ts() { date -u +%H:%M:%S; }

ready_pods() {
  kubectl -n "$NS" get pods -l llm-d.ai/role=decode \
    -o jsonpath='{range .items[?(@.status.containerStatuses[0].ready==true)]}{.metadata.name}{"\n"}{end}'
}

echo "=== lane EPPs ($(ts))"
kubectl apply -f "$SKILL/manifests/lane-epp-rbac.yaml"
for l in a b c d; do
  "$SKILL/scripts/render-lane-epp.sh" "$l" "$SKILL/manifests/epp/thunder-pr3-plugins.yaml" "$EPP_TAG" > "$RESULTS/lane-epp-$l.yaml"
  kubectl apply -f "$RESULTS/lane-epp-$l.yaml" >/dev/null
  kubectl -n "$NS" rollout status "deploy/agentx-epp-$l-epp" --timeout=10m
done

echo "=== phase 1: no offload, thunder c8 c4 on lanes a b, baseline c8 c4 on lanes c d ($(ts))"
LANES="a b" LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" thunder-60m 8 4 &
sleep 20
LANES="c d" LANE_EPP=0 "$SKILL/scripts/run-lanes.sh" baseline-60m 8 4 &
wait

restore() {
  echo "=== restoring the original vLLM deployment ($(ts))"
  kubectl replace -f "$RESULTS/vllm-deploy-before.json"
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=45m
}
trap restore EXIT

echo "=== phase 2: 400 GiB offload ($(ts))"
OLD=$(kubectl -n "$NS" get pods -l llm-d.ai/role=decode -o jsonpath='{.items[*].metadata.name}')
kubectl replace -f "$RESULTS/vllm-deploy-offload400.json"
# One offload pod per node and 3 points: wait for 3 new ready pods, not for all replicas
# (the cluster had 3 H100 nodes on 2026-10-09 evening).
NEW=""
for _ in $(seq 1 90); do
  NEW=$(ready_pods | grep -vxF -f <(tr ' ' '\n' <<< "$OLD") || true)
  [ "$(grep -c . <<< "$NEW")" -ge 3 ] && break
  sleep 30
done
N=$(grep -c . <<< "$NEW" || true)
echo "ready offload pods: $N"
for p in $NEW; do
  echo "$p $(vllm_get "$p" /metrics | grep -E '^vllm:cache_config_info' | grep -oE 'kv_offloading_size="[^"]*"' )"
done
if [ "$N" -ge 3 ]; then
  LANES="a b" LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" offload-thunder-60m 256 16 &
  sleep 20
  LANES="c" LANE_EPP=0 "$SKILL/scripts/run-lanes.sh" offload-baseline-60m 16 &
  wait
elif [ "$N" -eq 2 ]; then
  LANES="a" LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" offload-thunder-60m 256 &
  sleep 20
  { LANES="b" LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" offload-thunder-60m 16
    LANES="b" LANE_EPP=0 "$SKILL/scripts/run-lanes.sh" offload-baseline-60m 16; } &
  wait
elif [ "$N" -eq 1 ]; then
  LANES="a" LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" offload-thunder-60m 256 16
  LANES="a" LANE_EPP=0 "$SKILL/scripts/run-lanes.sh" offload-baseline-60m 16
else
  echo "no ready vLLM pod with offloading; phase 2 skipped"
fi

restore
trap - EXIT
echo "=== removing the lane EPPs ($(ts))"
for l in a b c d; do kubectl delete -f "$RESULTS/lane-epp-$l.yaml" --ignore-not-found >/dev/null; done

echo "=== four-arm report and dashboard bundle ($(ts))"
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-all/report" \
  "$RESULTS"/thunder-60m/c* "$RESULTS"/baseline-60m/c* "$RESULTS"/offload-thunder-60m/c* "$RESULTS"/offload-baseline-60m/c*
NAMES=(--name baseline-60m="no router" --name thunder-60m="thunder gate (PR3)"
       --name offload-baseline-60m="no router + 400 GiB offload" --name offload-thunder-60m="thunder + 400 GiB offload")
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare-all/report" --baseline baseline-60m "${NAMES[@]}" \
  "$RESULTS/compare-all/report/summary.csv"
uv run "$SKILL/scripts/export_bundle.py" --out "$STEP/../dashboard/data/step24-thunder-pr3-lanes.json" \
  --title "Step 24: thunder PR3 gate vs no router, 400 GiB CPU offload" \
  --description "One vLLM pod per lane (Qwen3-Coder-30B-A3B FP8, TP=2, 2 H100), AgentX Weka trace replay, 60 min per point, 2026-10-09 and 10." \
  --baseline baseline-60m "${NAMES[@]}" \
  "$RESULTS"/baseline-60m/c* "$RESULTS"/thunder-60m/c* "$RESULTS"/offload-baseline-60m/c* "$RESULTS"/offload-thunder-60m/c*
echo "=== done ($(ts))"
