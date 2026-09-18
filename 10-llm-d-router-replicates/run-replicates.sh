#!/usr/bin/env bash
# Step 10: the step 08 replicate protocol through the llm-d-router EPP.
#
# Three lanes in parallel, one vLLM pod each (deploy-lanes.sh). Within a lane
# the two arms run sequentially on the same pod with a prefix-cache reset and
# a fresh EPP (rollout restart with the arm's plugin config) between them.
# Arm order alternates across lanes to control drift:
#   lane a: sticky, thunder    lane b: thunder, sticky    lane c: sticky, thunder
#
# Usage: ./run-replicates.sh [concurrency] [reps] [window_s] [arms] [client_timeout_s]
#   defaults: 128 3 2700 sticky,thunder 1900
#   calibration: ./run-replicates.sh 128 1 600 thunder
#   step 08 client: ./run-replicates.sh 128 3 2700 sticky,thunder 600
set -euo pipefail

NS=llm-d-program-aware-scheduling
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${LLM_D_ROUTER:-$HOME/projects/llmdthunder/llm-d-router}"
CHART="$REPO/config/charts/llm-d-router-standalone"
CONC="${1:-128}"; REPS="${2:-3}"; WINDOW="${3:-2700}"; ARMS="${4:-sticky,thunder}"; CLIENT_TIMEOUT="${5:-1900}"
# Benchmark image. Default: official v0.7.0 (digest-pinned), which has the
# parked-permit bug (INFERENCE-PERF-BUGS.md issue 4). Override with BENCH_IMAGE.
BENCH_IMAGE="${BENCH_IMAGE:-quay.io/inference-perf/inference-perf@sha256:d247e6ad725dc5bb56df71d115abc8ca455bba9f0ccd4110e14bbb56504250ec}"
LANES=(a b c)

# shellcheck disable=SC1091
source "$HERE/results/lanes.env"
PREFIX="rep"; [ "$WINDOW" -lt 1800 ] && PREFIX="cal"
AB_ID="$PREFIX-$(date +%Y%m%d-%H%M%S)-c$CONC-t$CLIENT_TIMEOUT"
OUT_ROOT="$HERE/results/$AB_ID"
mkdir -p "$OUT_ROOT"
echo "run id: $AB_ID  concurrency=$CONC replicates=$REPS window=${WINDOW}s arms=$ARMS client_timeout=${CLIENT_TIMEOUT}s"

cat > "$OUT_ROOT/manifest-global.json" <<EOJ
{"ab_id":"$AB_ID","kind":"epp-replicates","started":"$(date -u +%Y-%m-%dT%H:%M:%SZ)",
 "concurrency":$CONC,"replicates":$REPS,"window_s":$WINDOW,"arms":"$ARMS","client_timeout_s":$CLIENT_TIMEOUT,
 "design":"one lane per replicate; within a lane both arms sequentially on the same pod through a fresh EPP",
 "epp_image":"us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/llm-d-router-endpoint-picker:thunder-agent-v3",
 "inference_perf":"$BENCH_IMAGE",
 "base_seed":20260915,
 "config_template_sha256":"$(shasum -a 256 "$HERE/config-tmpl.yaml" | cut -d' ' -f1)",
 "thunder_plugins_sha256":"$(shasum -a 256 "$HERE/thunder-plugins.yaml" | cut -d' ' -f1)",
 "sticky_plugins_sha256":"$(shasum -a 256 "$HERE/sticky-plugins.yaml" | cut -d' ' -f1)",
 "prober_sha256":"$(shasum -a 256 "$HERE/prober.py" | cut -d' ' -f1)",
 "lanes":"$(tr '\n' ' ' < "$HERE/results/lanes.env")"}
EOJ

kubectl create configmap weka-bench-scripts \
  --from-file=filter_traces.py="$HERE/filter_traces.py" \
  --from-file=prober.py="$HERE/prober.py" \
  -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep 20; done; }

epp_summary() { # epp_summary <bench-pod>  (prober container has the token and python)
  kubectl exec "$1" -n "$NS" -c prober -- python -c '
import os,re,urllib.request
t=open("/var/run/secrets/kubernetes.io/serviceaccount/token").read().strip()
r=urllib.request.Request(os.environ["EPP_METRICS_URL"]); r.add_header("Authorization","Bearer "+t)
m=urllib.request.urlopen(r,timeout=10).read().decode()
def g(n,l=""):
    x=re.search(r"^\S*"+re.escape(n)+r"(?:\{[^}]*"+re.escape(l)+r"[^}]*\})?\s+([\d.eE+-]+)",m,re.M); return int(float(x.group(1))) if x else 0
print("run",g("thunder_agent_programs","state=\"running\""),"idle",g("thunder_agent_programs","state=\"idle\""),"paused",g("thunder_agent_programs","state=\"paused\""),"holds",g("thunder_agent_holds_total","class=\"paused\"")+g("thunder_agent_holds_total","class=\"new\""),"pauses",g("thunder_agent_pauses_total"),"resumes",g("thunder_agent_resumes_total"),"queue",g("flow_control_queue_size"))' 2>/dev/null || echo n/a
}

run_cell() { # run_cell <cell> <lane> <arm> <pod> <ip>
  local CELL=$1 L=$2 ARM=$3 VP=$4 BIP=$5 REL="thunder-lane-$2" SVC="thunder-lane-$2-epp"
  local CELL_DIR="$OUT_ROOT/$CELL"; mkdir -p "$CELL_DIR"
  echo "===== $CELL (arm=$ARM lane=$L pod=$VP) ====="
  local VUID; VUID=$(kubectl get pod "$VP" -n "$NS" -o jsonpath='{.metadata.uid}' 2>/dev/null)
  [ -n "$VUID" ] || { echo "FATAL [$CELL]: pod $VP gone before start" >&2; return 1; }

  kubectl exec "$VP" -n "$NS" -c modelserver -- python3 -c "
import urllib.request
print('reset_prefix_cache:', urllib.request.urlopen(urllib.request.Request(
    'http://localhost:8000/reset_prefix_cache', method='POST')).status)"

  # Fresh EPP on this arm's config: re-render the lane with the arm's plugin
  # config, apply, and restart so the program table starts empty.
  "$HERE/render-lane.sh" "$L" "$ARM" > "$HERE/results/lane-$L-manifest.yaml"
  kubectl apply -f "$HERE/results/lane-$L-manifest.yaml" >/dev/null
  kubectl rollout restart "deploy/$SVC" -n "$NS" >/dev/null
  kubectl rollout status "deploy/$SVC" -n "$NS" --timeout=300s >/dev/null
  sleep 5
  local EPP_POD; EPP_POD=$(kubectl get pod -n "$NS" -l "app.kubernetes.io/name=$SVC" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  [ -n "$EPP_POD" ] || EPP_POD=$(kubectl get pod -n "$NS" -o name | grep "$SVC" | head -1 | sed 's|pod/||')
  local GATE; GATE=$(kubectl logs "$EPP_POD" -n "$NS" -c epp 2>/dev/null | grep -c "Initializing Flow Control layer" || true)
  case "$ARM" in
    thunder) [ "$GATE" -ge 1 ] || { echo "FATAL [$CELL]: thunder arm without flow control" >&2; return 1; } ;;
    sticky)  [ "$GATE" -eq 0 ] || { echo "FATAL [$CELL]: sticky arm started flow control" >&2; return 1; } ;;
  esac
  echo "[$CELL] epp pod $EPP_POD, flow control lines: $GATE"

  sed -e "s/__CONCURRENCY__/$CONC/" -e "s/__STAGE_TIMEOUT__/$WINDOW/" -e "s/__ROUTER__/$SVC/" \
      -e "s/__REQUEST_TIMEOUT__/$CLIENT_TIMEOUT/" \
    "$HERE/config-tmpl.yaml" > "$CELL_DIR/config.yml"
  kubectl create configmap "weka-bench-config-$CELL" --from-file=config.yml="$CELL_DIR/config.yml" \
    -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  kubectl delete job "weka-bench-$CELL" -n "$NS" --ignore-not-found >/dev/null
  kubectl wait --for=delete pod -l cell="$CELL" -n "$NS" --timeout=180s 2>/dev/null || true
  sed -e "s/__CELL__/$CELL/g" -e "s/__RUN_ID__/$AB_ID-$CELL/" -e "s/__ROUTER__/$SVC/" \
      -e "s/__BACKEND_IP__/$BIP/" -e "s/__MAX_TRACES__/0/" \
      -e "s/__RUN_BUDGET__/$((WINDOW + 2400))/" -e "s/__PROBE_MAX_SECONDS__/$((WINDOW + 1800))/" \
      -e "s|__BENCH_IMAGE__|$BENCH_IMAGE|" \
    "$HERE/job-weka.yaml" | kubectl apply -f - >/dev/null
  kubectl wait pod -l cell="$CELL" -n "$NS" --for=condition=Ready --timeout=900s >/dev/null
  local POD T0
  POD=$(kubectl get pod -l cell="$CELL" -n "$NS" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
  T0=$(date +%s)

  ( while ! kubectl exec "$POD" -n "$NS" -c bench -- test -f /results/DONE 2>/dev/null; do
      kubectl top pod -n "$NS" --no-headers 2>/dev/null \
        | awk -v t="$(date +%s)" -v r="$SVC" -v v="$VP" -v b="$POD" '$1 ~ r || $1 == v || $1 == b {print t","$1","$2","$3}' >> "$CELL_DIR/cpu-usage.csv"
      sleep 30
    done ) &
  local CPU_PID=$!

  local PREEMPTED=false
  while ! kubectl exec "$POD" -n "$NS" -c bench -- test -f /results/DONE 2>/dev/null; do
    local NOWUID; NOWUID=$(kubectl get pod "$VP" -n "$NS" -o jsonpath='{.metadata.uid}' 2>/dev/null)
    if [ "$NOWUID" != "$VUID" ]; then echo "PREEMPTED [$CELL]: pod $VP replaced; aborting cell" >&2; PREEMPTED=true; break; fi
    echo "$(date +%H:%M:%S) [$CELL] $(epp_summary "$POD")"
    sleep 60
  done
  kill $CPU_PID 2>/dev/null || true

  kubectl logs "$EPP_POD" -n "$NS" -c epp --tail=200000 > "$CELL_DIR/epp.log" 2>/dev/null || true
  kubectl logs "$POD" -n "$NS" -c prober --tail=1000 > "$CELL_DIR/prober.log" 2>/dev/null || true
  retry kubectl cp "$NS/$POD:/results" "$CELL_DIR/results" -c bench >/dev/null
  cat > "$CELL_DIR/manifest.json" <<EOJ
{"cell":"$CELL","arm":"$ARM","lane":"$L","concurrency":$CONC,"window_s":$WINDOW,"client_timeout_s":$CLIENT_TIMEOUT,
 "vllm_pod":"$VP","vllm_pod_uid":"$VUID","epp_pod":"$EPP_POD","bench_pod":"$POD",
 "preempted":$PREEMPTED,"started_epoch":$T0,"finished_epoch":$(date +%s),
 "config_sha256":"$(shasum -a 256 "$CELL_DIR/config.yml" | cut -d' ' -f1)",
 "plugins_sha256":"$(shasum -a 256 "$HERE/$ARM-plugins.yaml" | cut -d' ' -f1)"}
EOJ
  kubectl delete job "weka-bench-$CELL" -n "$NS" >/dev/null
  tail -3 "$CELL_DIR/results/bench-stdout.log" 2>/dev/null || true
  [ "$PREEMPTED" = false ] || { mv "$CELL_DIR" "$CELL_DIR-PREEMPTED"; return 1; }
}

run_lane() { # run_lane <replicate index 1..3>
  local R=$1
  local L=${LANES[$((R-1))]}
  local PODV="LANE_${L}_POD" IPV="LANE_${L}_IP"
  local ORDER="$ARMS"
  [ $((R % 2)) -eq 0 ] && ORDER=$(echo "$ARMS" | awk -F, '{for(i=NF;i>0;i--) printf "%s%s",$i,(i>1?",":"")}')
  for ARM in ${ORDER//,/ }; do
    run_cell "epp-$ARM-r$R" "$L" "$ARM" "${!PODV}" "${!IPV}"
  done
}

PIDS=()
for i in $(seq 1 "$REPS"); do
  run_lane "$i" > >(sed "s/^/[r$i] /") 2>&1 &
  PIDS+=($!)
done
FAIL=0
for p in "${PIDS[@]}"; do wait "$p" || FAIL=1; done

echo; echo "===== analysis ====="
if command -v uv >/dev/null 2>&1; then
  uv run --quiet --with matplotlib --with numpy python "$HERE/analyze.py" "$OUT_ROOT" || true
else
  "${VIZ_PYTHON:-python3}" "$HERE/analyze.py" "$OUT_ROOT" || true
fi
[ "$FAIL" = 0 ] || echo "WARNING: at least one lane failed (check for *-PREEMPTED dirs)"
echo "artifacts: $OUT_ROOT"
