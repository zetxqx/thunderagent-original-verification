#!/usr/bin/env bash
# Smoke test for the thunder-agent plugin in the llm-d-router EPP.
# Port-forwards to the EPP's envoy sidecar (traffic) and metrics port, then
# checks, in order: the running build, that the plugin loaded with the
# faithful config, real per-pod capacity, program tracking and stickiness
# across turns, class accounting, and session-final release.
set -uo pipefail

NS=llm-d-program-aware-scheduling
MODEL="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
HTTP=18081
METRICS=19090
FAILS=0
# Unique session ids per run: the EPP keeps program state (until the idle
# TTL) and its counters are cumulative, so checks below are deltas.
RUN=$(date +%s)
A="smoke-a-$RUN"; B="smoke-b-$RUN"

kubectl port-forward svc/program-aware-scheduling-epp -n "$NS" "$HTTP:80" "$METRICS:9090" >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 3

# The metrics port enforces kube-rbac on its non-resource URLs; see
# metrics-reader-rbac.yaml for the identity used here.
TOKEN=$(kubectl create token thunderagent-metrics-reader -n "$NS" --duration=1h)
mget() { curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:$METRICS$1"; }

step()  { echo; echo "=== $1 ==="; }
check() { # check <description> <condition-exit-code>
  if [ "$2" -eq 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; FAILS=$((FAILS+1)); fi
}
metric() { # metric <name> [label-filter]  -> prints the value of the first matching series
  mget /metrics | grep -E "^[a-z_]*$1(\{[^}]*${2:-}[^}]*\})? " | head -1 | awk '{print $NF}'
}
state() { # state -> the thunder-agent plugin's state JSON
  mget /debug/plugins/state | python3 -c '
import json,sys
d=json.load(sys.stdin)
for p in d.get("plugins",{}).values():
    if p.get("type")=="thunder-agent":
        print(json.dumps(p.get("state"))); break'
}
field() { echo "$1" | python3 -c "import json,sys; d=json.load(sys.stdin); print($2)"; }
chat() { # chat <session-id> <json-messages> [extra-curl-args...]
  local sid="$1" msgs="$2"; shift 2
  curl -s -D /tmp/smoke-headers "http://localhost:$HTTP/v1/chat/completions" \
    -H 'Content-Type: application/json' -H "x-session-id: $sid" "$@" \
    -d "{\"model\": \"$MODEL\", \"max_tokens\": 40, \"messages\": $msgs}"
}
reply() { python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'; }

step "1. running build"
INFO=$(mget /metrics | grep -E "^[a-z_]*inference_extension_info\{" | head -1)
echo "$INFO"
check "build info metric present" $([ -n "$INFO" ]; echo $?)

step "2. plugin loaded with the faithful config (new metrics exist only in this build)"
NAMES=$(mget /metrics | grep -oE "thunder_agent_[a-z_]+" | sort -u | tr '\n' ' ')
echo "metrics: $NAMES"
check "thunder_agent_pauses_total exists (v3 build)" $(echo "$NAMES" | grep -q pauses_total; echo $?)
check "thunder_agent_resumes_total exists (v3 build)" $(echo "$NAMES" | grep -q resumes_total; echo $?)
check "thunder_agent_sheds_total absent (old build)" $(echo "$NAMES" | grep -q sheds_total; [ $? -ne 0 ]; echo $?)

step "3. per-pod capacity is the real scraped value"
mget /metrics | grep -E "^[a-z_]*thunder_agent_pod_capacity_tokens" | sed 's/^.*thunder_agent_/thunder_agent_/'
REAL=$(mget /metrics | grep -cE 'thunder_agent_pod_capacity_tokens\{[^}]*source="real"[^}]*\} 2\.23704e\+06')
check "4 pods report source=real with 2,237,040 tokens (got $REAL)" $([ "$REAL" -eq 4 ]; echo $?)

step "4. state dump and counters before traffic"
S0=$(state); echo "$S0"
P0=$(field "$S0" 'd["totalPrograms"]')
NEW0=$(metric releases_total 'class="new"'); REAS0=$(metric releases_total 'class="reasoning"'); REB0=$(metric rebinds_total); FIN0=$(metric session_final_releases_total)
NEW0=${NEW0:-0}; REAS0=${REAS0:-0}; REB0=${REB0:-0}; FIN0=${FIN0:-0}
echo "baseline: programs=$P0 releases new=$NEW0 reasoning=$REAS0 rebinds=$REB0 final_releases=$FIN0"
check "state dump reachable" $([ -n "$P0" ]; echo $?)

step "5a. session smoke-a, turn 1"
R1=$(chat "$A" '[{"role":"user","content":"Say exactly: hello from turn one"}]')
echo "assistant: $(echo "$R1" | reply)"
grep -i "x-gateway-destination-endpoint\|x-went-into-req-headers\|HTTP/" /tmp/smoke-headers | tr -d '\r' | head -3
check "turn 1 answered" $(echo "$R1" | reply >/dev/null 2>&1; echo $?)

step "5b. session smoke-a, turn 2 (same history, grown)"
MSGS=$(echo "$R1" | python3 -c '
import json,sys; r=json.load(sys.stdin)
print(json.dumps([{"role":"user","content":"Say exactly: hello from turn one"},
 {"role":"assistant","content":r["choices"][0]["message"]["content"]},
 {"role":"user","content":"Now say exactly: hello from turn two"}]))')
R2=$(chat "$A" "$MSGS")
echo "assistant: $(echo "$R2" | reply)"
check "turn 2 answered" $(echo "$R2" | reply >/dev/null 2>&1; echo $?)

step "5c. session smoke-b, turn 1"
R3=$(chat "$B" '[{"role":"user","content":"Say exactly: hello from b"}]')
echo "assistant: $(echo "$R3" | reply)"
check "smoke-b answered" $(echo "$R3" | reply >/dev/null 2>&1; echo $?)

step "6. state dump after traffic: two programs, committed tokens, bound pods"
S1=$(state); echo "$S1"
check "2 new programs tracked" $([ "$(field "$S1" 'd["totalPrograms"]')" = "$((P0+2))" ]; echo $?)
check "committed tokens > 0" $([ "$(field "$S1" 'int(d["totalCommittedTokens"]>0)')" = "1" ]; echo $?)
check "no in-flight tokens left" $([ "$(field "$S1" 'd["totalInflightTokens"]')" = "0" ]; echo $?)
check "no program paused" $([ "$(field "$S1" 'd["pausedPrograms"]')" = "0" ]; echo $?)
check "every bound pod carries tokens" $([ "$(field "$S1" 'int(len(d["pods"])>0 and all(p["tokens"]>0 for p in d["pods"].values()))')" = "1" ]; echo $?)

step "7. class accounting and stickiness"
NEW=$(metric releases_total 'class="new"'); REAS=$(metric releases_total 'class="reasoning"'); REB=$(metric rebinds_total); HOLD=$(metric holds_total); PAUSE=$(metric pauses_total)
echo "deltas: releases new=$((NEW-NEW0)) reasoning=$((REAS-REAS0)) rebinds=$((REB-REB0)); totals holds=${HOLD:-0} pauses=$PAUSE"
check "two first turns dispatched as class=new" $([ "$((NEW-NEW0))" = "2" ]; echo $?)
check "one follow-up turn dispatched as class=reasoning" $([ "$((REAS-REAS0))" = "1" ]; echo $?)
check "no rebinds: $A stayed on its pod" $([ "$((REB-REB0))" = "0" ]; echo $?)
check "no holds, no pauses at real capacity" $([ "${HOLD:-0}" = "0" ] && [ "${PAUSE:-0}" = "0" ]; echo $?)

step "8. session-final releases $A"
R4=$(chat "$A" "$MSGS" -H 'x-session-final: true')
echo "assistant: $(echo "$R4" | reply)"
sleep 1
S2=$(state); echo "$S2"
check "one program released by the final turn" $([ "$(field "$S2" 'd["totalPrograms"]')" = "$((P0+1))" ]; echo $?)
check "session_final_releases_total advanced by 1" $([ "$(( $(metric session_final_releases_total) - FIN0 ))" = "1" ]; echo $?)

echo; echo "=== $FAILS check(s) failed ==="
exit $FAILS
