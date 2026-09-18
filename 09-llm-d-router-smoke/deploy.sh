#!/usr/bin/env bash
# Upgrade the existing Helm release of the EPP to the thunder-agent-v3 image
# and the step 09 plugin config. Everything else in the release is reused.
# Revert: helm rollback program-aware-scheduling <previous revision> -n $NS
set -euo pipefail

NS=llm-d-program-aware-scheduling
RELEASE=program-aware-scheduling
TAG="${1:-thunder-agent-v3}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${LLM_D_ROUTER:-$HOME/projects/llmdthunder/llm-d-router}"
CHART="$REPO/config/charts/llm-d-router-standalone"

PREV=$(helm history "$RELEASE" -n "$NS" --max 1 -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)[-1]["revision"])')
echo "previous revision: $PREV"
helm dependency update "$CHART" >/dev/null

# Pass the previous release's user-supplied values as a file rather than
# --reuse-values: in Helm 3, --reuse-values also swaps in the OLD chart's
# default values, and the release was last deployed from a newer chart whose
# envoy template needs helpers this checkout's chart does not define.
VALUES="$HERE/results/values-rev$PREV-user-supplied.yaml"
helm get values "$RELEASE" -n "$NS" -o yaml > "$VALUES"

helm upgrade "$RELEASE" "$CHART" -n "$NS" \
  -f "$VALUES" \
  --set "router.epp.image.tag=$TAG" \
  --set-file "router.epp.pluginsCustomConfig.thunder-plugins\.yaml=$HERE/thunder-plugins.yaml" \
  --wait --timeout 5m

kubectl rollout status deploy/program-aware-scheduling-epp -n "$NS" --timeout=5m
POD=$(kubectl get pod -n "$NS" -l app.kubernetes.io/component=inference-scheduler -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
[ -n "$POD" ] || POD=$(kubectl get pod -n "$NS" -o name | grep program-aware-scheduling-epp | head -1 | sed 's|pod/||')
echo "epp pod: $POD"
echo "image:   $(kubectl get pod "$POD" -n "$NS" -o jsonpath='{.spec.containers[?(@.name=="epp")].image}')"
echo "--- startup log lines (build, plugins, flow control) ---"
kubectl logs "$POD" -n "$NS" -c epp | grep -iE '"build"|thunder|flowControl|flow control|error' | head -20
