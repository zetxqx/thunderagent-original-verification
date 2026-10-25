#!/usr/bin/env bash
# Render the step 38 (GLM-5.2 2P1D) P/D thunder EPP; same image, chart and mechanics as steps 34 and 36.
# Render the P/D thunder EPP (release agentx-epp-<lane>-epp) for cluster a4-pr: chart from the
# PR #15 commit (8d1fbc87, the image's commit), image thunder-pd-8d1fbc87, plugin config
# thunder-pd-plugins.yaml, minus the chart's RBAC objects (file discovery needs none; our account
# cannot create Roles on a4-pr). Same mechanics as step 31's render-epp.sh.
#   ./render-epp.sh <lane> > results/lane-epp-<lane>.yaml && kubectl apply -f results/lane-epp-<lane>.yaml
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
LANE=${1:?lane}
PLUGINS=${PLUGINS:-$HERE/thunder-pd-plugins.yaml}
ROUTER_REPO=${ROUTER_REPO:-$HERE/../../../llm-d-router}
COMMIT=8d1fbc87
CHARTS=$(mktemp -d)
trap 'rm -rf "$CHARTS"' EXIT
git -C "$ROUTER_REPO" rev-parse -q --verify "$COMMIT^{commit}" >/dev/null \
  || git -C "$ROUTER_REPO" fetch -q origin thunder-agent-pd
git -C "$ROUTER_REPO" archive "$COMMIT" config/charts | tar -x -C "$CHARTS"
CHART_DIR="$CHARTS/config/charts" NS=bobzetian-llmd EXTRA_VALUES="$HERE/epp-values-pd-thunder.yaml" \
  "$HERE/../../.claude/skills/agentic-benchmark/scripts/render-lane-epp.sh" "$LANE" "$PLUGINS" thunder-pd-8d1fbc87 \
  | python3 -c "
import sys
docs = sys.stdin.read().split('\n---\n')
rbac = ('kind: ClusterRole\n', 'kind: ClusterRoleBinding\n', 'kind: Role\n', 'kind: RoleBinding\n')
sys.stdout.write('\n---\n'.join(d for d in docs if not any(k in d for k in rbac)))
"
