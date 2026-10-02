#!/usr/bin/env bash
# Step 20 smoke test, after `offload.sh on`. On each replica: offloading is on
# at 400 GiB with the GPU KV unchanged, no restart or allocation failure, the
# CPU tier serves a prefix the GPU lost and reset_external clears it
# (cpu-tier-probe.py). Then the lanes, deployed with SMOKE_LANE_ARMS (default:
# phase B's first point, a baseline, b lease, c tier): build, live config, the
# gate capacity each lane uses, session and class accounting over a few turns,
# and clean EPP logs.
# Exit code is the number of failed checks. Output also goes to
# results/smoke-test-output.txt.
set -uo pipefail
# With pipefail, `producer | grep -q` fails when grep exits at the first match
# and the producer gets SIGPIPE, which happens on long input. So text is read
# into a variable and searched with here-strings (grep -q ... <<< "$VAR").
source "$(dirname "$0")/lib.sh"
pin_kube
SFX="${SMOKE_SUFFIX:-}"  # appended to this test's output files, so a later run keeps the earlier ones
exec > >(tee "$RESULTS/smoke-test-output$SFX.txt") 2>&1
MODEL="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
LANE_ARMS="${SMOKE_LANE_ARMS:-a:baseline b:thunder-lease-main c:thunder-lease-main-tier}"
COMMIT="${EPP_IMAGE_TAG##*-}"
TIER_CAP=$(grep -oE "capacityTokens: [0-9]+" "$STEP10/thunder-lease-main-tier-plugins.yaml" | awk '{print $2}')
FAILS=0
RUN=$(date +%s)

step()  { echo; echo "=== $1 ==="; }
check() { if [ "$2" -eq 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; FAILS=$((FAILS+1)); fi; }
within() { python3 -c "import sys; a,b,t=map(float,sys.argv[1:]); sys.exit(0 if abs(a-b) <= t*b else 1)" "$1" "$2" "$3"; echo $?; }
jq_() { python3 -c "import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1], {}, {'d': d}))" "$1"; }

echo "smoke test $(date)  image $EPP_IMAGE_TAG  tier capacityTokens $TIER_CAP"
[ "$(deploy_offload_size)" = "400 3" ] || { echo "FATAL: the deployment is not the 3-replica, 400 GiB state; run offload.sh on first" >&2; exit 1; }

for L in $LANES; do
  N=$(lane_node "$L"); P=$(vllm_pod_on "$N")
  step "lane $L replica $P on $N: offloading (checks 1 to 3)"
  [ -n "$P" ] || { check "a running replica on $N" 1; continue; }
  M=$(vllm_get "$P" /metrics)
  CC=$(grep '^vllm:cache_config_info' <<< "$M" | head -1); echo "$CC" | cut -c1-400
  check "cache_config_info reports kv_offloading_size 400" $(grep -qE 'kv_offloading_size="400(\.0)?"' <<< "$CC"; echo $?)
  BS=$(echo "$CC" | grep -oE 'block_size="[0-9]+"' | grep -oE '[0-9]+'); NB=$(echo "$CC" | grep -oE 'num_gpu_blocks="[0-9]+"' | grep -oE '[0-9]+')
  check "GPU KV unchanged: ${BS:-?} x ${NB:-?} = $GPU_KV_TOKENS tokens" $([ "$(( ${BS:-0} * ${NB:-0} ))" = "$GPU_KV_TOKENS" ]; echo $?)
  LOG=$(kubectl logs "$P" -n "$NS" -c modelserver 2>/dev/null)
  check "log names OffloadingConnector" $(grep -q "OffloadingConnector" <<< "$LOG"; echo $?)
  MM=$(grep -oE "Created mmap file /dev/shm/vllm_offload_[^ ]* \([0-9.]+ GB\)" <<< "$LOG" | head -1); echo "$MM"
  GB=$(echo "$MM" | grep -oE "\([0-9.]+ GB\)" | grep -oE "[0-9.]+")
  TIER_TOK=$(python3 -c "print(int(float('${GB:-0}') * 1e9 / $KV_BYTES_PER_TOKEN))")
  check "CPU tier from the log is ${GB:-?} GB = $TIER_TOK tokens, within 1% of the tier arm's capacityTokens $TIER_CAP" $(within "$TIER_TOK" "$TIER_CAP" 0.01)
  SHM=$(kubectl exec "$P" -n "$NS" -c modelserver -- df -B1 /dev/shm | tail -1 | awk '{print $3}')
  check "/dev/shm holds the tier: $(python3 -c "print(round(${SHM:-0}/2**30))") GiB used (>= 380)" $([ "${SHM:-0}" -ge $((380 * 1073741824)) ]; echo $?)
  RS=$(kubectl get pod "$P" -n "$NS" -o jsonpath='{.status.containerStatuses[0].restartCount} {.status.containerStatuses[0].lastState.terminated.reason}')
  check "no restart or OOM kill (restarts, last reason: $RS)" $([ "${RS%% *}" = "0" ]; echo $?)
  # counters also export a <name>_created timestamp series; count only the value series
  AF=$(grep -E '^vllm:kv_offload_allocation_failure(_total)?[{ ]' <<< "$M" | awk '{s+=$NF} END {printf "%d", s}')
  check "kv_offload_allocation_failure = ${AF:-0}" $([ "${AF:-0}" = "0" ]; echo $?)

  step "lane $L replica $P: the CPU tier works (checks 4 and 5)"
  OUT=$(kubectl exec -i "$P" -n "$NS" -c modelserver -- python3 - "$MODEL" < "$STEP20/cpu-tier-probe.py" 2>&1 | tail -1)
  echo "$OUT"
  if echo "$OUT" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
    PT=$(echo "$OUT" | jq_ 'd["cold"]["prompt_tokens"]')
    check "resets returned success (both, GPU only, both)" $(echo "$OUT" | jq_ 'd["reset_both_before"] and d["reset_gpu_only"] and d["reset_both"]' | grep -q True; echo $?)
    check "cold request computed its prompt ($PT tokens, cached $(echo "$OUT" | jq_ 'd["cold"]["cached_tokens"]'))" $(echo "$OUT" | jq_ 'd["cold"]["cached_tokens"] < 0.05 * d["cold"]["prompt_tokens"]' | grep -q True; echo $?)
    check "after a GPU-only reset, cached_tokens $(echo "$OUT" | jq_ 'd["from_cpu"]["cached_tokens"]') >= 90% of the prompt" $(echo "$OUT" | jq_ 'd["from_cpu"]["cached_tokens"] >= 0.9 * d["cold"]["prompt_tokens"]' | grep -q True; echo $?)
    check "... and they came from the CPU tier: external hits $(echo "$OUT" | jq_ 'int(d["counters_from_cpu"].get("vllm:external_prefix_cache_hits", 0))')" $(echo "$OUT" | jq_ 'd["counters_from_cpu"].get("vllm:external_prefix_cache_hits", 0) >= 0.9 * d["cold"]["prompt_tokens"]' | grep -q True; echo $?)
    check "... load time $(echo "$OUT" | jq_ 'round(d["from_cpu"]["seconds"], 2)') s vs recompute $(echo "$OUT" | jq_ 'round(d["cold"]["seconds"], 2)') s (at most half)" $(echo "$OUT" | jq_ 'd["from_cpu"]["seconds"] <= 0.5 * d["cold"]["seconds"]' | grep -q True; echo $?)
    check "offload counters are exported and move: stored $(echo "$OUT" | jq_ 'round(d["counters_cold"].get("vllm:kv_offload_store_bytes", 0) / 1e9, 2)') GB on the cold request, loaded $(echo "$OUT" | jq_ 'round(d["counters_from_cpu"].get("vllm:kv_offload_load_bytes", 0) / 1e9, 2)') GB on the reload" $(echo "$OUT" | jq_ 'd["counters_cold"].get("vllm:kv_offload_store_bytes", 0) > 0 and d["counters_from_cpu"].get("vllm:kv_offload_load_bytes", 0) > 0' | grep -q True; echo $?)
    check "after reset_external=true: cached_tokens $(echo "$OUT" | jq_ 'd["after_reset"]["cached_tokens"]'), external hits $(echo "$OUT" | jq_ 'int(d["counters_after_reset"].get("vllm:external_prefix_cache_hits", 0))')" $(echo "$OUT" | jq_ 'd["after_reset"]["cached_tokens"] < 0.05 * d["cold"]["prompt_tokens"] and d["counters_after_reset"].get("vllm:external_prefix_cache_hits", 0) == 0' | grep -q True; echo $?)
  else
    check "cpu-tier-probe.py produced a result" 1
  fi
done

step "lanes: $LANE_ARMS"
"$STEP20/lanes.sh" deploy $LANE_ARMS || { echo "FATAL: lane deploy failed"; exit 1; }
sleep 10
TOKEN=$(kubectl create token thunderagent-metrics-reader -n "$NS" --duration=1h)
PF=()
trap 'kill "${PF[@]}" 2>/dev/null || true' EXIT
port_http() { case $1 in a) echo 18181;; b) echo 18182;; c) echo 18183;; esac; }
port_metrics() { case $1 in a) echo 19191;; b) echo 19192;; c) echo 19193;; esac; }
for L in $LANES; do
  kubectl port-forward "svc/thunder-lane-$L-epp" -n "$NS" "$(port_http "$L"):80" "$(port_metrics "$L"):9090" >/dev/null 2>&1 &
  PF+=($!)
done
sleep 4
mget() { curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:$(port_metrics "$1")/metrics"; }
metric() { # metric <lane> <name> [label-filter] -> value of the first matching series, 0 if absent
  local v; v=$(mget "$1" | grep -E "^[a-z_]*$2(\{[^}]*${3:-}[^}]*\})? " | head -1 | awk '{print $NF}')
  python3 -c "print(int(float('${v:-0}')))"
}
sessions() { echo $(( $(metric "$1" thunder_agent_sessions 'state="running"') + $(metric "$1" thunder_agent_sessions 'state="idle"') + $(metric "$1" thunder_agent_sessions 'state="paused"') )); }
chat() { # chat <lane> <session-id> <json-messages>
  curl -s "http://localhost:$(port_http "$1")/v1/chat/completions" -H 'Content-Type: application/json' -H "x-session-id: $2" \
    -d "{\"model\": \"$MODEL\", \"max_tokens\": 40, \"messages\": $3}"
}
reply() { python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'; }
epp_pod() { # the newest running lane EPP pod that is not being deleted
  kubectl get pods -n "$NS" -l "llm-d-router-standalone=thunder-lane-$1-epp" -o json | python3 -c '
import json, sys
pods = [p for p in json.load(sys.stdin)["items"] if p["status"].get("phase") == "Running" and not p["metadata"].get("deletionTimestamp")]
print(max(pods, key=lambda p: p["metadata"]["creationTimestamp"])["metadata"]["name"] if pods else "")'
}
epp_log() { kubectl logs "$(epp_pod "$1")" -n "$NS" -c epp 2>/dev/null; }

GATE_LANES=""
for LA in $LANE_ARMS; do
  L=${LA%%:*}
  if [ "${LA#*:}" != baseline ]; then GATE_LANES="$GATE_LANES $L"; continue; fi
  step "lane $L (baseline): no gate, answers"
  ELOG=$(epp_log "$L")
  check "lane $L's EPP log is readable ($(wc -l <<< "$ELOG" | tr -d ' ') lines)" $([ "$(wc -l <<< "$ELOG")" -gt 5 ]; echo $?)
  check "no flow control in lane $L's EPP log" $(grep -q "Initializing Flow Control layer" <<< "$ELOG"; [ $? -ne 0 ]; echo $?)
  R=$(chat "$L" "smoke-$L-$RUN" "[{\"role\":\"user\",\"content\":\"Say exactly: hello from lane $L\"}]")
  check "lane $L answered: $(echo "$R" | reply 2>/dev/null)" $(echo "$R" | reply >/dev/null 2>&1; echo $?)
done

for L in $GATE_LANES; do
  ARM=$(for LA in $LANE_ARMS; do [ "${LA%%:*}" = "$L" ] && echo "${LA#*:}"; done)
  PF="$STEP10/$ARM-plugins.yaml"
  CM=$(kubectl get cm "thunder-lane-$L-epp" -n "$NS" -o yaml)
  step "lane $L ($ARM): build, config and gate capacity (check 6)"
  INFO=$(mget "$L" | grep -E "^[a-z_]*(inference_extension|llm_d_epp)_info\{" | head -1); echo "$INFO"
  check "build info reports commit $COMMIT" $(grep -q "commit=\"$COMMIT" <<< "$INFO"; echo $?)
  ELOG=$(epp_log "$L")
  check "flow control on" $(grep -q "Initializing Flow Control layer" <<< "$ELOG"; echo $?)
  LEASE=$(grep -oE "idleLeaseSeconds: [0-9.]+" "$PF")
  check "live ConfigMap has $LEASE" $(grep -q "$LEASE" <<< "$CM"; echo $?)
  mget "$L" | grep -E "^[a-z_]*thunder_agent_endpoint_capacity_tokens" | sed 's/^.*thunder_agent_/thunder_agent_/'
  CAPS=$(mget "$L" | grep -E "^[a-z_]*thunder_agent_endpoint_capacity_tokens\{" | awk '{print $NF}')
  # a config that turns cache info off runs on its capacityTokens; any other on the scraped GPU KV
  if grep -q 'cacheInfoSpec: ""' "$PF"; then WANT=$TIER_CAP; else WANT=$GPU_KV_TOKENS; fi
  check "one endpoint at capacity $WANT tokens (got: $(echo $CAPS))" $([ "$(echo "$CAPS" | wc -w | tr -d ' ')" = 1 ] && python3 -c "import sys; sys.exit(0 if int(float('$CAPS')) == $WANT else 1)"; echo $?)
  if grep -q 'cacheInfoSpec: ""' "$PF"; then
    check "live ConfigMap has cacheInfoSpec \"\" and capacityTokens: $TIER_CAP" $(grep -q 'cacheInfoSpec: ""' <<< "$CM" && grep -q "capacityTokens: $TIER_CAP" <<< "$CM"; echo $?)
    check "EPP registered its own vllm engine mapping" $(grep "Registered engine mapping" <<< "$ELOG" | grep -q vllm; echo $?)
  fi
  OFF=$(grep -oE "offloadCapacityTokens: [0-9]+" "$PF" | awk '{print $2}')
  if [ "${OFF:-0}" -gt 0 ]; then
    check "live ConfigMap has offloadCapacityTokens: $OFF" $(grep -q "offloadCapacityTokens: $OFF" <<< "$CM"; echo $?)
    RES=$(mget "$L" | grep -cE "^[a-z_]*thunder_agent_endpoint_resident_tokens\{")
    check "the tier budget's resident footprint is exported ($RES series)" $([ "$RES" = 1 ]; echo $?)
  fi

  step "lane $L: session and class accounting (check 7)"
  S0=$(sessions "$L"); NEW0=$(metric "$L" releases_total 'class="new"'); ADM0=$(metric "$L" releases_total 'class="admitted"')
  A="smoke-$L-a-$RUN"; B="smoke-$L-b-$RUN"
  R1=$(chat "$L" "$A" '[{"role":"user","content":"Say exactly: hello from turn one"}]')
  check "$A turn 1 answered: $(echo "$R1" | reply 2>/dev/null)" $(echo "$R1" | reply >/dev/null 2>&1; echo $?)
  MSGS=$(echo "$R1" | python3 -c '
import json,sys; r=json.load(sys.stdin)
print(json.dumps([{"role":"user","content":"Say exactly: hello from turn one"},
 {"role":"assistant","content":r["choices"][0]["message"]["content"]},
 {"role":"user","content":"Now say exactly: hello from turn two"}]))' 2>/dev/null)
  R2=$(chat "$L" "$A" "$MSGS")
  check "$A turn 2 answered: $(echo "$R2" | reply 2>/dev/null)" $(echo "$R2" | reply >/dev/null 2>&1; echo $?)
  R3=$(chat "$L" "$B" '[{"role":"user","content":"Say exactly: hello from b"}]')
  check "$B answered: $(echo "$R3" | reply 2>/dev/null)" $(echo "$R3" | reply >/dev/null 2>&1; echo $?)
  check "2 new sessions tracked (sessions $S0 -> $(sessions "$L"))" $([ "$(sessions "$L")" = "$((S0+2))" ]; echo $?)
  check "no session running or paused after the turns" $([ "$(metric "$L" thunder_agent_sessions 'state="running"')" = 0 ] && [ "$(metric "$L" thunder_agent_sessions 'state="paused"')" = 0 ]; echo $?)
  NEW=$(metric "$L" releases_total 'class="new"'); ADM=$(metric "$L" releases_total 'class="admitted"')
  check "releases: new +$((NEW-NEW0)) (want 2), admitted +$((ADM-ADM0)) (want 1)" $([ "$((NEW-NEW0))" = 2 ] && [ "$((ADM-ADM0))" = 1 ]; echo $?)
  HOLD=$(( $(metric "$L" holds_total 'class="new"') + $(metric "$L" holds_total 'class="paused"') + $(metric "$L" holds_total 'class="admitted"') ))
  check "no holds or pauses on an idle replica (holds $HOLD, pauses $(metric "$L" pauses_total))" $([ "$HOLD" = 0 ] && [ "$(metric "$L" pauses_total)" = 0 ]; echo $?)
done

step "EPP logs"
for L in $LANES; do
  LOG=$(epp_log "$L")
  ERRS=$(grep -ciE '"level":"(error|dpanic|panic|fatal)"|"severity_text":"(ERROR|FATAL)"|panic:' <<< "$LOG" || true)
  check "lane $L: no error or panic lines (got $ERRS of $(wc -l <<< "$LOG" | tr -d ' ') lines)" $([ "$(wc -l <<< "$LOG")" -gt 5 ] && [ "$ERRS" -eq 0 ]; echo $?)
  echo "$LOG" > "$RESULTS/smoke-epp-lane-$L$SFX.log"
done

echo; echo "=== $FAILS check(s) failed ==="
exit $FAILS
