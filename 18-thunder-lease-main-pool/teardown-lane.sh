#!/usr/bin/env bash
# Remove the step 18 lane: its rendered manifest and the pod label.
set -uo pipefail
NS=llm-d-program-aware-scheduling
HERE="$(cd "$(dirname "$0")" && pwd)"
kubectl delete -f "$HERE/results/lane-a-manifest.yaml" --ignore-not-found >/dev/null
for p in $(kubectl get pods -n "$NS" -l thunder-lane=a -o name); do kubectl label "$p" -n "$NS" thunder-lane- >/dev/null; done
echo "lane a removed"
