#!/usr/bin/env bash
# Step 33: no-thunder 1P1D baseline sweep for Qwen3.5-397B-A17B-FP8 on 5qjv.
#   qwen35-pd-prefill (TP=4, GPUs 4-7) + qwen35-pd-decode (TP=4, GPUs 0-3), KV over NIXL/RDMA,
#   CPU offload on both, vllm-project/vllm#62862 fix on (VLLM_PR62862=1), decode MAX_NUM_SEQS 256;
#   client -> pd-proxy (vLLM toy proxy: every request P with max_tokens=1, then D). No router, no gate.
# Per point (step 26 settings): AgentX 60 min, RESET=1 (both KV tiers on both servers emptied, no
# restart), run-point.sh MODE=direct; a failed point is retried once under <label>-retry.
# Usage: setsid nohup ./run-baseline.sh > results/run-baseline.log 2>&1 < /dev/null &
#        CONCS="32 64" ./run-baseline.sh
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
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1 VLLM_PORTS=8200
export MODE=direct URL=http://pd-proxy:8000 DEPLOY=qwen35-pd-decode DECODE_SELECTOR=stack=qwen35-1p1d LANE=qb
LABEL=${LABEL:-qwen35-1p1d-baseline}
CONCS=${CONCS:-32 48 64 96 128}
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
pod_of() { k get pods -l "app=$1" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}'; }
mkdir -p "$RESULTS"

echo "=== 0. config ($(ts))"
k create configmap vllm-pr62862 --from-file="$HERE/pr62862/scheduler.py" --from-file="$HERE/pr62862/multi_connector.py" \
  --dry-run=client -o yaml | k apply -f - >/dev/null || exit 1
k create configmap pd-proxy-script --from-file="$HERE/toy_proxy_server.py" --dry-run=client -o yaml | k apply -f - >/dev/null || exit 1
k apply -f "$HERE/pd-proxy.yaml" >/dev/null || exit 1
k rollout restart deploy/pd-proxy >/dev/null; k rollout status deploy/pd-proxy --timeout=15m || exit 1
k apply -f "$HERE/vllm-qwen35-pd.yaml" || exit 1
for d in qwen35-pd-prefill qwen35-pd-decode; do
  k rollout status "deploy/$d" --timeout=60m || { echo "$d did not become available; stopping"; exit 1; }
done
P=$(pod_of qwen35-pd-prefill); D=$(pod_of qwen35-pd-decode)
for p in "$P" "$D"; do
  n=$(k logs "$p" -c modelserver | grep -c "VLLM_PR62862: applied")
  seqs=$(k exec "$p" -c modelserver -- printenv MAX_NUM_SEQS)
  echo "$p: patch lines=$n MAX_NUM_SEQS=$seqs"
  [ "$n" = 1 ] || { echo "fix not applied on $p; stopping"; exit 1; }
done
k exec deploy/pd-proxy -- python3 -c "
import json, urllib.request
req = urllib.request.Request('http://localhost:8000/v1/chat/completions', method='POST', headers={'content-type': 'application/json'},
  data=json.dumps({'model': '$MODEL', 'max_tokens': 16, 'messages': [{'role': 'user', 'content': 'Say hi.'}]}).encode())
print(urllib.request.urlopen(req, timeout=300).read().decode()[:300])" || { echo "proxy request failed; stopping"; exit 1; }

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

echo "=== analyze ($(ts))"
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/$LABEL/report" "$RESULTS"/$LABEL*/c*
echo "=== done ($(ts))"
