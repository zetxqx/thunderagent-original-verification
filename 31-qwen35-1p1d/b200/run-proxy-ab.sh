#!/usr/bin/env bash
# Step 31, router-less P/D A/B for the vllm-project/vllm#62862 fix (zetxqx/vllm#1).
# Same P/D pair and flags as smokes 4-5 (always P -> D, bidirectional_kv_xfer false), but the client
# goes to vLLM's NIXL toy proxy (pd-proxy.yaml) instead of the llm-d EPP + disagg sidecar.
# Arms, in order (each restarts both vLLM servers, about 12 minutes):
#   fix:  VLLM_PR62862=1 on P and D (the PR's scheduler.py + multi_connector.py, ported onto v0.31.0)
#   base: VLLM_PR62862=0 (stock v0.31.0)
# Per arm: check the patch is (not) applied, one request through the proxy, counters, AgentX c=4 for
# 120 s (run-point.sh MODE=direct, both servers' KV tiers emptied before), verify-point, deltas.
# Usage: setsid nohup ./run-proxy-ab.sh > results/run-proxy-ab.log 2>&1 < /dev/null &
#        ARMS="fix" ./run-proxy-ab.sh   # one arm only
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
ARMS=${ARMS:-fix base}
CONC=${CONC:-4}
DURATION=${DURATION:-120}
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
pod_of() { k get pods -l "app=$1" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}'; }
counters() {  # counters <pod> <out-file>, as run-smoke-prefix.sh
  k exec "$1" -c modelserver -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8200/metrics', timeout=10).read().decode())" \
    | grep -v '^#' | grep -E '^vllm:(request_success_total|prompt_tokens_total|prefix_cache_(hits|queries)_total|external_prefix_cache_(hits|queries)_total|nixl_bytes_transferred_(sum|count)|nixl_num_failed_transfers_total|kv_offload_[a-z_]*(bytes|size)_(total|sum))[{ ]' \
    | sed -E 's/\{[^}]*\}/ /' | awk '{a[$1]+=$2} END {for (k in a) printf "%s %.0f\n", k, a[k]}' | sort > "$2"
}
mkdir -p "$RESULTS"

echo "=== 0. ConfigMaps and proxy ($(ts))"
k create configmap vllm-pr62862 --from-file="$HERE/pr62862/scheduler.py" --from-file="$HERE/pr62862/multi_connector.py" \
  --dry-run=client -o yaml | k apply -f - >/dev/null || exit 1
k create configmap pd-proxy-script --from-file="$HERE/toy_proxy_server.py" --dry-run=client -o yaml | k apply -f - >/dev/null || exit 1
k apply -f "$HERE/pd-proxy.yaml" >/dev/null || exit 1
k rollout restart deploy/pd-proxy >/dev/null; k rollout status deploy/pd-proxy --timeout=15m || exit 1
k apply -f "$HERE/vllm-qwen35-pd.yaml" >/dev/null || exit 1

for ARM in $ARMS; do
  case "$ARM" in fix) FLAG=1 ;; base) FLAG=0 ;; *) echo "unknown arm $ARM"; exit 1 ;; esac
  LABEL=qwen35-1p1d-proxy-$ARM
  echo "=== $ARM: 1. servers with VLLM_PR62862=$FLAG ($(ts))"
  for d in qwen35-pd-prefill qwen35-pd-decode; do k set env "deploy/$d" -c modelserver "VLLM_PR62862=$FLAG" >/dev/null; done
  for d in qwen35-pd-prefill qwen35-pd-decode; do
    k rollout status "deploy/$d" --timeout=60m || { echo "$d did not become available; stopping"; exit 1; }
  done
  P=$(pod_of qwen35-pd-prefill); D=$(pod_of qwen35-pd-decode)
  for p in "$P" "$D"; do
    n=$(k logs "$p" -c modelserver | grep -c "VLLM_PR62862: applied")
    echo "$p: patch applied lines=$n (want $FLAG)"
    [ "$n" = "$FLAG" ] || { echo "patch state mismatch; stopping"; exit 1; }
  done

  echo "=== $ARM: 2. one request through the proxy ($(ts))"
  k exec deploy/pd-proxy -- python3 -c "
import json, urllib.request
req = urllib.request.Request('http://localhost:8000/v1/chat/completions', method='POST',
  headers={'content-type': 'application/json'},
  data=json.dumps({'model': '$MODEL', 'max_tokens': 64,
    'messages': [{'role': 'user', 'content': 'Write one sentence about prefill/decode disaggregation.'}]}).encode())
print(urllib.request.urlopen(req, timeout=300).read().decode()[:800])" || { echo "proxy request failed; stopping"; exit 1; }
  k logs "$D" -c modelserver --since=5m | grep -i -E "nixl compat|POST /v1/chat|ERROR|Traceback" | cut -c1-240 | tail -3

  echo "=== $ARM: 3. AgentX c=$CONC, $DURATION s ($(ts))"
  counters "$P" "$RESULTS/$LABEL-P-before.txt"; counters "$D" "$RESULTS/$LABEL-D-before.txt"
  k delete job "agentx-c$CONC-$LABEL" --ignore-not-found --wait=true >/dev/null
  MODE=direct URL=http://pd-proxy:8000 DEPLOY=qwen35-pd-decode DECODE_SELECTOR=stack=qwen35-1p1d LANE=qb \
    DURATION=$DURATION EXTRA_ARGS="--tokenizer-trust-remote-code --unsafe-override" \
    "$SCRIPTS/run-point.sh" "$CONC" "$LABEL" > "$RESULTS/$LABEL-c$CONC.log" 2>&1 \
    && echo "point finished ($(ts))" || echo "point failed; see $RESULTS/$LABEL-c$CONC.log ($(ts))"
  counters "$P" "$RESULTS/$LABEL-P-after.txt"; counters "$D" "$RESULTS/$LABEL-D-after.txt"
  "$SCRIPTS/verify-point.sh" "$RESULTS/$LABEL/c$CONC"

  echo "=== $ARM: 4. counter deltas over the point ($(ts))"
  for s in P D; do
    echo "--- $s"
    join "$RESULTS/$LABEL-$s-before.txt" "$RESULTS/$LABEL-$s-after.txt" | awk '{printf "  %-50s %15.0f\n", $1, $3-$2}'
  done
  python3 - "$RESULTS/$LABEL/c$CONC/aiperf_artifacts/profile_export.jsonl" <<'EOF'
import json, sys, collections
def v(m, k):
    x = m.get(k); return (x.get('value') if isinstance(x, dict) else x) or 0
recs = sorted((json.loads(l) for l in open(sys.argv[1])), key=lambda r: r['metadata']['request_start_ns'])
by = collections.defaultdict(list)
for r in recs: by[r['metadata']['conversation_id']].append(r)
ttft = sorted(v(r['metrics'], 'time_to_first_token') for r in recs)
print(f"--- client: {len(recs)} requests in {len(by)} conversations")
if ttft: print(f"    TTFT ms median {ttft[len(ttft)//2]:.0f}, max {ttft[-1]:.0f}")
EOF
  for p in "$P" "$D"; do echo "$p: $(k logs "$p" -c modelserver --since=15m | grep -c -E 'ERROR|Traceback') error lines"; done
done
echo "=== done ($(ts))"
