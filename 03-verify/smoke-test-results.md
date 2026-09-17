# Smoke test results (2026-09-15)

Run: `./smoke-test.sh` against `thunderagent-router:8300` in `llm-d-program-aware-scheduling` (image `thunderagent-original:7ddc861`, launched via `launcher.py`). Full raw output: `smoke-test-output.txt`.

## What was verified

| Check | Result |
|---|---|
| `/health` | `router_mode: tr`, `scheduling_enabled: true`, 4 backends, profiling on |
| KV capacity fetched from vLLM | all 4 backends: `block_size=16, num_gpu_blocks=139815, total_tokens_capacity=2237040` (parsed from `vllm:cache_config_info`) |
| Chat completion proxying | 3 requests completed with correct model output |
| Program tracking | `verify-a`: `step_count: 2`, `total_tokens: 44`, status `acting` after its turns; `verify-b`: `step_count: 1` |
| Sticky routing | `verify-a` stayed on `http://10.100.15.12:8000` for both turns |
| Load-balanced placement | `verify-b` (new program) was placed on a different backend (`http://10.100.2.5:8000`) |
| Per-program profiling | `avg_prompt_tokens`, `avg_completion_tokens`, `avg_tool_call_s` (0.3s think time between turn 1 and 2 captured as tool time) |
| Scheduler accounting (`/metrics`) | per-backend `active/reasoning/acting_program_tokens`, `buffer_per_program: 100`, `capacity_overflow: 0`, live vLLM metrics history |
| Explicit release | `POST /programs/release` returned `released: true` for both programs |

## Interpretation for the paper

The original router's core mechanics are all observable and working on a real vLLM cluster:

- The program abstraction (program_id -> tracked state with REASONING/ACTING lifecycle) works through the plain OpenAI API.
- Capacity scheduling has real numbers to work with: each backend reports 2,237,040 tokens of KV capacity, so admission control (pause when `sum(program tokens) + buffer > capacity`) is armed. With only 2 tiny test programs nothing pauses, as expected; pauses need a saturating workload (see "next steps" in the top-level README).
- Sticky program->backend placement (the KV cache reuse mechanism, the source of the paper's throughput claim) is confirmed: repeat turns of the same program hit the same backend.

## Upstream bugs found during setup (in ThunderAgent commit 7ddc861)

1. **The `thunderagent` CLI silently ignores its own flags.** `ThunderAgent/__init__.py` imports `.app`, and `app.py` creates its module-level `router` at import time using the default config. The import happens when the console script resolves `ThunderAgent.__main__:main`, i.e. before `main()` calls `set_config()`. Result: the server always runs with `backends=['http://localhost:8000']`, default intervals, and profiling off, regardless of flags (only settings read at `start()` time, like `--metrics`, take effect). First deployment attempt hit exactly this: log said `Started router with 1 backend(s): ['http://localhost:8000']`. Workaround (no upstream change): `02-deploy/launcher.py` builds the router through the documented embedding API (`Config` + `MultiBackendRouter` + `register_routes`).
2. **`GET /v1/models` is broken.** `app.py list_models` calls `proxy_get(backend, "/models")` which produces `http://backend:8000/models` - a 404 on vLLM (the correct path is `/v1/models`). Cosmetic; chat completions use `completions_url` which appends `/v1` correctly.

Both are worth reporting upstream; neither affects the scheduling logic the paper is about, but bug 1 means anyone who ran the published CLI multi-backend command got a single-backend proxy to localhost.
