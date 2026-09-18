#!/usr/bin/env bash
# Regenerate deployment.yaml from the live cluster.
# Read-only against the cluster; the only thing written is deployment.yaml here.
set -euo pipefail

NS="${NS:-llm-d-program-aware-scheduling}"
DEPLOY="${DEPLOY:-program-aware-vllm-decode}"
HERE="$(cd "$(dirname "$0")" && pwd)"

kubectl get deploy "$DEPLOY" -n "$NS" -o json > /tmp/deploy-raw.json

RUNNER="python3"
command -v uv >/dev/null 2>&1 && RUNNER="uv run --quiet --with pyyaml python"

$RUNNER - "$HERE/deployment.yaml" <<'PY'
import json, sys, datetime, yaml

out = sys.argv[1]
d = json.load(open('/tmp/deploy-raw.json'))
d.pop('status', None)
m = d['metadata']
for k in ('creationTimestamp', 'generation', 'resourceVersion', 'uid'):
    m.pop(k, None)
m.get('annotations', {}).pop('kubectl.kubernetes.io/last-applied-configuration', None)
d['spec']['template']['metadata'].pop('creationTimestamp', None)
rev = m.get('annotations', {}).get('deployment.kubernetes.io/revision')
today = datetime.date.today().isoformat()

header = f"""# Live manifest of the vLLM model server, exported {today} from
# namespace {d['metadata']['namespace']} on GKE cluster bobbm.
# Deployment revision {rev}: identical to revision 2 except --enable-prompt-tokens-details.
# This is the backend every benchmark in steps 04 to 13 ran against.
#
# Runtime-only fields (status, uid, resourceVersion, generation, creationTimestamp,
# last-applied-configuration) are stripped so this re-applies cleanly.
#
# Prerequisites in the target namespace:
#   - secret llm-d-hf-token with key HF_TOKEN (referenced below, value not included here)
#   - nodes matching the nodeSelector, with 2 free H100 GPUs per replica
"""
with open(out, 'w') as f:
    f.write(header)
    yaml.safe_dump(d, f, sort_keys=False, default_flow_style=False, width=1000)
print(f"wrote {out} (revision {rev})")
PY

echo "verifying it matches the cluster:"
kubectl diff -f "$HERE/deployment.yaml" >/dev/null && echo "  identical to what is running" \
  || echo "  DIFFERS from what is running (see: kubectl diff -f deployment.yaml)"
