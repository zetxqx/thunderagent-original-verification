#!/usr/bin/env bash
# Replicated A/B: the SAME configuration run three times, instead of the
# step-07 concurrency sweep.
#
# Why replicates and not a sweep: at c=96/128/192 ThunderAgent converged to
# the same operating point (32-35 admitted programs, 48-58 requests in
# flight), so the sweep measured one regime three times while *changing* the
# sampled trace subset (only 43/65 sessions overlapped between c=96 and
# c=128). Meanwhile two nominally identical 10-minute cells produced hit
# rates of 0.249 and 0.097, so single runs cannot be trusted. Replicates buy
# error bars; the sweep bought a confound.
#
# Layout: three lanes in parallel, one per vLLM pod on a distinct node. Each
# lane runs default then tr-decay SEQUENTIALLY on its own pod, with a prefix
# cache reset and a fresh router between them. Lane = replicate.
#
# Usage: ./run-replicates.sh [concurrency] [reps]     (default: 128 3)
set -euo pipefail

NS=llm-d-program-aware-scheduling
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONC="${1:-128}"
REPS="${2:-3}"
WINDOW=2700

AB_ID="rep-$(date +%Y%m%d-%H%M%S)-c$CONC"
OUT_ROOT="$SCRIPT_DIR/results/$AB_ID"
mkdir -p "$OUT_ROOT"
echo "run id: $AB_ID   concurrency=$CONC  replicates=$REPS  window=${WINDOW}s"

PODS=() IPS=() NODES=()
while read -r name node ip; do
  skip=""
  for n in "${NODES[@]:-}"; do [ "$n" = "$node" ] && skip=1; done
  [ -n "$skip" ] && continue
  NODES+=("$node"); PODS+=("$name"); IPS+=("$ip")
done < <(kubectl get pods -n "$NS" -l llm-d.ai/role=decode --field-selector=status.phase=Running \
  -o jsonpath='{range .items[*]}{.metadata.name} {.spec.nodeName} {.status.podIP}{"\n"}{end}' | sort)
echo "lane pods: ${PODS[*]}"
[ "${#PODS[@]}" -ge "$REPS" ] || { echo "need $REPS pods on distinct nodes, have ${#PODS[@]}" >&2; exit 1; }

cat > "$OUT_ROOT/manifest-global.json" <<EOF
{"ab_id":"$AB_ID","kind":"replicates","started":"$(date -u +%Y-%m-%dT%H:%M:%SZ)",
 "concurrency":$CONC,"replicates":$REPS,"window_s":$WINDOW,
 "design":"one lane per replicate; within a lane default then tr-decay on the same pod",
 "pods":"$(IFS=,; echo "${PODS[*]}")","nodes":"$(IFS=,; echo "${NODES[*]}")",
 "inference_perf":"quay.io/inference-perf/inference-perf:v0.7.0@sha256:d247e6ad725dc5bb56df71d115abc8ca455bba9f0ccd4110e14bbb56504250ec",
 "thunderagent_image":"us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/thunderagent-original:7ddc861",
 "base_seed":20260915,
 "config_template_sha256":"$(shasum -a 256 "$SCRIPT_DIR/config-tmpl.yaml" | cut -d' ' -f1)",
 "prober_sha256":"$(shasum -a 256 "$SCRIPT_DIR/prober.py" | cut -d' ' -f1)",
 "filter_traces_sha256":"$(shasum -a 256 "$SCRIPT_DIR/filter_traces.py" | cut -d' ' -f1)"}
EOF

kubectl create configmap weka-bench-scripts \
  --from-file=filter_traces.py="$SCRIPT_DIR/filter_traces.py" \
  --from-file=prober.py="$SCRIPT_DIR/prober.py" \
  -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep 20; done; }

run_cell() { # run_cell <cell> <router> <mode> <router_extra> <pod> <ip>
  local CELL=$1 RN=$2 RM=$3 RX=$4 VP=$5 BIP=$6
  local CELL_DIR="$OUT_ROOT/$CELL"
  mkdir -p "$CELL_DIR"
  echo "===== $CELL (mode=$RM pod=$VP) ====="

  local VUID
  VUID=$(kubectl get pod "$VP" -n "$NS" -o jsonpath='{.metadata.uid}' 2>/dev/null)
  [ -n "$VUID" ] || { echo "FATAL [$CELL]: pod $VP gone before start" >&2; return 1; }

  kubectl exec "$VP" -n "$NS" -c modelserver -- python3 -c "
import urllib.request
print('reset_prefix_cache:', urllib.request.urlopen(urllib.request.Request(
    'http://localhost:8000/reset_prefix_cache', method='POST')).status)"

  sed -e "s/__NAME__/$RN/g" -e "s/__MODE__/$RM/g" -e "s|__ROUTER_EXTRA__|$RX|g" \
      -e "s/__BACKEND_IP__/$BIP/g" "$SCRIPT_DIR/router-weka.yaml" | kubectl apply -f - >/dev/null
  kubectl rollout restart "deploy/$RN" -n "$NS" >/dev/null 2>&1 || true
  kubectl rollout status "deploy/$RN" -n "$NS" --timeout=180s >/dev/null
  local READY=""
  for _ in $(seq 1 30); do
    READY=$(kubectl exec "deploy/$RN" -n "$NS" -- python -c "import urllib.request,json;print(json.load(urllib.request.urlopen('http://localhost:8300/health'))['router_mode'])" 2>/dev/null || true)
    [ "$READY" = "$RM" ] && break
    sleep 2
  done
  [ "$READY" = "$RM" ] || { echo "FATAL [$CELL]: router not in $RM (got $READY)" >&2; return 1; }

  sed -e "s/__CONCURRENCY__/$CONC/" -e "s/__STAGE_TIMEOUT__/$WINDOW/" -e "s/__ROUTER__/$RN/" \
    "$SCRIPT_DIR/config-tmpl.yaml" > "$CELL_DIR/config.yml"
  kubectl create configmap "weka-bench-config-$CELL" --from-file=config.yml="$CELL_DIR/config.yml" \
    -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

  kubectl delete job "weka-bench-$CELL" -n "$NS" --ignore-not-found >/dev/null
  kubectl wait --for=delete pod -l cell="$CELL" -n "$NS" --timeout=180s 2>/dev/null || true
  sed -e "s/__CELL__/$CELL/g" -e "s/__RUN_ID__/$AB_ID-$CELL/" -e "s/__ROUTER__/$RN/" \
      -e "s/__BACKEND_IP__/$BIP/" -e "s/__MAX_TRACES__/0/" \
      -e "s/__RUN_BUDGET__/$((WINDOW + 1800))/" -e "s/__PROBE_MAX_SECONDS__/$((WINDOW + 900))/" \
    "$SCRIPT_DIR/job-weka.yaml" | kubectl apply -f - >/dev/null
  kubectl wait pod -l cell="$CELL" -n "$NS" --for=condition=Ready --timeout=900s >/dev/null
  local POD T0
  POD=$(kubectl get pod -l cell="$CELL" -n "$NS" --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}')
  T0=$(date +%s)

  # CPU sampling runs alongside: the router is a single asyncio process, so if
  # it sits near 1 core it is the in-flight ceiling, not the load generator.
  ( while ! kubectl exec "$POD" -n "$NS" -c bench -- test -f /results/DONE 2>/dev/null; do
      kubectl top pod -n "$NS" --no-headers 2>/dev/null \
        | awk -v t="$(date +%s)" -v r="$RN" -v v="$VP" -v b="$POD" \
          '$1 ~ r || $1 == v || $1 == b {print t","$1","$2","$3}' >> "$CELL_DIR/cpu-usage.csv"
      sleep 30
    done ) &
  local CPU_PID=$!

  local PREEMPTED=false
  while ! kubectl exec "$POD" -n "$NS" -c bench -- test -f /results/DONE 2>/dev/null; do
    local NOWUID
    NOWUID=$(kubectl get pod "$VP" -n "$NS" -o jsonpath='{.metadata.uid}' 2>/dev/null)
    if [ "$NOWUID" != "$VUID" ]; then
      echo "PREEMPTED [$CELL]: pod $VP replaced; aborting cell" >&2
      PREEMPTED=true; break
    fi
    echo "$(date +%H:%M:%S) [$CELL] $(kubectl exec "deploy/$RN" -n "$NS" -- python -c "import urllib.request,json;h=json.load(urllib.request.urlopen('http://localhost:8300/health'));print('progs',h['programs_count'],'paused',h['paused_count'])" 2>/dev/null || echo n/a)"
    sleep 30
  done
  kill $CPU_PID 2>/dev/null || true

  kubectl logs "deploy/$RN" -n "$NS" --tail=200000 > "$CELL_DIR/router.log" 2>/dev/null || true
  kubectl logs "$POD" -n "$NS" -c prober --tail=1000 > "$CELL_DIR/prober.log" 2>/dev/null || true
  retry kubectl cp "$NS/$POD:/results" "$CELL_DIR/results" -c bench >/dev/null
  cat > "$CELL_DIR/manifest.json" <<EOF
{"cell":"$CELL","router_mode":"$RM","router_extra":"$RX","concurrency":$CONC,
 "window_s":$WINDOW,"vllm_pod":"$VP","vllm_pod_uid":"$VUID","bench_pod":"$POD",
 "preempted":$PREEMPTED,"started_epoch":$T0,"finished_epoch":$(date +%s),
 "config_sha256":"$(shasum -a 256 "$CELL_DIR/config.yml" | cut -d' ' -f1)"}
EOF
  kubectl delete job "weka-bench-$CELL" -n "$NS" >/dev/null
  tail -3 "$CELL_DIR/results/bench-stdout.log" 2>/dev/null || true
  [ "$PREEMPTED" = false ] || { mv "$CELL_DIR" "$CELL_DIR-PREEMPTED"; return 1; }
}

run_lane() { # run_lane <replicate_index> <pod> <ip>
  local R=$1 VP=$2 BIP=$3 RN="thunderagent-rep$1"
  run_cell "default-r$R"  "$RN" default ""                         "$VP" "$BIP"
  run_cell "tr-decay-r$R" "$RN" tr      "--use-acting-token-decay" "$VP" "$BIP"
  kubectl delete "deploy/$RN" "svc/$RN" -n "$NS" --ignore-not-found >/dev/null
}

PIDS=()
for i in $(seq 0 $((REPS - 1))); do
  run_lane "$((i + 1))" "${PODS[$i]}" "${IPS[$i]}" > >(sed "s/^/[rep$((i + 1))] /") 2>&1 &
  PIDS+=($!)
done
FAIL=0
for p in "${PIDS[@]}"; do wait "$p" || FAIL=1; done

echo; echo "===== analysis ====="
"${VIZ_PYTHON:-python3}" "$SCRIPT_DIR/analyze.py" "$OUT_ROOT" || true
[ "$FAIL" = 0 ] || echo "WARNING: at least one lane failed (check for *-PREEMPTED dirs)"
echo "artifacts: $OUT_ROOT"
