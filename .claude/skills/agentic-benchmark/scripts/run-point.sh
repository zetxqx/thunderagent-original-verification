#!/usr/bin/env bash
# Run one AgentX concurrency point (aiperf --scenario agentx) as a Kubernetes Job
# and copy the artifacts back to $RESULTS/<label>/c<N>/.
#
# Usage: RESULTS=<step>/results run-point.sh <concurrency> [run-label]
#
# MODE=lane (default): one vLLM pod labeled agentx-lane=$LANE (a, b, c, ...),
#   reached directly through Service agentx-lane-$LANE (no EPP). Before the point
#   the lane pod is deleted and a fresh replacement claimed, so every point starts
#   on a fresh server. Lanes run in parallel, one point per vLLM pod, each with its
#   own PVC (agentx-data for lane a, agentx-data-<lane> otherwise; RWO).
#   LANE_EPP=1: the lane goes through its own EPP, deploy/agentx-epp-<lane>-epp,
#   rendered by render-lane-epp.sh and watching only this lane's pod. The lane EPP
#   is restarted after the fresh pod is claimed, X-Session-ID is sent and the EPP
#   metrics are scraped, as in pool mode.
# MODE=pool: the vLLM pods matching DECODE_SELECTOR through an EPP (URL,
#   EPP_DEPLOY); the vLLM deployment and the EPP are restarted before the point.
#   A native sidecar scrapes the EPP metrics port every 10 s (EPP_SCRAPE=0 to skip).
#
# The EPP's plugin config (the arm) is set by the caller before the point;
# this script only records it in meta/.
set -euo pipefail

SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPTS/lib.sh"   # NS DEPLOY CTX RESULTS pin_kube vllm_get vllm_pod_on deploy_selector

CONC=${1:?usage: run-point.sh <concurrency> [run-label]}
LABEL=${2:-$(date -u +%Y%m%d-%H%M%S)}
MODE=${MODE:-lane}
LANE=${LANE:-a}
LANE_EPP=${LANE_EPP:-0}
case "$LANE" in *[!a-z0-9]*|"") echo "LANE must be lowercase letters or digits" >&2; exit 1 ;; esac

IMAGE=${IMAGE:-us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/agentx-harness:agentx-v1.0.6}
MODEL=${MODEL:-Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8}
TOKENIZER=${TOKENIZER:-$MODEL}
DATASET=${DATASET:-semianalysis_cc_traces_weka_062126_256k}
DECODE_SELECTOR=${DECODE_SELECTOR:-llm-d.ai/guide=program-aware-scheduling,llm-d.ai/role=decode}
EPP_DEPLOY=${EPP_DEPLOY:-program-aware-scheduling-epp}
EPP_METRICS_PORT=${EPP_METRICS_PORT:-9090}
RESTART=${RESTART:-1}
if [ "$LANE" = a ]; then PVC=${PVC:-agentx-data}; else PVC=${PVC:-agentx-data-$LANE}; fi
CLIENT_POOL=${CLIENT_POOL:-default-pool}
CLIENT_CPU=${CLIENT_CPU:-8}
CLIENT_MEM=${CLIENT_MEM:-32Gi}
DEADLINE_SECONDS=${DEADLINE_SECONDS:-21600}
DURATION=${DURATION:-}       # empty keeps the agentx preset (3600 s)
EXTRA_ARGS=${EXTRA_ARGS:-}   # e.g. "--unsafe-override --num-dataset-entries 8"
case "$MODE" in
  lane)
    if [ "$LANE_EPP" = 1 ]; then
      EPP_DEPLOY=agentx-epp-$LANE-epp
      URL=${URL:-http://agentx-epp-$LANE-epp:80}; SESSION_ID_HEADER=${SESSION_ID_HEADER:-true}; EPP_SCRAPE=${EPP_SCRAPE:-1}
    else
      URL=${URL:-http://agentx-lane-$LANE:8000}; SESSION_ID_HEADER=${SESSION_ID_HEADER:-false}; EPP_SCRAPE=0
    fi ;;
  pool) URL=${URL:-http://program-aware-scheduling-epp:80}; SESSION_ID_HEADER=${SESSION_ID_HEADER:-true}; EPP_SCRAPE=${EPP_SCRAPE:-1} ;;
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
  kc get pods -l "$DECODE_SELECTOR,agentx-lane=$LANE" --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}
# claim <pod>: label an unclaimed pod for this lane. The resource-version guard makes
# the claim atomic, so lanes restarting at the same time never share a pod.
claim() {
  local rv lane
  read -r rv lane < <(kc get pod "$1" -o jsonpath='{.metadata.resourceVersion} {.metadata.labels.agentx-lane}' 2>/dev/null)
  [ -n "$rv" ] && [ -z "$lane" ] && kc label pod "$1" "agentx-lane=$LANE" --resource-version="$rv" >/dev/null 2>&1
}
unclaimed_pods() {
  kc get pods -l "$DECODE_SELECTOR,!agentx-lane" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
}
# A lane's first pod must be Ready: a pod still starting is the fresh replacement
# another lane is about to claim.
unclaimed_ready_pods() {
  kc get pods -l "$DECODE_SELECTOR,!agentx-lane" \
    -o jsonpath='{range .items[?(@.status.containerStatuses[0].ready==true)]}{.metadata.name}{"\n"}{end}'
}
epp_pods() {
  kc get pods -l "$(deploy_selector "$EPP_DEPLOY")" --field-selector=status.phase=Running \
    -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'
}
# pod_identity <pod...>: name uid ip node restarts-per-container, one line per pod.
# A new uid or a restart mid-run empties every cache (or the gate's ledger) and
# invalidates the point.
pod_identity() {
  for p in "$@"; do
    kc get pod "$p" -o jsonpath='{.metadata.name} {.metadata.uid} {.status.podIP} {.spec.nodeName} {range .status.containerStatuses[*]}{.restartCount},{end}{"\n"}'
  done
}

if kc get job "$JOB" >/dev/null 2>&1; then
  echo "job $JOB already exists; pick another run label" >&2
  exit 1
fi
if [ "$MODE" = lane ]; then
  kc apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Service
metadata: {name: agentx-lane-$LANE, namespace: $NS}
spec:
  selector: {llm-d.ai/guide: program-aware-scheduling, llm-d.ai/role: decode, agentx-lane: "$LANE"}
  ports: [{name: http, port: 8000, targetPort: 8000}]
EOF
fi
kc get pvc "$PVC" >/dev/null 2>&1 || kc apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {name: $PVC, namespace: $NS}
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: standard-rwo
  resources: {requests: {storage: 200Gi}}
EOF

EPPS=""
if [ "$MODE" = lane ]; then
  # Lanes never remove their label, so an unclaimed pod has served no point: it is fresh.
  POD=$(lane_pod)
  FRESH=0
  if [ -z "$POD" ]; then
    CANDS=$(unclaimed_ready_pods)
    if [ -n "${LANE_NODE:-}" ]; then  # the pod on LANE_NODE first
      PREF=$(vllm_pod_on "$LANE_NODE")
      CANDS="$(echo "$CANDS" | grep -xF "$PREF" || true) $(echo "$CANDS" | grep -vxF "$PREF" || true)"
    fi
    for p in $CANDS; do
      claim "$p" && { POD=$p; break; }
    done
    [ -n "$POD" ] || { echo "no unclaimed vLLM pod for lane $LANE" >&2; exit 1; }
    log "claimed $POD as lane $LANE (fresh: it has served no point)"
    FRESH=1
  fi
  if [ "$RESTART" = 1 ] && [ "$FRESH" = 0 ]; then
    log "lane $LANE: deleting $POD for a fresh server (AgentX restarts the server per point)"
    kc delete pod "$POD" --wait=true
    POD=""
    # Any unclaimed pod is fresh, including one created by another lane's restart a
    # moment earlier: lanes restarting together each take one, and none starves.
    for _ in $(seq 1 270); do
      for p in $(unclaimed_pods); do
        claim "$p" && { POD=$p; break; }
      done
      [ -n "$POD" ] && break
      sleep 10
    done
    [ -n "$POD" ] || { echo "no fresh vLLM pod could be claimed for lane $LANE" >&2; exit 1; }
    log "lane $LANE: claimed fresh pod $POD"
    kc wait --for=condition=Ready "pod/$POD" --timeout=45m
  fi
  if [ "$LANE_EPP" = 1 ]; then
    kc get "deploy/$EPP_DEPLOY" >/dev/null 2>&1 \
      || { echo "deploy/$EPP_DEPLOY missing: render-lane-epp.sh $LANE <plugins.yaml> | kubectl apply -f -" >&2; exit 1; }
    log "lane $LANE: restarting deploy/$EPP_DEPLOY (fresh gate ledger, sees the new pod)"
    kc rollout restart "deploy/$EPP_DEPLOY"
    kc rollout status "deploy/$EPP_DEPLOY" --timeout=15m
    EPPS=$(epp_pods)
    [ -n "$EPPS" ] || { echo "no running pod for deploy/$EPP_DEPLOY" >&2; exit 1; }
  fi
  TARGETS=$POD
else
  if [ "$RESTART" = 1 ]; then
    log "restarting deploy/$DEPLOY and deploy/$EPP_DEPLOY"
    kc rollout restart "deploy/$DEPLOY"
    kc rollout status "deploy/$DEPLOY" --timeout=45m
    kc rollout restart "deploy/$EPP_DEPLOY"
    kc rollout status "deploy/$EPP_DEPLOY" --timeout=15m
  fi
  TARGETS=$(decode_pods)
  EPPS=$(epp_pods)
  [ -n "$EPPS" ] || { echo "no running pod for deploy/$EPP_DEPLOY" >&2; exit 1; }
fi
[ -n "$TARGETS" ] || { echo "no running vLLM pods" >&2; exit 1; }
# The cluster autoscaler evicted a lane pod mid-run once (node scale-down); pods
# serving a point must not be evictable.
for p in $TARGETS; do
  kc annotate pod "$p" cluster-autoscaler.kubernetes.io/safe-to-evict=false --overwrite >/dev/null
done
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
EPP_METRICS_URLS=""
for p in $EPPS; do
  EPP_METRICS_URLS="$EPP_METRICS_URLS http://$(kc get pod "$p" -o jsonpath='{.status.podIP}'):$EPP_METRICS_PORT/metrics"
done
EPP_METRICS_URLS=${EPP_METRICS_URLS# }
GPUS_PER_POD=$(kc get "deploy/$DEPLOY" -o jsonpath='{.spec.template.spec.containers[0].resources.limits.nvidia\.com/gpu}')
NUM_PODS=$(echo "$TARGETS" | wc -l | tr -d ' ')
NUM_GPUS=$((GPUS_PER_POD * NUM_PODS))

log "saving server-side metadata to $OUT/meta"
pod_identity $TARGETS $EPPS > "$OUT/meta/pods-start.txt"
kc get "deploy/$DEPLOY" -o yaml > "$OUT/meta/vllm-deployment.yaml"
if [ -n "$EPPS" ]; then
  kc get "deploy/$EPP_DEPLOY" -o yaml > "$OUT/meta/epp-deployment.yaml"
  for cm in $(kc get "deploy/$EPP_DEPLOY" -o jsonpath='{.spec.template.spec.volumes[*].configMap.name}'); do
    kc get configmap "$cm" -o yaml > "$OUT/meta/epp-configmap-$cm.yaml"
  done
fi
for p in $TARGETS; do
  node=$(kc get pod "$p" -o jsonpath='{.spec.nodeName}')
  kubectl get pods -A --field-selector "spec.nodeName=$node,status.phase=Running" -o wide \
    > "$OUT/meta/node-$node-pods.txt"
  vllm_get "$p" /metrics | grep -E '^vllm:cache_config_info' > "$OUT/meta/cache-config-$p.txt" || true
done
"$REPO_ROOT/model-server/collect.sh" > "$OUT/meta/model-server.txt" 2>&1 || true

DURATION_ARG=""
[ -n "$DURATION" ] && DURATION_ARG="--benchmark-duration $DURATION"

SA_YAML=""; SIDECAR_YAML=""; SCRIPTS_VOLUME_YAML=""
if [ "$EPP_SCRAPE" = 1 ]; then
  kc create configmap agentic-bench-scripts --from-file=epp_scrape.py="$SCRIPTS/epp_scrape.py" \
    --dry-run=client -o yaml | kc apply -f - >/dev/null
  SA_YAML="serviceAccountName: thunderagent-metrics-reader"
  SIDECAR_YAML="initContainers:
      - name: epp-scrape
        image: python:3.12-alpine
        restartPolicy: Always
        command: [python, /scripts/epp_scrape.py]
        env:
        - {name: EPP_METRICS_URLS, value: \"$EPP_METRICS_URLS\"}
        - {name: OUT_DIR, value: $REMOTE/epp}
        - {name: INTERVAL, value: \"10\"}
        - {name: PYTHONUNBUFFERED, value: \"1\"}
        resources:
          requests: {cpu: 100m, memory: 128Mi}
          limits: {memory: 512Mi}
        volumeMounts:
        - {name: data, mountPath: /data}
        - {name: scripts, mountPath: /scripts}"
  SCRIPTS_VOLUME_YAML="- name: scripts
        configMap: {name: agentic-bench-scripts}"
fi

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
      $SA_YAML
      nodeSelector: {cloud.google.com/gke-nodepool: $CLIENT_POOL}
      securityContext: {runAsUser: 1000, runAsGroup: 1000, fsGroup: 1000}
      $SIDECAR_YAML
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
      $SCRIPTS_VOLUME_YAML
EOF

cat > "$OUT/meta/point.json" <<EOF
{
  "label": "$LABEL",
  "mode": "$MODE",
  "lane": "$LANE",
  "lane_epp": "$LANE_EPP",
  "epp_deploy": "$( [ -n "$EPPS" ] && echo "$EPP_DEPLOY" )",
  "concurrency": $CONC,
  "num_gpus": $NUM_GPUS,
  "num_vllm_pods": $NUM_PODS,
  "image": "$IMAGE",
  "model": "$MODEL",
  "dataset": "$DATASET",
  "url": "$URL",
  "server_metrics_urls": "$METRICS_URLS",
  "epp_metrics_urls": "$EPP_METRICS_URLS",
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
  line=$(kc logs "job/$JOB" -c aiperf --tail=1 2>/dev/null || true)
  [ -n "$line" ] && log "${line:0:200}"
done
log "job $STATUS"
kc logs "job/$JOB" -c aiperf > "$OUT/bench-stdout.log" 2>&1 || true
[ "$EPP_SCRAPE" = 1 ] && { kc logs "job/$JOB" -c epp-scrape > "$OUT/epp-scrape.log" 2>&1 || true; }

pod_identity $TARGETS $EPPS > "$OUT/meta/pods-end.txt" 2>&1 || true
POD_CHANGED=false
cmp -s "$OUT/meta/pods-start.txt" "$OUT/meta/pods-end.txt" || POD_CHANGED=true
[ "$POD_CHANGED" = false ] || log "WARNING: a vLLM or EPP pod was replaced or restarted during the run; the point is invalid"
cat > "$OUT/meta/finish.json" <<EOF
{"finished_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "job_status": "$STATUS", "pod_changed": $POD_CHANGED}
EOF

log "saving vLLM and EPP logs"
for p in $TARGETS; do
  kc logs "$p" -c modelserver 2>&1 | gzip > "$OUT/meta/vllm-$p.log.gz" || true
done
for p in $EPPS; do
  kc logs "$p" --all-containers --prefix > "$OUT/epp-$p.log" 2>&1 || true
done

# kubectl cp needs tar, which the distroless image lacks, so read the PVC from busybox.
FETCH="agentx-fetch-$(date +%s)"
kc run "$FETCH" --image=busybox:1.36 --restart=Never \
  --overrides="{\"spec\":{\"nodeSelector\":{\"cloud.google.com/gke-nodepool\":\"$CLIENT_POOL\"},\"volumes\":[{\"name\":\"data\",\"persistentVolumeClaim\":{\"claimName\":\"$PVC\",\"readOnly\":true}}],\"containers\":[{\"name\":\"fetch\",\"image\":\"busybox:1.36\",\"command\":[\"sleep\",\"3600\"],\"volumeMounts\":[{\"name\":\"data\",\"mountPath\":\"/data\",\"readOnly\":true}]}]}}"
kc wait --for=condition=Ready "pod/$FETCH" --timeout=10m
# fetch <remote dir> <local dir>: file by file with a size check and retries; kubectl cp
# of the whole tree broke off on large files ("unexpected EOF", truncated jsonl).
# server_metrics_export.json (hundreds of MB, includes warmup) is not used and stays on the PVC.
fetch() {
  local size f bad=0
  while read -r size f; do
    f=${f#./}
    [ "$f" = server_metrics_export.json ] && continue
    mkdir -p "$2/$(dirname "$f")"
    for _ in 1 2 3; do
      kc exec "$FETCH" -- cat "$1/$f" > "$2/$f" 2>/dev/null
      [ "$(wc -c < "$2/$f" | tr -d ' ')" = "$size" ] && break
    done
    [ "$(wc -c < "$2/$f" | tr -d ' ')" = "$size" ] || { log "WARNING: $f did not copy completely"; bad=1; }
  done < <(kc exec "$FETCH" -- sh -c "cd $1 && find . -type f | xargs ls -l" | awk '{print $5, $9}')
  return $bad
}
fetch "$REMOTE/aiperf_artifacts" "$OUT/aiperf_artifacts" || log "WARNING: some artifacts are incomplete; rerun the fetch"
[ "$EPP_SCRAPE" = 1 ] && { fetch "$REMOTE/epp" "$OUT/epp" || log "WARNING: no complete EPP scrape on the PVC"; }
kc delete pod "$FETCH" --wait=false

log "artifacts in $OUT"
[ "$STATUS" = succeeded ] && [ "$POD_CHANGED" = false ]
