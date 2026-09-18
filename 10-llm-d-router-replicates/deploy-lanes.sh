#!/usr/bin/env bash
# Install (or update) the three lanes thunder-lane-a/b/c, one per vLLM pod on
# a distinct node. Each lane's EPP is pinned to its pod with a label selector
# (standalone mode) and starts on the arm config given. Lanes are rendered
# with helm template and applied with kubectl (see render-lane.sh for why),
# so they are not Helm releases; teardown-lanes.sh deletes the manifests.
#
# Usage: ./deploy-lanes.sh [arm]     arm = thunder | sticky (default thunder)
# Lane -> pod assignment is written to results/lanes.env and reused by
# run-replicates.sh. Remove everything with ./teardown-lanes.sh.
set -euo pipefail
NS=llm-d-program-aware-scheduling
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${LLM_D_ROUTER:-$HOME/projects/llmdthunder/llm-d-router}"
CHART="$REPO/config/charts/llm-d-router-standalone"
ARM="${1:-thunder}"
LANES=(a b c)

helm dependency update "$CHART" >/dev/null
mkdir -p "$HERE/results"
kubectl apply -f "$HERE/lane-rbac.yaml" >/dev/null

# One pod per distinct node, same rule as step 08.
PODS=() NODES=()
while read -r name node; do
  skip=""; for n in "${NODES[@]:-}"; do [ "$n" = "$node" ] && skip=1; done
  [ -n "$skip" ] && continue
  NODES+=("$node"); PODS+=("$name")
done < <(kubectl get pods -n "$NS" -l llm-d.ai/role=decode --field-selector=status.phase=Running \
  -o jsonpath='{range .items[*]}{.metadata.name} {.spec.nodeName}{"\n"}{end}' | sort)
[ "${#PODS[@]}" -ge 3 ] || { echo "need 3 pods on distinct nodes, have ${#PODS[@]}" >&2; exit 1; }

: > "$HERE/results/lanes.env"
for i in 0 1 2; do
  L=${LANES[$i]}; P=${PODS[$i]}
  # Clear the label from any other pod first (spot churn can leave stale labels).
  for old in $(kubectl get pods -n "$NS" -l "thunder-lane=$L" -o name); do kubectl label "$old" -n "$NS" thunder-lane- >/dev/null; done
  kubectl label pod "$P" -n "$NS" "thunder-lane=$L" --overwrite >/dev/null
  echo "LANE_${L}_POD=$P" >> "$HERE/results/lanes.env"
  echo "LANE_${L}_IP=$(kubectl get pod "$P" -n "$NS" -o jsonpath='{.status.podIP}')" >> "$HERE/results/lanes.env"
  "$HERE/render-lane.sh" "$L" "$ARM" > "$HERE/results/lane-$L-manifest.yaml"
  kubectl apply -f "$HERE/results/lane-$L-manifest.yaml" >/dev/null
  kubectl rollout status "deploy/thunder-lane-$L-epp" -n "$NS" --timeout=300s >/dev/null
  echo "lane $L: thunder-lane-$L-epp -> pod $P (${NODES[$i]}), arm $ARM"
done
cat "$HERE/results/lanes.env"
