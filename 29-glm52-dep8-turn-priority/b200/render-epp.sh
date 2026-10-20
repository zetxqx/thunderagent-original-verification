#!/usr/bin/env bash
# Render a step 29 lane EPP for cluster a4-pr: llm-d-router v1.0.0 (chart and image of the
# v1.0.0 tag) with the DEP=8 turn-priority plugin config (flow control + session affinity),
# minus the chart's RBAC objects (our account cannot create Roles or ClusterRoles on a4-pr;
# file discovery needs none). Same mechanics as step 28's render-epp.sh.
#   ./render-epp.sh <lane> <server b|c> > lane-epp-<lane>.yaml && kubectl apply -f lane-epp-<lane>.yaml
# lane names the release (agentx-epp-<lane>-epp); server picks epp-values-v1-<server>.yaml,
# whose endpoints file lists the 8 rank ports of that server's vLLM Service.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LANE=${1:?lane}; SERVER=${2:?server b|c}
PLUGINS=${PLUGINS:-$HERE/dep8-turn-priority-plugins.yaml}
ROUTER_REPO=${ROUTER_REPO:-$HERE/../../../llm-d-router}
CHARTS=$(mktemp -d)
trap 'rm -rf "$CHARTS"' EXIT
git -C "$ROUTER_REPO" rev-parse -q --verify v1.0.0^{commit} >/dev/null \
  || git -C "$ROUTER_REPO" fetch -q https://github.com/llm-d/llm-d-router.git refs/tags/v1.0.0:refs/tags/v1.0.0
git -C "$ROUTER_REPO" archive v1.0.0 config/charts | tar -x -C "$CHARTS"
CHART_DIR="$CHARTS/config/charts" NS=bobzetian-llmd EXTRA_VALUES="$HERE/epp-values-v1-$SERVER.yaml" \
  "$HERE/../../.claude/skills/agentic-benchmark/scripts/render-lane-epp.sh" "$LANE" "$PLUGINS" v1.0.0 \
  | python3 -c "
import sys
docs = sys.stdin.read().split('\n---\n')
rbac = ('kind: ClusterRole\n', 'kind: ClusterRoleBinding\n', 'kind: Role\n', 'kind: RoleBinding\n')
sys.stdout.write('\n---\n'.join(d for d in docs if not any(k in d for k in rbac)))
"
