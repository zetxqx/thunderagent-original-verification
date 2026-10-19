#!/usr/bin/env bash
# Run the skill's tests with uv (no project venv needed):
#   .claude/skills/agentic-benchmark/tests/run.sh [pytest args]
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --with pytest --with numpy --with pandas --with pyarrow --with matplotlib --with tabulate --with pyyaml \
  python -m pytest tests -q -p no:cacheprovider "$@"
