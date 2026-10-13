# Step 25: GLM-5.2 on 8x B200, vLLM TP=8 with CPU KV offload: InferenceX comparison and the thunder gate

Status: done (2026-10-11). Part A: formal runs (fresh server per point, 3600 s), the InferenceX comparison at c=1 to 16 and the thunder gate at c=12 and 16. Part B: exploration runs (caches emptied instead of a restart), 900 s for no router and thunder variants at c=12 to 36, and 3600 s for no router against thunder at c=12 to 32 (B3). Every point valid unless noted.

## Takeaways

- **vLLM against InferenceX (formal, c=1 to 8):** output throughput ties the InferenceX B200 Dynamo + SGLang line at every point (51.3 against 51.2 tok/s per GPU at c=8); at these concurrencies the trace replay, not the server, sets throughput. vLLM is slower per request: TTFT p50 2.4x to 2.9x higher (0.57 against 0.24 s at c=8), p90 interactivity 8% to 19% lower, already at c=1 where the CPU tier serves nothing.
- **No KV thrashing without a router, up to c=32:** per request, recompute stays at about 0.7% of prompt tokens from c=8 to c=32. The GPU-only hit rate falls (91.5% at c=8, 55% at c=16, 32% at c=24 and 32) and the 820 GiB CPU tier serves almost all of the misses.
- **Why no router slows down at c>=24 anyway (exploration):** a running request needs its whole KV on the GPU, so vLLM runs only 6 to 7 of the ~250k-token requests at a time; the rest queue (vLLM queue time 6 s at c=24, 16 s at c=32, which is the TTFT). The rotation moves 64% of every prompt from CPU to GPU (39 to 46 TB per run), the copy path is busy almost all the time, and every engine step is 10% to 20% slower, so output throughput peaks at c=24 (104 tok/s per GPU) and falls at c=32 (95).
- **Over one hour (B3) thunder's throughput gain shrinks to a tie at c=12 to 16, +2% at c=20 and 24 and +14% at c=32, while TTFT p90 stays 1.6 to 5.7 s against 6.1 to 35.8 s; 0.7% to 2.5% of turns wait over 60 s and at c=24 and 32 the 1800 s backstop fired (TTFT max about 1810 s). The 900 s numbers below overstate the throughput gain.**
- **Thunder gate, GPU capacity, lease 10 s (best configuration seen, exploration):** keeps the GPU hit rate at about 85% and cuts CPU-to-GPU traffic by about 85%. Against no router: output throughput +4% at c=20, +6% to +10% at c=24 (3 runs), +24% to +27% at c=32 (2 runs); TTFT p50 about 0.6 s and p90 2.0 to 3.1 s at every concurrency from c=16 to 36 (no router: p90 8.6 s, 16 s, 40 s at c=20, 24, 32). Thunder keeps scaling to c=36 (125.8 tok/s per GPU).
- **The cost is long waits for paused turns:** 0.6% (c=24) and 1.6% (c=32) of turns wait a median of 3 to 4 minutes, so 13% to 45% of sessions hit at least one turn over 60 s, and 2 to 6 requests per run are still waiting at the end of the window. About half of the long waits are first turns of a new conversation, half are sessions paused mid-task.
- **Forced admission does not fix the long waits:** with a 60 s or 300 s backstop, more sessions have a turn over 60 s and the throughput gain is lost (60 s: back to no router). A fix that pauses idle sessions before a forced admission (zetxqx/llm-d-router#14) changed nothing measurable. The backstop that never fires (1800 s) is best.
- **Formal thunder at c=16 (GPU capacity, lease 30 s):** TTFT p90 2.46 against 6.13 s for no router, but 5% less output throughput and TTFT p99 75 against 15 s; a tie at c=12.
- Exploration points are one 900 s window each, with caches emptied rather than a fresh server, and are not comparable with InferenceX or with Part A. Run-to-run spread measured in this mode: no router about 1% (throughput), thunder about 4%.

## Every run, by mode

**Formal**: a fresh vLLM server before every point (AgentX rule), `MAX_NUM_SEQS` = 2x concurrency, server A only. **Exploration**: no restart; before every point both KV tiers are emptied (`POST /reset_prefix_cache?reset_external=true`) and the EPP is restarted; `MAX_NUM_SEQS=64`; 900 s; servers A and B run one point each at the same time. Results under `b200/results/<label>/c<N>/`.

| label | mode | window | concurrency | arm | EPP image |
|---|---|---|---|---|---|
| `smoke1` | smoke | 120 s | 1 | no router | |
| `calib` | formal | 900 s | 1 | no router | |
| `r1` | formal | 3600 s | 1, 4, 8, 12, 16 | no router | |
| `thunder-r1` | formal | 3600 s | 12, 16 | thunder, GPU capacity, lease 30 s, backstop 1800 s | `-produces` |
| `thunder-cpu-l10-r1` | formal | 3600 s | 16 | thunder, capacity 3.91M (too high, see A2), lease 10 s | `-produces` |
| `smoke-thunder`, `smoke-thunder2`, `smoke-thunder-cpu-l10` | smoke | 120 s | 4 | thunder plumbing checks (the first failed: plain PR3 image) | |
| `explore-direct` | exploration | 900 s | 20, 24, 32 | no router | |
| `explore-direct-r2` | exploration | 900 s | 24, 32 | no router, second run | |
| `explore-thunder-gpu-l10` | exploration | 900 s | 12, 16, 20, 24, 28, 32, 36 | thunder, GPU capacity, lease 10 s, backstop 1800 s | `-produces` |
| `explore-thunder-gpu-l10-r2`, `-r2-retry` | exploration | 900 s | 24, 32 (retry: 24) | same, second and third runs | `-produces` |
| `explore-thunder-gpu-l30` | exploration | 900 s | 24, 32 | thunder, GPU capacity, lease 30 s, backstop 1800 s | `-produces` |
| `explore-thunder-gpu-l10-s60`, `-s300` | exploration | 900 s | 24, 32 | lease 10 s, backstop 60 s / 300 s | `-produces` |
| `explore-thunder-gpu-l10-s60-forced`, `-s300-forced` | exploration | 900 s | 24, 32 | same, with the forced-admission fix | `-forced-7ae26276` |
| `explore1h-direct` | exploration | 3600 s | 20, 24, 32 | no router | |
| `explore1h-thunder-gpu-l10` | exploration | 3600 s | 12, 16, 20, 24, 32 | thunder, GPU capacity, lease 10 s, backstop 1800 s | `-produces` |
| `explore-thunder-cputier-aborted` | stopped in warmup | | 24 | capacity 2.27M (stopped on request, no result) | `-produces` |

Dashboard (`python3 -m http.server -d dashboard 8000`): `dashboard/data/step25-glm52-tp8-offload.json` (formal, 9 points) and `dashboard/data/step25-explore.json` (exploration 900 s, 25 points), `dashboard/data/step25-explore1h.json` (exploration 3600 s, 10 points).

Benchmark report for the one-hour comparison (B3), no-router vs llm-d-thunder-agent-simplified (lease 10 s) at 12 to 128 sessions: [benchmark-report-1h.md](benchmark-report-1h.md). The 48 to 128 points (2026-10-12) come from `b200/run-1h-highc.sh` and `b200/run-1h-highc-tail.sh`, analyzed in `b200/results/explore1h-highc/report/`.

Three-arm report (passthrough, thunder lease 10 s, thunder lease 30 s, one hour each) with the effect of CPU offload (same arms without the CPU tier): [benchmark-report-3arm.md](benchmark-report-3arm.md). Runners: `b200/run-1h-l30-nooff.sh`, `b200/run-1h-nooff-tail.sh`.

## Question

How does vLLM with native CPU KV offload compare with the InferenceX SGLang + HiCache result for GLM-5.2 on the AgentX workload, with the same model, GPUs, parallelism, offload size and client? And where the server overloads, does the thunder gate help?

## Setup

The request was the GB200 line on the InferenceX cache-reuse page (`gb200_dynamo-sglang`, recipe `glm5.2/sglang/gb200-fp4/agentx/agg.yaml`, 2 GB200 nodes, TP=8). On 2026-10-10 the `a4x-baker` cluster had no 2 free nodes, so the run moved to B200; the GB200 manifests are in `gb200/` (LWS + ComputeDomain, never served a request). The B200 target is `glm5.2-fp4-b200-dynamo-sglang-agentic-agg` (recipe `multi_node/srt-slurm-recipes/glm5.2/sglang/b200-fp4/agentx/agg-variants.yaml`, concurrency 1, 4, 8). Compare with the InferenceX B200 line, not the GB200 one.

| | |
|---|---|
| Cluster | GKE `a4-pr` (project `supercomputer-testing`, europe-west4-b), namespace `bobzetian-llmd`, kubeconfig `/tmp/a4-pr.kubeconfig` |
| Servers | A `glm52-tp8` (node `...-5qjv`, `b200/vllm.yaml`), B `glm52-tp8-b` (node `...-13z6`, `b200/vllm-b.yaml`, exploration only); one `a4-highgpu-8g` each (8x B200, DRA `gpu.nvidia.com`) |
| Model server | `vllm/vllm-openai:v0.31.0`, `nvidia/GLM-5.2-NVFP4` at revision `aec724e8` (the InferenceX pin) |
| GPU KV | 1,694,080 tokens with `MAX_NUM_SEQS` 2 to 32; 1,572,864 with 64 (fp8_e4m3, block 64) |
| CPU KV offload | vLLM native `OffloadingConnector`, 820 GiB in `/dev/shm`; it holds a copy of every GPU block, so the distinct tokens kept is the CPU tier's size: about 18.2M tokens. GLM-5.2 uses MLA, so the KV cache is identical on all 8 GPUs, and vLLM v0.31 stores a single CPU copy for all of them (`replicated_layout` in `v1/kv_offload/cpu/spec.py`); 820 GiB / 48.4 KB per token per GPU = about 18.2M tokens. Measured: each block stored costs 48.2 KB per token (one copy) and each load 387 KB per token (8 GPUs x 48.4 KB). An earlier estimate of 2.27M assumed one copy per GPU and was wrong |
| Client | agentx-harness `agentx-v1.0.6`, `--scenario agentx`, dataset `semianalysis_cc_traces_weka_062126` (uncapped, 1M context), node pool `pool-1` |
| Thunder arm | lane EPP from the skill (`render-lane-epp.sh`) in file-discovery mode (`b200/render-epp.sh`; our account cannot create RBAC objects on `a4-pr`, so the EPP reads one endpoint, the vLLM Service ClusterIP, from a file and starts no controllers). Image `thunder-agent-pr3-a025437b-produces` (`sha256:e038ea5a...`, PR3 commit `a025437b` plus the Produces() fix). Plugin configs `b200/thunder-*-plugins.yaml` |

How each SGLang setting maps to vLLM:

| InferenceX SGLang (B200 agg) | vLLM here | Note |
|---|---|---|
| `tensor-parallel-size: 8` | `--tensor-parallel-size 8` | |
| `kv-cache-dtype: fp8_e4m3` | `--kv-cache-dtype fp8_e4m3` | |
| `context-length: 1048576` | `--max-model-len 1048576` | |
| `chunked-prefill-size` / `max-prefill-tokens: 8192` | `--max-num-batched-tokens 8192` | |
| `max-running-requests`: c1 2, c4 8, c8 16 | `--max-num-seqs` (env `MAX_NUM_SEQS`) | 2x concurrency in formal runs, 64 in exploration |
| EAGLE, 3 steps, 4 draft tokens | MTP, `num_speculative_tokens: 3` | |
| `mem-fraction-static: 0.8` | `--gpu-memory-utilization 0.8` | not the same definition |
| HiCache `hicache-size: 110` GB per rank, `write_back` | `--kv-offloading-size 820` (GiB, summed over ranks) | 110e9 B x 8 = 820 GiB |
| `SGLANG_DEFAULT_THINKING=1`, `REASONING_EFFORT=max` | none | the GLM-5.2 chat template defaults to thinking on, effort max |
| no tool parser | `--enable-auto-tool-choice --tool-call-parser glm47` | AgentX sends `tools`; output parsing only |
| Dynamo KV router, one worker | none | one worker: no routing choice |

Cluster-specific settings in `b200/vllm.yaml`: `NCCL_NET_PLUGIN=none` and `NCCL_TUNER_PLUGIN=none` (the node's plugins expect RDMA devices the pod does not claim), driver libraries at `/usr/local/nvidia/lib64`, HF cache on node-local SSD, `progressDeadlineSeconds: 3600`. A fresh server takes about 27 minutes on a node with the cached checkpoint: about 15 minutes to pre-fault the 820 GiB offload region and 4 minutes to pin it.

## Part A: formal runs (fresh server, 3600 s)

### A1. vLLM against InferenceX, c=1, 4, 8

`b200/run-grid.sh` (2026-10-10). Whole profiling window, against the InferenceX B200 rows (`b200/results/inferencex-b200-glm52-agg.json`, from the dashboard API):

| conc | arm | output tok/s/GPU | total tok/s/GPU | TTFT p50 (s) | TTFT p90 (s) | interactivity p50 | interactivity p90 | E2E p90 (s) | completed | hit % |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | InferenceX Dynamo + SGLang | 18.6 | 2588 | 0.37 | 1.03 | 322 | 292 | 16.9 | 271 | 98.0 |
| 1 | InferenceX SGLang | 18.3 | 2507 | 0.73 | 1.35 | 318 | 301 | 17.7 | 267 | 98.0 |
| 1 | vLLM + 820 GiB offload | 18.6 | 2601 | 1.06 | 1.66 | 348 | 269 | 16.2 | 272 | 98.0 |
| 4 | InferenceX Dynamo + SGLang | 27.3 | 3875 | 0.23 | 0.79 | 311 | 258 | 13.4 | 604 | 97.3 |
| 4 | InferenceX SGLang | 27.5 | 3895 | 0.39 | 1.33 | 311 | 260 | 13.9 | 608 | 98.2 |
| 4 | vLLM + 820 GiB offload | 27.8 | 4014 | 0.58 | 1.80 | 294 | 211 | 13.5 | 620 | 97.7 |
| 8 | InferenceX Dynamo + SGLang | 51.2 | 6976 | 0.24 | 0.86 | 265 | 188 | 12.5 | 1312 | 87.7 |
| 8 | InferenceX SGLang | 51.1 | 6924 | 0.37 | 1.22 | 264 | 197 | 12.9 | 1315 | 90.3 |
| 8 | vLLM + 820 GiB offload | 51.3 | 6999 | 0.57 | 1.55 | 240 | 152 | 12.8 | 1328 | 97.5 |

InferenceX's hit rate is GPU only; ours counts either tier. GPU only, ours is 98.0% / 97.6% / 91.5%. The c=1 calibration point (900 s, 106 requests, 96.8% hit, TTFT p90 1.44 s) agreed with the 3600 s point.

Cache tiers (`analyze.py`, profiling window):

| conc | theoretical hit | GPU hit | CPU tier hit | overall hit | lost to recompute | working set / GPU pool (mean, max) | GPU KV peak | preemptions |
|---|---|---|---|---|---|---|---|---|
| 1 | 98.1% | 98.0% | 0.02% | 98.0% | 0.1 pt | 0.20x, 0.32x | 33% | 0 |
| 4 | 97.9% | 97.6% | 0.10% | 97.7% | 0.2 pt | 0.69x, 1.01x | 65% | 0 |
| 8 | 97.8% | 91.5% | 6.07% | 97.5% | 0.2 pt | 1.07x, 1.52x | 99% | 0 |

### A2. No router against thunder at c=12 and c=16

`b200/run-thunder.sh` (2026-10-10, arms alternated) and `b200/run-thunder-cpu-l10.sh` (2026-10-11).

| conc | arm | completed | output tok/s/GPU | TTFT p50 (s) | TTFT p90 (s) | TTFT p99 (s) | TTFT max (s) | interactivity p90 | GPU hit | CPU tier hit | waiting avg | sessions with a turn over 60 s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12 | no router | 1653 | 62.6 | 0.62 | 1.63 | | | 135 | 83.0% | 14.0% | 0.08 | 0% |
| 12 | thunder, GPU capacity, lease 30 s | 1639 | 61.8 | 0.61 | 1.76 | | | 140 | 85.6% | 11.4% | 0.06 | 4.2% |
| 16 | no router | 2328 | 79.0 | 0.77 | 6.13 | 15.0 | 24.6 | 88 | 55.4% | 41.7% | 0.81 | 0% |
| 16 | thunder, GPU capacity, lease 30 s | 2288 | 75.0 | 0.62 | 2.46 | 75.3 | 470.5 | 109 | 83.9% | 13.0% | 0.11 | 36.1% |
| 16 | thunder, capacity 3.91M, lease 10 s | 2323 | 78.7 | 0.81 | 5.60 | 15.9 | 28.3 | 87 | 55.3% | 41.8% | 0.81 | 0% |

- c=12: a tie. c=16: thunder (GPU capacity) cuts TTFT p90 from 6.13 to 2.46 s by keeping the working set on the GPU (345 pauses), at 5% less output throughput and a TTFT p99 of 75 s.
- With the 3.91M capacity the gate almost never holds anyone and matches no router on every metric. (The capacity was computed as GPU plus a 2.27M CPU tier estimate; the tier actually holds about 18.2M tokens, see Setup, so 3.91M is not a CPU-tier capacity either.)

## Part B: exploration runs (caches emptied, 900 s)

### B1. No router against thunder (GPU capacity, lease 10 s, backstop 1800 s), c=12 to 36

| conc | arm | completed | output tok/s/GPU | TTFT p50 (s) | TTFT p90 (s) | TTFT p99 (s) | interactivity p90 | GPU hit | vLLM waiting avg | sessions with a turn over 60 s |
|---|---|---|---|---|---|---|---|---|---|---|
| 12 | thunder | 566 | 68.4 | 0.50 | 1.19 | 5.6 | 148 | 90.1% | 0.04 | 0% |
| 16 | thunder | 544 | 75.2 | 0.57 | 2.03 | 28.5 | 130 | 84.2% | 0.10 | 22.2% |
| 20 | no router | 778 | 99.1 | 0.75 | 8.58 | 20.3 | 73 | 48.2% | 1.79 | 0% |
| 20 | thunder | 795 | 102.8 | 0.60 | 3.12 | 35.7 | 85 | 81.7% | 0.23 | 16.7% |
| 24 | no router (2 runs) | 911, 916 | 103.7, 104.3 | 4.06, 4.29 | 16.1, 15.4 | 34.4, 33.9 | 57, 62 | 31.8% | 5.9 | 0% |
| 24 | thunder (3 runs) | 995 to 1034 | 109.8 to 113.9 | 0.57, 0.58 | 2.3 to 3.0 | 36.4 to 40.0 | 83 to 86 | 85% | 0.3 | 13% to 20% |
| 28 | thunder | 1085 | 120.2 | 0.60 | 2.19 | 59.4 | 76 | 86.4% | 0.28 | 33.3% |
| 32 | no router (2 runs) | 939, 946 | 95.3, 94.2 | 15.7, 15.6 | 40.5, 38.4 | 51.9, 50.5 | 54, 57 | 31.9% | 15.8 | 0% to 2.6% |
| 32 | thunder (2 runs) | 1118, 1100 | 121.1, 118.0 | 0.62, 0.64 | 2.13, 2.03 | 131.9, 150.6 | 79, 73 | 85.9% | 0.3 | 38% to 45% |
| 36 | thunder | 1090 | 125.8 | 0.61 | 2.37 | 109.5 | 79 | 83.7% | 0.30 | 31.0% |

From c=28 on the gate holds vLLM's running requests at 7.5 to 8 and pauses the extra sessions (66 to 80 paused), so interactivity stops falling (p50 137, 136, 133 at c=28, 32, 36); the p90 order between c=28 and c=32 (76 against 79) is within noise.

### B2. Thunder variants at c=24 and c=32

All lease 10 s and GPU capacity unless noted; the 1800 s rows are the B1 runs.

| conc | variant | completed | output tok/s/GPU | TTFT p90 (s) | TTFT p99 (s) | TTFT max (s) | GPU hit | sessions with a turn over 60 s | forced admissions |
|---|---|---|---|---|---|---|---|---|---|
| 24 | backstop 1800 s (3 runs) | 995 to 1034 | 109.8 to 113.9 | 2.3 to 3.0 | 36 to 40 | 355 to 370 | 85% | 13% to 20% | 0 |
| 24 | lease 30 s | 1004 | 105.2 | 2.07 | 66.1 | 394 | 89.7% | 29.6% | 0 |
| 24 | backstop 300 s | 959 | 103.5 | 3.08 | 73.5 | 318 | 84.3% | 28.1% | 5 |
| 24 | backstop 300 s, forced-admission fix | 953 | 103.2 | 3.73 | 165.1 | 322 | 82.3% | 46.9% | 4 |
| 24 | backstop 60 s | 1000 | 104.0 | 9.29 | 69.6 | 84 | 54.3% | 64.5% | 62 |
| 24 | backstop 60 s, forced-admission fix | 1009 | 103.6 | 14.45 | 71.4 | 88 | 53.6% | 67.7% | 63 |
| 32 | backstop 1800 s (2 runs) | 1100, 1118 | 118.0, 121.1 | 2.0, 2.1 | 132, 151 | 495, 622 | 86% | 38% to 45% | 0 |
| 32 | lease 30 s | 1107 | 123.6 | 1.82 | 62.9 | 387 | 90.7% | 33.3% | 0 |
| 32 | backstop 300 s | 1059 | 114.2 | 4.15 | 301.9 | 327 | 74.5% | 65.0% | 16 |
| 32 | backstop 300 s, forced-admission fix | 1059 | 112.0 | 5.82 | 301.7 | 326 | 76.0% | 67.5% | 14 |
| 32 | backstop 60 s | 988 | 97.2 | 38.3 | 91.6 | 109 | 37.4% | 80.0% | 101 |
| 32 | backstop 60 s, forced-admission fix | 987 | 99.6 | 35.8 | 92.1 | 102 | 35.3% | 79.5% | 106 |

- Lease 30 s against 10 s: at c=24 about 7% less throughput and a higher TTFT p99 (outside thunder's spread); at c=32 a lower TTFT p99 (63 against 132 and 151 s) and a throughput tie.
- Backstop: a forced admission puts the pool over capacity, the gate then admits less, and more waiting turns reach the backstop (at c=32 with 300 s the TTFT p99 sits at the backstop). 60 s brings throughput and TTFT p90 back to no router's level.
- The forced-admission fix (image `thunder-agent-pr3-a025437b-forced-7ae26276`, `sha256:80810fd6...`: `a025437b` plus zetxqx/llm-d-router#14) changes nothing measurable: the gate paused about as many sessions (203 against 197, 225 against 218, 205 against 212, 226 against 230), so at forced-admission time there were few sessions idle past the lease to reclaim; the overflow comes from the forced sessions themselves (gate working set 2.14x capacity at c=32 with 60 s under either image). The c=24, 300 s gap (p99 165 against 73.5 s) rests on 4 and 5 forced admissions among about 32 sessions in single runs.

### B3. One-hour exploration points: no router against thunder (GPU capacity, lease 10 s, backstop 1800 s)

`b200/run-1h.sh` (2026-10-11, 15:28 to 18:47 PDT): same method as B1 (no restart, both KV tiers emptied and the EPP restarted before each point, `MAX_NUM_SEQS=64`) but 3600 s per point, on four servers at once (A and B as before; C `glm52-tp8-c` on node `0x6t` and D `glm52-tp8-d` on `1j8l`, `b200/vllm-c.yaml`, `vllm-d.yaml`; thunder EPPs `agentx-epp-a`, `-c`, `-d`, image `-produces`). Pairs ran at the same time: c=24 (A no router, B thunder), c=20 (A, B), c=32 (D no router, C thunder). No router at c=12 and 16 is the formal 3600 s `r1` point. Clients 4 CPU, 16 GiB requested (they used about 7 GiB). All 8 points valid, no retries; no router c=24 had 1 client error.

| conc | arm | completed | output tok/s/GPU | TTFT p50 (s) | TTFT p90 (s) | TTFT p99 (s) | TTFT max (s) | interactivity p90 | GPU hit | CPU tier hit | vLLM queue time (s) | turns over 60 s | sessions with a turn over 60 s | forced admissions |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12 | no router (formal) | 1653 | 62.6 | 0.62 | 1.63 | 6.2 | 14 | 135 | 83.0% | 14.0% | | 0% | 0% | |
| 12 | thunder | 1643 | 62.1 | 0.56 | 1.62 | 9.1 | 27 | 151 | 84.2% | 12.8% | 0.14 | 0% | 0% | 0 |
| 16 | no router (formal) | 2328 | 79.0 | 0.77 | 6.13 | 15.0 | 25 | 88 | 55.4% | 41.7% | | 0% | 0% | |
| 16 | thunder | 2340 | 78.8 | 0.64 | 2.53 | 43.7 | 297 | 109 | 80.3% | 16.6% | 0.23 | 0.68% | 16.7% | 0 |
| 20 | no router | 2710 | 96.7 | 1.32 | 10.60 | 20.6 | 32 | 81 | 37.0% | 60.1% | 2.77 | 0% | 0% | |
| 20 | thunder | 2783 | 98.9 | 0.69 | 3.33 | 74.7 | 448 | 102 | 80.6% | 16.4% | 0.25 | 1.19% | 26.2% | 0 |
| 24 | no router | 2921 | 101.1 | 6.21 | 17.72 | 29.3 | 40 | 66 | 16.6% | 80.5% | 7.05 | 0% | 0% | |
| 24 | thunder | 3065 | 103.3 | 0.71 | 3.64 | 114.5 | 1810 | 94 | 82.0% | 14.9% | 0.23 | 1.53% | 33.3% | 2 |
| 32 | no router | 2791 | 95.5 | 19.21 | 35.81 | 50.2 | 61 | 62 | 8.5% | 88.7% | 18.50 | 0.07% | 3.6% | |
| 32 | thunder | 3331 | 109.0 | 0.72 | 5.71 | 193.1 | 1817 | 93 | 79.4% | 17.2% | 0.28 | 2.46% | 63.8% | 4 |

- Over an hour thunder's throughput gain is smaller than in the 900 s windows: a tie at c=12 and 16, +2% at c=20 and c=24 (900 s: +6% to +10% at c=24), +14% at c=32 (900 s: +24% to +27%). The 900 s windows overstate it: the first five minutes run at low load (a third of a 900 s window), and over an hour the sessions' contexts and the gate's working set grow, so it admits fewer sessions.
- The latency gain holds: TTFT p90 1.6 to 5.7 s against 6.1 to 35.8 s, interactivity p90 higher at every point.
- The tail is worse over an hour: 0.7% to 2.5% of turns wait over 60 s, TTFT p99 44 to 193 s, and at c=24 and 32 the 1800 s backstop fired for the first time (2 and 4 forced admissions; TTFT max 1810 and 1817 s).
- Still no thrashing without a router: overall hit 97.1% to 97.2% against a theoretical 97.4% to 97.5%, excess recompute 0.6%. Over an hour the GPU-only hit falls further (16.6% at c=24, 8.5% at c=32) and the CPU tier serves 80% to 89%; vLLM queue time 7.1 s and 18.5 s.

## Analysis

### No KV thrashing, and the working-set estimate

Per request, the prompt tokens missed beyond what the turn added since the previous turn (an upper bound on recompute; AgentX context resets count too) are 0.70%, 0.76%, 0.65% at c=8, 12, 16 (formal) and 0.63% at c=24 (exploration): flat. The summed working set (latest ISL of every live session) is above the old 2.27M-token tier estimate most of the time at c=12 and 16; that estimate was wrong. The tier holds about 18.2M tokens (one copy shared by the 8 GPUs, see Setup), far above the working set at every point (peak 8.5M at c=32), which matches the flat recompute. An LRU simulation over the recorded requests confirms it: a 2.27M cache would give a 89% hit at c=12 and 13% at c=32, against the measured 97%.

### Why no router slows down from c=24 although nothing is recomputed

| no router | c=20 | c=24 | c=32 | thunder c=24 |
|---|---|---|---|---|
| vLLM queue time avg (s) | 2.2 | 6.0 | 15.8 | 0.3 |
| vLLM prefill time avg, CPU loads included (s) | 0.39 | 0.43 | 0.45 | 0.34 |
| vLLM running / waiting avg | 6.0 / 1.8 | 7.4 / 5.9 | 7.0 / 15.7 | 6.7 / 0.3 |
| waiting because KV is full | 81% | 90% | 96% | 45% |
| prompt tokens loaded from the CPU tier | 48% | 64% | 64% | 10% |
| CPU-to-GPU bytes / recorded transfer time (run incl. warmup) | 30 TB | 38.7 TB / 1482 s | 45.6 TB / 1688 s | 5.6 TB / 220 s |
| engine steps in the run (thunder c=24: 45.3k) | | 39.7k | 38.2k | 45.3k |
| server ITL mean (ms) | | 25.7 | 26.0 | 21.3 |
| output tok/s/GPU | 99 | 104 | 95 | 114 |

1. The CPU tier keeps the KV but does not add running capacity: each running request needs its whole context (about 250k tokens) on the GPU, so vLLM runs 6 to 7 at a time and queues the rest. The TTFT is the vLLM queue time; the extra prefill for CPU loads is about 0.1 s per request.
2. The rotation through all lanes reloads 64% of each prompt from the CPU tier. The recorded transfer time equals the run time: the copy path is busy almost continuously. With the same batch size, context length (98k against 94k mean ISL), MTP acceptance (0.678 against 0.671) and prefill tokens per step, no router runs 9% to 14% fewer engine steps and every decoding request is slower, which is the throughput loss. How the transfers slow the steps (waits on copy completion, scheduler lookups: 21k synchronous lookups at about 1 ms against 1.3k at thunder, or bandwidth contention) is not measured; a profiler trace would show it.
3. Without offload the reloaded 64% would be recomputed: about 380k tokens/s of prefill at c=24 against a measured single-request prefill rate of about 335k tokens/s, so the offload most likely saves far more than it costs. Not measured: there is no run without offload.

### Long waits under thunder

At c=24 and c=32, 6 of 1029 and 18 of 1118 turns waited over 60 s (median wait 248 s and 192 s); half were first turns of a conversation (new sessions or newly spawned subagents), half later turns of paused sessions. With the 1800 s backstop nothing is forced in: every completed request was admitted when a running session idled past the 10 s lease or finished (longest 355 to 622 s), and 2 to 6 requests per run (14 for lease 30 s at c=32) were still waiting when the window ended. Agents rarely idle 10 s (median gap between turns 1.9 s, 85% under 10 s), so a paused session waits until another hits a long tool call or a subagent wait. Admission can therefore take minutes but has no upper bound below the backstop.

### Run-to-run spread (exploration)

No router, two runs: throughput within about 1%, TTFT within 5%. Thunder lease 10 s, two to three runs: throughput within about 4%, TTFT p90 2.0 to 3.0 s, TTFT p99 within about 15%, sessions over 60 s within about 7 points.

## Expectations written before the runs, and outcomes

| expectation | outcome |
|---|---|
| c=1: one session fits in GPU KV; hit near 99%, CPU tier changes little | held: 98.0% hit, CPU tier 0.02% |
| c=8: past the GPU tier but within GPU plus CPU; hit above 90% with CPU tier hits | held: 97.5% hit, 6.07 points from the CPU tier |
| against InferenceX: no direction | throughput ties; vLLM's TTFT and p90 interactivity worse at every point |
| c=12/16 no router: GPU hit well below 91.5%, recompute above 1 point at c=16 | GPU hit fell as expected (83.0%, 55.4%); recompute stayed at 0.2 to 0.4 points |
| c=12/16 thunder: tie at c=12, more throughput and lower TTFT p90 at c=16 | tie at c=12; at c=16 TTFT p90 lower, throughput 5% lower |
| exploration no router: recompute rises at c=24 or 32 | did not: 0.63% at c=24; the cost is queueing and CPU-to-GPU churn |
| backstop 60 s: far fewer sessions over 60 s, some gain lost | failed: more sessions over 60 s (65%, 80%), whole gain lost |
| second lease-10 s run gives thunder's spread | about 4% throughput, about 7 points sessions over 60 s |

## Incidents and fixes

- Plain PR3 image failed every request through the gate ("wrote undeclared request attribute inflight-estimate/thunder-agent; add it to Produces()"); the `-produces` image (and zetxqx/llm-d-router#14) declares it.
- No RBAC on `a4-pr`: the EPP runs in file-discovery mode with the chart's RBAC objects removed.
- vLLM NCCL init failed until `NCCL_NET_PLUGIN=none`, `NCCL_TUNER_PLUGIN=none`.
- Deployment `progressDeadlineSeconds` 600 s made `rollout status` fail during the 27-minute start; set to 3600.
- Two parallel points collided twice: on the temporary kubeconfig (`lib.sh`) and on the fetch pod name (`run-point.sh`); both fixed. One point's data was fetched from the PVC by hand.
- Skill changes for this step: `run-point.sh` `MODE=direct`, `SERVER_ENV`, `RESET=1`; `render-lane-epp.sh` `EXTRA_VALUES` and the `-produces` default image.

## Next

- Runs without CPU offload at c=24 (no router and thunder), to measure what the CPU tier is worth and whether thunder then wins on throughput as in step 24.
- Bound thunder's waits without overcommit: let subagents of an admitted session inherit its admission, keep the waiting at session start rather than mid-task, or rotate by pausing the longest-running session when a paused one has waited too long.
- A gate capacity above the GPU pool (1.57M), up to the CPU tier size (about 18.2M).
- A profiler trace of a no-router c=24 point, to see how CPU-to-GPU transfers slow the engine step.
- The c=1 TTFT gap against SGLang (prefill kernels, MTP, offload lookups).
