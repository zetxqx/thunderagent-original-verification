#!/usr/bin/env bash
# Step 32 follow-up: c=48 only, 3600 s per arm, same config as the 900 s sweep.
# Change from the 900 s runs: SGLang restarted with
# --uvicorn-access-log-exclude-prefixes /metrics /health (log keeps every
# release_session line) and --enable-cache-report (per-request cached tokens);
# SGLang logs are also streamed for the whole point.
#
# Order: restart SGLang -> smoke c=4 (close, 120 s) -> c48 baseline-lru 3600 s -> c48 thunder-close 3600 s -> analysis.
# Usage: setsid nohup ./run-c48-1h.sh > ../results/run-c48-1h.log 2>&1 < /dev/null &
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$HERE/../.."
SCRIPTS="$REPO_ROOT/.claude/skills/agentic-benchmark/scripts"
export PATH="$HOME/.local/bin:$PATH"

export RESULTS="$HERE/../results"
export PROFILE=a4-pr
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=Qwen/Qwen3.5-397B-A17B-FP8
export DATASET=semianalysis_cc_traces_weka_062126_256k
export CLIENT_POOL=pool-1
export GPUS_PER_POD=4
export MODEL_SERVER_COLLECT=0
export CLIENT_CPU=3
export CLIENT_MEM=32Gi
export CLIENT_MEM_REQUEST=12Gi
export VLLM_PORTS=8000
export VLLM_CONTAINER=modelserver
export DECODE_SELECTOR="llm-d.ai/engine-type=sglang"
export DEPLOY=sglang-qwen35-a
export MODE=pool
export EPP_DEPLOY=agentx-epp-sglang-epp
export URL="http://agentx-epp-sglang-epp:80"
export SESSION_ID_HEADER=true
export EPP_SCRAPE=1
export EXTRA_ARGS="--tokenizer-trust-remote-code --unsafe-override"
export RESTART=0
export RESET=0

ts() { date -u +%H:%M:%S; }
log() { echo "[$(ts)] $*"; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
sglang_pods() { k get pods -l "$DECODE_SELECTOR" --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}'; }

mkdir -p "$RESULTS/streams"

restart_sglang() {
  log "Applying SGLang manifest (adds --uvicorn-access-log-exclude-prefixes)"
  k apply -f "$HERE/sglang-qwen35.yaml"
  k rollout status deploy/sglang-qwen35-a --timeout=60m || { log "FATAL: sglang-qwen35-a rollout failed"; exit 1; }
  k rollout status deploy/sglang-qwen35-b --timeout=60m || { log "FATAL: sglang-qwen35-b rollout failed"; exit 1; }
  # Wait for old pods to be gone so selectors see only the new ones.
  for i in $(seq 1 60); do
    n=$(k get pods -l "$DECODE_SELECTOR" --no-headers 2>/dev/null | wc -l)
    [ "$n" -eq 2 ] && break
    sleep 10
  done
  for pod in $(sglang_pods); do
    local ok=0
    for i in $(seq 1 120); do
      if k exec "$pod" -c "$VLLM_CONTAINER" -- python3 -c "
import urllib.request
assert urllib.request.urlopen('http://localhost:8000/v1/models', timeout=5).status == 200" >/dev/null 2>&1; then
        ok=1; log "  $pod serving /v1/models"; break
      fi
      sleep 5
    done
    [ "$ok" -eq 1 ] || { log "FATAL: $pod not serving"; exit 1; }
    k get pod "$pod" -o jsonpath='{.spec.containers[0].args}' | grep -q 'enable-cache-report' \
      || { log "FATAL: $pod lacks --enable-cache-report"; exit 1; }
  done
  k get pods -l "$DECODE_SELECTOR" -o wide
}

flush_sglang_cache() {
  for pod in $(sglang_pods); do
    k exec "$pod" -c "$VLLM_CONTAINER" -- python3 -c "
import urllib.request
r = urllib.request.urlopen(urllib.request.Request('http://localhost:8000/flush_cache', data=b'', method='POST'), timeout=30)
print('  $pod flush status', r.status)" || log "WARNING: flush failed on $pod"
  done
}

configure_epp() {
  local plugins_file="$1" arm="$2"
  log "Configuring EPP: $arm ($plugins_file)"
  "$HERE/render-epp.sh" sglang "$plugins_file" | k apply -f -
  k rollout restart "deploy/$EPP_DEPLOY"
  k rollout status "deploy/$EPP_DEPLOY" --timeout=5m
}

run_one_point() {
  local conc="$1" label="$2" dur="$3"
  log "=== Point conc=$conc label=$label duration=${dur}s ==="
  local job_name
  job_name=$(echo "agentx-c$conc-$label" | tr '[:upper:]_.' '[:lower:]--' | cut -c1-63)
  k delete job "$job_name" --ignore-not-found --wait=true >/dev/null 2>&1 || true

  flush_sglang_cache
  k rollout restart "deploy/$EPP_DEPLOY" >/dev/null 2>&1
  k rollout status "deploy/$EPP_DEPLOY" --timeout=5m >/dev/null 2>&1

  # Stream SGLang logs for the whole point.
  local pids=()
  for pod in $(sglang_pods); do
    # kubectl directly (not the k function) so $! is the kubectl pid and the kill below stops it.
    KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" logs -f "$pod" -c "$VLLM_CONTAINER" --since=1s \
      > "$RESULTS/streams/$label-c$conc-$pod.log" 2>&1 &
    pids+=($!)
  done

  local rc=0
  DURATION="$dur" "$SCRIPTS/run-point.sh" "$conc" "$label" || rc=$?
  kill "${pids[@]}" 2>/dev/null || true
  [ "$rc" -eq 0 ] && log "Point $label c$conc succeeded" || log "ERROR: point $label c$conc failed (rc=$rc)"

  "$SCRIPTS/verify-point.sh" "$RESULTS/$label/c$conc" || log "WARNING: verify-point warnings for $label c$conc"
  for f in "$RESULTS"/streams/$label-c$conc-*.log; do
    log "  $(basename "$f"): close_session=$(grep -c 'POST /close_session' "$f") release_session(TP0)=$(grep 'TP0\]' "$f" | grep -c 'release_session')"
  done
  return $rc
}

log "=== Step 32 follow-up: c=48, 3600 s per arm ==="
restart_sglang

log "--- Smoke c=4 (thunder-close, 120 s) ---"
configure_epp "$HERE/thunder-close-plugins.yaml" "thunder-close"
run_one_point 4 sglang-1h-smoke 120 || { log "FATAL: smoke failed"; exit 1; }
status=$(python3 -c "import json; print(json.load(open('$RESULTS/sglang-1h-smoke/c4/meta/finish.json')).get('job_status'))" 2>/dev/null)
[ "$status" = "succeeded" ] || { log "FATAL: smoke job status $status"; exit 1; }
grep -q 'usage_prompt_cache_read_tokens' "$RESULTS/sglang-1h-smoke/c4/aiperf_artifacts/profile_export.jsonl" \
  || { log "FATAL: smoke responses carry no cached-token usage"; exit 1; }
log "Smoke OK: responses carry cached-token usage"

log "--- c48 baseline-lru (closeSession: false), 3600 s ---"
configure_epp "$HERE/baseline-lru-plugins.yaml" "baseline-lru"
run_one_point 48 sglang-baseline-lru-1h 3600

log "--- c48 thunder-close (closeSession: true), 3600 s ---"
configure_epp "$HERE/thunder-close-plugins.yaml" "thunder-close"
run_one_point 48 sglang-thunder-close-1h 3600

log "--- Analysis ---"
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/compare-1h-c48/report" \
  "$RESULTS"/sglang-baseline-lru-1h/c48 "$RESULTS"/sglang-thunder-close-1h/c48 > "$RESULTS/analyze-1h.log" 2>&1 \
  || log "analyze.py exited non-zero (see analyze-1h.log)"
if [ -f "$RESULTS/compare-1h-c48/report/summary.csv" ]; then
  uv run "$SCRIPTS/make_figures.py" --out "$RESULTS/compare-1h-c48/report" \
    --baseline sglang-baseline-lru-1h \
    --name "sglang-thunder-close-1h=ThunderAgent (closeSession=true)" \
    --name "sglang-baseline-lru-1h=ThunderAgent (closeSession=false)" \
    "$RESULTS/compare-1h-c48/report/summary.csv" > "$RESULTS/make_figures-1h.log" 2>&1 \
    || log "make_figures.py exited non-zero (see make_figures-1h.log)"
fi
log "=== Done. Results under $RESULTS/{sglang-baseline-lru-1h,sglang-thunder-close-1h}/c48 ==="
