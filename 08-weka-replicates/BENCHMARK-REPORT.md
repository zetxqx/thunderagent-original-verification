# LLM Inference Benchmarking Report: ThunderAgent vs passthrough on one vLLM replica, Qwen3-Coder-30B-A3B-FP8, real Claude Code traffic
**Date:** 2026-09-17
**Author:** [fill in]

Data: `results/rep-20260917-031427-c128`. Longer write-up with figures: `REPORT.md`. Run index and history: `RESULTS.md`.

---

## 1. Executive Summary
* **Objective:** Measure what ThunderAgent's admission control adds on a single, over-subscribed vLLM pod, with real coding-agent sessions, when clients never tell the router that a session is finished. Compare it against the same router in passthrough mode. Run the same test three times to see how stable the result is.
* **Key Finding:** ThunderAgent gives **2.1x the output-token throughput** (469 vs 221 tokens/s), cuts the **median time to first token from 52.5 s to 3.0 s**, and lifts the steady-state prefix-cache hit rate from **0.008 to 0.685**. The three runs agree within 1.3% on throughput. The cost is the tail: **p99 TTFT is 1.9x worse** (223 s vs 119 s), because a few sessions are held at the router for minutes. The 2.1x is total work done by the pod. Part of it comes from ThunderAgent reaching more sessions in the 45 minutes. Looking only at sessions that both arms ran, each session got through about 1.3x as many turns under ThunderAgent. So an operator sees 2.1x; a single user sees about 1.3x.
* **Decision / Recommendation:** On this kind of traffic, admission control in front of vLLM is worth having. The 1800 s forced-admission limit and the resume order should be tuned before any latency-sensitive use, and the client timeout must be set above the router's hold limit. The upstream Python router also has two bugs that make it unfit for production as-is (section 7); the llm-d port is the path forward.

---

## 2. Setup & Environment
* **Hardware:** Per test lane, one vLLM pod using 2x NVIDIA H100 80GB (tensor parallel 2). Three lanes ran in parallel on three different nodes. Node type: GKE `a3-highgpu-4g`, spot. Each node has 4 H100s; the pod uses 2 of them.
* **Host:** 104 vCPU and 965 GiB RAM per node. CPU model not recorded. The vLLM pod is limited to 16 CPU cores and 128 GiB.
* **Software:** GKE, kubelet `v1.35.3-gke.1389002`, GPU driver channel `latest`. The exact driver and CUDA versions were not recorded; CUDA comes bundled in the vLLM image.
* **Serving Engine & Version:** `vllm/vllm-openai:v0.28.0`, official image, not modified.
* **Model Configuration:** `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8` (mixture of experts, 30B total, 3B active), TP=2, PP=1, `--max-model-len 262144`, FP8 weights, FP8 KV cache, `--gpu-memory-utilization 0.88`, chunked prefill and prefix caching on. KV cache pool: 139,815 blocks x 16 tokens = **2,237,040 tokens** per pod (about 102 GiB).
* **Router under test:** upstream ThunderAgent, commit `7ddc861`, Python, unmodified. One router per lane, one backend each.
* **Load generator:** `quay.io/inference-perf/inference-perf:v0.7.0`, official image, digest-pinned. 24 CPU cores requested.

---

## 3. Workload & Traffic
* **Input / Output Token Lengths:** Real, not fixed. Per request: prompt median 51k to 56k tokens, p90 77k to 100k, max about 200k. Output median 350 tokens, mean 557. About 100 prompt tokens per output token.
* **Traffic Pattern:** Replay of 338 recorded Claude Code sessions (public weka trace set). Each session is a multi-turn conversation. A turn is sent only after the previous turn's answer has arrived, plus the real think time from the recording, capped at 10 s. Sessions run in a closed loop: when one session finishes, the next one starts. No text is stored in the traces; the load generator rebuilds prompts from 64-token block ids, so cache reuse between turns is the same as in the real sessions.
* **Concurrency Levels Tested:** One level, configured as 128 sessions. Because of a bug in inference-perf v0.7.0 the real load was lower: 65 to 110 sessions ever sent a request, and 27 to 32 requests were in flight at the pod on average. Both arms had the same limit. See section 7.
* **Test Duration / Warm-up:** 45 minutes per cell. The first 10 minutes are warm-up: the KV pool is filling and the two arms behave the same. Steady-state numbers use minutes 10 to 45. Each arm was run 3 times (one run per lane, each on its own pod). Prefix cache reset and fresh router before every cell.

---

## 4. Test Arms (Variables Under Test)
* **Arm 0 (Baseline), "passthrough":** `--router default`. The router forwards every request to the pod at once. No capacity check, no holding. vLLM's own queue and cache eviction decide everything.
* **Arm 1, "ThunderAgent":** `--router tr --use-acting-token-decay`. The router tracks each session's token count. Every 5 s it compares the total of admitted sessions against the 2,237,040-token pool. When the total is too high it holds new and idle sessions inside the router; their next request does not reach the pod. When room frees it lets them in again. A session held for 1800 s is let in regardless. The decay flag makes an idle session's footprint shrink over time, which is needed because no client ever sends a release call.
* **Same in both arms:** router image, pod, workload, client settings, `--metrics --profile`, client request timeout 600 s, no release calls.

---

## 5. Key Metrics Tracked
* **TTFT (Time to First Token):** p50, p90, p99, in seconds. Values are large here because they include queueing in the pod (Arm 0) or holding in the router plus queueing (Arm 1).
* **ITL (Inter-Token Latency):** p50, p90, p99, in ms. Each request's mean ITL is taken first; the percentiles are over requests.
* **Throughput:** Output tokens per second over the whole 45-minute window; completed requests per second.
* **Cache:** Prefix-cache hit rate from the pod's own counters (hits divided by queries), steady state and whole window; share of requests that got zero cache hit.
* **Resource Usage:** Peak KV cache utilization from vLLM metrics. VRAM is not a useful metric here: vLLM reserves 88% of each GPU at start (70.4 GiB per GPU) in both arms, so it never changes. GPU compute utilization was not collected. CPU of the router, the pod and the load generator was sampled every 30 s.
* **Fairness:** Per-session progress on the sessions both arms touched; longest hold per session; count of 1800 s forced admissions.

---

## 6. Results

Mean over 3 runs, with the min to max range in brackets. TTFT in seconds, ITL in ms.

| Test Arm | Concurrency (configured / real in flight) | p50 TTFT (s) | p90 TTFT (s) | p99 TTFT (s) | p50 ITL (ms) | p99 ITL (ms) | Output Tokens/s | Requests/s | Steady hit rate | Peak KV |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Arm 0 (passthrough)** | 128 / 30 | 52.5 (45.9 to 58.0) | 98.4 (70.2 to 104.5) | 118.5 (79.3 to 122.2) | 139 (135 to 143) | 267 (254 to 277) | 221 (210 to 242) | 0.39 | 0.008 (0.007 to 0.009) | 100% |
| **Arm 1 (ThunderAgent)** | 128 / 28 | **3.0** (2.9 to 3.2) | **17.9** (17.4 to 19.1) | 222.6 (147.4 to 251.3) | **61** (60 to 65) | **238** (210 to 259) | **469** (464 to 476) | **0.74** | **0.685** (0.661 to 0.698) | 100% |
| ratio, Arm 1 vs Arm 0 | | 18x lower | 5.5x lower | **1.9x higher** | 2.3x lower | 1.1x lower | **2.12x** | 1.88x | 85x | same |

Per run:

| run | arm | requests ok | client timeouts | out tok/s | p50 TTFT (s) | p99 TTFT (s) | p50 ITL (ms) | steady hit rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| r1 | passthrough | 1035 | 15 | 211 | 58.0 | 122.2 | 143 | 0.009 |
| r1 | ThunderAgent | 2011 | 50 | 466 | 3.2 | 147.4 | 65 | 0.661 |
| r2 | passthrough | 1108 | 17 | 242 | 45.9 | 118.3 | 135 | 0.009 |
| r2 | ThunderAgent | 1993 | 45 | 464 | 2.9 | 251.3 | 61 | 0.698 |
| r3 | passthrough | 1033 | 20 | 210 | 54.3 | 79.3 | 139 | 0.007 |
| r3 | ThunderAgent | 1978 | 45 | 476 | 2.9 | 213.9 | 60 | 0.696 |

Other measured facts:

| | Arm 0 (passthrough) | Arm 1 (ThunderAgent) |
| :--- | :--- | :--- |
| requests with zero cache hit | 88% | 36% |
| vLLM waiting queue, mean | 17.7 | 1.2 |
| sessions admitted at once (mean) | all, 55 to 59 | 34 to 35 |
| tokens of admitted sessions vs pool | 1.7x the pool | 0.98x the pool |
| sessions held by the router at peak | 0 | 69 to 85 |
| sessions forced in after 1800 s | 0 | 16 to 18 per run |
| per-session progress on shared sessions | 1x | 1.12x to 1.54x, mean 1.3x |
| router CPU, median | 0.06 to 0.11 cores | 0.06 to 0.11 cores |

**Figure 1. The five headline metrics, one dot per run.** Bar is the mean, whisker is min to max. The p99 TTFT panel on the right is the one metric where ThunderAgent is worse and where its three runs spread widely.

![Throughput, steady-state hit rate and TTFT p50, p90, p99 for both arms, three runs each](results/rep-20260917-031427-c128/replicates.png)

**Figure 2. Why Arm 1 logs more client timeouts.** Left: share of requests the client gave up on after 600 s. Middle: end-to-end time of the successful requests, sorted; the median is 27 s under ThunderAgent and 100 s under passthrough. Right: how long the router held each session; 161 holds were longer than the client's 600 s patience, which matches the 140 timeouts.

![Client timeouts, successful request durations, and router hold durations](results/rep-20260917-031427-c128/errors.png)

---

## 7. Analysis
* **Primary Bottleneck:** KV cache capacity, not compute. The pod ran only 27 to 32 requests at a time against a `max_num_seqs` of 1024, but its KV pool was 100% full in every cell. Under Arm 0 the live sessions needed 1.7x the pool, so every new prefill evicted blocks that another live session was about to reuse. The steady-state hit rate fell to 0.008, and almost every turn was a full prefill of 50k or more tokens. Under Arm 1 the router kept the admitted set at 0.98x the pool. Those sessions kept their cache between turns, so the same pod did 2.1x the work.
* **Trade-offs:** Arm 1 improves throughput 2.12x, median TTFT 18x, and median ITL 2.3x (the pod is less overloaded, so decoding is faster too). It does this by moving the waiting from the pod's queue into the router. Most requests then wait seconds instead of a minute. But the waiting is no longer spread evenly. A few sessions wait minutes, and 16 to 18 per run wait the full 1800 s. That is why p99 TTFT is 1.9x worse and why p99 TTFT is the only metric where the three runs disagree widely. For a single session that both arms served, the gain is 1.3x, not 2.1x; the rest of the throughput gain comes from serving more sessions in the window (91 to 109 vs 65 to 73).
* **Anomalies / Failures:**
  * **Client timeouts.** 2.3% of Arm 1 requests and 1.6% of Arm 0 requests hit the client's 600 s timeout. They are not server errors. In Arm 1 they are requests held at the router for more than 600 s (161 such holds, 140 timeouts). The client's patience was set 3x shorter than the router's own 1800 s limit; that was a configuration mistake. Each timeout also ends its session and drops its remaining turns, so Arm 1 lost about 2100 to 2500 turns per run, mostly from the largest sessions. Restricted to minutes 10 to 30, before most timeouts, Arm 1 is 2.06x, not 2.12x.
  * **Router accounting bug (upstream).** A request that ends without a usage chunk, for example one the client abandoned, leaves its session marked as active forever in the router. By minute 45 the router believed 76 to 83 sessions were active while the pod ran 17 to 20. This throttled admissions late in each run, emptied the pod to about 40% KV, and pushed the survivors' hit rate to about 0.8. Part of Arm 1's late-window numbers is this artifact.
  * **Load generator bug.** inference-perf v0.7.0 holds a worker slot for every queued turn, so most configured sessions never start. Real load was 65 to 110 sessions, not 128. Both arms had the same limit, so the comparison holds, but the concurrency label does not. Fixed in commit `d5a7c8c` on `zetxqx/inference-perf`.
  * **One HTTP 500** in 9350 requests: a race between the router's pause sweep and an in-flight request. Recorded as an upstream issue.
  * **What was not tested:** a plain concurrency cap as a third arm, more than one concurrency level, and a client timeout above 1800 s. Step 10 later ran the llm-d port of the same policy with a 1900 s client and measured 1.54x.

---

## 8. Reproduce

```
./run-replicates.sh 128 3          # three lanes in parallel, about 1 h 40 min
python3 analyze.py results/<run>   # analysis.md and the two figures
```

Per cell the folder keeps the rendered client config, a manifest with pod UID and mode, the router log, 2 s time series from the pod and the router, CPU samples, and the inference-perf reports without prompt text.
