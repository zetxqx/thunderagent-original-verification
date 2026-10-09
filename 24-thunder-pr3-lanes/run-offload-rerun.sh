#!/usr/bin/env bash
# Step 24 phase 2 rerun: the offload-thunder points that failed in run-offload.sh.
#   c=64 and c=32: run-point.sh's claim bug (a lane restarting next to others could
#     find no "fresh" pod; fixed: any unclaimed pod is fresh);
#   c=128: one root warmup request got envoy's 503 "reset before headers: connection
#     termination" (envoy reused an upstream connection vLLM had just closed at its
#     5 s keep-alive; fixed: lane envoy idle_timeout 4 s).
# Waits for run-offload.sh, moves the failed points to offload-thunder-60m-invalid/,
# turns offloading back on, redeploys the lane EPPs with the envoy fix, reruns the
# three points, restores the original deployment on every exit path, and rebuilds the
# four-arm comparison.
#   nohup caffeinate -i ./run-offload-rerun.sh > results/run-offload-rerun.log 2>&1 &
set -uo pipefail

STEP="$(cd "$(dirname "$0")" && pwd)"
SKILL="$STEP/../.claude/skills/agentic-benchmark"
export RESULTS="$STEP/results"
source "$SKILL/scripts/lib.sh"   # NS, DEPLOY, pin_kube, vllm_get
pin_kube
export CLIENT_CPU=4
EPP_TAG=thunder-agent-pr3-a025437b-produces
RERUN="128 64 32"
ts() { date -u +%H:%M:%S; }

echo "=== waiting for run-offload.sh ($(ts))"
until grep -q "=== done" "$RESULTS/run-offload.log" 2>/dev/null; do
  pgrep -f "run-offload.sh" >/dev/null || { echo "run-offload.sh stopped without finishing; rerun not started"; exit 1; }
  sleep 120
done
pin_kube

echo "=== archiving the failed points ($(ts))"
mkdir -p "$RESULTS/offload-thunder-60m-invalid"
for c in $RERUN; do
  [ -d "$RESULTS/offload-thunder-60m/c$c" ] && mv "$RESULTS/offload-thunder-60m/c$c" "$RESULTS/offload-thunder-60m-invalid/c$c"
  kubectl -n "$NS" delete job "agentx-c$c-offload-thunder-60m" --ignore-not-found --wait=true
done
for pvc in agentx-data agentx-data-b agentx-data-c agentx-data-d; do
  pod="agentx-clean-$pvc-$(date +%s)"
  kubectl -n "$NS" run "$pod" --image=busybox:1.36 --restart=Never --overrides="{\"spec\":{\"nodeSelector\":{\"cloud.google.com/gke-nodepool\":\"default-pool\"},\"volumes\":[{\"name\":\"data\",\"persistentVolumeClaim\":{\"claimName\":\"$pvc\"}}],\"containers\":[{\"name\":\"c\",\"image\":\"busybox:1.36\",\"command\":[\"sh\",\"-c\",\"rm -rf /data/results/offload-thunder-60m/c128 /data/results/offload-thunder-60m/c64 /data/results/offload-thunder-60m/c32\"],\"volumeMounts\":[{\"name\":\"data\",\"mountPath\":\"/data\"}]}]}}" >/dev/null
  kubectl -n "$NS" wait --for=jsonpath='{.status.phase}'=Succeeded "pod/$pod" --timeout=10m >/dev/null && echo "cleaned $pvc"
  kubectl -n "$NS" delete pod "$pod" --wait=false >/dev/null
done

restore() {
  echo "=== restoring the original vLLM deployment ($(ts))"
  kubectl replace -f "$RESULTS/vllm-deploy-before.json"
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=45m
}
trap restore EXIT

echo "=== offloading on again ($(ts))"
kubectl replace -f "$RESULTS/vllm-deploy-offload400.json"
kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=60m \
  || echo "not every replica became ready; running on the ready ones"
READY=$(kubectl -n "$NS" get pods -l llm-d.ai/role=decode \
  -o jsonpath='{range .items[?(@.status.containerStatuses[0].ready==true)]}{.metadata.name}{"\n"}{end}')
N=$(echo "$READY" | grep -c . || true)
[ "$N" -ge 1 ] || { echo "no ready vLLM pod with offloading"; exit 1; }
[ "$N" -gt 3 ] && N=3   # three points
LANES=$(echo "a b c" | cut -d' ' -f1-"$N")
export LANES
echo "ready pods: $(echo "$READY" | grep -c .), lanes: $LANES"

echo "=== lane EPPs with the envoy idle timeout ($(ts))"
for l in a b c d; do
  "$SKILL/scripts/render-lane-epp.sh" "$l" "$SKILL/manifests/epp/thunder-pr3-plugins.yaml" "$EPP_TAG" > "$RESULTS/lane-epp-$l.yaml"
  kubectl apply -f "$RESULTS/lane-epp-$l.yaml" >/dev/null
done
for l in $LANES; do kubectl -n "$NS" rollout status "deploy/agentx-epp-$l-epp" --timeout=10m; done

echo "=== offload thunder rerun ($(ts))"
LANE_EPP=1 "$SKILL/scripts/run-lanes.sh" offload-thunder-60m $RERUN

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
