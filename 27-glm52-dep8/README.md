# Step 27: GLM-5.2 on 8x B200 with DEP=8 instead of TP=8

Status: done (2026-10-15). Report: [benchmark-report-tp8-vs-dep8.md](benchmark-report-tp8-vs-dep8.md). Runners: `b200/run-dep8.sh` (c=32, 64), `b200/run-dep8-b32.sh` (session affinity c=32 again), `b200/run-dep8-more.sh` (c=24, 48). Analysis: `b200/results/report/` (DEP=8), `b200/results/report-tp8/` (step 25 TP=8 points, same `analyze.py`), comparison `b200/results/report-compare/`.

## Question

With TP=8, each of the 8 GPUs keeps a full copy of GLM-5.2's MLA KV, so 8 B200 hold only 1.57M tokens, and a CPU-tier load copies 387 KB for each token (8 copies). This is why llm-d-thunder-agent-simplified helps GLM-5.2 (step 26 report, section 8).

1. Is DEP=8 (attention data parallel 8, MoE expert parallel 8) a better configuration for GLM-5.2 at 32 and 64 agent sessions?
2. On DEP=8, does llm-d-thunder-agent-simplified still help?

## Prediction (step 26 report, section 8)

- DEP=8 keeps different sessions on each rank. The GPU KV holds approximately 5x to 8x more distinct tokens (each rank keeps a full copy of the non-expert weights, so a rank's pool is smaller than 1.57M). A CPU-tier load copies 48.4 KB for each token, 8x less.
- Thus the two conditions for llm-d-thunder-agent-simplified become weaker. no-router on DEP=8 is much better than on TP=8 at 32 and 64 sessions. llm-d-thunder-agent-simplified adds little on DEP=8.

## Arms

32 and 64 sessions (then 24 and 48), 3600 s, both KV tiers emptied before each point (same method as the step 25 one-hour runs), GLM full trace corpus `semianalysis_cc_traces_weka_062126`.

| arm | server | how requests reach the ranks | data |
|---|---|---|---|
| TP=8, no-router | step 25 `glm52-tp8` | direct | step 25 `explore1h-direct` c32, c64 (reused) |
| TP=8, llm-d-thunder-agent-simplified | step 25 | EPP, PR3 image | step 25 `explore1h-thunder-gpu-l10` c32, c64 (reused) |
| DEP=8, no-router | `glm52-dep8-a`, node `5qjv` | one vLLM API server, vLLM's internal DP load balancer (by load, no session affinity) | new: `dep8-direct` |
| DEP=8, session affinity | `glm52-dep8-b`, node `13z6` | one API server for each rank (ports 8000 to 8007), EPP `session-affinity-scorer` (`x-session-id`) plus `token-load-scorer` for new sessions | new: `dep8-affinity` |
| DEP=8, llm-d-thunder-agent-simplified | `glm52-dep8-c`, node `0x6t` | one API server for each rank, EPP thunder (pins each session to its rank, capacity for each rank from vLLM, lease 10 s, forced admission after 1800 s) plus `token-load-scorer` | new: `dep8-thunder-l10` |

The session affinity arm separates two effects: DEP=8 with any session-aware router, and llm-d-thunder-agent-simplified on top of it. EPP image for the two new router arms: upstream main `ghcr.io/llm-d/llm-d-router-endpoint-picker:main@sha256:c0d60804...` (commit `907c5fe8`). The token-load scorer has weight 0.1, so the pinned rank always wins for a known session.

## Server

`b200/vllm-dep8.yaml.tmpl`. Same as step 25 (`vllm/vllm-openai:v0.31.0`, `nvidia/GLM-5.2-NVFP4` revision `aec724e8`, FP8 KV, MTP 3, `--gpu-memory-utilization 0.8`), with these changes:

- `--data-parallel-size 8 --enable-expert-parallel`, no `--tensor-parallel-size` (TP=1 in each rank).
- Session affinity and thunder arms: `--data-parallel-size-local 8 --data-parallel-multi-port-external-lb`. vLLM starts one API server for each rank on ports 8000 to 8007, and an aggregated health endpoint on port 9256.
- `--kv-offloading-size 102.5` (GiB). Each rank is its own engine with its own CPU tier, so 8 x 102.5 = 820 GiB, the same total as step 25.
- `--max-num-seqs 32` and `--max-num-batched-tokens 8192` for each rank (step 25: 64 and 8192 for the one TP=8 engine).

The longest request in the trace is approximately 783k tokens. It must fit in the KV pool of one rank.

Measured on 2026-10-15: the weights use 85.8 GiB on each rank, so 35.3 GiB to 36.9 GiB remains for KV. vLLM refused `--max-model-len 1048576` (47.28 GiB needed). The template uses `--max-model-len 783872`, the value vLLM proposed. Each rank's pool is 818,175 tokens (same on all ranks of servers a and c), so 6.55M tokens in total, 4.2x the TP=8 pool (1.57M). The thunder capacity for each rank is 818,175.

## Steps

1. Scale the Qwen3.5 servers of step 26 to 0 on node `5qjv` (`qwen35-tp4-a`, `-b`). Start `glm52-dep8-a`. Record each rank's `kv_cache_size_tokens`.
2. If step 1 works, scale the other Qwen3.5 servers to 0 and start `glm52-dep8-b` and `-c`, then the two EPPs.
3. `b200/run-dep8.sh`: the three new arms at the same time, c32, then c64.
4. Compare with the reused TP=8 points: throughput, the agent metrics (E2E normalized interactivity p50 and p90, request latency p99, session progress), GPU and CPU-tier hit, CPU-to-GPU traffic.

## Incidents

- dep8-affinity c=32: both tries failed at the cache reset with a transient Kubernetes API error ("the server is currently unable to handle the request", 08:44 UTC). `run-dep8-b32.sh` runs the point again on server b after b's c=64 point, as label `dep8-affinity-r2`.

- At 64 sessions, Kubernetes stopped three clients for memory (OOMKilled, 32 GiB limit) during the export of the server metrics (26M rows; the slow servers made the warmup long): `dep8-direct/c64`, `dep8-direct-retry/c64`, `dep8-affinity/c64`. The per-request records are complete. The comparison uses `dep8-direct/c64` and `dep8-affinity-retry/c64`.

## Changes to shared scripts

- `run-point.sh`: `VLLM_PORTS` (default `8000`). The point reads server metrics from, and empties the KV tiers on, each port of each pod.
- `analyze.py`: a point without `profile_export_aiperf.json` (client killed after the run) is analyzed from the records and the parquet, with a check line. For a server with several engines behind one URL (vLLM's internal DP load balancer), each engine counts as a pod, so gauges are summed over the engines, not averaged.
