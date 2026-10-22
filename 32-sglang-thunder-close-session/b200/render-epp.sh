#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
RELEASE=${1:-sglang}
PLUGINS=${2:-$HERE/thunder-close-plugins.yaml}
ROUTER_REPO=${ROUTER_REPO:-/usr/local/google/home/bobzetian/projects/playground/llm-d-router}
CHART_DIR="$ROUTER_REPO/config/charts"
CHART_DIR="$CHART_DIR" NS=bobzetian-llmd EXTRA_VALUES="$HERE/epp-values-sglang.yaml" \
  "$HERE/../../.claude/skills/agentic-benchmark/scripts/render-lane-epp.sh" "$RELEASE" "$PLUGINS" "thunder-sglang-close-7eec9d9c" \
  | python3 -c "
import sys
docs = sys.stdin.read().split('\n---\n')
rbac = ('kind: ClusterRole\n', 'kind: ClusterRoleBinding\n', 'kind: Role\n', 'kind: RoleBinding\n')
sys.stdout.write('\n---\n'.join(d for d in docs if not any(k in d for k in rbac)))
"
