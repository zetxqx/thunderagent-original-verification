#!/usr/bin/env bash
# Render one lane EPP release: an EPP and envoy that see only the vLLM pod labeled
# agentx-lane=<lane>, running the given plugin config. Manifests go to stdout:
#   render-lane-epp.sh b ../manifests/epp/thunder-pr3-plugins.yaml | kubectl apply -f -
# Usage: render-lane-epp.sh <lane> <plugins.yaml> [epp-image-tag]
# CHART_DIR: the llm-d-router charts folder matching the image (default: the PR3
# worktree). The chart is copied to a temp folder for `helm dependency update`, so
# the worktree is not touched.
set -euo pipefail
L=${1:?lane}; PLUGINS=${2:?plugins file}; TAG=${3:-thunder-agent-pr3-a025437b}
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPTS/lib.sh"
CHART_DIR=${CHART_DIR:-$REPO_ROOT/../llm-d-router-thunder-lease/config/charts}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp -R "$CHART_DIR/llm-d-router-standalone" "$CHART_DIR/routerlib" "$TMP/"
helm dependency update "$TMP/llm-d-router-standalone" >/dev/null
sed -e "s/__LANE__/$L/g" -e "s/__TAG__/$TAG/" "$SCRIPTS/../manifests/lane-epp-values.yaml" > "$TMP/values.yaml"
helm template "agentx-epp-$L" "$TMP/llm-d-router-standalone" -n "$NS" -f "$TMP/values.yaml" \
  --set-file "router.epp.pluginsCustomConfig.thunder-plugins\.yaml=$PLUGINS" \
  | python3 -c "
import sys, re
doc = sys.stdin.read()
# The chart mounts the envoy config map by the hardcoded name 'envoy' (the main
# release's map); point the volume at this lane's map.
fixed, n = re.subn(r'(- configMap:\n(?:[^\n]*\n){0,4}?\s+name: )\x27?envoy\x27?(?=\s)', r'\g<1>agentx-epp-$L-envoy', doc)
assert n == 1, f'expected exactly one envoy volume reference, found {n}'
sys.stdout.write(fixed)
"
