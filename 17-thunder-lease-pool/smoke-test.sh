#!/usr/bin/env bash
# Smoke test of the lease thunder-agent on the main EPP release over the
# 4-pod pool: deploy the thunder-lease arm the way run-pool.sh does, then check
# the running build, the lease build's metric set, scraped capacity on every
# pod, session tracking across turns, class accounting and a clean EPP log.
# Every check reads /metrics. Exit code is the number of failed checks.
# Usage: smoke-test.sh [image-tag]   (kubectl/helm must point at bobbm)
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
POOL="$HERE/../12-llm-d-router-pool"
NS=llm-d-program-aware-scheduling
RELEASE=program-aware-scheduling
SVC=program-aware-scheduling-epp
TAG="${1:-thunder-agent-lease-20e3b1ee}"
COMMIT="${TAG##*-}"
CHART="${LLM_D_ROUTER:-$HOME/projects/llmdthunder/llm-d-router}/config/charts/llm-d-router-standalone"
MODEL="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
HTTP=18082
METRICS=19092
FAILS=0
RUN=$(date +%s)
A="smoke-a-$RUN"; B="smoke-b-$RUN"

step()  { echo; echo "=== $1 ==="; }
check() { if [ "$2" -eq 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; FAILS=$((FAILS+1)); fi; }

step "0. deploy the thunder-lease arm on the main release (image $TAG)"
helm upgrade "$RELEASE" "$CHART" -n "$NS" -f "$POOL/main-values.yaml" --set "router.epp.image.tag=$TAG" \
  --set-file "router.epp.pluginsCustomConfig.thunder-plugins\.yaml=$POOL/thunder-lease-plugins.yaml" >/dev/null
kubectl rollout restart "deploy/$SVC" -n "$NS" >/dev/null
kubectl rollout status "deploy/$SVC" -n "$NS" --timeout=300s
EPP_POD=$(kubectl get pod -n "$NS" --field-selector=status.phase=Running -o name | grep "$SVC" | head -1 | sed 's|pod/||')
echo "epp pod $EPP_POD"
[ -n "$EPP_POD" ] || { echo "FATAL: no running EPP pod found"; exit 1; }
sleep 10

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
msum() { # msum <name> -> sum over every series
  mget | grep -E "^[a-z_]*$1(\{[^}]*\})? " | awk '{s+=$NF} END {printf "%d\n", s}'
}
programs() { echo $(( $(metric thunder_agent_programs 'state="running"') + $(metric thunder_agent_programs 'state="idle"') + $(metric thunder_agent_programs 'state="paused"') )); }
chat() { # chat <session-id> <json-messages>
  curl -s "http://localhost:$HTTP/v1/chat/completions" -H 'Content-Type: application/json' -H "x-session-id: $1" \
    -d "{\"model\": \"$MODEL\", \"max_tokens\": 40, \"messages\": $2}"
}
reply() { python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'; }

step "1. running build and config"
INFO=$(mget | grep -E "^[a-z_]*(inference_extension|llm_d_epp)_info\{" | head -1); echo "$INFO"
check "build info reports commit $COMMIT" $(echo "$INFO" | grep -q "commit=\"$COMMIT"; echo $?)
check "live ConfigMap has idleLeaseSeconds: 30" $(kubectl get cm "$SVC" -n "$NS" -o yaml | grep -q "idleLeaseSeconds: 30"; echo $?)

step "2. metric set of the lease build"
NAMES=$(mget | grep -oE "thunder_agent_[a-z_]+" | sort -u | tr '\n' ' '); echo "metrics: $NAMES"
check "pod_working_set_tokens exists" $(echo "$NAMES" | grep -q pod_working_set_tokens; echo $?)
check "resumes_total absent (removed in the lease build)" $(echo "$NAMES" | grep -q resumes_total; [ $? -ne 0 ]; echo $?)
check "working set has no view label" $(mget | grep -q 'thunder_agent_pod_working_set_tokens{[^}]*view='; [ $? -ne 0 ]; echo $?)
check "capacity has no source label" $(mget | grep -q 'thunder_agent_pod_capacity_tokens{[^}]*source='; [ $? -ne 0 ]; echo $?)

step "3. every pod reports its scraped capacity"
mget | grep -E "^[a-z_]*thunder_agent_pod_capacity_tokens" | sed 's/^.*thunder_agent_/thunder_agent_/'
CAP=$(mget | grep -cE '^[a-z_]*thunder_agent_pod_capacity_tokens\{[^}]*\} 2\.23704e\+06')
check "4 pods at 2,237,040 tokens (got $CAP series)" $([ "$CAP" -eq 4 ]; echo $?)

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
check "pool working set > 0" $([ "$(msum thunder_agent_pod_working_set_tokens)" -gt 0 ]; echo $?)

step "7. class accounting"
NEW=$(metric releases_total 'class="new"'); REAS=$(metric releases_total 'class="reasoning"')
HOLD=$(( $(metric holds_total 'class="new"') + $(metric holds_total 'class="paused"') + $(metric holds_total 'class="reasoning"') )); PAUSE=$(metric pauses_total)
echo "deltas: releases new=$((NEW-NEW0)) reasoning=$((REAS-REAS0)); totals holds=$HOLD pauses=$PAUSE"
check "two first turns dispatched as class=new" $([ "$((NEW-NEW0))" = "2" ]; echo $?)
check "one follow-up turn dispatched as class=reasoning" $([ "$((REAS-REAS0))" = "1" ]; echo $?)
check "no holds, no pauses on an idle pool" $([ "$HOLD" = "0" ] && [ "$PAUSE" = "0" ]; echo $?)

step "8. EPP log"
LOG=$(kubectl logs "$EPP_POD" -n "$NS" -c epp 2>/dev/null)
ERRS=$(echo "$LOG" | grep -ciE '"level":"(error|dpanic|panic|fatal)"|panic:' || true)
echo "EPP log: $(echo "$LOG" | wc -l | tr -d ' ') lines"
check "no error or panic lines in the EPP log (got $ERRS of $(echo "$LOG" | wc -l | tr -d ' ') lines)" $([ -n "$LOG" ] && [ "$ERRS" -eq 0 ]; echo $?)

echo; echo "=== $FAILS check(s) failed ==="
exit $FAILS
