#!/usr/bin/env bash
# Step 25 exploration, 1-hour points at high concurrency (2026-10-12, user request): the
# CPU tier holds about 18.2M tokens (one copy for the 8 GPUs, see README Setup), and the
# working set reaches it around c=70 to 90; measure no router and thunder-gpu-l10 (GPU
# capacity, lease 10 s, backstop 1800 s, image -produces) at c=48, 64, 96, 128, with offload.
# Same method as run-1h.sh: no server restart per point, RESET=1 empties both KV tiers (and
# restarts the EPP), 3600 s, MAX_NUM_SEQS 64. First every server gets its offload flags back
# (run-1h-l30-nooff.sh removed them). Four chains, paired points run at the same time:
#   A glm52-tp8   (lane a): no router c=128, then c=48
#   B glm52-tp8-b (lane b, agentx-epp-a): thunder c=128, then c=48
#   C glm52-tp8-c (lane c, agentx-epp-c): thunder c=96, then c=64
#   D glm52-tp8-d (lane d): no router c=96, then c=64
# Clients get a 48 GiB limit (24 GiB request): prompts reach about 790k tokens at up to 128
# lanes. No `rm` of results/bobbm.kubeconfig at the end (see run-1h-nooff-tail.sh).
# Usage: nohup caffeinate -i ./run-1h-highc.sh > results/run-1h-highc.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=48Gi CLIENT_MEM_REQUEST=24Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
DIRECT=explore1h-direct THUNDER=explore1h-thunder-gpu-l10

k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
dep_of() { [ "$1" = a ] && echo glm52-tp8 || echo "glm52-tp8-$1"; }
epp_of() { [ "$1" = b ] && echo agentx-epp-a-epp || echo "agentx-epp-$1-epp"; }

offload_on() {  # offload_on <server>: put the --kv-offloading-* line back after the MTP line
  local dep; dep=$(dep_of "$1")
  echo "=== $1: restoring CPU offload on $dep ($(date -u +%H:%M:%S))"
  k get "deploy/$dep" -o json | python3 -c "
import json, sys
d = json.load(sys.stdin)
c = d['spec']['template']['spec']['containers'][0]
out = []
for a in c['args']:
    lines = [l for l in a.split('\n') if '--kv-offloading-' not in l]
    i = next(i for i, l in enumerate(lines) if '--speculative-config' in l)
    lines.insert(i + 1, '  --kv-offloading-size 820 --kv-offloading-backend native \\\\')
    out.append('\n'.join(lines))
c['args'] = out
assert any(e['name'] == 'MAX_NUM_SEQS' and e['value'] == '64' for e in c['env']), 'MAX_NUM_SEQS is not 64'
print(json.dumps(d))" | k replace -f - || return 1
  k rollout status "deploy/$dep" --timeout=90m || return 1
  echo "=== $1: $dep up with offload ($(date -u +%H:%M:%S))"
}
point() {  # point <server> <direct|thunder> <concurrency>; one retry
  local srv=$1 arm=$2 c=$3 dep epp label try
  dep=$(dep_of "$srv"); epp=$(epp_of "$srv")
  if [ "$arm" = direct ]; then label=$DIRECT; else label=$THUNDER; fi
  echo "=== $srv: $label c=$c ($(date -u +%H:%M:%S))"
  for try in "$label" "$label-retry"; do
    if [ "$arm" = direct ]; then
      MODE=direct URL=http://$dep:8000 DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$srv \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    else
      MODE=pool URL=http://$epp:80 EPP_DEPLOY=$epp DEPLOY=$dep DECODE_SELECTOR=app=$dep LANE=$srv \
        "$SCRIPTS/run-point.sh" "$c" "$try" > "$RESULTS/$try-c$c.log" 2>&1 && return 0
    fi
    echo "=== $try/c$c on $srv failed; $( [ "$try" = "$label" ] && echo retrying || echo giving up ) ($(date -u +%H:%M:%S))"
  done
  return 1
}
chain() {  # chain <server> <arm> <conc> <conc> [lane file]
  local srv=$1 rc=0
  [ -n "${5:-}" ] && { k apply -f "$HERE/$5" >/dev/null || return 1; }
  offload_on "$srv" || return 1
  point "$srv" "$2" "$3" || rc=1
  point "$srv" "$2" "$4" || rc=1
  echo "=== $srv done ($(date -u +%H:%M:%S))"
  return $rc
}

FAILED=""
chain a direct 128 48 & pa=$!
sleep 5
chain b thunder 128 48 lane-epp-a-gpu-l10-b.yaml & pb=$!
sleep 5
chain c thunder 96 64 lane-epp-c-gpu-l10-c.yaml & pc=$!
sleep 5
chain d direct 96 64 & pd=$!
wait $pa || FAILED="$FAILED A"
wait $pb || FAILED="$FAILED B"
wait $pc || FAILED="$FAILED C"
wait $pd || FAILED="$FAILED D"

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore1h-highc/report" \
  "$RESULTS"/explore1h-direct/c{48,64,96,128} "$RESULTS"/explore1h-thunder-gpu-l10/c{48,64,96,128}
[ -z "$FAILED" ] || { echo "chains with a failed point:$FAILED"; exit 1; }
