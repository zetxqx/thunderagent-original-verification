#!/usr/bin/env bash
# Step 31, second smoke: same P/D pair, EPP switched to prefix-based-pd-decider (pd-plugins-prefix.yaml).
# Questions: do later turns of a session stay on the decode pod, and does the decode pod then hit its
# own prefix cache (smoke 1, always-disagg: 0 local hits, every turn's whole prompt pulled over NIXL)?
#   1. re-render and apply the EPP with pd-plugins-prefix.yaml, check the decider in the config;
#   2. snapshot both servers' counters, AgentX c=4 for 120 s (run-point.sh, both servers reset), snapshot;
#   3. counter deltas per server and the client's first-turn / later-turn split.
# Usage: setsid nohup ./run-smoke-prefix.sh > results/run-smoke-prefix.log 2>&1 < /dev/null &
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
LABEL=qwen35-1p1d-prefix-smoke
EPP=agentx-epp-pd-epp
ts() { date -u +%H:%M:%S; }
k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
pod_of() { k get pods -l "app=$1" -o jsonpath='{.items[0].metadata.name}'; }
# counters <pod> <out-file>: the summed vLLM counters this smoke compares, one "name value" per line
counters() {
  k exec "$1" -c modelserver -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8200/metrics', timeout=10).read().decode())" \
    | grep -v '^#' | grep -E '^vllm:(request_success_total|prompt_tokens_total|prefix_cache_(hits|queries)_total|external_prefix_cache_(hits|queries)_total|nixl_bytes_transferred_(sum|count)|nixl_num_failed_transfers_total|kv_offload_[a-z_]*(bytes|size)_(total|sum))[{ ]' \
    | sed -E 's/\{[^}]*\}/ /' | awk '{a[$1]+=$2} END {for (k in a) printf "%s %.0f\n", k, a[k]}' | sort > "$2"
}
mkdir -p "$RESULTS"

echo "=== 1. EPP with prefix-based-pd-decider ($(ts))"
PLUGINS="$HERE/pd-plugins-prefix.yaml" "$HERE/render-epp.sh" pd > "$RESULTS/lane-epp-pd-prefix.yaml" || { echo "render failed"; exit 1; }
k apply -f "$RESULTS/lane-epp-pd-prefix.yaml" >/dev/null || { echo "apply failed"; exit 1; }
k rollout restart "deploy/$EPP" >/dev/null; k rollout status "deploy/$EPP" --timeout=5m || exit 1
sleep 5
k logs "deploy/$EPP" -c epp | grep -E '"parsed config"|prefix-based-pd-decider|ERROR' | grep -v 'parsing response' | cut -c1-500 | tail -4
k get configmap "$EPP" -o yaml | grep -q 'prefill: prefix-based-pd-decider' && echo "decider in the EPP config: prefix-based-pd-decider" \
  || { echo "the EPP config does not use prefix-based-pd-decider; stopping"; exit 1; }

P=$(pod_of qwen35-pd-prefill); D=$(pod_of qwen35-pd-decode)
echo "=== 2. AgentX c=4, 120 s ($(ts))"
counters "$P" "$RESULTS/$LABEL-P-before.txt"; counters "$D" "$RESULTS/$LABEL-D-before.txt"
k delete job "agentx-c4-$LABEL" --ignore-not-found --wait=true >/dev/null
MODE=pool URL="http://$EPP:80" EPP_DEPLOY="$EPP" DEPLOY=qwen35-pd-decode DECODE_SELECTOR=stack=qwen35-1p1d LANE=qb \
  DURATION=120 EXTRA_ARGS="--tokenizer-trust-remote-code --unsafe-override" \
  "$SCRIPTS/run-point.sh" 4 "$LABEL" > "$RESULTS/$LABEL-c4.log" 2>&1 \
  && echo "smoke point finished ($(ts))" || echo "smoke point failed; see $RESULTS/$LABEL-c4.log ($(ts))"
counters "$P" "$RESULTS/$LABEL-P-after.txt"; counters "$D" "$RESULTS/$LABEL-D-after.txt"
"$SCRIPTS/verify-point.sh" "$RESULTS/$LABEL/c4"

echo "=== 3. counter deltas over the point ($(ts))"
for s in P D; do
  echo "--- $s"
  join "$RESULTS/$LABEL-$s-before.txt" "$RESULTS/$LABEL-$s-after.txt" | awk '{printf "  %-50s %15.0f\n", $1, $3-$2}'
done
python3 - "$RESULTS/$LABEL/c4/aiperf_artifacts/profile_export.jsonl" <<'EOF'
import json, sys, collections
def v(m, k):
    x = m.get(k); return (x.get('value') if isinstance(x, dict) else x) or 0
recs = sorted((json.loads(l) for l in open(sys.argv[1])), key=lambda r: r['metadata']['request_start_ns'])
by = collections.defaultdict(list)
for r in recs: by[r['metadata']['conversation_id']].append(r)
first = sum(1 for rs in by.values()); later = len(recs) - first
ftok = sum(v(rs[0]['metrics'], 'input_sequence_length') for rs in by.values())
ltok = sum(v(r['metrics'], 'input_sequence_length') for rs in by.values() for r in rs[1:])
new = [max(0, v(r['metrics'], 'input_sequence_length') - v(p['metrics'], 'input_sequence_length') - v(p['metrics'], 'output_sequence_length'))
       for rs in by.values() for p, r in zip(rs, rs[1:])]
print(f"--- client: {len(recs)} requests in {len(by)} conversations; first turns {first} ({ftok:,} tokens), later turns {later} ({ltok:,} tokens)")
if new: print(f"    later turns' new tokens vs the previous turn: median {sorted(new)[len(new)//2]:,}, max {max(new):,}, over 4096: {sum(n >= 4096 for n in new)}")
ttft = sorted(v(r['metrics'], 'time_to_first_token') for r in recs)
if ttft: print(f"    TTFT ms median {ttft[len(ttft)//2]:.0f}, max {ttft[-1]:.0f}")
EOF
echo "=== done ($(ts))"
