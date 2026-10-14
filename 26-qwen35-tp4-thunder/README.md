# Step 26: llm-d-thunder-agent-simplified on Qwen3.5-397B-A17B-FP8, vLLM TP=4, 4x B200

Status: runs done (2026-10-14). Report comparing with GLM-5.2 (step 25): [benchmark-report-qwen35-vs-glm52.md](benchmark-report-qwen35-vs-glm52.md).

## Question

InferenceX run 442369 serves Qwen3.5-397B-A17B-FP8 on 4 B200 (SGLang, TP4, HiCache) for the AgentX workload. Does llm-d-thunder-agent-simplified help this model the way it helps GLM-5.2?

## Setup

- Cluster a4-pr, namespace bobzetian-llmd, kubeconfig `/tmp/a4-pr.kubeconfig` (regenerate with `KUBECONFIG=/tmp/a4-pr.kubeconfig gcloud container clusters get-credentials a4-pr --region europe-west4 --project supercomputer-testing` if `/tmp` was cleaned).
- Servers: `b200/vllm-qwen35.yaml.tmpl` (the SGLang to vLLM mapping is in its header), rendered to `vllm-qwen35-{a..f}.yaml`, GPUs from `gpu-claim.yaml` (4 per server), two servers per a4-highgpu-8g node.
- llm-d-thunder-agent-simplified: `b200/thunder-l10-q{b,d,f}-plugins.yaml`, one per thunder server, capacity = that server's vLLM `kv_cache_size_tokens` (vLLM uses 2128-token blocks for this hybrid model, so block size x blocks would overstate it by 13%); lease 10 s, forced admission after 1800 s. EPP lanes `lane-epp-q{b,d,f}.yaml` (rendered by `render-epp.sh`, image replaced by `ghcr.io/llm-d/llm-d-router-endpoint-picker:main@sha256:c0d60804...`, commit `907c5fe8`).
- Trace set: `semianalysis_cc_traces_weka_062126_256k`, as InferenceX uses for qwen3.5.

## Runs

| label | server | concurrency | arm | result |
|---|---|---|---|---|
| `qwen35-direct` | qwen35-tp4-a | 32 | no-router | ok (2 request errors from the 5 s keep-alive) |
| `qwen35-thunder-gpu-l10` | qwen35-tp4-b | 32 | llm-d-thunder-agent-simplified | ok |
| `qwen35-direct` | qwen35-tp4-c | 48 | no-router | ok |
| `qwen35-thunder-gpu-l10` | qwen35-tp4-d | 48 | llm-d-thunder-agent-simplified | ok |
| `qwen35-direct` | qwen35-tp4-e | 64 | no-router | ok on the third attempt (`run-c64-direct.sh`) |
| `qwen35-thunder-gpu-l10` | qwen35-tp4-f | 64 | llm-d-thunder-agent-simplified | ok |
| `qwen35-thunder-u08` | qwen35-tp4-d | 48 | llm-d-thunder-agent-simplified, `utilThreshold` 0.8 (`thunder-l10-u8-qd-plugins.yaml`) | ok |
| `qwen35-thunder-u06` | qwen35-tp4-c | 48 | llm-d-thunder-agent-simplified, `utilThreshold` 0.6 (`thunder-l10-u6-qc-plugins.yaml`) | ok |

Runner: `b200/run-1h.sh` (all six at once, 3600 s, cache reset per point); the two `utilThreshold` points: `b200/run-util.sh`, analysis `b200/results/report-util/`. Analysis: `b200/results/report/`; comparison with GLM-5.2: `b200/results/report-compare/` (`collect_qwen.py` is step 25's collector pointed at these runs).

## Incidents

- no-router c=64 failed twice in warmup with "Connection reset by peer": vLLM closes idle HTTP connections after 5 s (`VLLM_HTTP_TIMEOUT_KEEP_ALIVE`), and the client reused one it had just closed. Server e was restarted with `VLLM_HTTP_TIMEOUT_KEEP_ALIVE=1800` (the template now sets it; InferenceX sets `SGLANG_TIMEOUT_KEEP_ALIVE=1800` for the same reason). The third attempt first failed at once because the old Jobs still existed; delete them before reusing a label.
- The runner was restarted twice before any point started: once after its header was edited while running (bash reads scripts as it goes), once to set the per-server llm-d-thunder-agent-simplified capacities.
