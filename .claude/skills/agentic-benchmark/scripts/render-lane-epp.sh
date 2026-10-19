#!/usr/bin/env bash
# Render one lane EPP release: an EPP and envoy that see only the vLLM pod labeled
# agentx-lane=<lane>, running the given plugin config. Manifests go to stdout:
#   render-lane-epp.sh b ../manifests/epp/thunder-pr3-plugins.yaml | kubectl apply -f -
# Usage: render-lane-epp.sh <lane> <plugins.yaml> [epp-image-tag]
# The image tag defaults to the profile's EPP_IMAGE_TAG; CHART_DIR (or the profile's
# EPP_CHART_DIR) is the llm-d-router charts folder matching the image (default: the
# PR3 worktree next to the repo). EXTRA_VALUES: an optional values file applied last
# (cluster-specific overrides, e.g. node affinity). The chart is copied to a temp
# folder for `helm dependency update`, so the worktree is not touched.
set -euo pipefail
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPTS/lib.sh"
# bobbm default image: PR3 plus the Produces() fix (24-thunder-pr3-lanes/thunder-produces.patch);
# plain PR3 rejects its own request-attribute write and fails every request.
L=${1:?lane}; PLUGINS=${2:?plugins file}; TAG=${3:-$EPP_IMAGE_TAG}
CHART_DIR=${CHART_DIR:-${EPP_CHART_DIR:-$REPO_ROOT/../llm-d-router-thunder-lease/config/charts}}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp -R "$CHART_DIR/llm-d-router-standalone" "$CHART_DIR/routerlib" "$TMP/"
helm dependency update "$TMP/llm-d-router-standalone" >/dev/null
sed -e "s/__LANE__/$L/g" -e "s/__TAG__/$TAG/" "$SCRIPTS/../manifests/lane-epp-values.yaml" > "$TMP/values.yaml"
helm template "agentx-epp-$L" "$TMP/llm-d-router-standalone" -n "$NS" -f "$TMP/values.yaml" ${EXTRA_VALUES:+-f "$EXTRA_VALUES"} \
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
