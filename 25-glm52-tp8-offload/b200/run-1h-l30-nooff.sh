#!/usr/bin/env bash
# Step 25 exploration, 1-hour points, round 2 (2026-10-11, user request):
#  - default thunder (thunder-plugins.yaml: GPU capacity, lease 30 s, backstop 1800 s,
#    image -produces) at c=20, 24, 32, with CPU offload, to complete the three-arm
#    report (c=12 and 16: formal thunder-r1 points);
#  - no CPU offload (--kv-offloading-* removed): no router at c=16, 24, 32 and
#    thunder-gpu-l10 at c=16, 24, 32, to measure what offload does.
# Same method as run-1h.sh: no client-side restart, RESET=1 empties the KV cache (and
# restarts the EPP) before every point, 3600 s, MAX_NUM_SEQS 64. Four chains:
#   A glm52-tp8   (lane a): offload off, then no router c=24, c=32, c=16
#   B glm52-tp8-b (lane b, agentx-epp-a): l30 c=24; offload off; l10 c=24
#   C glm52-tp8-c (lane c, agentx-epp-c): l30 c=32; offload off; l10 c=32
#   D glm52-tp8-d (lane d, agentx-epp-d): l30 c=20; offload off; l10 c=16
# The servers are left without offload at the end; `kubectl apply -f vllm-<x>.yaml`
# restores B, C, D (A also needs MAX_NUM_SEQS 64).
# Usage: nohup caffeinate -i ./run-1h-l30-nooff.sh > results/run-1h-l30-nooff.log 2>&1 &
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="$HERE/../../.claude/skills/agentic-benchmark/scripts"

export RESULTS="$HERE/results"
export CTX=gke_supercomputer-testing_europe-west4_a4-pr
export KUBECONFIG_SOURCE=/tmp/a4-pr.kubeconfig
export NS=bobzetian-llmd
export MODEL=nvidia/GLM-5.2-NVFP4 DATASET=semianalysis_cc_traces_weka_062126
export CLIENT_POOL=pool-1 GPUS_PER_POD=8 MODEL_SERVER_COLLECT=0
export CLIENT_CPU=4 CLIENT_MEM=32Gi CLIENT_MEM_REQUEST=16Gi
export EXTRA_ARGS="--tokenizer-trust-remote-code" DURATION=3600 RESTART=0 RESET=1
L30=explore1h-thunder-gpu-l30 DIRECT_NOOFF=explore1h-direct-nooff THUNDER_NOOFF=explore1h-thunder-gpu-l10-nooff

k() { KUBECONFIG=$KUBECONFIG_SOURCE kubectl --context "$CTX" -n "$NS" "$@"; }
dep_of() { [ "$1" = a ] && echo glm52-tp8 || echo "glm52-tp8-$1"; }
epp_of() { [ "$1" = b ] && echo agentx-epp-a-epp || echo "agentx-epp-$1-epp"; }

offload_off() {  # offload_off <server>: drop the --kv-offloading-* line; one rollout
  local dep; dep=$(dep_of "$1")
  echo "=== $1: removing CPU offload from $dep ($(date -u +%H:%M:%S))"
  k get "deploy/$dep" -o json | python3 -c "
import json, sys
d = json.load(sys.stdin)
c = d['spec']['template']['spec']['containers'][0]
c['args'] = ['\n'.join(l for l in a.split('\n') if '--kv-offloading-' not in l) for a in c['args']]
print(json.dumps(d))" | k replace -f - || return 1
  k rollout status "deploy/$dep" --timeout=90m || return 1
  echo "=== $1: $dep up without offload ($(date -u +%H:%M:%S))"
}
point() {  # point <server> <direct|thunder> <concurrency> <label>; one retry
  local srv=$1 arm=$2 c=$3 label=$4 dep epp try
  dep=$(dep_of "$srv"); epp=$(epp_of "$srv")
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
thunder_chain() {  # thunder_chain <server> <lane file l30> <l30 conc> <lane file l10> <no-offload conc>
  local srv=$1 rc=0
  k apply -f "$HERE/$2" >/dev/null || return 1
  point "$srv" thunder "$3" "$L30" || rc=1
  offload_off "$srv" || return 1
  k apply -f "$HERE/$4" >/dev/null || return 1
  point "$srv" thunder "$5" "$THUNDER_NOOFF" || rc=1
  echo "=== $srv done ($(date -u +%H:%M:%S))"
  return $rc
}
direct_chain() {
  local rc=0 c
  offload_off a || return 1
  for c in 24 32 16; do point a direct "$c" "$DIRECT_NOOFF" || rc=1; done
  echo "=== a done ($(date -u +%H:%M:%S))"
  return $rc
}

FAILED=""
direct_chain & pa=$!
sleep 5
thunder_chain b lane-epp-a-gpu-l30-b.yaml 24 lane-epp-a-gpu-l10-b.yaml 24 & pb=$!
sleep 5
thunder_chain c lane-epp-c-gpu-l30-c.yaml 32 lane-epp-c-gpu-l10-c.yaml 32 & pc=$!
sleep 5
thunder_chain d lane-epp-d-gpu-l30-d.yaml 20 lane-epp-d-gpu-l10-d.yaml 16 & pd=$!
wait $pa || FAILED="$FAILED A"
wait $pb || FAILED="$FAILED B"
wait $pc || FAILED="$FAILED C"
wait $pd || FAILED="$FAILED D"

uv run "$SCRIPTS/analyze.py" --out "$RESULTS/explore1h-r2/report" \
  "$RESULTS"/explore1h-thunder-gpu-l30/c* "$RESULTS"/explore1h-*-nooff/c*
rm -f "$RESULTS/bobbm.kubeconfig"
[ -z "$FAILED" ] || { echo "chains with a failed point:$FAILED"; exit 1; }
