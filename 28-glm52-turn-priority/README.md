# Step 28: llm-d-router v1.0.0 turn-priority on GLM-5.2-NVFP4, vLLM TP=8 + 820 GiB CPU offload, 8x B200

Status: done (2026-10-19). All four points valid, no retries, no client errors.

## Question

llm-d-router v1.0.0 ships flow control with a program-aware fairness policy whose `turn-priority` strategy (upstream [#2116](https://github.com/llm-d/llm-d-router/pull/2116)) dispatches the deepest session first when the pool is saturated, to keep prefixes that are already resident. How does it compare, out of the box, with no router and with llm-d-thunder-agent-simplified on the same GLM-5.2 server and workload as step 25?

## Setup

- **Servers:** step 25's four GLM-5.2-NVFP4 deployments on cluster a4-pr (`glm52-tp8`, `-b`, `-c`, `-d`): vLLM v0.31.0, TP=8 on 8 B200, MTP 3, `--kv-offloading-size 820` (CPU tier 18.17M tokens), `MAX_NUM_SEQS` 64, GPU KV about 1.57M tokens. Unchanged from step 25 except the node of a, b and c: step 27's DEP=8 servers hold their step 25 nodes, so they moved to free B200 nodes (same machine type, `a4-highgpu-8g`). Scaled from 0 to 1 for this step and back to 0 after it.
- **Router:** llm-d-router v1.0.0, image `ghcr.io/llm-d/llm-d-router-endpoint-picker:v1.0.0`, chart from the v1.0.0 tag (`b200/render-epp.sh`), one EPP and envoy per server (releases `agentx-epp-t{a,b,c,d}`), endpoints from a file as in step 25. Plugin config [`b200/turn-priority-plugins.yaml`](b200/turn-priority-plugins.yaml):
  - `agent-identity` reads `X-Session-ID`, so one session is one fairness flow;
  - `program-aware-fairness` with `strategy: turn-priority` and its defaults: score = turns already dispatched + 0.05 x head wait in seconds; a session idle for 120 s counts as turn one;
  - saturation: v1.0.0's default utilization detector, saturated when vLLM's waiting queue reaches 5 or KV cache usage reaches 0.8;
  - `defaultRequestTTL: 0s` (no request is shed while waiting; envoy ext_proc timeout 2400 s).
- **Client and method:** as step 25's 1-hour points: AgentX harness `agentx-v1.0.6`, dataset `semianalysis_cc_traces_weka_062126`, 60 min per point, `RESET=1` (both KV tiers emptied and the EPP restarted before every point, no server restart), one point per server, all four at once.
- **Grid:** c = 24, 32, 48, 64. Compared with step 25's no-router and llm-d-thunder-agent-simplified lease 10 s points at the same c (same servers, same `MAX_NUM_SEQS`, same reset method).
- **Smoke test first:** c = 4 for 2 minutes through one EPP, to check that requests flow and the EPP logs no errors.

## Expectations (written before the run)

1. With offload, vLLM's KV cache usage is above 0.8 most of the time at these concurrencies, so the default detector keeps the pool saturated and most requests pass through the router's queue; vLLM's own waiting queue stays short (near the detector's 5).
2. Turn-priority orders turns but does not limit how many sessions are active, so the working set still outgrows the GPU pool: the hit rate and throughput land between no router and llm-d-thunder-agent-simplified at c = 48 and 64, and close to no router at c = 24.
3. Deep sessions go first, so the median TTFT is below no router's from c = 32 on, while shallow and new sessions wait longer: a longer TTFT tail than no router, but no burst like the 1800 s forced admission (waits age at 0.05 turns per second instead).
4. Falsified if every metric is within about 5% of no router at all four points (the policy then rarely reorders anything).

## Results

Steady state (requests started after minute 5), 8 B200, `MAX_NUM_SEQS` 64, offload on. No-router and lease 10 s are step 25's `explore1h-direct` and `explore1h-thunder-gpu-l10` (same servers, same reset method). Report: [`b200/results/compare-step25/report/summary.md`](b200/results/compare-step25/report/summary.md); runs under `b200/results/turn-priority-v1/c<N>/`, log `b200/results/run-turn-priority.log`.

| c | arm | output tok/s/GPU | total tok/s/GPU | TTFT p50 s | TTFT p90 s | E2E p99 s | hit | vLLM waiting avg | router queue p90 s |
|---|---|---|---|---|---|---|---|---|---|
| 24 | no-router | 102 | 14.8k | 7.45 | 18.3 | 82 | 97.4% | 6.2 | |
| 24 | turn-priority | 102 | 14.5k | 7.46 | 19.9 | 86 | 97.3% | 2.9 | 10.0 |
| 24 | thunder-agent lease 10 s | 105 | 14.6k | 0.74 | 4.6 | 146 | 97.2% | 0.2 | |
| 32 | no-router | 94.0 | 14.3k | 21.8 | 37.3 | 97 | 97.4% | 15.5 | |
| 32 | turn-priority | 95.0 | 14.3k | 19.5 | 40.9 | 101 | 97.4% | 7.1 | 25.5 |
| 32 | thunder-agent lease 10 s | 108 | 14.5k | 0.74 | 7.8 | 198 | 96.9% | 0.2 | |
| 48 | no-router | 95.9 | 13.9k | 45.5 | 65.0 | 168 | 97.2% | 33.8 | |
| 48 | turn-priority | 96.3 | 13.9k | 43.9 | 79.1 | 136 | 97.2% | 15.5 | 47.9 |
| 48 | thunder-agent lease 10 s | 109 | 12.1k | 0.69 | 11.9 | 633 | 94.4% | 3.5 | |
| 64 | no-router | 97.5 | 12.9k | 79.4 | 108 | 184 | 96.2% | 58.6 | |
| 64 | turn-priority | 96.0 | 12.9k | 77.4 | 142 | 230 | 96.3% | 26.7 | > 60 |
| 64 | thunder-agent lease 10 s | 109 | 10.2k | 0.69 | 16.3 | 1060 | 91.0% | 7.3 | |

Router queue p90 is the EPP's flow-control queue duration (whole window); its top histogram bucket is 60 s, so c=64 only shows it is above that.

Against the expectations:

1. Confirmed in part: the pool is saturated most of the time and requests wait at the router, but vLLM's waiting queue still averages 3 to 27, far above the detector's 5 at c >= 32 (about half of no-router's).
2. Not confirmed: throughput and hit rate are within 2% of no-router at every c, not between no-router and thunder-agent. Turn-priority does not cap the active sessions, so the working set is the same as no-router's, and the 820 GiB CPU tier already gives no-router a 96 to 97% hit.
3. Half confirmed: the TTFT tail is longer than no-router's (p90 +9% to +31%), but the median is only 0 to 2.3 s lower: the wait moved from vLLM's queue to the router's, it did not shrink.
4. Met: every throughput and hit metric is within 5% of no-router. Out of the box (default weight, utilization detector, TTL 0), turn-priority does not help this workload; llm-d-thunder-agent-simplified lease 10 s gives 3% to 15% more output throughput and sub-second median TTFT at the same c, at the cost of a long E2E p99.

## Notes

- Step 25 pinned each server to the node with its checkpoint on local SSD. Step 27's DEP=8 servers held the nodes of a, b and c, so the first attempt waited 90 min for them (`b200/results/run-turn-priority-attempt1.log`); the script now moves a, b and c to free nodes.
- The c=24 client waited 85 min for CPU on node pool `pool-1` (full with other clients and EPPs), so c=24 ran after the other three instead of with them. Its server was idle and already reset in the meantime.
- Every EPP logs `parsing response: invalid character '#'` for most responses; the error only drops usage metrics (the request still completes in the director). Step 25's PR3 EPP logs the same.
