#!/usr/bin/env bash
set -uo pipefail
NS=llm-d-program-aware-scheduling
for L in a b c; do
  HERE="$(cd "$(dirname "$0")" && pwd)"
  [ -f "$HERE/results/lane-$L-manifest.yaml" ] && kubectl delete -f "$HERE/results/lane-$L-manifest.yaml" --ignore-not-found >/dev/null && echo "removed thunder-lane-$L"
  for p in $(kubectl get pods -n "$NS" -l "thunder-lane=$L" -o name); do kubectl label "$p" -n "$NS" thunder-lane- >/dev/null && echo "unlabeled $p"; done
done
kubectl delete -f "$(cd "$(dirname "$0")" && pwd)/lane-rbac.yaml" --ignore-not-found
