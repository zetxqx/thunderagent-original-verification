#!/usr/bin/env bash
# Step 12: three EPP scheduling policies on the whole 4-pod pool, one EPP.
#
# Arms (plugin configs in this directory): baseline (llm-d default: prefix
# cache + queue + KV scorers), affinity (session-affinity-scorer only),
# thunder (the ThunderAgent port). Cells run sequentially because the pool is
# shared; each cell: prefix-cache reset on every pod, main EPP release
# switched to the arm's config and restarted, one inference-perf job at
# concurrency c over the whole corpus. Arm order is a Latin square across
# replicates: r1 baseline,affinity,thunder  r2 affinity,thunder,baseline
# r3 thunder,baseline,affinity.
#
# Usage: ./run-pool.sh [concurrency] [reps] [window_s] [arms] [client_timeout_s]
#   defaults: 338 3 2700 baseline,affinity,thunder 1900
#   calibration: ./run-pool.sh 338 1 600 thunder
# Requires BENCH_IMAGE with the session-replay permit fix (see README).
set -euo pipefail

NS=llm-d-program-aware-scheduling
RELEASE=program-aware-scheduling
DEPLOY=program-aware-scheduling-epp
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${LLM_D_ROUTER:-$HOME/projects/llmdthunder/llm-d-router}"
CHART="$REPO/config/charts/llm-d-router-standalone"
CONC="${1:-338}"; REPS="${2:-3}"; WINDOW="${3:-2700}"; ARMS="${4:-baseline,affinity,thunder}"; CLIENT_TIMEOUT="${5:-1900}"
BENCH_IMAGE="${BENCH_IMAGE:-$(cat "$HERE/results/inference-perf-image.txt")}"
# EPP image tag; thunder-agent-v4 adds resumePlacement (origin-only arm). v3 and v4 behave the same under most-room.
EPP_IMAGE_TAG="${EPP_IMAGE_TAG:-thunder-agent-v3}"

PREFIX="rep"; [ "$WINDOW" -lt 1800 ] && PREFIX="cal"
# AB_ID may be preset to append cells (e.g. a make-up replicate) to an existing run directory;
# REP_START sets the first replicate index for such a run.
AB_ID="${AB_ID:-$PREFIX-$(date +%Y%m%d-%H%M%S)-c$CONC-t$CLIENT_TIMEOUT}"; REP_START="${REP_START:-1}"
# OUT_BASE lets another step (e.g. the step 13 sweep) collect cells under its own results directory.
OUT_ROOT="${OUT_BASE:-$HERE/results}/$AB_ID"; mkdir -p "$OUT_ROOT"
echo "run id: $AB_ID  concurrency=$CONC replicates=$REPS window=${WINDOW}s arms=$ARMS client_timeout=${CLIENT_TIMEOUT}s"

# Pool: every running decode pod.
PODS=(); IPS=()
while read -r name ip; do PODS+=("$name"); IPS+=("$ip"); done < <(kubectl get pods -n "$NS" -l llm-d.ai/role=decode --field-selector=status.phase=Running -o jsonpath='{range .items[*]}{.metadata.name} {.status.podIP}{"\n"}{end}' | sort)
VLLM_URLS=$(printf "http://%s:8000," "${IPS[@]}"); VLLM_URLS=${VLLM_URLS%,}
echo "pool: ${PODS[*]}"

[ -f "$OUT_ROOT/manifest-global.json" ] || cat > "$OUT_ROOT/manifest-global.json" <<EOJ
{"ab_id":"$AB_ID","kind":"pool","started":"$(date -u +%Y-%m-%dT%H:%M:%SZ)",
 "concurrency":$CONC,"replicates":$REPS,"window_s":$WINDOW,"arms":"$ARMS","client_timeout_s":$CLIENT_TIMEOUT,
 "design":"one EPP over the whole pool; arms sequential per replicate in Latin-square order; fresh EPP and cache reset per cell",
 "epp_image":"$EPP_IMAGE_TAG","inference_perf":"$BENCH_IMAGE","base_seed":20260915,
 "pods":"$(IFS=,; echo "${PODS[*]}")",
 "config_template_sha256":"$(shasum -a 256 "$HERE/config-tmpl.yaml" | cut -d' ' -f1)",
 "prober_sha256":"$(shasum -a 256 "$HERE/prober.py" | cut -d' ' -f1)"}
EOJ
kubectl create configmap weka-bench-scripts --from-file=filter_traces.py="$HERE/filter_traces.py" --from-file=prober.py="$HERE/prober.py" -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
helm dependency update "$CHART" >/dev/null

retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep 20; done; }
pod_uids() { kubectl get pods -n "$NS" -l llm-d.ai/role=decode -o jsonpath='{range .items[*]}{.metadata.uid}{" "}{end}'; }

epp_summary() { # <bench-pod>
  kubectl exec "$1" -n "$NS" -c prober -- python -c '
import os,re,urllib.request
t=open("/var/run/secrets/kubernetes.io/serviceaccount/token").read().strip()
r=urllib.request.Request(os.environ["EPP_METRICS_URL"]); r.add_header("Authorization","Bearer "+t)
m=urllib.request.urlopen(r,timeout=10).read().decode()
def g(n,l=""):
    x=re.search(r"^\S*"+re.escape(n)+r"(?:\{[^}]*"+re.escape(l)+r"[^}]*\})?\s+([\d.eE+-]+)",m,re.M); return int(float(x.group(1))) if x else 0
q=sum(float(v) for v in re.findall(r"^\S*flow_control_queue_size(?:\{[^}]*\})?\s+([\d.eE+-]+)",m,re.M))
print("paused",g("thunder_agent_programs","state=\"paused\""),"holds",g("thunder_agent_holds_total","class=\"paused\"")+g("thunder_agent_holds_total","class=\"new\""),"pauses",g("thunder_agent_pauses_total"),"queued",int(q))' 2>/dev/null || echo n/a
}

run_cell() { # <cell> <arm>
  local CELL=$1 ARM=$2 CELL_DIR="$OUT_ROOT/$1"; mkdir -p "$CELL_DIR"
  echo "===== $CELL (arm=$ARM) ====="
  local UIDS0; UIDS0=$(pod_uids)
  for VP in "${PODS[@]}"; do
    kubectl exec "$VP" -n "$NS" -c modelserver -- python3 -c "
import urllib.request
print('reset_prefix_cache $VP:', urllib.request.urlopen(urllib.request.Request('http://localhost:8000/reset_prefix_cache', method='POST')).status)"
  done
  # Switch the main release to this arm's config, restart for a clean plugin
  # state. Retried: a transient API-server timeout lost baseline-r2 on
  # 2026-09-18 (the arm check then refused to run under the wrong config).
  retry helm upgrade "$RELEASE" "$CHART" -n "$NS" -f "$HERE/main-values.yaml" --set "router.epp.image.tag=$EPP_IMAGE_TAG" \
    --set-file "router.epp.pluginsCustomConfig.thunder-plugins\.yaml=$HERE/$ARM-plugins.yaml" >/dev/null
  retry kubectl rollout restart "deploy/$DEPLOY" -n "$NS" >/dev/null
  kubectl rollout status "deploy/$DEPLOY" -n "$NS" --timeout=300s >/dev/null; sleep 5
  local EPP_POD; EPP_POD=$(kubectl get pod -n "$NS" -l "app.kubernetes.io/name=$DEPLOY" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
  [ -n "$EPP_POD" ] || EPP_POD=$(kubectl get pod -n "$NS" -o name | grep "$DEPLOY" | head -1 | sed 's|pod/||')
  local PARSED; PARSED=$(kubectl logs "$EPP_POD" -n "$NS" -c epp 2>/dev/null | grep -m1 '"msg":"parsed config"' | grep -oE 'Scorers: \[[^]]*\]' || true)
  local GATE; GATE=$(kubectl logs "$EPP_POD" -n "$NS" -c epp 2>/dev/null | grep -c "Initializing Flow Control layer" || true)
  local IMAGE; IMAGE=$(kubectl get pod "$EPP_POD" -n "$NS" -o jsonpath='{.spec.containers[?(@.name=="epp")].image}')
  echo "[$CELL] epp pod $EPP_POD  image ${IMAGE##*/}  $PARSED  flow-control=$GATE"
  case "$IMAGE" in *":$EPP_IMAGE_TAG") ;; *) echo "FATAL [$CELL]: EPP image is $IMAGE, expected tag $EPP_IMAGE_TAG" >&2; return 1 ;; esac
  case "$ARM" in
    thunder)  [ "$GATE" -ge 1 ] && echo "$PARSED" | grep -q thunder-agent || { echo "FATAL [$CELL]: thunder arm not active" >&2; return 1; } ;;
    thunder-origin)
      [ "$GATE" -ge 1 ] && echo "$PARSED" | grep -q thunder-agent || { echo "FATAL [$CELL]: thunder-origin arm not active" >&2; return 1; }
      kubectl get cm "$DEPLOY" -n "$NS" -o yaml | grep -q 'resumePlacement: origin-only' || { echo "FATAL [$CELL]: origin-only not in the EPP config" >&2; return 1; } ;;
    affinity) echo "$PARSED" | grep -q session-affinity || { echo "FATAL [$CELL]: affinity arm not active" >&2; return 1; } ;;
    baseline) echo "$PARSED" | grep -q prefix-cache-scorer || { echo "FATAL [$CELL]: baseline arm not active" >&2; return 1; } ;;
  esac

  sed -e "s/__CONCURRENCY__/$CONC/" -e "s/__STAGE_TIMEOUT__/$WINDOW/" -e "s/__ROUTER__/$DEPLOY/" -e "s/__REQUEST_TIMEOUT__/$CLIENT_TIMEOUT/" "$HERE/config-tmpl.yaml" > "$CELL_DIR/config.yml"
  kubectl create configmap "weka-bench-config-$CELL" --from-file=config.yml="$CELL_DIR/config.yml" -n "$NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
  kubectl delete job "weka-bench-$CELL" -n "$NS" --ignore-not-found >/dev/null
  kubectl wait --for=delete pod -l cell="$CELL" -n "$NS" --timeout=180s 2>/dev/null || true
  sed -e "s/__CELL__/$CELL/g" -e "s/__RUN_ID__/$AB_ID-$CELL/" -e "s/__ROUTER__/$DEPLOY/" -e "s|__VLLM_URLS__|$VLLM_URLS|" \
      -e "s/__MAX_TRACES__/0/" -e "s/__RUN_BUDGET__/$((WINDOW + 2400))/" -e "s/__PROBE_MAX_SECONDS__/$((WINDOW + 1800))/" \
      -e "s|__BENCH_IMAGE__|$BENCH_IMAGE|" "$HERE/job-weka.yaml" | kubectl apply -f - >/dev/null
  kubectl wait pod -l cell="$CELL" -n "$NS" --for=condition=Ready --timeout=900s >/dev/null
  # The name lookup can return nothing on a transient API error; an empty name
  # would make the DONE poll below spin forever (lost the step 13 c256 cell's collection).
  local POD T0 n=0
  until POD=$(kubectl get pod -l cell="$CELL" -n "$NS" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null) && [ -n "$POD" ]; do
    n=$((n+1)); [ "$n" -ge 30 ] && { echo "ERROR [$CELL]: bench pod name not found" >&2; return 1; }; sleep 10
  done; T0=$(date +%s)
  ( while ! kubectl exec "$POD" -n "$NS" -c bench -- test -f /results/DONE 2>/dev/null; do
      kubectl top pod -n "$NS" --no-headers 2>/dev/null | awk -v t="$(date +%s)" -v e="$DEPLOY" -v b="$POD" '$1 ~ e || $1 ~ /program-aware-vllm-decode/ || $1 == b {print t","$1","$2","$3}' >> "$CELL_DIR/cpu-usage.csv"; sleep 30; done ) &
  local CPU_PID=$! PREEMPTED=false
  while ! kubectl exec "$POD" -n "$NS" -c bench -- test -f /results/DONE 2>/dev/null; do
    [ "$(pod_uids)" = "$UIDS0" ] || { echo "PREEMPTED [$CELL]: a pool pod was replaced; aborting cell" >&2; PREEMPTED=true; break; }
    echo "$(date +%H:%M:%S) [$CELL] $(epp_summary "$POD")"; sleep 60
  done
  kill $CPU_PID 2>/dev/null || true
  kubectl logs "$EPP_POD" -n "$NS" -c epp --tail=200000 > "$CELL_DIR/epp.log" 2>/dev/null || true
  kubectl logs "$POD" -n "$NS" -c prober --tail=2000 > "$CELL_DIR/prober.log" 2>/dev/null || true
  retry kubectl cp "$NS/$POD:/results" "$CELL_DIR/results" -c bench >/dev/null
  # The bench pod downloads a 700 MB slice of the trace corpus at start; a truncated
  # download leaves too few traces to fill the concurrency (the step 13 origin c=192
  # cell got 10 of 338 traces). Such a cell is voided below, like a preempted one.
  local KEPT; KEPT=$(python3 -c "import json;print(json.load(open('$CELL_DIR/results/trace-manifest.json')).get('kept',0))" 2>/dev/null || echo 0)
  cat > "$CELL_DIR/manifest.json" <<EOJ
{"cell":"$CELL","arm":"$ARM","concurrency":$CONC,"window_s":$WINDOW,"client_timeout_s":$CLIENT_TIMEOUT,"epp_pod":"$EPP_POD","epp_image":"$EPP_IMAGE_TAG","bench_pod":"$POD","corpus_traces":$KEPT,
 "pods":"$(IFS=,; echo "${PODS[*]}")","preempted":$PREEMPTED,"started_epoch":$T0,"finished_epoch":$(date +%s),
 "config_sha256":"$(shasum -a 256 "$CELL_DIR/config.yml" | cut -d' ' -f1)","plugins_sha256":"$(shasum -a 256 "$HERE/$ARM-plugins.yaml" | cut -d' ' -f1)"}
EOJ
  kubectl delete job "weka-bench-$CELL" -n "$NS" >/dev/null
  tail -3 "$CELL_DIR/results/bench-stdout.log" 2>/dev/null || true
  [ "$PREEMPTED" = false ] || { mv "$CELL_DIR" "$CELL_DIR-PREEMPTED"; return 1; }
  [ "$KEPT" -ge "$CONC" ] || [ "$KEPT" -ge 338 ] || { echo "WARNING [$CELL]: corpus has $KEPT traces, fewer than concurrency $CONC (truncated download); voiding cell" >&2; mv "$CELL_DIR" "$CELL_DIR-SHORTCORPUS"; return 1; }
}

IFS=, read -r -a ARM_LIST <<< "$ARMS"; N=${#ARM_LIST[@]}
FAIL=0
for R in $(seq "$REP_START" $((REP_START + REPS - 1))); do
  for i in $(seq 0 $((N-1))); do
    ARM=${ARM_LIST[$(( (i + R - 1) % N ))]}   # Latin-square rotation across replicates
    # CELL_TAG names cells by something other than the replicate index (the sweep uses c<concurrency>).
    run_cell "epp-$ARM-${CELL_TAG:-r$R}" "$ARM" || FAIL=1
  done
done
echo; echo "===== analysis ====="
if [ -z "${SKIP_ANALYSIS:-}" ]; then
  if command -v uv >/dev/null 2>&1; then uv run --quiet --with matplotlib --with numpy python "$HERE/analyze.py" "$OUT_ROOT" || true; else python3 "$HERE/analyze.py" "$OUT_ROOT" || true; fi
fi
[ "$FAIL" = 0 ] || echo "WARNING: at least one cell failed"
echo "artifacts: $OUT_ROOT"
