#!/usr/bin/env bash
# Step 34: thunder-agent (PR zetxqx/llm-d-router#15) on the step 33 1P1D pair, against step 33's
# no-thunder baseline. Servers untouched since step 33 (vllm#62862 fix on, decode MAX_NUM_SEQS 256).
# Client -> agentx-epp-pdt-epp (envoy + EPP: P/D always-disagg + thunder gate) -> decode sidecar,
# which prefills on P and decodes on D.
#   1. smoke: AgentX c=4 for 120 s, verify-point (EPP scrape present, no gate warning);
#   2. c=64 and c=96, 60 min each (step 26/33 settings: RESET=1, the EPP restarted before each point,
#      so the ledger starts empty), a failed point retried once;
#   3. analyze both arms together against step 33 (COMPARE_CONCS, default CONCS).
# Usage: setsid nohup ./run-thunder.sh > results/run-thunder.log 2>&1 < /dev/null &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"
export PATH="$HOME/.local/bin:$PATH"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=Qwen/Qwen3.5-397B-A17B-FP8 DATASET=semianalysis_cc_traces_weka_062126_256k
export CLIENT_POOL=pool-1 GPUS_PER_POD=4 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=3 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=12Gi
export RESTART=0 RESET=1 VLLM_PORTS=8200
EPP=agentx-epp-pdt-epp
export MODE=pool URL=http://$EPP:80 EPP_DEPLOY=$EPP DEPLOY=qwen35-pd-decode DECODE_SELECTOR=stack=qwen35-1p1d LANE=pdt
LABEL=${LABEL:-qwen35-1p1d-thunder-l10}
CONCS=${CONCS:-64 96}
SMOKE=${SMOKE:-1}
COMPARE_CONCS=${COMPARE_CONCS:-$CONCS}   # points analyzed together at the end (e.g. "64 96 128")
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

echo "=== analyze against step 33 ($(ts))"
B33="$HERE/../../33-qwen35-1p1d-baseline/b200/results/qwen35-1p1d-baseline"
pts=()
for c in $COMPARE_CONCS; do pts+=("$B33/c$c"); for d in "$RESULTS"/$LABEL/c$c "$RESULTS"/$LABEL-retry/c$c; do [ -d "$d" ] && pts+=("$d"); done; done
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/compare/report" "${pts[@]}"
echo "=== done ($(ts))"
