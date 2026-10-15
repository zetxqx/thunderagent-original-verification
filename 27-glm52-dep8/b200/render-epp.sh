#!/usr/bin/env bash
# Render the thunder lane EPP for cluster a4-pr: the skill's render-lane-epp.sh
# with this step's values, minus the chart's RBAC objects (our account cannot
# create Roles or ClusterRoles on a4-pr; file discovery needs none).
#   ./render-epp.sh [plugins.yaml] [values.yaml] [lane] > lane-epp-a.yaml && kubectl apply -f lane-epp-a.yaml
# lane names the release (agentx-epp-<lane>-epp); default a. EPP_TAG picks the
# EPP image tag (default: render-lane-epp.sh's).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PLUGINS=${1:-$HERE/thunder-plugins.yaml}
VALUES=${2:-$HERE/epp-values-a4pr.yaml}
LANE=${3:-a}
NS=bobzetian-llmd EXTRA_VALUES="$VALUES" \
  "$HERE/../../.claude/skills/agentic-benchmark/scripts/render-lane-epp.sh" "$LANE" "$PLUGINS" ${EPP_TAG:+"$EPP_TAG"} \
  | python3 -c "
import sys
docs = sys.stdin.read().split('\n---\n')
rbac = ('kind: ClusterRole\n', 'kind: ClusterRoleBinding\n', 'kind: Role\n', 'kind: RoleBinding\n')
sys.stdout.write('\n---\n'.join(d for d in docs if not any(k in d for k in rbac)))
"
