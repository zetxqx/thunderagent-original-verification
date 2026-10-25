#!/usr/bin/env bash
# Step 38: thunder-agent (PR zetxqx/llm-d-router#15, image thunder-pd-8d1fbc87) on the step 37 GLM-5.2
# 2P1D servers (two prefill + one decode TP=8 server on three nodes), against step 37's no-router
# baseline. Servers untouched since step 37.
# Client -> agentx-epp-g2pt-epp (envoy + EPP: P/D always-disagg, prefill pinned per session, thunder gate
# with the decode pod's KV pool as capacity) -> decode sidecar, which prefills on the picked P and
# decodes on D.
#   1. smoke: AgentX c=4 for 120 s, verify-point (EPP scrape present, no gate warning);
#   2. CONCS, 60 min each (RESET=1: both KV tiers of all three servers emptied and the EPP restarted
#      before each point, so the ledger starts empty), a failed point retried once;
#   3. analyze against step 37 at the same concurrencies.
# Usage: setsid nohup ./run-thunder.sh > results/run-thunder.log 2>&1 < /dev/null &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
export PATH="$HOME/.local/bin:$PATH"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=64Gi CLIENT_MEM_REQUEST=16Gi
export RESTART=0 RESET=1 VLLM_PORTS=8200
EPP=agentx-epp-g2pt-epp
export MODE=pool URL=http://$EPP:80 EPP_DEPLOY=$EPP DEPLOY=glm52-2p1d-decode DECODE_SELECTOR=stack=glm52-2p1d LANE=g2pt
LABEL=${LABEL:-glm52-2p1d-thunder-l10}
CONCS=${CONCS:-96 48 64 32 144}
SMOKE=${SMOKE:-1}
COMPARE_CONCS=${COMPARE_CONCS:-32 48 64 96 144}
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
mkdir -p "$RESULTS"

if [ "$SMOKE" = 1 ]; then
  echo "=== smoke c=4, 120 s ($(ts))"
  k delete job agentx-c4-$LABEL-smoke --ignore-not-found --wait=true >/dev/null
  DURATION=120 EXTRA_ARGS="--tokenizer-trust-remote-code --unsafe-override" \
    "$SCRIPTS/run-point.sh" 4 "$LABEL-smoke" > "$RESULTS/$LABEL-smoke-c4.log" 2>&1 \
    || { echo "smoke failed; see $RESULTS/$LABEL-smoke-c4.log ($(ts))"; exit 1; }
  "$SCRIPTS/verify-point.sh" "$RESULTS/$LABEL-smoke/c4" || { echo "smoke not valid; stopping"; exit 1; }
  for d in glm52-2p1d-prefill-a glm52-2p1d-prefill-b; do
    echo "$d served $(k logs deploy/$d -c modelserver --since=6m | grep -c 'POST /v1') requests in the smoke window"
  done
  [ "${SMOKE_ONLY:-0}" = 1 ] && { echo "=== smoke only, stopping ($(ts))"; exit 0; }
fi

export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600
for c in $CONCS; do
  for try in "$LABEL" "$LABEL-retry"; do
    echo "=== c=$c as $try ($(ts))"
    k delete job "agentx-c$c-$try" --ignore-not-found --wait=true >/dev/null
    if "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1; then
      echo "=== c=$c done ($(ts))"; "$SCRIPTS/verify-point.sh" "$RESULTS/$try/c$c"; break
    fi
    echo "=== c=$c failed as $try; see $RESULTS/$try-c$c.log ($(ts))"
  done
done

echo "=== analyze against step 37 ($(ts))"
B37="$HERE/../../37-glm52-2p1d/b200/results/glm52-2p1d-baseline"
pts=()
for c in $COMPARE_CONCS; do pts+=("$B37/c$c"); for d in "$RESULTS"/$LABEL/c$c "$RESULTS"/$LABEL-retry/c$c; do [ -d "$d" ] && pts+=("$d"); done; done
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/compare/report" "${pts[@]}"
echo "=== all done ($(ts))"
