# P/D Disaggregation Compared With Aggregated Serving on This Workload

Written on 2026-10-26. This report compares every prefill/decode (P/D) deployment and every aggregated deployment in this repository:

- GLM-5.2-NVFP4: steps 25, 27, and 35 to 40.
- Qwen3.5-397B-A17B-FP8: steps 26, 33, and 34.

All numbers are steady state. The steady state contains the requests that started after minute 5 of a 60-minute point. Each deployment has one point per concurrency. [`make_pd_report_figures.py`](make_pd_report_figures.py) makes the figures from the dashboard bundles and from the step 38 and step 40 summaries.

## 0. Takeaways

1. **On GLM-5.2, no P/D deployment is worth its GPUs.**
   - The best P/D deployments produce 72 to 73 output tok/s per GPU (1P2D + thunder, 1P1D + thunder).
   - TP=8 aggregated + thunder produces 109, and DEP8 aggregated + thunder produces 127. P/D reaches only 0.57x to 0.67x of these values.
   - At equal output per GPU, aggregated serving gives the same per-user decode speed and a higher E2E-normalized interactivity (Figure 1).
   - P/D decodes faster only in comparisons at equal concurrency per GPU. Equal concurrency per GPU is not equal cost.
2. **On Qwen3.5, P/D is competitive.**
   - The P/D peak is 0.88x of the aggregated peak (370 against 421 output tok/s per GPU).
   - At about 370 tok/s per GPU, P/D gives 1.55x the per-user decode speed (111 against about 72 tok/s).
   - At that output, the E2E-normalized interactivity is equal (60.5 against about 59).
   - P/D also reaches E2E-normalized values of 94 to 113 at 180 to 275 tok/s per GPU. We did not measure aggregated serving in that range (Figure 2).
3. **A decode server is more productive than an aggregated server on both models.**
   - On GLM-5.2, a decode GPU produces 1.3x to 1.7x the output of an aggregated GPU (142 to 181 against 109 tok/s).
   - On Qwen3.5, a decode GPU produces 1.76x (739 against 421 tok/s).
   - Output per GPU of a P/D deployment = output per decode GPU x the decode share of the GPUs. Thus the prefill GPUs decide the result.
   - The break-even decode share is about 60% to 77% on GLM-5.2 (against TP=8 + thunder) and 57% on Qwen3.5.
   - The GLM-5.2 deployments had decode shares of 33% (2P1D), 50% (1P1D), and 67% (1P2D) (Figure 3).
4. **A larger decode share moves the limit to the prefill server.**
   - The prefill server keeps the history of every session.
   - Without thunder, 1P2D is the best P/D deployment up to c=64 (63 tok/s per GPU).
   - At c=96, 1P2D collapses. The working set on its prefill server was about 20M tokens. This is more than its GPU pool and its 820 GiB CPU tier can hold.
   - As a result, recompute increased to 6.6%, and the output decreased to 763 tok/s (31.8 tok/s per GPU).
5. **Thunder has a larger effect than the topology.**
   - On every topology, thunder keeps the TTFT p50 between 1 s and 4 s. Without thunder, the TTFT p50 increases to a maximum of 175 s.
   - Thunder increases the output where the baseline is overloaded: 1.05x to 1.17x on 2P1D from c=64, and 1.14x (c=64) and 2.13x (c=96) on 1P2D.
   - The cost is a long tail. Completed requests are 6% to 39% shorter, the E2E p99 is 1.6x to 7.5x, and the forced admissions increase with the load.
   - The thunder ledger contains only decode pods. Thus thunder does not see a saturated prefill server.
6. **GLM-5.2 has four properties that make P/D expensive** (Section 5):
   - With TP=8, each rank keeps a full copy of the MLA KV. Thus a decode server holds only 1.5M tokens, which is 5 to 8 requests of 100k to 250k tokens.
   - The always-disaggregated path prefills the full prompt on the prefill server in every turn. That server also keeps the history of every session.
   - The KV of each request crosses NIXL eight times. This gives 165 to 219 TB per hour, but the network was not a limit.
   - Each role uses a full 8-GPU node, so the P:D ratio has only coarse steps.
7. **Recommendation:**
   - For GLM-5.2 on this workload, use aggregated serving with thunder.
   - TP=8 at 2.5 to 4 sessions per GPU gives 100 to 108 tok/s per GPU and a TTFT p50 of 0.7 s. Each user gets 158 to 164 tok/s.
   - DEP8 gives more output (118 to 127 tok/s per GPU) at a lower per-user decode speed (40 to 55 tok/s).
   - For Qwen3.5, P/D is the better choice when a per-user decode speed of more than about 100 tok/s is necessary at high load. In other cases, aggregated serving gives more output per GPU.

## 1. Test Environment

| | |
|---|---|
| Hardware | GKE `a4-highgpu-8g` nodes (8x B200 and 8 RDMA NICs each), cluster `a4-pr` |
| GLM-5.2 | `nvidia/GLM-5.2-NVFP4`, vLLM v0.31.0, FP8 KV, 1M context, MTP 3. Each server has an 820 GiB CPU KV tier (`OffloadingConnector`). P/D uses `MultiConnector` (NIXL over RDMA, plus the CPU tier) with the vllm#62862 fix. The GPU KV pool of a TP=8 server is 1,505,088 tokens (decode) or 1,572,864 tokens (prefill). |
| Qwen3.5 | `Qwen3.5-397B-A17B-FP8`, TP=4 servers. P/D is a 1P1D pair of two TP=4 servers on one node. |
| Workload | AgentX `agentx-v1.0.6` replays uncapped `semianalysis_cc_traces_weka_062126` Claude Code sessions. The mean input is 100k to 160k tokens and the median output is 420 to 470 tokens. The prefix-cache hit rate is 93% to 99%, mostly from the CPU tier. Each point is 60 minutes. The KV tiers are empty at the start of each point. |
| Metrics | Output tok/s per GPU uses all GPUs of the deployment. Per-user decode speed (interactivity) = output tokens / decode time. E2E-normalized interactivity = output tokens / total request time, TTFT included. |
| Thunder | llm-d-thunder-agent-simplified (zetxqx/llm-d-router PR #15 for P/D). It keeps a KV ledger per pod, with a 10 s idle lease and a 1800 s forced admission. Under P/D, only decode pods are in the ledger. |

## 2. Deployments

| Model | Deployment | GPUs | Decode GPUs | Router | Step |
|---|---|---|---|---|---|
| GLM-5.2 | TP=8 aggregated | 8 | – | none | 25 |
| GLM-5.2 | TP=8 aggregated + thunder | 8 | – | thunder EPP | 25 |
| GLM-5.2 | DEP8 aggregated + thunder (data-parallel attention, expert parallel) | 8 | – | thunder EPP | 27 |
| GLM-5.2 | 1P1D, with and without thunder | 16 | 8 | vLLM NIXL toy proxy / thunder EPP | 35, 36 |
| GLM-5.2 | 2P1D, with and without thunder | 24 | 8 | toy proxy (prefill server fixed per session) / thunder EPP | 37, 38 |
| GLM-5.2 | 1P2D, with and without thunder | 24 | 16 | toy proxy (decode server fixed per session) / thunder EPP | 39, 40 |
| Qwen3.5 | TP=4 aggregated, with and without thunder | 4 | – | none / thunder EPP | 26 |
| Qwen3.5 | 1P1D, with and without thunder | 8 | 4 | toy proxy / thunder EPP | 33, 34 |

All P/D deployments are always disaggregated. In each turn, a prefill server prefills the prompt (`max_tokens=1`). Then a decode server pulls the KV over NIXL and decodes. The decode server uses its own cached prefix again (the #62862 fix).

## 3. Peak Output

| Model | Deployment | Peak output tok/s per GPU (total) | c at peak | TTFT p50 at peak | Per-user decode tok/s at peak | E2E-normalized at peak |
|---|---|---|---|---|---|---|
| GLM-5.2 | **DEP8 aggregated + thunder** | **127.1** (1,017) | 64 | 1.2 s | 40 | 30 |
| GLM-5.2 | **TP=8 aggregated + thunder** | **108.7** (870) | 48 | 0.7 s | 135 | 94 |
| GLM-5.2 | TP=8 aggregated | 102.3 (818) | 24 | 7.5 s | 120 | 42 |
| GLM-5.2 | 1P1D + thunder | 72.8 (1,165) | 64 | 1.2 s | 168 | 98 |
| GLM-5.2 | 1P2D + thunder | 71.8 (1,724) | 64 | 3.4 s | 199 | 78 |
| GLM-5.2 | 1P1D | 70.8 (1,132) | 64 | 49 s | 177 | 9 |
| GLM-5.2 | 1P2D | 63.3 (1,519) | 48 | 14 s | 216 | 31 |
| GLM-5.2 | 2P1D + thunder | 60.5 (1,451) | 64 | 0.9 s | 175 | 115 |
| GLM-5.2 | 2P1D | 53.8 (1,292) | 96 | 71 s | 159 | 6 |
| Qwen3.5 | **TP=4 aggregated** | **420.6** (1,682) | 64 | 11 s | 45 | 20 |
| Qwen3.5 | TP=4 aggregated + thunder | 407.5 (1,630) | 48 | 0.9 s | 59 | 49 |
| Qwen3.5 | 1P1D | 369.7 (2,957) | 64 | 3.2 s | 111 | 61 |
| Qwen3.5 | 1P1D + thunder | 354.7 (2,838) | 96 | 4.7 s | 113 | 52 |

The P/D deployments have the largest totals because they use 2x to 3x the GPUs. Per GPU, every GLM-5.2 P/D deployment produces less than every aggregated deployment.

## 4. Interactivity at Equal Cost

![](figures/pd-fig1-glm-pareto.png)

Figure 1. GLM-5.2, all deployments and concurrencies. Panel (a) shows the E2E-normalized interactivity and panel (b) the per-user decode speed, against output tok/s per GPU. Up and right is better. The labels give the concurrency per GPU. Aggregated lines are solid and P/D lines are dashed.

![](figures/pd-fig2-qwen-pareto.png)

Figure 2. The same views for Qwen3.5. We measured aggregated serving only from 8 sessions per GPU, so its curve starts at 315 tok/s per GPU.

The table compares the deployments at the same output per GPU. The symbol `~` marks a value interpolated between the two nearest measured points.

| Model | Output tok/s per GPU | Aggregated: per-user decode tok/s / E2E-normalized | P/D: per-user decode tok/s / E2E-normalized |
|---|---|---|---|
| GLM-5.2 | ~50 | TP=8, 1 per GPU (53.5): 237 / 163 | 1P2D, 1.33 per GPU (50.2): 236 / 74 |
| GLM-5.2 | ~60 | TP=8 + thunder, 1.5 per GPU (64.6): 217 / 157 | 2P1D + thunder, 2.67 per GPU (60.5): 175 / 115. 1P1D, 1.5 per GPU (60.0): 200 / 81 |
| GLM-5.2 | ~72 | TP=8 + thunder: ~200 / ~141 | 1P2D + thunder (71.8): 199 / 78. 1P1D + thunder (72.8): 168 / 98 |
| GLM-5.2 | 100 to 127 | TP=8 + thunder (100.6 to 108.7): 164 to 135 / 112 to 94. DEP8 + thunder (118 to 127): 55 to 40 / 42 to 30 | no P/D deployment reaches this output |
| Qwen3.5 | ~355 | TP=4: ~77 / ~63 | 1P1D + thunder (354.7): 113 / 52 |
| Qwen3.5 | ~370 | TP=4: ~72 / ~59 | 1P1D (369.7): 111 / 60.5 |
| Qwen3.5 | 407 to 421 | TP=4, with or without thunder: 59 to 45 / 49 to 20 | no P/D deployment reaches this output |

GLM-5.2:

- At each output that P/D reaches, an aggregated deployment with fewer sessions per GPU gives the same per-user decode speed. Examples: 236 against 237 at about 50 tok/s per GPU, and 199 against about 200 at 72.
- The aggregated deployment also gives 1.4x to 2.2x the E2E-normalized interactivity. No prefill queue and no KV transfer come before its first token.
- Only aggregated deployments produce more than 73 tok/s per GPU.

Qwen3.5:

- At 355 to 370 tok/s per GPU, P/D gives 1.47x to 1.55x the per-user decode speed of aggregated serving.
- At these points, the E2E-normalized interactivity is equal (60.5 against about 59) or lower (52 against about 63).
- Aggregated serving produces 10% to 14% more output per GPU, at 45 to 59 tok/s per user.

## 5. Use of the GPUs

![](figures/pd-fig3-decode-gpu.png)

Figure 3. The output of each P/D deployment at its peak. Light bars show the output per decode GPU. Dark bars show the output per GPU of the full deployment. The dashed line is the best aggregated output per GPU.

Output per GPU = output per decode GPU x the decode share of the GPUs. On GLM-5.2, a decode GPU produces 142 to 181 tok/s at its best. This is 1.3x to 1.7x the 109 tok/s of TP=8 + thunder. But the decode share is only 33% to 67%. Thus the full deployment produces 54 to 73 tok/s per GPU.

The break-even decode share against TP=8 + thunder is 109 / 181 = 60% at the best decode output that we measured (2P1D + thunder). With the decode output of 1P1D, the break-even share is 77%. Against DEP8 + thunder (127), the break-even share is 70% to 90%.

On Qwen3.5, a decode GPU produces 739 tok/s, which is 1.76x the 421 tok/s of aggregated serving. Thus the break-even share is 57%. The decode share of 1P1D is 50%, so 1P1D comes close (0.88x).

1P2D shows the limit of a larger decode share. With one prefill server for two decode servers, the decode GPUs produced only 95 to 108 tok/s each. The prefill server did not supply enough prefills.

### The Limit in Each GLM-5.2 Deployment

| Deployment | Limit | Data (steady-state means) |
|---|---|---|
| 1P1D | prefill server | 4.8, 19.6, and 44 requests wait on the prefill server at c = 32, 48, and 64. The decode server runs only 5 to 6 requests (KV 74%), with fewer than 3.5 waiting. |
| 2P1D | decode server | 6.5 to 20 requests wait on the decode server, 5 to 8 run, and the KV use is 82% to 89%. At c=32, the two prefill servers are almost idle. |
| 1P2D | prefill server, then its cache capacity | 3.3, 14.5, 44.8, and 111 requests wait on the prefill server at c = 32 to 96. The decode servers use 34% to 54% of their KV. At c=96, recompute is 6.6% and the prompt tokens are half of the c=64 value. |
| 1P1D + thunder, 2P1D + thunder | thunder | The TTFT p50 is 0.9 s to 1.4 s, and 0.1 to 6 requests wait on the prefill servers (12 at 2P1D, c=144). In 2P1D + thunder, fewer than 1 request waits on the decode server, at 46% to 54% KV. The ledger counts idle sessions in their lease at full size. |
| 1P2D + thunder | prefill server (thunder does not see it) | 1.3 to 41 requests wait on the prefill server. The decode servers use 20% to 35% of their KV. After c=64, recompute on the prefill server increases to 6% and the output decreases. |

### Why P/D Is Expensive for GLM-5.2

- **Small decode batches.** With TP=8, each rank keeps a full copy of the MLA KV. Thus the GPU pool of a decode server is 1.5M tokens, which is 5 to 8 requests of this workload. Aggregated TP=8 has the same pool, so P/D does not give a larger batch. DEP8 divides its KV across the ranks. Thus DEP8 + thunder runs about 35 requests and has the highest output per GPU.
- **Prefill work in every turn.** The always-disaggregated path prefills the full prompt of each turn on the prefill server. The server loads most of that prompt from its CPU tier, and it keeps the history of every session. An aggregated server keeps the prefix of each session on the same server that decodes it.
- **Repeated transfer.** Each decode rank pulls the full MLA block, so the KV of each request crosses NIXL eight times. Without thunder, this is 165 to 219 TB per hour. With thunder, it is 3x to 6x less, because admitted sessions keep their KV on the decode server. The network links were never the limit.
- **Coarse P:D ratios.** Each role uses a full 8-GPU node. Thus we tested only the ratios 1:1, 2:1, and 1:2.

## 6. Thunder on P/D

| Deployment, c | Output tok/s per GPU, thunder against none | TTFT p50, thunder against none | Input length of completed requests | E2E p99, thunder against none |
|---|---|---|---|---|
| 1P1D, c=64 | 72.8 against 70.8 (1.03x) | 1.2 s against 49 s | 32% shorter | 1,109 s against 153 s |
| 2P1D, c=64 | 60.5 against 51.6 (1.17x) | 0.9 s against 42 s | 39% shorter | 552 s against 132 s |
| 2P1D, c=144 | 50.6 against 48.0 (1.05x) | 1.0 s against 175 s | 23% shorter | 2,081 s against 446 s |
| 1P2D, c=64 | 71.8 against 63.2 (1.14x) | 3.4 s against 34 s | 29% shorter | 548 s against 134 s |
| 1P2D, c=96 | 67.9 against 31.8 (2.13x) | 3.9 s against 145 s | 35% shorter | 1,307 s against 478 s |
| Qwen3.5 1P1D, c=96 | 355 against 287 (1.23x) | 4.7 s against 36 s | – | 222 s against 155 s |

Thunder changes the queue of an overloaded P/D deployment. Admitted sessions get a short TTFT, and held sessions wait a long time. Thunder serves smaller sessions first: a session that does not fit does not block the other sessions. As a result, part of the gain in TTFT and interactivity comes from shorter requests. The output tok/s values are a fair comparison. The input tok/s and the interactivity values are not.

## 7. Limits of This Comparison

- Each deployment has one point per concurrency. Earlier repeated runs in this repository varied by 2% to 6% between points.
- At high load, the nominal concurrency is less than the request concurrency, because sessions start sub-agent requests. At c=144, the 2P1D baseline had a mean of 206 requests in progress. The thunder deployments had 80 to 124. Comparisons up to about c=64 change little.
- The P/D deployments without thunder use the vLLM toy proxy with a session hash. The thunder deployments use the llm-d EPP and the disagg sidecar.
- The first 2P1D + thunder run sent 87% of the requests to one prefill server. The cause was a tie-break counter that `max-score-picker` shares between profiles. We discarded that run.
- Qwen3.5 has fewer points. Its aggregated deployments start at 8 sessions per GPU.
- We did not test these options:
  - Selective P/D (`prefix-based-pd-decider`), which prefills small uncached suffixes on the decode server.
  - DEP or wide-EP decode servers.
  - P:D ratios other than 1:1, 2:1, and 1:2.
  - Prefill servers with a different parallelism.
  - Multi-node scale, where one prefill server supplies many decode servers.

## 8. Sources

| Step | README | Content |
|---|---|---|
| 25 | [`../25-glm52-tp8-offload/`](../25-glm52-tp8-offload/) | GLM-5.2 TP=8 aggregated, with and without thunder |
| 27 | [`../27-glm52-dep8/`](../27-glm52-dep8/) | GLM-5.2 DEP8 aggregated, with thunder |
| 35, 36 | [`../35-glm52-1p1d/README.md`](../35-glm52-1p1d/README.md), [`../36-glm52-1p1d-thunder/README.md`](../36-glm52-1p1d-thunder/README.md) | GLM-5.2 1P1D, with and without thunder |
| 37, 38 | [`../37-glm52-2p1d/README.md`](../37-glm52-2p1d/README.md), [`../38-glm52-2p1d-thunder/README.md`](../38-glm52-2p1d-thunder/README.md) | GLM-5.2 2P1D, with and without thunder |
| 39, 40 | [`../39-glm52-1p2d/README.md`](../39-glm52-1p2d/README.md), [`../40-glm52-1p2d-thunder/README.md`](../40-glm52-1p2d-thunder/README.md) | GLM-5.2 1P2D, with and without thunder |
| 26 | [`../26-qwen35-tp4-thunder/`](../26-qwen35-tp4-thunder/) | Qwen3.5 TP=4 aggregated, with and without thunder |
| 33, 34 | [`../33-qwen35-1p1d-baseline/`](../33-qwen35-1p1d-baseline/), [`../34-qwen35-1p1d-thunder/`](../34-qwen35-1p1d-thunder/) | Qwen3.5 1P1D, with and without thunder |
| – | [`pd-vs-nonpd.png`](figures/pd-vs-nonpd.png) | the earlier version of this comparison, with 1P1D only |

To make the figures, run `uv run summary-report/make_pd_report_figures.py <glm bundle> <qwen bundle> 38-glm52-2p1d-thunder/b200/results/compare/report/summary.csv 40-glm52-1p2d-thunder/b200/results/compare/report/summary.csv summary-report/figures`. Export the two bundles from `dashboard/data/` on `main` (`glm52-nvfp4-8xb200.json`, `qwen35-397b-fp8-4xb200.json`).
