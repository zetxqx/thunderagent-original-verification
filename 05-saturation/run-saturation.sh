#!/usr/bin/env bash
# Run the saturation benchmark as an in-cluster Job, wait for completion,
# copy the results locally, and clean up the Job.
set -euo pipefail

NS=llm-d-program-aware-scheduling
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_ID="sat-$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$SCRIPT_DIR/results/$RUN_ID"

echo "run id: $RUN_ID"

kubectl create configmap thunderagent-bench-script \
  --from-file=benchmark.py="$SCRIPT_DIR/../04-benchmark/benchmark.py" \
  -n "$NS" --dry-run=client -o yaml | kubectl apply -f -

kubectl delete job thunderagent-saturation-bench -n "$NS" --ignore-not-found
sed "s/RUN_ID_PLACEHOLDER/$RUN_ID/" "$SCRIPT_DIR/job.yaml" | kubectl apply -f -

echo "waiting for bench pod..."
kubectl wait pod -l app=thunderagent-saturation-bench -n "$NS" \
  --for=condition=Ready --timeout=300s
POD=$(kubectl get pod -l app=thunderagent-saturation-bench -n "$NS" \
  -o jsonpath='{.items[0].metadata.name}')
echo "pod: $POD; polling for completion (router paused counts shown live)"

while ! kubectl exec "$POD" -n "$NS" -- test -f /results/DONE 2>/dev/null; do
  PAUSED=$(kubectl exec deploy/thunderagent-original -n "$NS" -- \
    python -c "import urllib.request,json;h=json.load(urllib.request.urlopen('http://localhost:8300/health'));print(h['programs_count'],h['reasoning_count'],h['acting_count'],h['paused_count'])" 2>/dev/null || echo "n/a")
  echo "$(date +%H:%M:%S) programs/reasoning/acting/paused: $PAUSED"
  sleep 15
done

mkdir -p "$OUT_DIR"
kubectl cp "$NS/$POD:/results/$RUN_ID" "$OUT_DIR" >/dev/null
kubectl cp "$NS/$POD:/results/stdout.log" "$OUT_DIR/stdout.log" >/dev/null
kubectl delete job thunderagent-saturation-bench -n "$NS"

echo
tail -20 "$OUT_DIR/stdout.log"
echo
echo "results: $OUT_DIR"
