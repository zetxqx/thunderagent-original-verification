# Original ThunderAgent router setup (paper verification)

Goal: run the original (upstream Python) ThunderAgent router from the paper (arXiv 2602.13692, commit `7ddc861` of `ThunderAgent/`) against the real vLLM backends in the `llm-d-program-aware-scheduling` namespace, so the paper's program-aware scheduling behavior can be verified on a live cluster.

This folder records every step. Files are numbered in the order they were used.

## Environment baseline (2026-09-15)

- Cluster: GKE `bobbm` (`gke_bobzetian-gke-dev_us-central1_bobbm`)
- Namespace: `llm-d-program-aware-scheduling`
- Backends: Deployment `program-aware-vllm-decode`, 4 replicas of `vllm/vllm-openai:v0.28.0`, model `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8`, TP=2 on H100 (spot), serving port 8000
- Full serving-side reference (engine flags, resolved batch and chunked-prefill settings, KV pool, hardware, change history): `model-server/README.md`, re-collectable with `model-server/collect.sh`
- Already present (untouched by this setup): the llm-d EPP with the Go `thunder-agent` plugin (`program-aware-scheduling-epp`)
- Upstream ThunderAgent source: `../ThunderAgent` at git commit `7ddc861`, clean working tree

The original router is a Python FastAPI proxy. Clients send OpenAI chat completions to it with a `program_id` in the body (or `X-Session-ID` header); it tracks per-program token state, schedules admission against each backend's KV capacity (fetched from vLLM `/metrics` at startup: `vllm:cache_config_info` block_size x num_gpu_blocks), and proxies to a sticky vLLM backend.

## Steps

### 1. Build the container image (Cloud Build)

The upstream repo has no Dockerfile. `01-image/Dockerfile` packages it with `pip install .` (deps: fastapi, httpx, uvicorn). The host here is an arm64 Mac without Docker, so the image is built for amd64 with Google Cloud Build via `01-image/build.sh`, which:

1. Stages the upstream source plus the Dockerfile into a temp dir (the upstream checkout is not modified).
2. Runs `gcloud builds submit` in project `bobzetian-gke-dev`.
3. Pushes `us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/thunderagent-original:7ddc861`.

Run: `./01-image/build.sh`

### 2. Deploy to the cluster

Manifests in `02-deploy/`, applied with `kubectl apply -f 02-deploy/`:

- `backends-headless.yaml`: headless Service `thunderagent-vllm-backends` selecting the existing vLLM pods on port 8000. Used only for DNS discovery of pod IPs.
- `launcher.py`: startup script, mounted as ConfigMap `thunderagent-launcher`. Needed because of an upstream bug: the `thunderagent` CLI silently ignores all its flags (the router is created at package import time with the default config, before `main()` sets the CLI config). The first deployment attempt proved it: the pod logged `Started router with 1 backend(s): ['http://localhost:8000']` despite a correct `--backends` flag. The launcher uses upstream's documented embedding API (`Config` + `MultiBackendRouter` + `register_routes`) so the config actually takes effect. No upstream source is modified.
- `thunderagent.yaml`: Deployment (1 replica, CPU node) + Service `thunderagent-router` on port 8300.

Apply order:

```
cd 02-deploy
kubectl create configmap thunderagent-launcher --from-file=launcher.py -n llm-d-program-aware-scheduling
kubectl apply -f backends-headless.yaml -f thunderagent.yaml
```

ThunderAgent takes a static `--backends` list at startup. The pod's entrypoint resolves the headless service DNS, waits until all 4 backend IPs are visible, then execs:

```
python /launcher/launcher.py --router tr --backend-type vllm --backends http://<ip1>:8000,... --port 8300 --metrics --profile
```

Flags match the paper's "tr" (ThunderAgent router) mode with defaults: scheduler interval 5s, acting-token-weight 1.0, decay off. `--metrics` enables the 5s background metrics poll (needed for the shared_tokens prefix discount), `--profile` enables per-program timing needed for verification.

Limitation (accepted for a verification setup): backend IPs are resolved once at startup. If a spot vLLM pod is replaced, restart the router: `kubectl rollout restart deploy/thunderagent-original -n llm-d-program-aware-scheduling`.

### 3. Smoke test

`03-verify/smoke-test.sh` port-forwards to the router service and checks, in order:

1. `GET /health` - router mode is `tr`, scheduling enabled, 4 backends
2. `GET /v1/models` - proxying to vLLM works
3. Two chat completions for the same `program_id` (multi-turn), one for a second program
4. `GET /programs` - both programs tracked with token counts and step counts, sticky backend recorded
5. `GET /metrics` - per-backend KV capacity (cache_config) fetched, kv usage and prefix-cache hit rate visible
6. `POST /programs/release` - explicit release works

Run: `./03-verify/smoke-test.sh` (results recorded in `03-verify/smoke-test-results.md`)

### 4. Benchmark with metrics time series

`04-benchmark/benchmark.py` drives N concurrent agentic sessions (one `program_id` each, unique large preamble, growing multi-turn context) through the router, while a prober thread records 2s-interval time series of per-backend prefix-cache hit rate (computed from counter deltas), KV cache utilization, queue depth, and the router's program-state counts (REASONING/ACTING/paused). It then validates the run: all requests OK, sticky routing per program, aggregate hit rate above threshold, KV cache touched, programs tracked and released. Exit code is non-zero if any check fails.

Run: `./04-benchmark/run-benchmark.sh` (pass-through flags, e.g. `--sessions 24 --turns 8`). Results of the recorded run: `04-benchmark/results.md`, all checks PASS, aggregate prefix-cache hit rate 0.799 with sticky placement confirmed on all 12 sessions.

### 5. Saturation test (admission control / pause+resume)

`05-saturation/` runs the same benchmark script as an in-cluster Job at 2.2x KV over-subscription (320 sessions x ~61k tokens against 8.95M tokens total capacity) to verify the paper's pause/resume admission control. The benchmark script gained per-session release (required: capacity only frees on release), start ramp, pause profiling, and an `--expect-pauses` check for this.

Run: `./05-saturation/run-saturation.sh`. Recorded run: all 6 checks PASS - max 186 programs paused concurrently, 318/320 programs held at admission, KV peaked at 96%, everything resumed and completed. Details: `05-saturation/results.md`.

### 6. Single-node A/B: tr vs default (the paper's headline claim)

`06-single-node-ab/` compares the original router's `tr` mode against `default` (pure proxy) on ONE vLLM pod, so admission control is isolated from placement. Workload scaled to one node: 80 sessions x ~61k tokens = 2.2x over-subscription. Arms run sequentially against the same pod with a prefix-cache reset between them (`run-ab.sh` orchestrates: reset -> deploy `thunderagent-ab` router in the arm's mode -> in-cluster job -> collect; `compare.py` renders the comparison).

Recorded results (two runs): with per-session release, tr is 1.5x faster end-to-end (457s -> 305s, hit rate 0.000 -> 0.362). The main run then removed ALL release calls (realistic: clients never signal completion) across three arms: `default` 457.5s, `tr + acting decay` **315.3s (1.45x faster, no release needed)**, `tr without decay` **3677.7s (8x slower - held sessions serve full 1800s forced-resume timeouts because capacity accounting never frees)**. Conclusion: the paper's mechanism survives uncooperative clients only with `--use-acting-token-decay` enabled (off by default upstream). Details: `06-single-node-ab/results.md`.

### 7. Weka trace replay A/B (done)

`07-inference-perf-weka/` replays REAL Claude Code sessions (weka dataset, official inference-perf v0.7.0, digest-pinned) through the router: `default` vs `tr-decay` at c=96/128/192, 45 min per cell, three lanes in parallel on three pods, paired per-request analysis.

**Result: tr-decay delivers 2.0-2.4x the output-token throughput and lifts the prefix-cache hit rate from 0.04-0.10 to 0.54-0.69**, with TTFT p50 an order of magnitude lower. The paired per-request analysis was later found unsound (`graph_event_id` is not unique per session) and is retracted in `07-inference-perf-weka/RESULTS.md`; every arm-level result stands. Design and version pins: `PLAN.md`; incident write-ups: `HANG-INVESTIGATION.md`, `UPSTREAM-ISSUES.md`.

### 8. Replicated A/B (done) - error bars, warm-up split, per-session fairness

`08-weka-replicates/` runs ONE configuration (c=128) three times instead of sweeping concurrency, because the sweep turned out to measure a single operating point while changing which traces were sampled.

**Result: 2.12x throughput, reproducible to +-1.3%** across three independent replicates, and **85x steady-state hit rate** (0.008 -> 0.685); TTFT p50 52.7s -> 3.0s. Three things the single-run sweep could not show:

- the arms are **indistinguishable during warm-up** (hit rate 0.197 vs 0.188) and all run-to-run noise lives there - which is why the earlier 10-minute cells disagreed by 2.6x;
- restricted to the sessions **both** arms touched, per-session progress is **1.3x**, not 2.1x (the rest of the system-level gain comes from reaching more sessions);
- the ~50-request in-flight ceiling is the **load generator**, not the single-process router (measured: router 0.06-0.11 cores).

Open item, resolved in step 10: the extra errors were 600 s client timeouts on the longest-held sessions, and each one also dropped that session's remaining turns from the workload (about 2300 per tr cell), so the 2.12x is measured on a client-trimmed workload; see the addendum in `08-weka-replicates/RESULTS.md`.

### 9. llm-d-router port on the cluster: smoke test (done)

`09-llm-d-router-smoke/` puts the rewritten `thunder-agent` EPP plugin (upstream tr-decay semantics: 1 s acting decay, 5 s pause sweep, paused-before-new admission, 1800 s forced admission) on the same 4 pods and checks the plumbing with simple traffic: the running build, the new config parsed, real scraped capacity on all pods, program accounting per turn, class ordering, stickiness, and session-final release. **All 20 checks pass.** No load and no holds yet; that is the next step. Details: `09-llm-d-router-smoke/README.md`.

### 10. llm-d-router port: the step 08 protocol through the EPP (done)

`10-llm-d-router-replicates/` runs step 08's replicate protocol through per-lane EPPs, `epp-sticky` (scorer only) vs `epp-thunder` (the port), twice: with a 1900 s client and with step 08's 600 s client. **The EPP path is free (sticky equals the Python proxy). The port delivers 1.54x with a patient client and 1.80x with step 08's client, with the same TTFT and the same loaded-phase hit rate as upstream.** Upstream's 2.12x stands as measured but stacks two artifacts the port does not have: the 600 s client trimmed about 2300 turns per cell in tr-decay's favor, and the Python router leaves client-abandoned requests as phantom REASONING programs (76 to 83 on its books against 17 to 20 running), throttling admission into a lighter, hotter engine late in each run. Time series per lane in both run folders. Details and step 11 in `10-llm-d-router-replicates/RESULTS.md`.

### 12. llm-d-router: three EPP policies on the whole 4-pod pool (done)

`12-llm-d-router-pool/` compares, through one EPP over the four pods, llm-d's default profile (prefix-cache, queue and KV scorers), plain session affinity, and the ThunderAgent port, at c=338 (the whole corpus) for 45 minutes, three replicates each, with the load generator fixed first (inference-perf v0.7.0 lets only about half of the sessions start; see `INFERENCE-PERF-BUGS.md` issue 4). **The two llm-d policies are indistinguishable (1020 tok/s, hit rate 0.002, TTFT p50 123 s). The port gives 1.42x throughput, a 0.25 steady-state hit rate and a 3.7 s median TTFT.** Admission control is the entire effect; placement alone does nothing under oversubscription. The port loses half its single-pod hit rate to pod hopping on resume (70 percent of resumes move), identified before the run; an origin-only resume policy is the next step. Details: `12-llm-d-router-pool/RESULTS.md`.

### 15. Minimal thunder-agent rewrite on one pod (done)

`15-thunder-minimal-single-pod/` runs the minimal rewrite of the plugin (llm-d-router `thunder-agent-minimal` at `33dde5d2`) through step 10's single-pod protocol, one cell, against step 10's v3 cells. **The gate works and the ledger closes (smoke test 20 of 20; vLLM waiting 0.5, no EPP errors). The cell reached 397 tok/s and a 0.57 steady-state hit rate against v3's 351 (327-367) and 0.49, with a heavier long-wait tail (TTFT p99 712 s vs 410 s).** Both follow from the intended removal of `markedForPause`: 345 pauses instead of 971, and the working set over capacity 65 percent of the time instead of 24. One cell, no same-day control. Details: `15-thunder-minimal-single-pod/README.md`.

### 16. Minimal thunder-agent rewrite on the 4-pod pool (done)

`16-thunder-minimal-pool/` runs the same build through step 13's pool protocol at c=128, three cells per configuration, against step 13's three origin-only cells. **At upstream's settings (half-life 1 s, sweep 5 s) the minimal build reproduces origin-only on every main metric (1770 vs 1693 tok/s, steady-state hit rate 0.71 vs 0.68, strict session attainment 0.68 vs 0.70) with under a third of the pauses, and a 90-minute cell shows no drift against origin-only's. Half-life 10 s trades the tail for efficiency (1846 tok/s, attainment 0.55). Adding a 1 s pause sweep keeps the pods under the line and gives the best c=128 result so far: 1945 tok/s, hit rate 0.80, goodput within SLO 1.77 turns/s (1.15x and 1.16x origin-only), with attainment back to 0.64.** Details: `16-thunder-minimal-pool/README.md`.

### 25. vLLM TP=8 with CPU KV offload against InferenceX GLM-5.2, and the thunder gate past saturation (done)

`25-glm52-tp8-offload/` runs `nvidia/GLM-5.2-NVFP4` on vLLM v0.31.0, TP=8 on 8x B200 (cluster `a4-pr`) with 820 GiB native CPU KV offload, matched to the InferenceX B200 Dynamo + SGLang + HiCache recipe, AgentX client. **Formal runs: throughput ties InferenceX (51.3 against 51.2 output tok/s per GPU at c=8), but vLLM's TTFT p50 is 2.4x to 2.9x higher. No KV thrashing up to c=32: the CPU tier serves nearly all GPU misses, but from c=24 no router queues (only 6 to 7 of the ~250k-token requests fit on the GPU) and the CPU-to-GPU churn slows every step. Exploration runs (caches emptied, 900 s): the thunder gate (GPU capacity, lease 10 s) raises output throughput 6% to 10% at c=24 and 24% to 27% at c=32 with TTFT p90 2 to 3 s, at the cost of 0.6% to 1.6% of turns waiting 3 to 4 minutes; forced-admission backstops and the reclaim fix (zetxqx/llm-d-router#14) do not help.**

### 29. llm-d-router v1.0.0 turn-priority on GLM-5.2 DEP=8 (done)

`29-glm52-dep8-turn-priority/` puts llm-d-router v1.0.0's flow control with the `turn-priority` fairness strategy on top of step 27's session-affinity routing to the 8 DP ranks of GLM-5.2 (DEP=8, 8x B200, 820 GiB offload), c = 24 to 64, one hour each, against step 27's `dep8-affinity` and `dep8-thunder-l10`. **Where the router's gate was active part of the time (c=48, pool saturated 24% of the samples) turn-priority gives 1.99x the output throughput of session affinity alone (58.2 against 29.3 tok/s/GPU) and 85% against 64% hit rate; at c=64 (saturated 67% of the time) it is a tie (1.18x) with a worse TTFT median, because ordering does not bound the per-rank working set (2.0x the pool). At c=24 and 32 the router never queued. llm-d-thunder-agent-simplified lease 10 s stays 1.08x to 5.78x ahead of turn-priority in output throughput with a sub-second TTFT median.** Unlike TP=8 (step 28, a tie with no router), turn-priority does something on DEP=8; admission control on the working set does much more.

### 30. llm-d-router v1.0.0 turn-priority on Qwen3.5-397B TP=4 (done)

`30-qwen35-turn-priority/` runs step 28's turn-priority config, unchanged, in front of step 26's Qwen3.5-397B-A17B-FP8 TP=4 servers (4x B200, 387 GiB offload, 256k-capped traces), c = 32, 48, 64, one hour each, against step 26's no-router and llm-d-thunder-agent-simplified points. **A tie with no router at every c: output throughput 1.01x, 1.03x, 1.03x, identical hit rates (93%, 92%, 88%). The router was active at c=64 (pool saturated 80% of the time, 6.2 s mean wait at the router, vLLM waiting 19 to 6) and the TTFT median did not move (11.27 against 11.29 s): the wait changed queues, the order did not shorten it; TTFT p90 is 27% longer. thunder-agent's trade at c=64 stands apart: TTFT median 1.7 s for 3% less throughput.** With steps 28 and 29: on one engine with a CPU tier the policy is a tie; it helps only where small per-rank pools overflow (DEP=8, c=48).

### 33. No-thunder 1P1D baseline sweep on Qwen3.5-397B (done)

`33-qwen35-1p1d-baseline/` runs Qwen3.5-397B-A17B-FP8 as 1 prefill + 1 decode server (TP=4 each on one 8x B200 node, KV over NIXL/RDMA, 387 GiB CPU tier on both, the vllm-project/vllm#62862 fix on), with no router (vLLM's NIXL toy proxy, every request P then D), at c = 32, 48, 64, 96, 128, one hour each. **The knee is c=64 (370 output tok/s/GPU, TTFT p50 3.2 s). Past it the system collapses instead of plateauing (287 tok/s/GPU and TTFT p50 36 s at c=96; 75 and 342 s at c=128), because the single prefill server queues 82 to 215 requests while decode sits idle, and cache thrashing (hit rate down to 55%) feeds the queue. Against two aggregated TP=4 servers (step 26), 1P1D gives 3x to 4x higher per-user decode speed but loses on throughput and TTFT beyond c=64.** Baseline for a P/D thunder-agent arm at c = 64 and 96.

### 34. llm-d-thunder-agent-simplified on the 1P1D pair (done)

`34-qwen35-1p1d-thunder/` puts thunder-agent (built from zetxqx/llm-d-router#15, which tracks only decode pods under P/D; capacity = the prefill server's GPU KV pool, lease 10 s) in front of step 33's 1P1D pair, always P then D through the llm-d disagg sidecar, at c = 64 and 96, one hour each. **At c=96 the gate keeps the pair at its knee: 355 against 287 output tok/s/GPU (1.23x), TTFT p50 4.7 s against 36 s, prefill queue 10 against 82, 20% more completed requests; the cost is the held sessions' tail (E2E p99 222 against 155 s, 26 forced admissions, mean router wait 9.8 s). At c=64, where the baseline does not thrash, it is a small loss (0.95x throughput, 1.19x TTFT p90 and E2E p99).**

### 35. No-router 1P1D GLM-5.2 across two nodes (done)

`35-glm52-1p1d/` runs GLM-5.2-NVFP4 as one prefill and one decode TP=8 server on two 8x B200 nodes (KV over cross-node NIXL/RDMA, 820 GiB CPU tier on each, vllm#62862 fix on), with no router (vLLM's NIXL toy proxy), at c = 16 to 64, one hour each, against step 25's TP=8 aggregated server. **Per GPU 1P1D never wins: 0.68x to 0.92x TP=8 aggregated at equal concurrency per GPU, TTFT p50 2x to 12x higher; it saturates at about 70 output tok/s/GPU from c=48. Decode is KV-bound at 5 to 6 long requests but never queues; the prefill server does (19.6 waiting at c=48, 44 at c=64). Against one 8-GPU server at the same load, the 16 GPUs give 1.05x to 1.45x the total throughput, half the TTFT and 1.3x to 2.4x the per-user decode speed. MLA makes the transfer 8x redundant (every decode rank pulls the whole block): 63 to 211 TB per hour, not a limit.**

### 36. llm-d-thunder-agent-simplified on the GLM-5.2 1P1D pair (done)

`36-glm52-1p1d-thunder/` puts step 34's thunder EPP (zetxqx/llm-d-router#15, capacity = the prefill server's GPU KV pool 1,572,864 tokens, lease 10 s) in front of step 35's GLM-5.2 1P1D pair, always P then D through the disagg sidecar, at c = 24, 32, 48 and 64, one hour each. **TTFT p50 stays at 1.2 to 1.4 s at every load (no thunder: 3.4, 9.7, 25, 49 s), E2E-normalized interactivity p50 is 1.4x to 11x higher, output throughput 0.91x to 1.03x, NIXL traffic 4x to 5x lower. The gate admits only 4 to 8 of these ~250k-token sessions and serves smaller sessions first, at a cost that grows with the load: completed requests 12% to 32% shorter, E2E p99 2.3x to 7.5x the baseline (124 to 1,109 s), 1 to 32 forced admissions.**

### 37. GLM-5.2 2P1D across three nodes, no router (done)

`37-glm52-2p1d/` adds a second prefill server to step 35's pair: two prefill and one decode TP=8 server on three 8x B200 nodes (24 GPUs), step 35's toy proxy with session-sticky prefill choice (CRC32 of the session id), no router, at c = 32, 48, 64, 96 and 144, one hour each. **Per GPU it is the worst of the four GLM deployments: 44 to 54 output tok/s/GPU, 0.5x to 0.6x TP=8 aggregated, about 0.5x TP=8 + thunder and 0.75x to 0.8x 1P1D at equal load per GPU; peak total 1,292 tok/s at c=96, only 2% to 9% above 1P1D at the same total concurrency. The second prefill server empties the prefill queue at c=32 (under 1 waiting), and the decode server becomes the limit: KV-bound at 5 to 8 of the ~150k-token requests (KV 82% to 89%), queue 6.5 to 20. TTFT p50 7.8 s at c=32 and 20 to 175 s above; the session hash splits requests 43:57 to 57:43 but leaves the two prefill queues 2x to 4x apart.**

### 38. llm-d-thunder-agent-simplified on the GLM-5.2 2P1D servers (done)

`38-glm52-2p1d-thunder/` puts the thunder EPP (zetxqx/llm-d-router#15, commit 8d1fbc87) in front of step 37's 2P1D servers, always P then D through the disagg sidecar, with `capacityTokens` = the decode server's GPU KV pool (1,505,088; only decode pods enter the ledger) and the prefill server pinned per session (`session-affinity-scorer` + `weighted-random-picker`), at c = 32 to 144, one hour each. A first attempt with `max-score-picker` on the prefill profile sent 87% of requests to one prefill server (its tie-break counter is shared with the decode profile's pick) and was discarded. **TTFT p50 stays at 0.93 to 1.19 s at every load (no router: 7.8 to 175 s) and E2E-normalized interactivity p50 at 99 to 122 (no router: 50 to 2.6); output throughput is 0.87x and 0.97x at c=32 and 48 and 1.05x to 1.17x from c=64 (1,451 tok/s at c=64, the highest GLM-5.2 P/D total); NIXL traffic 3x to 6x lower. D's KV stays at about 50%: the ledger, not a server, sets the load. Per GPU it stays below 1P1D + thunder (0.80x to 0.98x) and about half TP=8 + thunder. Costs as in step 36: completed requests 18% to 39% shorter, E2E p99 2.9x to 7.4x the baseline (up to 2,081 s), 4 to 123 forced admissions.**

### 39. GLM-5.2 1P2D across three nodes, no router (done, c=144 not measured)

`39-glm52-1p2d/` swaps step 37's second prefill server for a second decode server: one prefill and two decode TP=8 servers on the same three nodes (24 GPUs), step 37's toy proxy with the decode server chosen per session (CRC32 of the session id), no router, at c = 32, 48, 64 and 96, one hour each; c=144 could not finish its warmup within the job's 6 h deadline. **Up to c=64 it is the best no-router P/D deployment: 1.13x to 1.26x 2P1D's output on the same GPUs (50 to 63 tok/s/GPU; peak 1,519 tok/s at c=48, the highest GLM-5.2 P/D total, thunder included), lower TTFT (4.8 to 34 s) and the highest per-user decode speed (interactivity p50 211 to 236). The single prefill server is the limit (3.3, 14.5, 44.8 waiting) while both decode servers stay at 34% to 54% KV; at c=96 it collapses (111 waiting, half the prompt tokens, recompute 6.6%): 763 tok/s, TTFT p50 145 s. Per GPU still 0.6x to 0.8x TP=8 aggregated.**

## Proposals (not part of the numbered steps)

`proposal/PROPOSAL.md` - eight ThunderAgent proposals; Part 3 and its Option B were run in step 13, the rest are unrun. Kept outside the numbered sequence.

**Part 1, admission-wait starvation**: why a minority of sessions wait up to 30 minutes for admission. Measured cause: `_greedy_resume` orders the waiting pool by token count **ascending** with no aging, so large sessions lose every round to a refreshed supply of smaller newcomers. **71% of sessions above 80k tokens were held past 600s; 0% of sessions below 40k tokens were**, with holds pinned at upstream's hard-coded 1800s forced-admission backstop. Four remedies compared (lower the timeout / age the queue / head-of-line reservation / shed with Retry-After), with a one-cell experiment and pre-registered expectations.

**Part 2, the 5s scheduler interval**: 67% of admission holds last under 12s and pile up on the polling period, and the engine sits idle 9.3% of the time under tr (5.6% under the proxy) with a non-empty waiting queue - so shortening the interval should recover throughput. But the capacity decision reads a single instantaneous sample (`latest_metrics`, never an average), and one sample misjudges free capacity by +-87k tokens - more than a median session - so faster polling multiplies noise-driven decisions rather than averaging them. Proposal: shorten the interval AND smooth the signal, with a three-arm experiment to separate the two.

**Part 3, origin-only resume on a multi-pod pool**: in step 12, 70% of the port's resumes (about 3100 of 4470 per cell) moved the session to another pod, because on equally loaded pods the origin pod rarely has room at the instant a paused session's turn arrives while the pod with the most room always does; upstream's best-fit-decreasing placement behaves the same way. Each move is a full re-prefill, and the pool hit rate ended at half the single-pod value. Proposal: a `resumePlacement` switch, default unchanged, `origin-only` making paused sessions wait for their own pod unless it vanished or the forced-admission backstop fired; new sessions still go to the pod with most room. One more pool arm with pre-registered expectations (rebinds near zero, hit rate toward 0.49, forced admissions as the risk metric).

**Part 4, P/D disaggregation**: step 13 shows the pool is bound by prefill work caused by KV capacity, not by prefill interference. P/D moves prefill without reducing it and shrinks the resident pool, so it cannot help throughput here; on `a3-highgpu-4g` without RDMA the 2.46 GB per-turn KV transfer is not clearly cheaper than recompute. ITL does degrade 6.5x under load, which P/D would partly fix; one cheap `max-num-batched-tokens` experiment separates the interference share from the batch-size share before any P/D work.

**Part 5, CPU KV offloading**: the c=338 working set (811 GB) fits in GPU plus host RAM, a resumed turn becomes a 0.1 s PCIe copy instead of a 2.9 s recompute, and vLLM v0.28.0 already ships the native connector (`kv_offloading_size` is just unset). Likely the largest single lever on this workload, and likely to remove much of admission control's value, which the proposal says plainly. Three arms to measure it.

**Part 6, mixed chat and agentic**: anonymous chat KV is invisible to the port's fit view (`kvUsageCorrection` has never been on), all chat shares one flow that is gated as NEW behind agentic resumes, and session-bearing chat wins admission then gets paused first for no gain. Fix path: a separate priority band for chat, `kvUsageCorrection: true`, a general load scorer in the profile, plus Part 1's aging. One mixed-traffic cell family to quantify each gap.

**Part 7, session-level metrics under an SLO**: request-level TTFT percentiles hide who pays under overload. llm-d's default makes every request slow; the port makes most turns fast and holds a few sessions at the door for minutes (at 84 sessions per pod: TTFT p50 101 s and no 300 s waits, vs p50 4 s and 188 waits over 300 s). Three metrics to replace the percentiles: goodput within SLO (computable now), session SLO attainment, and the per-session progress distribution (both need a session id in the inference-perf per-request report, a ten-line fix). Capacity should then be stated as the largest sessions per pod at which session attainment meets a target.

`proposal/ADMISSION-ORDERING.md` - the question underneath Parts 1, 3 and 8: when capacity frees, which waiting session should get it? It argued for replacing the smallest-footprint tie-break, then records that the age-only cell tested precisely that and lost to plain origin-only (1461 vs 1693 tok/s, strict attainment 0.39 vs 0.70), because oldest-first is largest-first, so each freed block of room resumes fewer sessions and the queue lengthens for everyone. What survives is the choice of variable: the wait-cost curve shows idle age predicts cached fraction with a cliff at 10 to 12 s, which is why acting on residency (Part 8's 8 s wait cap) beat reordering by proxies for it. Also compares llm-d's merged `turn-priority` strategy (PR #2116) with numbers read off its plots, and explains why its single-replica, 512 GiB CPU-offloaded, ungated setup does not transfer to a gated multi-pod pool.

**Part 8, residency-aware hold-or-move**: the wait-cost curve shows a paused session's prefix survives about 10 to 12 s on its pod at 32 sessions per pod, then is gone; origin-only's tail is sessions waiting for an origin that has already evicted them, most-room's cost is moving sessions whose prefix was still warm, and both 15 s policies acted on cold sessions. Proposal: decide hold-or-move from measured residency (llm-d's KV block index from vLLM KV events) and real free room, with a static 8 s origin-wait cap as the cheap first test.

## Data note: per-request reports are not in this repo

Every inference-perf cell in `07-inference-perf-weka/results/` and `08-weka-replicates/results/` is published complete except one file: `report/per_request_lifecycle_metrics.json` (50-123 MB each, 1.6 GB total, over GitHub's file limit; the size comes from per-token timing arrays that the v0.7.0 field filter cannot drop - see `INFERENCE-PERF-BUGS.md` issue 5). Every number in the write-ups is also derivable from the files that are here: the summary and per-stage lifecycle reports, `vllm-metrics.csv`, `programs-timeline.csv`, `router-health.csv`, and the committed `analysis.md` per run. Only re-running `analyze.py`, `pair.py` and `verdict.py` from scratch needs the raw per-request files; ask and we will share them.

## Start here

- `LESSONS.md` - what bit us and the rules that came out of it: which metrics must always be recorded, why the overnight driver died (and the cluster-side grace period that saved the results), why `--enable-prompt-tokens-details` was missing, and how to calibrate the pressure regime before spending hours.
- `08-cluster-changes.md` - every change made to shared cluster state, with revert instructions.
- `INFERENCE-PERF-BUGS.md` - the five inference-perf v0.7.0 bugs this campaign hit, written to be filed upstream as-is.

## Result summary

Setup succeeded on 2026-09-15. The original router is live in `tr` mode with all 4 vLLM backends, real per-backend KV capacity (2,237,040 tokens each), working program tracking, sticky routing, load-balanced placement, profiling, and release. Details and the two upstream bugs found along the way (broken CLI flag handling, broken `/v1/models` proxy path) are in `03-verify/smoke-test-results.md`; raw output in `03-verify/smoke-test-output.txt`.

Access from a laptop:

```
kubectl port-forward svc/thunderagent-router -n llm-d-program-aware-scheduling 18300:8300
curl http://localhost:18300/health
```

Send requests exactly like the paper describes: OpenAI chat completions with `"program_id": "<session>"` in the body (or an `X-Session-ID` header).

## How to tear down

```
kubectl delete -f 02-deploy/
```

The vLLM backends and the llm-d EPP are untouched.

## What this setup enables next

With the router live you can replay an agentic workload (e.g. the weka trace via inference-perf, sending `program_id` per session) through:

- `thunderagent-router:8300` (original paper router, tr mode)
- the same router restarted with `--router default` (pure proxy baseline)
- the existing llm-d gateway (Go port)

and compare prefix-cache hit rate, prefill tokens, and latency, which is the paper's headline claim (1.5-3.6x throughput from program-aware scheduling).
