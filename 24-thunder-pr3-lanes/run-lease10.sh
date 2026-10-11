#!/usr/bin/env bash
# Step 24, 400 GiB CPU offload: the thunder gate with a 10 s idle lease
# (manifests/epp/thunder-pr3-lease10-plugins.yaml; GPU-sized capacity, 1800 s forced
# admission, everything else as offload-thunder-60m) at c = 32 24 20 16 on lanes a b,
# and the 30 s lease (offload-thunder-60m) at the missing c = 24 20 on lane c.
# Three offload pods (one per H100 node), two waves. The original vLLM deployment is
# restored on every exit path; then the lane EPPs are removed and the five-arm report
# and the dashboard bundle are rebuilt.
#   nohup caffeinate -i ./run-lease10.sh > results/run-lease10.log 2>&1 &
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube, vllm_get
pin_kube
export CLIENT_CPU=4
EPP_TAG=thunder-agent-pr3-a025437b-produces
LEASE10="$SKILL/manifests/epp/thunder-pr3-lease10-plugins.yaml"
LEASE30="$SKILL/manifests/epp/thunder-pr3-plugins.yaml"
ts() { date -u +%H:%M:%S; }

ready_pods() {
  kubectl -n "$NS" get pods -l llm-d.ai/role=decode \
    -o jsonpath='{range .items[?(@.status.containerStatuses[0].ready==true)]}{.metadata.name}{"\n"}{end}'
}

restore() {
  echo "=== restoring the original vLLM deployment ($(ts))"
  kubectl replace -f "$RESULTS/vllm-deploy-before.json"
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=45m
}
trap restore EXIT

echo "=== 400 GiB offload on ($(ts))"
OLD=$(kubectl -n "$NS" get pods -l llm-d.ai/role=decode -o jsonpath='{.items[*].metadata.name}')
kubectl replace -f "$RESULTS/vllm-deploy-offload400.json"
NEW=""
for _ in $(seq 1 90); do
  NEW=$(ready_pods | grep -vxF -f <(tr ' ' '\n' <<< "$OLD") || true)
  [ "$(grep -c . <<< "$NEW")" -ge 3 ] && break
  sleep 30
done
N=$(grep -c . <<< "$NEW" || true)
echo "ready offload pods: $N"
for p in $NEW; do
  echo "$p $(vllm_get "$p" /metrics | grep -E '^vllm:cache_config_info' | grep -oE 'kv_offloading_size="[^"]*"')"
done
[ "$N" -ge 3 ] || { echo "need 3 offload pods, have $N; stopping"; exit 1; }

echo "=== lane EPPs: a b lease 10 s, c lease 30 s ($(ts))"
kubectl apply -f "$SKILL/manifests/lane-epp-rbac.yaml"
for l in a b c; do
  plugins=$LEASE10; want=10
  [ "$l" = c ] && { plugins=$LEASE30; want=30; }
  "$SKILL/scripts/render-lane-epp.sh" "$l" "$plugins" "$EPP_TAG" > "$RESULTS/lane-epp-$l.yaml"
  kubectl apply -f "$RESULTS/lane-epp-$l.yaml" >/dev/null
  kubectl -n "$NS" rollout status "deploy/agentx-epp-$l-epp" --timeout=10m
  got=$(kubectl -n "$NS" get configmap "agentx-epp-$l-epp" -o yaml | grep -oE 'idleLeaseSeconds: [0-9]+' | sort -u)
  echo "lane $l: $got"
  [ "$got" = "idleLeaseSeconds: $want" ] || { echo "lane $l EPP config is not idleLeaseSeconds $want; stopping"; exit 1; }
done

echo "=== points ($(ts))"
LANES="a b" LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" offload-thunder-lease10-60m 32 24 20 16 &
sleep 20
LANES="c" LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" offload-thunder-60m 24 20 &
wait

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
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-all/report" "${POINTS[@]}"
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare-all/report" --baseline baseline-60m "${NAMES[@]}" \
  "$RESULTS/compare-all/report/summary.csv"
uv run "$SKILL/scripts/export_bundle.py" --out "$STEP/../dashboard/data/step24-thunder-pr3-lanes.json" \
  --title "Step 24: thunder PR3 gate vs no router, 400 GiB CPU offload" \
  --description "One vLLM pod per lane (Qwen3-Coder-30B-A3B FP8, TP=2, 2 H100), AgentX Weka trace replay, 60 min per point, 2026-10-09 to 11." \
  --baseline baseline-60m "${NAMES[@]}" "${POINTS[@]}"
echo "=== done ($(ts))"
