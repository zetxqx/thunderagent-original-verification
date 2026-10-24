#!/usr/bin/env bash
# Step 37: no-router 2P1D sweep for GLM-5.2-NVFP4 across three nodes:
#   glm52-2p1d-prefill-a (TP=8, gw0s) + glm52-2p1d-prefill-b (TP=8, t3gv) + glm52-2p1d-decode (TP=8,
#   p3mf), KV over NIXL/RDMA between the nodes, 820 GiB CPU tier on each, vllm#62862 fix on;
#   client -> pd-proxy (vLLM toy proxy: every request P with max_tokens=1, then D; a session's turns go
#   to the same prefill server by a hash of X-Session-ID, which the client sends: SESSION_ID_HEADER).
# Client settings as steps 25/27 (uncapped 1M-context Weka traces, 60 min per point, RESET=1:
# both servers' KV tiers emptied before every point, no restart), run-point.sh MODE=direct.
#   0. config: ConfigMaps, proxy, servers; wait; check the patch, the NIXL path with one request;
#   1. smoke c=4 for 120 s + verify-point (SMOKE=0 skips);
#   2. CONCS, a failed point retried once; 3. analyze.
# Usage: setsid nohup ./run-baseline.sh > results/run-baseline.log 2>&1 < /dev/null &
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
export MODE=direct URL=http://pd-proxy:8000 DEPLOY=glm52-2p1d-decode DECODE_SELECTOR=stack=glm52-2p1d LANE=qb SESSION_ID_HEADER=true
LABEL=${LABEL:-glm52-2p1d-baseline}
CONCS=${CONCS:-32 48 64 96}
SMOKE=${SMOKE:-1}
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
pod_of() { k get pods -l "app=$1" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}'; }
mkdir -p "$RESULTS"

echo "=== 0. config ($(ts))"
k create configmap vllm-pr62862 --from-file="$HERE/pr62862/scheduler.py" --from-file="$HERE/pr62862/multi_connector.py" \
  --dry-run=client -o yaml | k apply -f - >/dev/null || exit 1
k create configmap pd-proxy-script --from-file="$HERE/toy_proxy_server.py" --dry-run=client -o yaml | k apply -f - >/dev/null || exit 1
k apply -f "$HERE/gpu-nic-claim.yaml" -f "$HERE/vllm-glm52-2p1d.yaml" -f "$HERE/pd-proxy.yaml" >/dev/null || exit 1
k rollout status deploy/pd-proxy --timeout=15m || exit 1
for d in glm52-2p1d-prefill-a glm52-2p1d-prefill-b glm52-2p1d-decode; do
  k rollout status "deploy/$d" --timeout=120m || { echo "$d did not become available; stopping"; exit 1; }
done
PA=$(pod_of glm52-2p1d-prefill-a); PB=$(pod_of glm52-2p1d-prefill-b); D=$(pod_of glm52-2p1d-decode)
for p in "$PA" "$PB" "$D"; do
  n=$(k logs "$p" -c modelserver | grep -c "VLLM_PR62862: applied")
  echo "--- $p: patch lines=$n MAX_NUM_SEQS=$(k exec "$p" -c modelserver -- printenv MAX_NUM_SEQS)"
  [ "$n" = 1 ] || { echo "fix not applied on $p; stopping"; exit 1; }
  k logs "$p" -c modelserver | grep -E "GPU KV cache size|MultiConnector|NixlConnector|OffloadingConnector|UCX|nixl.*backend" | cut -c1-220 | head -8
done
k exec deploy/pd-proxy -- python3 -c "
import json, urllib.request
req = urllib.request.Request('http://localhost:8000/v1/chat/completions', method='POST', headers={'content-type': 'application/json'},
  data=json.dumps({'model': '$MODEL', 'max_tokens': 16, 'messages': [{'role': 'user', 'content': 'Say hi.'}]}).encode())
print(urllib.request.urlopen(req, timeout=600).read().decode()[:300])
for sid in ('s-a', 's-b', 's-c', 's-d'):
    r = urllib.request.Request('http://localhost:8000/v1/chat/completions', method='POST', headers={'content-type': 'application/json', 'x-session-id': sid},
      data=json.dumps({'model': '$MODEL', 'max_tokens': 4, 'messages': [{'role': 'user', 'content': 'Hi.'}]}).encode())
    urllib.request.urlopen(r, timeout=600).read()" || { echo "proxy request failed; stopping"; exit 1; }
for p in "$PA" "$PB"; do echo "$p served $(k logs "$p" -c modelserver --since=10m | grep -c 'POST /v1/chat') chat requests"; done
k logs "$D" -c modelserver --since=10m | grep -i -E "nixl compat|handshake|POST /v1/chat|ERROR|Traceback" | cut -c1-220 | tail -4

if [ "$SMOKE" = 1 ]; then
  echo "=== 1. smoke c=4, 120 s ($(ts))"
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

echo "=== analyze ($(ts))"
pts=(); for c in $CONCS; do for d in "$RESULTS"/$LABEL/c$c "$RESULTS"/$LABEL-retry/c$c; do [ -d "$d" ] && pts+=("$d"); done; done
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/$LABEL/report" "${pts[@]}"
echo "=== done ($(ts))"
