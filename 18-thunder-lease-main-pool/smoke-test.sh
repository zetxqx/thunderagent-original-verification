#!/usr/bin/env bash
# Smoke test of the step 18 build on the single-pod lane (deploy-lane.sh
# first): the running build and config, the renamed metric set of the
# minimal ledger, scraped capacity, session tracking across turns, class
# accounting and a clean EPP log. Exit code is the number of failed checks.
# Usage: smoke-test.sh [commit]   (kubectl must point at bobbm)
set -uo pipefail

NS=llm-d-program-aware-scheduling
SVC=thunder-lane-a-epp
COMMIT="${1:-1a98a6c5}"
MODEL="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
HTTP=18083
METRICS=19094
FAILS=0
RUN=$(date +%s)
A="smoke-a-$RUN"; B="smoke-b-$RUN"

step()  { echo; echo "=== $1 ==="; }
check() { if [ "$2" -eq 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; FAILS=$((FAILS+1)); fi; }

EPP_POD=$(kubectl get pod -n "$NS" --field-selector=status.phase=Running -o name | grep "$SVC" | head -1 | sed 's|pod/||')
[ -n "$EPP_POD" ] || { echo "FATAL: no running lane EPP pod"; exit 1; }
echo "epp pod $EPP_POD"

kubectl port-forward "svc/$SVC" -n "$NS" "$HTTP:80" "$METRICS:9090" >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 3

TOKEN=$(kubectl create token thunderagent-metrics-reader -n "$NS" --duration=1h)
mget() { curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:$METRICS/metrics"; }
metric() { # metric <name> [label-filter] -> value of the first matching series, 0 if absent
  local v; v=$(mget | grep -E "^[a-z_]*$1(\{[^}]*${2:-}[^}]*\})? " | head -1 | awk '{print $NF}')
  python3 -c "print(int(float('${v:-0}')))"
}
sessions() { echo $(( $(metric thunder_agent_sessions 'state="running"') + $(metric thunder_agent_sessions 'state="idle"') + $(metric thunder_agent_sessions 'state="paused"') )); }
chat() { # chat <session-id> <json-messages>
  curl -s "http://localhost:$HTTP/v1/chat/completions" -H 'Content-Type: application/json' -H "x-session-id: $1" \
    -d "{\"model\": \"$MODEL\", \"max_tokens\": 40, \"messages\": $2}"
}
reply() { python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'; }

step "1. running build and config"
INFO=$(mget | grep -E "^[a-z_]*(inference_extension|llm_d_epp)_info\{" | head -1); echo "$INFO"
check "build info reports commit $COMMIT" $(echo "$INFO" | grep -q "commit=\"$COMMIT"; echo $?)
check "live ConfigMap has idleLeaseSeconds: 30" $(kubectl get cm "$SVC" -n "$NS" -o yaml | grep -q "idleLeaseSeconds: 30"; echo $?)

step "2. metric set of the minimal ledger"
NAMES=$(mget | grep -oE "thunder_agent_[a-z_]+" | sort -u | tr '\n' ' '); echo "metrics: $NAMES"
# holds_total and releases_total are labeled counters: they appear only once
# incremented, so step 7 checks releases and the run checks holds.
for want in sessions endpoint_working_set_tokens endpoint_capacity_tokens pauses_total resumes_total starvation_promotions_total; do
  check "$want exists" $(echo "$NAMES" | grep -qw "thunder_agent_$want"; echo $?)
done
check "old names programs and pod_working_set_tokens absent" $(echo "$NAMES" | grep -qE "thunder_agent_(programs|pod_working_set_tokens)"; [ $? -ne 0 ]; echo $?)
check "working set has no view label" $(mget | grep -q 'thunder_agent_endpoint_working_set_tokens{[^}]*view='; [ $? -ne 0 ]; echo $?)

step "3. the lane pod reports its scraped capacity"
mget | grep -E "^[a-z_]*thunder_agent_endpoint_capacity_tokens" | sed 's/^.*thunder_agent_/thunder_agent_/'
CAP=$(mget | grep -cE '^[a-z_]*thunder_agent_endpoint_capacity_tokens\{[^}]*\} 2\.23704e\+06')
check "1 pod at 2,237,040 tokens (got $CAP series)" $([ "$CAP" -eq 1 ]; echo $?)

step "4. counters before traffic"
S0=$(sessions); NEW0=$(metric releases_total 'class="new"'); ADM0=$(metric releases_total 'class="admitted"')
echo "sessions=$S0 releases new=$NEW0 admitted=$ADM0"

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

step "6. accounting after traffic (metrics are computed at scrape time)"
mget | grep -E "^[a-z_]*thunder_agent_(sessions|endpoint_working_set_tokens)" | sed 's/^.*thunder_agent_/thunder_agent_/'
check "2 new sessions tracked (sessions $S0 -> $(sessions))" $([ "$(sessions)" = "$((S0+2))" ]; echo $?)
check "no session running after the turns ended (in-flight closed)" $([ "$(metric thunder_agent_sessions 'state="running"')" = "0" ]; echo $?)
check "no session paused" $([ "$(metric thunder_agent_sessions 'state="paused"')" = "0" ]; echo $?)
check "working set > 0" $([ "$(metric thunder_agent_endpoint_working_set_tokens)" -gt 0 ]; echo $?)

step "7. class accounting"
NEW=$(metric releases_total 'class="new"'); ADM=$(metric releases_total 'class="admitted"')
HOLD=$(( $(metric holds_total 'class="new"') + $(metric holds_total 'class="paused"') + $(metric holds_total 'class="admitted"') )); PAUSE=$(metric pauses_total)
echo "deltas: releases new=$((NEW-NEW0)) admitted=$((ADM-ADM0)); totals holds=$HOLD pauses=$PAUSE"
check "two first turns dispatched as class=new" $([ "$((NEW-NEW0))" = "2" ]; echo $?)
check "one follow-up turn dispatched as class=admitted" $([ "$((ADM-ADM0))" = "1" ]; echo $?)
check "no holds, no pauses on an idle pod" $([ "$HOLD" = "0" ] && [ "$PAUSE" = "0" ]; echo $?)

step "8. EPP log"
LOG=$(kubectl logs "$EPP_POD" -n "$NS" -c epp 2>/dev/null)
ERRS=$(echo "$LOG" | grep -ciE '"level":"(error|dpanic|panic|fatal)"|"severity_text":"(ERROR|FATAL)"|panic:' || true)
check "no error or panic lines in the EPP log (got $ERRS of $(echo "$LOG" | wc -l | tr -d ' ') lines)" $([ -n "$LOG" ] && [ "$ERRS" -eq 0 ]; echo $?)

echo; echo "=== $FAILS check(s) failed ==="
exit $FAILS
