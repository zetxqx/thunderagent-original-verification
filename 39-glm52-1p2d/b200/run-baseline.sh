#!/usr/bin/env bash
# Step 39: no-router 1P2D sweep for GLM-5.2-NVFP4 on step 37's three nodes:
#   glm52-2p1d-prefill-a (TP=8, gw0s) + glm52-2p1d-decode (TP=8, p3mf) + glm52-1p2d-decode-b (TP=8, t3gv),
#   KV over NIXL/RDMA between the nodes, 820 GiB CPU tier on each, vllm#62862 fix on;
#   client -> pd-proxy (vLLM toy proxy: every request P with max_tokens=1, then D; a session's turns go to
#   the same decode server by a hash of X-Session-ID, which the client sends: SESSION_ID_HEADER).
# Client settings as step 37 (uncapped 1M-context Weka traces, 60 min per point, RESET=1: all three
# servers' KV tiers emptied before every point, no restart), run-point.sh MODE=direct.
#   0. config: scale step 37's prefill-b and step 38's EPP to 0, start decode-b, switch the proxy; wait;
#      check the patch on all three servers and the routing (8 sessions x 2 turns: both decoders used,
#      a session's second turn on the same decoder);
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
LABEL=${LABEL:-glm52-1p2d-baseline}
CONCS=${CONCS:-64 96 32 48 144}
SMOKE=${SMOKE:-1}
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
pod_of() { k get pods -l "app=$1" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}'; }
mkdir -p "$RESULTS"

echo "=== 0. config ($(ts))"
k scale deploy/glm52-2p1d-prefill-b deploy/agentx-epp-g2pt-epp --replicas=0 || exit 1
k wait --for=delete pod -l app=glm52-2p1d-prefill-b --timeout=10m || exit 1
k create configmap pd-proxy-script-1p2d --from-file="$HERE/toy_proxy_server.py" --dry-run=client -o yaml | k apply -f - >/dev/null || exit 1
k apply -f "$HERE/vllm-glm52-1p2d-decode-b.yaml" -f "$HERE/pd-proxy.yaml" >/dev/null || exit 1
k rollout status deploy/pd-proxy --timeout=15m || exit 1
for d in glm52-2p1d-prefill-a glm52-2p1d-decode glm52-1p2d-decode-b; do
  k rollout status "deploy/$d" --timeout=120m || { echo "$d did not become available; stopping"; exit 1; }
done
P=$(pod_of glm52-2p1d-prefill-a); DA=$(pod_of glm52-2p1d-decode); DB=$(pod_of glm52-1p2d-decode-b)
for p in "$P" "$DA" "$DB"; do
  # The start-up log line can be rotated away on a long-running pod (step 37's servers have run for a day),
  # so compare the installed files with the ConfigMap copies instead of grepping the log.
  n=$(k exec "$p" -c modelserver -- bash -c 'SP=/usr/local/lib/python3.12/dist-packages/vllm
    cmp -s /pr62862/scheduler.py "$SP/v1/core/sched/scheduler.py" && cmp -s /pr62862/multi_connector.py "$SP/distributed/kv_transfer/kv_connector/v1/multi_connector.py" && echo 1 || echo 0')
  echo "--- $p: patch installed=$n MAX_NUM_SEQS=$(k exec "$p" -c modelserver -- printenv MAX_NUM_SEQS)"
  [ "$n" = 1 ] || { echo "fix not applied on $p; stopping"; exit 1; }
  k logs "$p" -c modelserver | grep -E "GPU KV cache size|NixlConnector|OffloadingConnector" | cut -c1-200 | head -3
done
k exec deploy/pd-proxy -- python3 -c "
import json, urllib.request
for turn in (1, 2):
    for i in range(8):
        r = urllib.request.Request('http://localhost:8000/v1/chat/completions', method='POST', headers={'content-type': 'application/json', 'x-session-id': 'route-%d' % i},
          data=json.dumps({'model': '$MODEL', 'max_tokens': 4, 'messages': [{'role': 'user', 'content': 'Hi %d.' % i}]}).encode())
        urllib.request.urlopen(r, timeout=900).read()
print('16 requests ok')" || { echo "proxy request failed; stopping"; exit 1; }
for p in "$P" "$DA" "$DB"; do echo "$p served $(k logs "$p" -c modelserver --since=10m | grep -c 'POST /v1/chat') chat requests"; done
k logs "$DB" -c modelserver --since=10m | grep -i -E "nixl compat|handshake|ERROR|Traceback" | cut -c1-200 | tail -3

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

echo "=== analyze with step 37 at the same concurrencies ($(ts))"
B37="$HERE/../../37-glm52-2p1d/b200/results/glm52-2p1d-baseline"
pts=()
for c in 32 48 64 96 144; do
  [ -d "$B37/c$c" ] && pts+=("$B37/c$c")
  for d in "$RESULTS"/$LABEL/c$c "$RESULTS"/$LABEL-retry/c$c; do [ -d "$d" ] && pts+=("$d"); done
done
uv run "$SCRIPTS/analyze.py" --ttft-slo 60 --skip-minutes 5 --out "$RESULTS/compare/report" "${pts[@]}"
echo "=== all done ($(ts))"
