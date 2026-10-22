#!/usr/bin/env bash
# Step 32: SGLang session radix cache with ThunderAgent close_session on 8x B200 (Qwen3.5-397B-A17B-FP8)
# Concurrency grid: c in {16, 24, 32, 48} (strictly adhering to user instructions)
# Profiling duration: 900s per point
# Two arms:
#   1. thunder-close: closeSession=true (PR #16 image thunder-sglang-close-7eec9d9c)
#   2. baseline-lru:  closeSession=false
#
# Pre-run smoke test: c=4 (120s) with thunder-close.
#
# Usage: setsid nohup ./run-benchmark.sh > results/run-benchmark.log 2>&1 < /dev/null &
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
export DURATION=900
export EXTRA_ARGS="--tokenizer-trust-remote-code --unsafe-override"
export RESTART=0
export RESET=0

ts() { date -u +%H:%M:%S; }
log() { echo "[$(ts)] $*"; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }

mkdir -p "$RESULTS"

# 1. Wait for both SGLang model servers to be ready
wait_for_servers() {
  log "Waiting for SGLang deployments to be ready..."
  k rollout status deploy/sglang-qwen35-a --timeout=30m || { log "sglang-qwen35-a rollout failed"; exit 1; }
  k rollout status deploy/sglang-qwen35-b --timeout=30m || { log "sglang-qwen35-b rollout failed"; exit 1; }
  
  log "Checking SGLang /v1/models endpoint on all pods..."
  for pod in $(k get pods -l "$DECODE_SELECTOR" --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}'); do
    local ok=0
    for i in $(seq 1 60); do
      if k exec "$pod" -c "$VLLM_CONTAINER" -- python3 -c "
import urllib.request
r = urllib.request.urlopen('http://localhost:8000/v1/models', timeout=5)
assert r.status == 200" >/dev/null 2>&1; then
        ok=1
        log "  $pod is healthy and serving /v1/models"
        break
      fi
      sleep 5
    done
    if [ "$ok" -ne 1 ]; then
      log "FATAL: $pod did not become healthy in 5 minutes"
      exit 1
    fi
  done
}

# 2. Flush SGLang Radix Cache across all pods
flush_sglang_cache() {
  log "Flushing SGLang radix cache on all model servers..."
  for pod in $(k get pods -l "$DECODE_SELECTOR" --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}'); do
    k exec "$pod" -c "$VLLM_CONTAINER" -- python3 -c "
import urllib.request
req = urllib.request.Request('http://localhost:8000/flush_cache', data=b'', method='POST')
try:
    r = urllib.request.urlopen(req, timeout=10)
    print(f'  $pod flush status: {r.status}')
except Exception as e:
    print(f'  $pod flush warning: {e}')
" || log "Warning: flush call failed on $pod"
  done
}

# 3. Apply EPP plugins config and rollout restart
configure_epp() {
  local plugins_file="$1"
  local arm_name="$2"
  log "Configuring EPP with $plugins_file for arm: $arm_name"
  
  "$HERE/render-epp.sh" sglang "$plugins_file" | k apply -f -
  k rollout restart "deploy/$EPP_DEPLOY"
  k rollout status "deploy/$EPP_DEPLOY" --timeout=5m
  log "EPP $EPP_DEPLOY rollout complete for $arm_name"
}

# 4. Run single concurrency point
run_one_point() {
  local conc="$1"
  local label="$2"
  local dur="$3"
  
  log "=== Starting Point: conc=$conc, label=$label, duration=${dur}s ==="
  
  # Clean up any stale Job for this point
  local job_name
  job_name=$(echo "agentx-c$conc-$label" | tr '[:upper:]_.' '[:lower:]--' | cut -c1-63)
  k delete job "$job_name" --ignore-not-found --wait=true >/dev/null 2>&1 || true
  
  # Flush SGLang cache & restart EPP to guarantee fresh state
  flush_sglang_cache
  k rollout restart "deploy/$EPP_DEPLOY" >/dev/null 2>&1
  k rollout status "deploy/$EPP_DEPLOY" --timeout=5m >/dev/null 2>&1
  
  if DURATION="$dur" PROFILE=a4-pr DEPLOY=sglang-qwen35-a GPUS_PER_POD=4 \
     "$SCRIPTS/run-point.sh" "$conc" "$label"; then
    log "Point conc=$conc label=$label succeeded"
  else
    log "WARNING: Point conc=$conc label=$label failed; retrying once..."
    k delete job "$job_name" --ignore-not-found --wait=true >/dev/null 2>&1 || true
    flush_sglang_cache
    k rollout restart "deploy/$EPP_DEPLOY" >/dev/null 2>&1
    k rollout status "deploy/$EPP_DEPLOY" --timeout=5m >/dev/null 2>&1
    if DURATION="$dur" PROFILE=a4-pr DEPLOY=sglang-qwen35-a GPUS_PER_POD=4 \
       "$SCRIPTS/run-point.sh" "$conc" "$label"; then
      log "Point conc=$conc label=$label succeeded on retry"
    else
      log "ERROR: Point conc=$conc label=$label failed on retry"
    fi
  fi
  
  "$SCRIPTS/verify-point.sh" "$RESULTS/$label/c$conc" || log "WARNING: verify-point reported warnings for c$conc"
}

# ----------------- EXECUTION FLOW -----------------

log "=================================================="
log "Step 32: SGLang Session Radix Cache Benchmark"
log "Grid: c in {16, 24, 32, 48}"
log "Model: $MODEL, 8x B200 (2x TP=4)"
log "=================================================="

# Phase 0: Wait for model servers
wait_for_servers

# Phase 1: Smoke Test with thunder-close (c=4, 120s)
log "--- Phase 1: Smoke Test (c=4, 120s) ---"
configure_epp "$HERE/thunder-close-plugins.yaml" "thunder-close"

SMOKE_LABEL="sglang-smoke"
run_one_point 4 "$SMOKE_LABEL" 120

# Check smoke test finish status
if [ -f "$RESULTS/$SMOKE_LABEL/c4/meta/finish.json" ]; then
  status=$(python3 -c "import json; print(json.load(open('$RESULTS/$SMOKE_LABEL/c4/meta/finish.json')).get('job_status'))")
  if [ "$status" = "succeeded" ]; then
    log "Smoke test Job succeeded!"
  else
    log "FATAL: Smoke test Job status is $status; aborting"
    exit 1
  fi
else
  log "FATAL: Smoke test did not produce meta/finish.json; aborting"
  exit 1
fi

# Check smoke test metrics
log "Smoke test verification:"
grep -c '"severity_text":"ERROR"' "$RESULTS"/$SMOKE_LABEL/c4/epp-*.log 2>/dev/null | sed 's/^/  EPP error lines: /' || true
if [ -f "$RESULTS/$SMOKE_LABEL/c4/epp/raw-epp-metrics.txt.gz" ]; then
  log "  EPP close_session metric samples:"
  zcat "$RESULTS/$SMOKE_LABEL/c4/epp/raw-epp-metrics.txt.gz" | grep -E 'thunder_agent_session_closes_total' | tail -5 | sed 's/^/    /' || true
fi

# Phase 2: Arm 1 - thunder-close (c in 16, 24, 32, 48)
ARM1_LABEL="sglang-thunder-close"
log "--- Phase 2: Arm 1 - thunder-close (closeSession: true) ---"
configure_epp "$HERE/thunder-close-plugins.yaml" "thunder-close"

for c in 16 24 32 48; do
  run_one_point "$c" "$ARM1_LABEL" 900
done

# Phase 3: Arm 2 - baseline-lru (c in 16, 24, 32, 48)
ARM2_LABEL="sglang-baseline-lru"
log "--- Phase 3: Arm 2 - baseline-lru (closeSession: false) ---"
configure_epp "$HERE/baseline-lru-plugins.yaml" "baseline-lru"

for c in 16 24 32 48; do
  run_one_point "$c" "$ARM2_LABEL" 900
done

# Phase 4: Comparative Analysis & Figure Generation
log "--- Phase 4: Analysis & Figures ---"
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --out "$RESULTS/compare-report" \
  "$RESULTS"/$ARM1_LABEL/c* "$RESULTS"/$ARM2_LABEL/c* > "$RESULTS/analyze.log" 2>&1 || log "analyze.py finished with warnings"

if [ -f "$RESULTS/compare-report/summary.csv" ]; then
  uv run "$SCRIPTS/make_figures.py" --out "$RESULTS/compare-figures" \
    --baseline "$ARM2_LABEL" \
    --name "$ARM1_LABEL=ThunderAgent (closeSession=true)" \
    --name "$ARM2_LABEL=Baseline (closeSession=false)" \
    "$RESULTS/compare-report/summary.csv" > "$RESULTS/make_figures.log" 2>&1 || log "make_figures.py finished with warnings"
fi

log "=================================================="
log "Step 32 Benchmark Complete! All artifacts in $RESULTS"
log "=================================================="
