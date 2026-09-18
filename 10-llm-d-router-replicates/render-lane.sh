#!/usr/bin/env bash
# Render one lane's manifests: helm template of the standalone chart with the
# lane values and the arm's plugin config, then fix the one chart defect that
# blocks side-by-side releases in a namespace: the EPP Deployment mounts the
# envoy config map by the hardcoded name "envoy" instead of the configured
# router.proxy.configMap.name. Output goes to stdout.
# Usage: render-lane.sh <lane a|b|c> <arm thunder|sticky>
set -euo pipefail
L=$1; ARM=$2
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${LLM_D_ROUTER:-$HOME/projects/llmdthunder/llm-d-router}"
CHART="$REPO/config/charts/llm-d-router-standalone"
sed "s/__LANE__/$L/g" "$HERE/lane-values-tmpl.yaml" > "$HERE/results/lane-values-$L.yaml"
helm template "thunder-lane-$L" "$CHART" -n llm-d-program-aware-scheduling \
  -f "$HERE/results/lane-values-$L.yaml" \
  --set-file "router.epp.pluginsCustomConfig.thunder-plugins\.yaml=$HERE/$ARM-plugins.yaml" \
  | python3 -c "
import sys, re
doc = sys.stdin.read()
# Only the volume reference: '        - configMap:\n ... name: envoy' -> lane map.
fixed, n = re.subn(r'(- configMap:\n(?:[^\n]*\n){0,4}?\s+name: )envoy\b', r'\g<1>thunder-lane-$L-envoy', doc)
assert n == 1, f'expected exactly one envoy volume reference, found {n}'
sys.stdout.write(fixed)
"
