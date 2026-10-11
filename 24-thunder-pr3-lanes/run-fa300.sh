#!/usr/bin/env bash
# Step 24, 400 GiB CPU offload: the thunder gate with a 300 s forced admission
# (manifests/epp/thunder-pr3-fa300-plugins.yaml; otherwise as offload-thunder-60m: lease 30 s,
# GPU-sized capacity) at c = 192 128 96 64 32 24, label offload-thunder-fa300-60m.
# Three offload pods, lanes a b c, two waves, largest first:
#   a: c192 then c24, b: c128 then c32, c: c96 then c64
# The original vLLM deployment is restored on every exit path; then the lane EPPs are
# removed and the reports and the dashboard bundle are rebuilt.
#   nohup caffeinate -i ./run-fa300.sh > results/run-fa300.log 2>&1 &
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube, vllm_get
pin_kube
export CLIENT_CPU=4
EPP_TAG=thunder-agent-pr3-a025437b-produces
FA300="$SKILL/manifests/epp/thunder-pr3-fa300-plugins.yaml"
LABEL=offload-thunder-fa300-60m
ts() { date -u +%H:%M:%S; }

ready_pods() {
  kubectl -n "$NS" get pods -l llm-d.ai/role=decode \
    -o jsonpath='{range .items[?(@.status.containerStatuses[0].ready==true)]}{.metadata.name}{"\n"}{end}'
}
# The API server throttled applies on 2026-10-11 ("ENHANCE_YOUR_CALM").
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
for c in 192 128 96 64 32 24; do
  kubectl -n "$NS" delete job "agentx-c$c-$LABEL" --ignore-not-found --wait=true
done

echo "=== 400 GiB offload on ($(ts))"
OLD=$(kubectl -n "$NS" get pods -l llm-d.ai/role=decode -o jsonpath='{.items[*].metadata.name}')
kubectl replace -f "$RESULTS/vllm-deploy-offload400.json"
NEW=""
for _ in $(seq 1 90); do
  NEW=$(ready_pods | grep -vxF -f <(tr ' ' '\n' <<< "$OLD") || true)
  [ "$(grep -c . <<< "$NEW")" -ge 3 ] && break
  sleep 30
done
for p in $NEW; do
  echo "$p $(kubectl -n "$NS" get pod "$p" -o jsonpath='{.spec.nodeName}') $(vllm_get "$p" /metrics | grep -E '^vllm:cache_config_info' | grep -oE 'kv_offloading_size="[^"]*"')"
done
[ "$(grep -c . <<< "$NEW")" -ge 3 ] || { echo "need 3 offload pods; stopping"; exit 1; }

echo "=== lane EPPs a b c, forced admission 300 s ($(ts))"
apply_retry "$SKILL/manifests/lane-epp-rbac.yaml"
for l in a b c; do
  "$SKILL/scripts/render-lane-epp.sh" "$l" "$FA300" "$EPP_TAG" > "$RESULTS/lane-epp-$l.yaml"
  apply_retry "$RESULTS/lane-epp-$l.yaml" || { echo "lane $l EPP apply failed"; exit 1; }
  kubectl -n "$NS" rollout status "deploy/agentx-epp-$l-epp" --timeout=10m
  cm=$(kubectl -n "$NS" get configmap "agentx-epp-$l-epp" -o yaml)
  hw=$(grep -oE 'headWaitStarvationMs: [0-9]+' <<< "$cm" | sort -u)
  il=$(grep -oE 'idleLeaseSeconds: [0-9]+' <<< "$cm" | sort -u)
  echo "lane $l: $hw, $il"
  [ "$hw" = "headWaitStarvationMs: 300000" ] && [ "$il" = "idleLeaseSeconds: 30" ] \
    || { echo "lane $l EPP config is not the 300 s forced admission with a 30 s lease; stopping"; exit 1; }
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
{ run_one a 192; run_one a 24; } &
sleep 20
{ run_one b 128; run_one b 32; } &
sleep 20
{ run_one c 96; run_one c 64; } &
wait

restore
trap - EXIT
echo "=== removing the lane EPPs ($(ts))"
for l in a b c; do kubectl delete -f "$RESULTS/lane-epp-$l.yaml" --ignore-not-found >/dev/null; done

echo "=== reports and dashboard bundle ($(ts))"
LABELS=(thunder-60m baseline-60m offload-thunder-60m offload-thunder-lease10-60m offload-thunder-fa300-60m offload-baseline-60m)
POINTS=()
for l in "${LABELS[@]}"; do POINTS+=("$RESULTS/$l"/c*); done
NAMES=(--name baseline-60m="no router" --name thunder-60m="thunder gate (PR3)"
       --name offload-baseline-60m="no router + 400 GiB offload" --name offload-thunder-60m="thunder + 400 GiB offload"
       --name offload-thunder-lease10-60m="thunder lease 10 s + 400 GiB offload"
       --name offload-thunder-fa300-60m="thunder FA 300 s + 400 GiB offload")
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/$LABEL/report" "$RESULTS/$LABEL"/c* > "$RESULTS/report-$LABEL.log" 2>&1
uv run "$SKILL/scripts/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-all/report" "${POINTS[@]}"
uv run "$SKILL/scripts/make_figures.py" --out "$RESULTS/compare-all/report" --baseline baseline-60m "${NAMES[@]}" \
  "$RESULTS/compare-all/report/summary.csv"
uv run "$SKILL/scripts/export_bundle.py" --out "$STEP/../dashboard/data/step24-thunder-pr3-lanes.json" \
  --title "Step 24: thunder PR3 gate vs no router, 400 GiB CPU offload" \
  --description "One vLLM pod per lane (Qwen3-Coder-30B-A3B FP8, TP=2, 2 H100), AgentX Weka trace replay, 60 min per point, 2026-10-09 to 12." \
  --baseline baseline-60m "${NAMES[@]}" "${POINTS[@]}"
echo "=== done ($(ts))"
