#!/usr/bin/env bash
# Step 24, 400 GiB offload: two more points for the lease 10 s arm (offload-thunder-lease10-60m,
# manifests/epp/thunder-pr3-lease10-plugins.yaml, image thunder-agent-pr3-a025437b-produces):
#   lane a: c28 (between c24 and c32), lane b: c48 (between c32 and c64), in parallel.
# Restores the original vLLM deployment on every exit path, removes the lane EPPs, and rebuilds the
# reports and the dashboard bundle.
#   nohup caffeinate -i ./run-lease10-c28-c48.sh > results/run-lease10-c28-c48.log 2>&1 &
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube, vllm_get
pin_kube
export CLIENT_CPU=4
EPP_TAG=thunder-agent-pr3-a025437b-produces
LEASE10="$SKILL/manifests/epp/thunder-pr3-lease10-plugins.yaml"
LABEL=offload-thunder-lease10-60m
ts() { date -u +%H:%M:%S; }

ready_pods() {
  kubectl -n "$NS" get pods -l llm-d.ai/role=decode \
    -o jsonpath='{range .items[?(@.status.containerStatuses[0].ready==true)]}{.metadata.name}{"\n"}{end}'
}
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

echo "=== removing leftover jobs ($(ts))"
for c in 28 48; do kubectl -n "$NS" delete job "agentx-c$c-$LABEL" --ignore-not-found --wait=true; done

echo "=== 400 GiB offload on ($(ts))"
OLD=$(kubectl -n "$NS" get pods -l llm-d.ai/role=decode -o jsonpath='{.items[*].metadata.name}')
kubectl replace -f "$RESULTS/vllm-deploy-offload400.json"
NEW=""
for _ in $(seq 1 90); do
  NEW=$(ready_pods | grep -vxF -f <(tr ' ' '\n' <<< "$OLD") || true)
  [ "$(grep -c . <<< "$NEW")" -ge 2 ] && break
  sleep 30
done
for p in $NEW; do
  echo "$p $(kubectl -n "$NS" get pod "$p" -o jsonpath='{.spec.nodeName}') $(vllm_get "$p" /metrics | grep -E '^vllm:cache_config_info' | grep -oE 'kv_offloading_size="[^"]*"')"
done
[ "$(grep -c . <<< "$NEW")" -ge 2 ] || { echo "need 2 offload pods; stopping"; exit 1; }

echo "=== lane EPPs a b, lease 10 s ($(ts))"
apply_retry "$SKILL/manifests/lane-epp-rbac.yaml"
for l in a b; do
  "$SKILL/scripts/render-lane-epp.sh" "$l" "$LEASE10" "$EPP_TAG" > "$RESULTS/lane-epp-$l.yaml"
  apply_retry "$RESULTS/lane-epp-$l.yaml" || { echo "lane $l EPP apply failed"; exit 1; }
  kubectl -n "$NS" rollout status "deploy/agentx-epp-$l-epp" --timeout=10m
  cm=$(kubectl -n "$NS" get configmap "agentx-epp-$l-epp" -o yaml)
  hw=$(grep -oE 'headWaitStarvationMs: [0-9]+' <<< "$cm" | sort -u)
  il=$(grep -oE 'idleLeaseSeconds: [0-9]+' <<< "$cm" | sort -u)
  echo "lane $l: $hw, $il"
  [ "$hw" = "headWaitStarvationMs: 1800000" ] && [ "$il" = "idleLeaseSeconds: 10" ] \
    || { echo "lane $l EPP config is not the lease 10 s arm; stopping"; exit 1; }
done

run_one() {
  local lane=$1 conc=$2
  echo "=== $LABEL lane $lane: c$conc start ($(ts))"
  if LANE=$lane LANE_EPP=1 MODE=lane "$SKILL/scripts/run-point.sh" "$conc" "$LABEL" \
      > "$RESULTS/$LABEL-$lane-c$conc.log" 2>&1; then
    echo "=== $LABEL lane $lane: c$conc done ($(ts))"
  else
    echo "=== $LABEL lane $lane: c$conc did not succeed or is invalid ($(ts))"
  fi
}
run_one a 28 &
sleep 20
run_one b 48 &
wait

restore
trap - EXIT
echo "=== removing the lane EPPs ($(ts))"
for l in a b; do kubectl delete -f "$RESULTS/lane-epp-$l.yaml" --ignore-not-found >/dev/null; done

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
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/$LABEL/report" "$RESULTS/$LABEL"/c* > "$RESULTS/report-$LABEL.log" 2>&1
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-all/report" "${POINTS[@]}"
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare-all/report" --baseline baseline-60m "${NAMES[@]}" \
  "$RESULTS/compare-all/report/summary.csv"
uv run "$SKILL/scripts/export_bundle.py" --out "$STEP/../dashboard/data/step24-thunder-pr3-lanes.json" \
  --title "Step 24: thunder PR3 gate vs no router, 400 GiB CPU offload" \
  --description "One vLLM pod per lane (Qwen3-Coder-30B-A3B FP8, TP=2, 2 H100), AgentX Weka trace replay, 60 min per point, 2026-10-09 to 12." \
  --baseline baseline-60m --kv-bytes-per-token 49152 "${NAMES[@]}" "${POINTS[@]}"
echo "=== done ($(ts))"
