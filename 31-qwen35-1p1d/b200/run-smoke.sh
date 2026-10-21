#!/usr/bin/env bash
# Step 31 smoke test of the minimal P/D pair (qwen35-pd-prefill + qwen35-pd-decode on node 5qjv)
# behind the P/D EPP (agentx-epp-pd-epp, always-disagg-pd-decider):
#   1. wait for both servers; record each one's KV pool and the connectors it loaded;
#   2. one chat completion through the EPP, then check that it went P -> D: the sidecar logged the
#      prefill target, the prefill vLLM served it, and the decode vLLM pulled KV over NIXL;
#   3. AgentX c=4 for 120 s through the EPP (run-point.sh MODE=pool, both servers reset before),
#      then verify-point.sh;
#   4. NIXL and CPU-offload counters from both servers' /metrics.
# The servers and the EPP stay up afterwards.
# Usage: setsid nohup ./run-smoke.sh > results/run-smoke.log 2>&1 < /dev/null &
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
LABEL=qwen35-1p1d-smoke
EPP=agentx-epp-pd-epp
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
pod_of() { k get pods -l "app=$1" -o jsonpath='{.items[0].metadata.name}'; }
metrics() {  # metrics <pod> <regex>: matching sample lines from the pod's vLLM /metrics
  k exec "$1" -c modelserver -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8200/metrics', timeout=10).read().decode())" \
    | grep -E "$2" | grep -v '^#'
}
mkdir -p "$RESULTS"

echo "=== 1. servers ($(ts))"
for d in qwen35-pd-prefill qwen35-pd-decode; do
  k rollout status "deploy/$d" --timeout=60m || { echo "$d did not become available; stopping"; exit 1; }
done
P=$(pod_of qwen35-pd-prefill); D=$(pod_of qwen35-pd-decode)
for p in "$P" "$D"; do
  echo "--- $p"
  k logs "$p" -c modelserver | grep -E "Model loading took|GPU KV cache size|Creating v1 connector|NixlConnector|OffloadingConnector|MultiConnector|Bidirectional KV|nixl.*backend|UCX" | cut -c1-240 | head -12
  metrics "$p" '^vllm:cache_config_info' | grep -oE 'kv_cache_size_tokens="[0-9]+"|num_gpu_blocks="[0-9]+"|block_size="[0-9]+"' | tr '\n' ' '; echo
done
k rollout status "deploy/$EPP" --timeout=5m || exit 1

echo "=== 2. one request through the EPP ($(ts))"
k run "pd-curl-$$" --rm -i --restart=Never --image=curlimages/curl:8.10.1 \
  --overrides='{"spec":{"nodeSelector":{"cloud.google.com/gke-nodepool":"pool-1"}}}' -- \
  curl -sS -m 300 "http://$EPP:80/v1/chat/completions" -H 'content-type: application/json' -H 'x-session-id: pd-smoke-1' \
  -d '{"model":"Qwen/Qwen3.5-397B-A17B-FP8","max_tokens":64,"messages":[{"role":"user","content":"Write one sentence about prefill/decode disaggregation."}]}' \
  | tee "$RESULTS/one-request.json" | head -c 1200; echo
echo "--- sidecar (prefill target)"
k logs "$D" -c routing-proxy --since=10m | grep -i -E "prefill|prefiller|error" | cut -c1-300 | tail -5
echo "--- prefill vLLM (request served)"
k logs "$P" -c modelserver --since=10m | grep -E "POST /v1/(chat/)?completions|ERROR|Traceback" | cut -c1-240 | tail -5
echo "--- decode vLLM (NIXL pull)"
k logs "$D" -c modelserver --since=10m | grep -i -E "nixl|transfer|handshake|ERROR|Traceback|POST /v1" | cut -c1-240 | tail -8

echo "=== 3. AgentX c=4, 120 s ($(ts))"
k delete job "agentx-c4-$LABEL" --ignore-not-found --wait=true >/dev/null
if MODE=pool URL="http://$EPP:80" EPP_DEPLOY="$EPP" DEPLOY=qwen35-pd-decode DECODE_SELECTOR=stack=qwen35-1p1d LANE=qb \
    DURATION=120 EXTRA_ARGS="--tokenizer-trust-remote-code --unsafe-override" \
    "$SCRIPTS/run-point.sh" 4 "$LABEL" > "$RESULTS/$LABEL-c4.log" 2>&1; then
  echo "smoke point finished ($(ts))"
else
  echo "smoke point failed; see $RESULTS/$LABEL-c4.log ($(ts))"
fi
"$SCRIPTS/verify-point.sh" "$RESULTS/$LABEL/c4"

echo "=== 4. NIXL and offload counters ($(ts))"
for p in "$P" "$D"; do
  echo "--- $p"
  metrics "$p" 'nixl|kv_offload|offload|prefix_cache_(hits|queries)_total|external_prefix_cache|kv_transfer' | cut -c1-200 | head -25
done
echo "--- request errors in the logs"
for p in "$P" "$D"; do echo "$p: $(k logs "$p" -c modelserver --since=15m | grep -c -E 'ERROR|Traceback') error lines"; done
echo "=== done ($(ts))"
