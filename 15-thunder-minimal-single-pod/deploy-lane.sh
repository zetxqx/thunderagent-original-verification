#!/usr/bin/env bash
# Install one step 10 style lane (thunder-lane-a) on one vLLM pod, running the
# minimal thunder-agent build with the thunder-min arm config. Lane files and
# lanes.env go to this step's results/, so step 10's records stay untouched.
# Usage: ./deploy-lane.sh [image-tag]    (default thunder-agent-min-33dde5d2)
# Remove with: kubectl delete -f results/lane-a-manifest.yaml; kubectl label pod <pod> thunder-lane-
set -euo pipefail
NS=llm-d-program-aware-scheduling
HERE="$(cd "$(dirname "$0")" && pwd)"
STEP10="$HERE/../10-llm-d-router-replicates"
REPO="${LLM_D_ROUTER:-$HOME/projects/llmdthunder/llm-d-router}"
export EPP_IMAGE_TAG="${1:-thunder-agent-min-33dde5d2}"
export RESULTS_DIR="$HERE/results"
L=a

helm dependency update "$REPO/config/charts/llm-d-router-standalone" >/dev/null
kubectl apply -f "$STEP10/lane-rbac.yaml" >/dev/null

P=$(kubectl get pods -n "$NS" -l llm-d.ai/role=decode --field-selector=status.phase=Running \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' | sort | head -1)
[ -n "$P" ] || { echo "no running vLLM pod" >&2; exit 1; }
for old in $(kubectl get pods -n "$NS" -l "thunder-lane=$L" -o name); do kubectl label "$old" -n "$NS" thunder-lane- >/dev/null; done
kubectl label pod "$P" -n "$NS" "thunder-lane=$L" --overwrite >/dev/null
{ echo "LANE_${L}_POD=$P"; echo "LANE_${L}_IP=$(kubectl get pod "$P" -n "$NS" -o jsonpath='{.status.podIP}')"; } > "$RESULTS_DIR/lanes.env"

"$STEP10/render-lane.sh" "$L" thunder-min > "$RESULTS_DIR/lane-$L-manifest.yaml"
kubectl apply -f "$RESULTS_DIR/lane-$L-manifest.yaml" >/dev/null
kubectl rollout restart "deploy/thunder-lane-$L-epp" -n "$NS" >/dev/null
kubectl rollout status "deploy/thunder-lane-$L-epp" -n "$NS" --timeout=300s >/dev/null
echo "lane $L: thunder-lane-$L-epp -> pod $P, image $EPP_IMAGE_TAG"
cat "$RESULTS_DIR/lanes.env"
