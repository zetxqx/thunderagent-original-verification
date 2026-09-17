#!/usr/bin/env bash
# Smoke test for the original ThunderAgent router.
# Port-forwards to the router service and verifies program tracking,
# sticky routing, and capacity scheduling state end to end.
set -euo pipefail

NS=llm-d-program-aware-scheduling
MODEL="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
PORT=18300

kubectl port-forward svc/thunderagent-router -n "$NS" "$PORT:8300" >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 3

step() { echo; echo "=== $1 ==="; }

step "1. /health"
curl -sf "http://localhost:$PORT/health" | python3 -m json.tool

step "2. /v1/models (known upstream bug: proxies to /models instead of /v1/models, so vLLM returns 404)"
curl -s "http://localhost:$PORT/v1/models"; echo

chat() { # chat <program_id> <json_messages>
  curl -sf "http://localhost:$PORT/v1/chat/completions" \
    -H 'Content-Type: application/json' \
    -d "{\"model\": \"$MODEL\", \"program_id\": \"$1\", \"max_tokens\": 40, \"messages\": $2}"
}

step "3a. program verify-a, turn 1"
R1=$(chat verify-a '[{"role":"user","content":"Say exactly: hello from turn one"}]')
A1=$(echo "$R1" | python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])')
echo "assistant: $A1"

step "3b. program verify-a, turn 2 (multi-turn, same prefix)"
MSGS=$(echo "$R1" | python3 -c '
import json, sys
r = json.load(sys.stdin)
print(json.dumps([
    {"role": "user", "content": "Say exactly: hello from turn one"},
    {"role": "assistant", "content": r["choices"][0]["message"]["content"]},
    {"role": "user", "content": "Now say exactly: hello from turn two"},
]))')
chat verify-a "$MSGS" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("assistant:", d["choices"][0]["message"]["content"]); print("usage:", d["usage"])'

step "3c. program verify-b, turn 1"
chat verify-b '[{"role":"user","content":"Reply with the single word: pong"}]' \
  | python3 -c 'import json,sys; print("assistant:", json.load(sys.stdin)["choices"][0]["message"]["content"])'

step "4. /programs (program state tracking)"
curl -sf "http://localhost:$PORT/programs" | python3 -m json.tool

step "5. /metrics (per-backend capacity + prefix cache)"
curl -sf "http://localhost:$PORT/metrics" | python3 -m json.tool

step "6. release both programs"
curl -sf -X POST "http://localhost:$PORT/programs/release" -H 'Content-Type: application/json' -d '{"program_id":"verify-a"}'
echo
curl -sf -X POST "http://localhost:$PORT/programs/release" -H 'Content-Type: application/json' -d '{"program_id":"verify-b"}'
echo

step "done"
