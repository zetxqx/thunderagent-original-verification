#!/usr/bin/env bash
# Smoke test of the minimal thunder-agent on the step 15 lane (one EPP, one
# vLLM pod): the running build, the metric set of the minimal plugin, real
# capacity, session tracking across turns, class accounting and stickiness.
# The minimal plugin has no state dump, so every check reads /metrics.
# Exit code is the number of failed checks.
set -uo pipefail

NS=llm-d-program-aware-scheduling
SVC=thunder-lane-a-epp
COMMIT="${COMMIT:-33dde5d2}"
MODEL="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
HTTP=18082
METRICS=19092
FAILS=0
RUN=$(date +%s)
A="smoke-a-$RUN"; B="smoke-b-$RUN"

kubectl port-forward "svc/$SVC" -n "$NS" "$HTTP:80" "$METRICS:9090" >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 3

TOKEN=$(kubectl create token thunderagent-metrics-reader -n "$NS" --duration=1h)
mget() { curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:$METRICS/metrics"; }

step()  { echo; echo "=== $1 ==="; }
check() { if [ "$2" -eq 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; FAILS=$((FAILS+1)); fi; }
metric() { # metric <name> [label-filter] -> value of the first matching series, 0 if absent
  local v; v=$(mget | grep -E "^[a-z_]*$1(\{[^}]*${2:-}[^}]*\})? " | head -1 | awk '{print $NF}')
  python3 -c "print(int(float('${v:-0}')))"
}
programs() { echo $(( $(metric thunder_agent_programs 'state="running"') + $(metric thunder_agent_programs 'state="idle"') + $(metric thunder_agent_programs 'state="paused"') )); }
chat() { # chat <session-id> <json-messages>
  curl -s "http://localhost:$HTTP/v1/chat/completions" -H 'Content-Type: application/json' -H "x-session-id: $1" \
    -d "{\"model\": \"$MODEL\", \"max_tokens\": 40, \"messages\": $2}"
}
reply() { python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'; }

step "1. running build"
INFO=$(mget | grep -E "^[a-z_]*(inference_extension|llm_d_epp)_info\{" | head -1); echo "$INFO"
check "build info reports commit $COMMIT" $(echo "$INFO" | grep -q "commit=\"$COMMIT"; echo $?)

step "2. metric set of the minimal plugin"
NAMES=$(mget | grep -oE "thunder_agent_[a-z_]+" | sort -u | tr '\n' ' '); echo "metrics: $NAMES"
check "pod_working_set_tokens exists (minimal build)" $(echo "$NAMES" | grep -q pod_working_set_tokens; echo $?)
for gone in pod_utilization rebinds_total session_final_releases_total reserved_pods; do
  check "$gone absent (removed in the minimal build)" $(echo "$NAMES" | grep -q "$gone"; [ $? -ne 0 ]; echo $?)
done

step "3. capacity is the real scraped value"
mget | grep -E "^[a-z_]*thunder_agent_pod_capacity_tokens" | sed 's/^.*thunder_agent_/thunder_agent_/'
REAL=$(mget | grep -cE 'thunder_agent_pod_capacity_tokens\{[^}]*source="real"[^}]*\} 2\.23704e\+06')
check "the lane pod reports source=real with 2,237,040 tokens (got $REAL series)" $([ "$REAL" -eq 1 ]; echo $?)

step "4. counters before traffic"
P0=$(programs); NEW0=$(metric releases_total 'class="new"'); REAS0=$(metric releases_total 'class="reasoning"')
echo "programs=$P0 releases new=$NEW0 reasoning=$REAS0"

step "5. traffic: two turns of $A, one of $B"
R1=$(chat "$A" '[{"role":"user","content":"Say exactly: hello from turn one"}]')
check "$A turn 1 answered: $(echo "$R1" | reply 2>/dev/null)" $(echo "$R1" | reply >/dev/null 2>&1; echo $?)
MSGS=$(echo "$R1" | python3 -c '
import json,sys; r=json.load(sys.stdin)
print(json.dumps([{"role":"user","content":"Say exactly: hello from turn one"},
 {"role":"assistant","content":r["choices"][0]["message"]["content"]},
 {"role":"user","content":"Now say exactly: hello from turn two"}]))')
R2=$(chat "$A" "$MSGS")
check "$A turn 2 answered: $(echo "$R2" | reply 2>/dev/null)" $(echo "$R2" | reply >/dev/null 2>&1; echo $?)
R3=$(chat "$B" '[{"role":"user","content":"Say exactly: hello from b"}]')
check "$B answered: $(echo "$R3" | reply 2>/dev/null)" $(echo "$R3" | reply >/dev/null 2>&1; echo $?)

step "6. accounting after traffic (gauges refresh at most once per second)"
sleep 3
mget | grep -E "^[a-z_]*thunder_agent_(programs|pod_working_set_tokens)" | sed 's/^.*thunder_agent_/thunder_agent_/'
check "2 new sessions tracked (programs $P0 -> $(programs))" $([ "$(programs)" = "$((P0+2))" ]; echo $?)
check "no session running after the turns ended (in-flight closed)" $([ "$(metric thunder_agent_programs 'state="running"')" = "0" ]; echo $?)
check "no session paused" $([ "$(metric thunder_agent_programs 'state="paused"')" = "0" ]; echo $?)
check "undecayed working set > 0" $([ "$(metric thunder_agent_pod_working_set_tokens 'view="undecayed"')" -gt 0 ]; echo $?)

step "7. class accounting"
NEW=$(metric releases_total 'class="new"'); REAS=$(metric releases_total 'class="reasoning"')
HOLD=$(( $(metric holds_total 'class="new"') + $(metric holds_total 'class="paused"') + $(metric holds_total 'class="reasoning"') )); PAUSE=$(metric pauses_total)
echo "deltas: releases new=$((NEW-NEW0)) reasoning=$((REAS-REAS0)); totals holds=$HOLD pauses=$PAUSE"
check "two first turns dispatched as class=new" $([ "$((NEW-NEW0))" = "2" ]; echo $?)
check "one follow-up turn dispatched as class=reasoning" $([ "$((REAS-REAS0))" = "1" ]; echo $?)
check "no holds, no pauses at real capacity" $([ "$HOLD" = "0" ] && [ "$PAUSE" = "0" ]; echo $?)

echo; echo "=== $FAILS check(s) failed ==="
exit $FAILS
