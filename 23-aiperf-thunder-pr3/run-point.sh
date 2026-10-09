#!/usr/bin/env bash
# Run one AgentX concurrency point (aiperf --scenario agentx) as a Kubernetes Job
# and copy the artifacts back to results/<label>/c<N>/.
#
# Usage: ./run-point.sh <concurrency> [run-label]
#
# MODE=lane (default): one vLLM pod labeled agentx-lane=a, reached directly
#   through Service agentx-lane (no EPP). Before the point the lane pod is
#   deleted and its replacement labeled, so every point starts on a fresh server.
# MODE=pool: all vLLM pods through the gateway (envoy + EPP); the vLLM deployment
#   and the EPP are restarted before the point.
#
# Shared settings and pin_kube come from step 20's lib.sh, with this step's results.
set -euo pipefail

STEP23="$(cd "$(dirname "$0")" && pwd)"
export STEP_RESULTS="$STEP23/results"
source "$STEP23/../20-cpu-offload-pool/lib.sh"   # NS DEPLOY CTX pin_kube vllm_get

CONC=${1:?usage: run-point.sh <concurrency> [run-label]}
LABEL=${2:-$(date -u +%Y%m%d-%H%M%S)}
MODE=${MODE:-lane}

IMAGE=${IMAGE:-us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/agentx-harness:agentx-v1.0.6}
MODEL=${MODEL:-Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8}
TOKENIZER=${TOKENIZER:-$MODEL}
DATASET=${DATASET:-semianalysis_cc_traces_weka_062126_256k}
DECODE_SELECTOR="llm-d.ai/guide=program-aware-scheduling,llm-d.ai/role=decode"
EPP_DEPLOY=${EPP_DEPLOY:-program-aware-scheduling-epp}
RESTART=${RESTART:-1}
PVC=${PVC:-agentx-data}
CLIENT_POOL=${CLIENT_POOL:-default-pool}
CLIENT_CPU=${CLIENT_CPU:-8}
CLIENT_MEM=${CLIENT_MEM:-32Gi}
DEADLINE_SECONDS=${DEADLINE_SECONDS:-21600}
DURATION=${DURATION:-}       # empty keeps the agentx preset (3600 s)
EXTRA_ARGS=${EXTRA_ARGS:-}   # e.g. "--unsafe-override --num-dataset-entries 8"
case "$MODE" in
  lane) URL=${URL:-http://agentx-lane:8000}; SESSION_ID_HEADER=${SESSION_ID_HEADER:-false} ;;
  pool) URL=${URL:-http://program-aware-scheduling-epp:80}; SESSION_ID_HEADER=${SESSION_ID_HEADER:-true} ;;
  *) echo "MODE must be lane or pool" >&2; exit 1 ;;
esac

OUT="$RESULTS/$LABEL/c$CONC"
REMOTE="/data/results/$LABEL/c$CONC"
JOB=$(echo "agentx-c$CONC-$LABEL" | tr '[:upper:]_.' '[:lower:]--' | cut -c1-63)
mkdir -p "$OUT/meta"
pin_kube
kc() { kubectl -n "$NS" "$@"; }
log() { echo "[$(date -u +%H:%M:%S)] $*"; }
decode_pods() {
  kc get pods -l "$DECODE_SELECTOR" --field-selector=status.phase=Running \
    -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
}
lane_pod() {
  kc get pods -l "$DECODE_SELECTOR,agentx-lane=a" --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}
# pod_identity <pod...>: name uid ip node restarts, one line per pod (LESSONS: a new
# uid or a restart mid-run empties every cache and invalidates the point).
pod_identity() {
  for p in "$@"; do
    kc get pod "$p" -o jsonpath='{.metadata.name} {.metadata.uid} {.status.podIP} {.spec.nodeName} {.status.containerStatuses[0].restartCount}{"\n"}'
  done
}

if kc get job "$JOB" >/dev/null 2>&1; then
  echo "job $JOB already exists; pick another run label" >&2
  exit 1
fi
kc get svc agentx-lane >/dev/null 2>&1 || kc apply -f "$STEP23/lane-svc.yaml"

if [ "$MODE" = lane ]; then
  LANE=$(lane_pod)
  if [ -z "$LANE" ]; then
    LANE=$( [ -n "${LANE_NODE:-}" ] && vllm_pod_on "$LANE_NODE" || decode_pods | head -1 )
    log "labeling $LANE as lane a"
    kc label pod "$LANE" agentx-lane=a --overwrite
  fi
  if [ "$RESTART" = 1 ]; then
    BEFORE=$(decode_pods)
    log "deleting lane pod $LANE for a fresh server (AgentX restarts the server per point)"
    kc delete pod "$LANE" --wait=true
    NEW=""
    for _ in $(seq 1 270); do
      NEW=$(kc get pods -l "$DECODE_SELECTOR" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' \
        | grep -vxF -f <(echo "$BEFORE") | head -1 || true)
      [ -n "$NEW" ] && break
      sleep 10
    done
    [ -n "$NEW" ] || { echo "no replacement vLLM pod appeared" >&2; exit 1; }
    kc wait --for=condition=Ready "pod/$NEW" --timeout=45m
    kc label pod "$NEW" agentx-lane=a --overwrite
    LANE=$NEW
  fi
  TARGETS=$LANE
else
  if [ "$RESTART" = 1 ]; then
    log "restarting deploy/$DEPLOY and deploy/$EPP_DEPLOY"
    kc rollout restart "deploy/$DEPLOY"
    kc rollout status "deploy/$DEPLOY" --timeout=45m
    kc rollout restart "deploy/$EPP_DEPLOY"
    kc rollout status "deploy/$EPP_DEPLOY" --timeout=15m
  fi
  TARGETS=$(decode_pods)
fi
[ -n "$TARGETS" ] || { echo "no running vLLM pods" >&2; exit 1; }
FIRST=$(echo "$TARGETS" | head -1)

# AgentX aborts on the first failed root warmup request, so the endpoint must
# serve a real completion before the Job starts.
log "waiting for $URL to serve a completion"
for i in $(seq 1 30); do
  if kc exec "$FIRST" -c modelserver -- python3 -c "
import json, urllib.request
req = urllib.request.Request('$URL/v1/chat/completions',
    data=json.dumps({'model': '$MODEL', 'max_tokens': 1,
                     'messages': [{'role': 'user', 'content': 'ping'}]}).encode(),
    headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req, timeout=30).read()
" >/dev/null 2>&1; then break; fi
  [ "$i" = 30 ] && { echo "$URL did not serve a completion in 5 minutes" >&2; exit 1; }
  sleep 10
done

METRICS_URLS=""
for p in $TARGETS; do
  METRICS_URLS="$METRICS_URLS http://$(kc get pod "$p" -o jsonpath='{.status.podIP}'):8000/metrics"
done
METRICS_URLS=${METRICS_URLS# }
GPUS_PER_POD=$(kc get "deploy/$DEPLOY" -o jsonpath='{.spec.template.spec.containers[0].resources.limits.nvidia\.com/gpu}')
NUM_PODS=$(echo "$TARGETS" | wc -l | tr -d ' ')
NUM_GPUS=$((GPUS_PER_POD * NUM_PODS))

log "saving server-side metadata to $OUT/meta"
pod_identity $TARGETS > "$OUT/meta/pods-start.txt"
kc get "deploy/$DEPLOY" -o yaml > "$OUT/meta/vllm-deployment.yaml"
[ "$MODE" = lane ] || kc get "deploy/$EPP_DEPLOY" -o yaml > "$OUT/meta/epp-deployment.yaml"
for p in $TARGETS; do
  node=$(kc get pod "$p" -o jsonpath='{.spec.nodeName}')
  kubectl get pods -A --field-selector "spec.nodeName=$node,status.phase=Running" -o wide \
    > "$OUT/meta/node-$node-pods.txt"
  vllm_get "$p" /metrics | grep -E '^vllm:cache_config_info' > "$OUT/meta/cache-config-$p.txt" || true
done
"$STEP23/../model-server/collect.sh" > "$OUT/meta/model-server.txt" 2>&1 || true

DURATION_ARG=""
[ -n "$DURATION" ] && DURATION_ARG="--benchmark-duration $DURATION"

cat > "$OUT/meta/job.yaml" <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: $JOB
  namespace: $NS
  labels: {app: agentx-bench, agentx-label: "$LABEL", agentx-conc: "$CONC"}
spec:
  backoffLimit: 0
  activeDeadlineSeconds: $DEADLINE_SECONDS
  ttlSecondsAfterFinished: 86400
  template:
    metadata:
      labels: {app: agentx-bench}
    spec:
      restartPolicy: Never
      nodeSelector: {cloud.google.com/gke-nodepool: $CLIENT_POOL}
      securityContext: {runAsUser: 1000, runAsGroup: 1000, fsGroup: 1000}
      containers:
      - name: aiperf
        image: $IMAGE
        # The image is distroless: bash and the aiperf venv only, no coreutils.
        args:
        - |
          aiperf profile --scenario agentx \\
            --url $URL --model $MODEL --tokenizer $TOKENIZER \\
            --concurrency $CONC --public-dataset $DATASET $DURATION_ARG \\
            --server-metrics $METRICS_URLS \\
            --server-metrics-formats json csv parquet \\
            --output-artifact-dir $REMOTE/aiperf_artifacts $EXTRA_ARGS
          rc=\$?
          aiperf analyze swim-lane $REMOTE/aiperf_artifacts -c $CONC --html \\
            || echo "swim-lane render failed"
          exit \$rc
        env:
        - {name: HF_HOME, value: /data/hf}
        - {name: AIPERF_DATASET_MMAP_CACHE_DIR, value: /data/mmap}
        - {name: AIPERF_HTTP_X_SESSION_ID_FROM_CORRELATION_ID, value: "$SESSION_ID_HEADER"}
        - {name: AIPERF_SERVER_METRICS_COLLECTION_INTERVAL, value: "1.0"}
        - {name: PYTHONUNBUFFERED, value: "1"}
        resources:
          requests: {cpu: "$CLIENT_CPU", memory: $CLIENT_MEM}
          limits: {memory: $CLIENT_MEM}
        volumeMounts:
        - {name: data, mountPath: /data}
      volumes:
      - name: data
        persistentVolumeClaim: {claimName: $PVC}
EOF

cat > "$OUT/meta/point.json" <<EOF
{
  "label": "$LABEL",
  "mode": "$MODE",
  "concurrency": $CONC,
  "num_gpus": $NUM_GPUS,
  "num_vllm_pods": $NUM_PODS,
  "image": "$IMAGE",
  "model": "$MODEL",
  "dataset": "$DATASET",
  "url": "$URL",
  "server_metrics_urls": "$METRICS_URLS",
  "session_id_header": "$SESSION_ID_HEADER",
  "restart": $RESTART,
  "extra_args": "$EXTRA_ARGS",
  "job": "$JOB",
  "started_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

log "submitting job $JOB (mode $MODE, concurrency $CONC, $NUM_GPUS GPUs)"
kc apply -f "$OUT/meta/job.yaml"

STATUS=""
while :; do
  s=$(kc get job "$JOB" -o jsonpath='{.status.succeeded}/{.status.failed}')
  case "$s" in
    1/*) STATUS=succeeded; break ;;
    */1) STATUS=failed; break ;;
  esac
  sleep 60
  line=$(kc logs "job/$JOB" --tail=1 2>/dev/null || true)
  [ -n "$line" ] && log "${line:0:200}"
done
log "job $STATUS"
kc logs "job/$JOB" > "$OUT/bench-stdout.log" 2>&1 || true

pod_identity $TARGETS > "$OUT/meta/pods-end.txt" 2>&1 || true
POD_CHANGED=false
cmp -s "$OUT/meta/pods-start.txt" "$OUT/meta/pods-end.txt" || POD_CHANGED=true
[ "$POD_CHANGED" = false ] || log "WARNING: a vLLM pod was replaced or restarted during the run; the point is invalid"
cat > "$OUT/meta/finish.json" <<EOF
{"finished_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "job_status": "$STATUS", "pod_changed": $POD_CHANGED}
EOF

# kubectl cp needs tar, which the distroless image lacks, so read the PVC from busybox.
FETCH="agentx-fetch-$(date +%s)"
kc run "$FETCH" --image=busybox:1.36 --restart=Never \
  --overrides="{\"spec\":{\"nodeSelector\":{\"cloud.google.com/gke-nodepool\":\"$CLIENT_POOL\"},\"volumes\":[{\"name\":\"data\",\"persistentVolumeClaim\":{\"claimName\":\"$PVC\",\"readOnly\":true}}],\"containers\":[{\"name\":\"fetch\",\"image\":\"busybox:1.36\",\"command\":[\"sleep\",\"3600\"],\"volumeMounts\":[{\"name\":\"data\",\"mountPath\":\"/data\",\"readOnly\":true}]}]}}"
kc wait --for=condition=Ready "pod/$FETCH" --timeout=10m
kc cp "$FETCH:$REMOTE/aiperf_artifacts" "$OUT/aiperf_artifacts"
kc delete pod "$FETCH" --wait=false

log "artifacts in $OUT"
[ "$STATUS" = succeeded ] && [ "$POD_CHANGED" = false ]
