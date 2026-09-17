#!/usr/bin/env bash
# Port-forward to the router and run the benchmark. Extra args pass through
# to benchmark.py (e.g. ./run-benchmark.sh --sessions 24 --turns 8).
set -euo pipefail

NS=llm-d-program-aware-scheduling
PORT=18300
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

kubectl port-forward svc/thunderagent-router -n "$NS" "$PORT:8300" >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 3

python3 "$SCRIPT_DIR/benchmark.py" --base-url "http://localhost:$PORT" "$@"
