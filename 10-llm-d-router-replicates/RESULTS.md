# Step 10 results: the step 08 protocol through the llm-d-router EPP

Two runs: `results/rep-20260917-173839-c128-t1900` (client timeout 1900 s, above the forced-admission backstop) and `results/rep-20260917-221857-c128-t600` (client timeout 600 s, step 08's client). Run 1 first.

## Run 1: client timeout 1900 s

Run `results/rep-20260917-173839-c128-t1900`: c=128, 45 minutes per cell, three lanes (one vLLM pod each), both arms per lane, prefix cache reset and a fresh EPP between arms, arm order alternated across lanes. Image `thunder-agent-v3` (llm-d-router commit `ae371354`). All six cells completed with complete reports. Figure: `results/rep-20260917-173839-c128-t1900/replicates.png`.

## Headline

| metric | epp-sticky | epp-thunder | ratio | step 08 py default | step 08 py tr-decay |
|---|---|---|---|---|---|
| output throughput (tok/s) | 227 (221-236) | 351 (327-367) | 1.54x | 221 | 469 (464-476) |
| requests completed | 979 | 1398 | 1.43x | 1059 | 1994 |
| hit rate, steady state (after 10 min) | 0.003 | 0.489 (0.482-0.502) | 173x | 0.008 | 0.685 |
| TTFT p50 (s) | 49.4 | 4.0 | 0.08x | 52.7 | 3.0 |
| TTFT p90 (s) | 113.5 | 22.0 | 0.19x | 92.5 | 18.0 |
| requests with zero cache hit | 0.86 | 0.38 | | 0.88 | 0.36 |
| errors (client timeout) | 0 | 5 to 6 per cell at 1900 s | | 17 at 600 s | 47 at 600 s |

Three findings:

1. **The EPP path is free.** `epp-sticky` reproduces the Python proxy arm on every metric: 227 vs 221 tok/s, steady-state hit rate near zero, TTFT p50 49 vs 53 s, the same in-flight load (28 vs 30) and the same KV usage (0.92 vs 0.91). Envoy, ext_proc and the EPP add nothing measurable at this load.
2. **Under equal load the port reproduces upstream.** The time series (`results/rep-20260917-173839-c128-t1900/timeseries.png`, script `plot_timeseries.py`) show the Python tr-decay lanes running their KV cache as full as the EPP lanes for the first 30 minutes. Restricted to minutes 10 to 30, where all four arms carry the same in-flight load, the two tr arms are within 0.02 of each other on hit rate and within 10 percent on throughput:

   | arm, minutes 10 to 30 | hit rate | KV | in flight | tok/s | ratio over its proxy |
   |---|---|---|---|---|---|
   | py default | 0.013 | 0.96 | 33.0 | 210 | |
   | py tr-decay | 0.571 | 0.92 | 35.2 | 433 | 2.06x |
   | epp-sticky | 0.004 | 0.96 | 31.6 | 214 | |
   | epp-thunder | 0.550 | 0.94 | 32.7 | 393 | 1.84x |

3. **The whole-window gap is a client-timeout artifact in step 08, not a difference in the schedulers.** From minute 30 the Python tr-decay lanes drop to 25 in flight, their KV empties to 0.67 and their hit rate climbs to 0.81 (619 tok/s in that window), while the EPP lanes stay at 28 in flight, KV 0.94, hit rate 0.42. The cause is in the load generator's logs. inference-perf starts all 128 sessions at minute 0 and starts a new one only when a session ends; in 45 minutes no weka session ends naturally, a session ends when one of its requests fails and its remaining turns are skipped ("predecessor failed"). Step 08 ran with `request_timeout: 600`; step 10 with 1900. The counts line up exactly:

   | arm | client timeout | requests failed per cell | downstream turns skipped per cell | sessions ended (new ones started) |
   |---|---|---|---|---|
   | py tr-decay (step 08) | 600 s | 45 to 50, all at 600 s, from minute 10 on | 2126 to 2471 | 43 to 52 |
   | py default (step 08) | 600 s | 15 to 20 | 572 to 829 | 14 to 18 |
   | epp-thunder | 1900 s | 5 to 6, all at 1900 s | 118 to 278 | 8 to 12 |
   | epp-sticky | 1900 s | 0 | 0 | 0 to 5 |

   Under tr-decay the requests that wait longest are the largest sessions (proposal Part 1). With a 600 s client, those sessions were killed and their remaining turns, about 2300 per cell, left the workload; the pool got lighter and hotter, and the arm's tail throughput and hit rate rose. With a 1900 s client the EPP kept those sessions, force-admitted them at 1800 s (8 to 11 per cell) and paid their cold prefills. Step 08's 2.12x was therefore measured on a workload the client trimmed in tr-decay's favor; step 10's 1.54x was measured on the full workload. Neither number is comparable to the other as they stand. The step 08 write-up recorded the errors as "the mechanism working" but did not account for the skipped successors; an addendum now does.

Pre-registered expectations: `epp-sticky` near 221 tok/s, met. `epp-thunder` near 469 tok/s, not met on the whole window, but the target itself was inflated by the confound above; under equal load the port is at 91 percent of upstream's throughput and the same hit rate.

## What remains unexplained

About 10 percent of throughput under equal load (393 vs 433 tok/s at 2 to 3 fewer requests in flight), and the tail behavior once the largest sessions are force-admitted. Candidates, in order: the size estimator (about 7 bytes per token here against upstream's 5 chars per token, so the port under-sizes programs), the ext_proc round trip per turn, and event-driven admission versus upstream's 5 s tick. None of these can be separated from the timeout confound until both routers have been run with the same client patience.

## Tail behavior

Each thunder cell had 8 to 11 forced admissions (heads that waited the full 1800 s) and 5 to 6 requests that exceeded the 1900 s client timeout after being force-admitted. That is upstream's starvation tail from proposal Part 1, reproduced through the EPP and now measured with a client timeout that no longer hides it. Only 2 to 4 holds per cell were new sessions; the queue was almost entirely paused sessions waiting to resume (mean queue 25 to 34 requests, growing to 40 to 60 by the end as the backlog of large sessions accumulated).

## Per-cell regime

| cell | in-flight mean | KV mean | preemptions | sessions | paused mean | marked mean | holds | pauses | forced |
|---|---|---|---|---|---|---|---|---|---|
| py default r1/r2/r3 | 29.9 / 31.0 / 28.9 | 0.93 / 0.91 / 0.90 | 8 / 11 / 2 | 68 / 73 / 65 | 0 | - | - | - | - |
| py tr-decay r1/r2/r3 | 26.9 / 25.8 / 26.7 | 0.70 / 0.68 / 0.71 | 3 / 0 / 2 | 109 / 103 / 91 | 35 / 37 / 31 | - | - | ~943 (r2) | - |
| epp-sticky r1/r2/r3 | 28.0 / 27.5 / 28.0 | 0.92 / 0.92 / 0.91 | 6 / 5 / 12 | - | 0 | 0 | 0 | 0 | 0 |
| epp-thunder r1/r2/r3 | 29.8 / 27.3 / 27.8 | 0.89 / 0.89 / 0.88 | 0 / 3 / 1 | 60 / 63 / 62 | 21 / 27 / 23 | 21 / 20 / 21 | 654 / 615 / 674 | 966 / 938 / 1009 | 10 / 8 / 11 |

In-flight and KV are means after the first 60 s. "Sessions" is the number of distinct programs the router saw. The EPP arm had a queue-wait mean of 3.6 to 13.6 s per cell.

## What is not in this run

- No per-session progress comparison: the EPP state dump lists no program ids, and inference-perf's report carries no session id (bug 2 in `INFERENCE-PERF-BUGS.md`).
- No hold-duration histogram: the prober records the flow-control histogram sum and count only. The distribution can be reconstructed from the per-request latencies if needed.

## Caveat on the offered load (2026-09-18)

All cells in steps 07 to 10 ran inference-perf v0.7.0, in which an event parked on its predecessors keeps its worker permit (see `INFERENCE-PERF-BUGS.md`, issue 4 root cause). Only 51 to 62 of the 128 dispatched sessions issued a first request in the 1900 s cells and 68 to 97 in the 600 s cells, equally for both arms, so "c=128" here means about 55 to 65 concurrently active sessions and a per-pod oversubscription closer to 1.6x than 3.5x. Arm comparisons within a run are unaffected; absolute numbers should be quoted with the active-session count. Step 12 must use an image built from the fix.

## Run 2: step 08's client (600 s), `results/rep-20260917-221857-c128-t600`

Same lanes, same protocol, `request_timeout: 600` so each arm faces exactly what its step 08 twin faced, including the client killing its longest-held requests and dropping those sessions' remaining turns. Time series: `results/rep-20260917-221857-c128-t600/timeseries.png`.

| metric | epp-sticky | epp-thunder | ratio | py default (step 08) | py tr-decay (step 08) |
|---|---|---|---|---|---|
| output throughput (tok/s) | 225 (215-230) | 405 (375-434) | 1.80x | 221 | 469 (2.12x) |
| requests completed | 1075 | 1706 | 1.59x | 1059 | 1994 |
| hit rate, steady state | 0.010 | 0.483 (0.453-0.503) | | 0.008 | 0.685 |
| TTFT p50 / p90 (s) | 48.5 / 80.2 | 3.3 / 17.9 | | 52.7 / 92.5 | 3.0 / 18.0 |
| client timeouts per cell | 18 | 39 | | 17 | 47 |
| turns dropped per cell | 896 | 1900 | | 711 | 2285 |
| sessions started per cell | 148 | 176 | | 147 | 178 |
| forced admissions | 0 | 0 | | | |

With the same client the session churn matches (176 vs 178 sessions, 1900 vs 2285 dropped turns), the sticky arm again equals the proxy, and the port reaches 1.80x against upstream's 2.12x, with the same TTFT. All six arm variants over equal windows, mean of three replicates:

| arm | timeouts | dropped turns | hit rate 10-30 | tok/s 10-30 | in flight 10-30 | hit rate 30-45 | tok/s 30-45 | in flight 30-45 | KV 30-45 |
|---|---|---|---|---|---|---|---|---|---|
| py default (600) | 17 | 711 | 0.013 | 210 | 33.0 | 0.002 | 176 | 29.9 | 0.96 |
| py tr-decay (600) | 47 | 2285 | 0.571 | 433 | 35.2 | 0.813 | 619 | 24.8 | 0.67 |
| epp-sticky (600) | 18 | 896 | 0.014 | 209 | 33.2 | 0.006 | 171 | 31.1 | 0.96 |
| epp-thunder (600) | 39 | 1900 | 0.482 | 397 | 36.8 | 0.507 | 365 | 32.7 | 0.95 |
| epp-sticky (1900) | 0 | 0 | 0.004 | 214 | 31.6 | 0.002 | 208 | 27.5 | 0.96 |
| epp-thunder (1900) | 6 | 188 | 0.550 | 393 | 32.7 | 0.423 | 288 | 28.1 | 0.94 |

The remaining difference is confined to the tail and is now unambiguous: with identical kills, the Python router keeps 25 requests in the engine after minute 30 while the port keeps 33; the Python engine's KV empties to 0.67 and its hit rate climbs to 0.81; the port's stays at 0.95 and 0.51.

### Why upstream runs the engine lighter: phantom REASONING programs

The step 08 prober recorded the router's own REASONING count next to vLLM's running count. In every Python cell the router's count climbs while the engine's does not:

| cell | router REASONING / vLLM running, per 5-minute bucket |
|---|---|
| py tr-decay r1 | 33/27, 44/38, 46/36, 52/33, 57/35, 64/37, 67/29, 73/25, 83/20 |
| py tr-decay r2 | 31/24, 46/39, 48/38, 55/38, 57/35, 63/33, 65/31, 71/23, 79/20 |
| py tr-decay r3 | 35/28, 47/39, 47/37, 52/35, 57/34, 62/32, 64/33, 71/25, 76/17 |
| py default r1 | 33/28, 45/37, 48/34, 52/32, 56/33, 57/30, 59/30, 61/31, 63/29 |

By the end the tr-decay router believes 76 to 83 programs are on the GPU when 17 to 20 are. The cause is in `ThunderAgent/scheduler/vllm_request_processor.py:205-210`: `on_usage`, which is the only place a program returns to ACTING, runs in a `finally` block guarded by `total_tokens is not None`. A stream that ends without a usage chunk (the client disconnected at its timeout, or the proxy failed) never finalizes, and the code comment says so. A program stuck in REASONING counts in full in both capacity views, is never decayed (decay applies to ACTING only), is never paused (the sweep only marks REASONING programs, and the mark matures on a response that never comes), and is never evicted (upstream has no TTL). Each client kill under tr-decay therefore converts a large held session into a permanent phantom occupant of the router's capacity model. As phantoms accumulate, the router admits fewer live programs, the engine runs at 20 to 25 requests instead of 33, its KV empties, the survivors' prefixes stop being evicted, and the arm's hit rate and per-token throughput rise. The default arm accumulates phantoms too (63 against 29 running at the end) but has no gate for them to act on.

The port has no phantoms: when the client disconnects, envoy cancels the ext_proc stream, the director runs `ResponseBody` with end of stream for every request that picked a pod, the in-flight estimate is removed and the program returns to idle, where it decays, is paused and is eventually evicted. Step 10 measured that directly: EPP in-flight tokens returned to zero at every idle point, and the REASONING bypass never applied to a dead session.

### Conclusions

1. `epp-sticky` equals the Python proxy under both clients. The EPP path is free.
2. Under the same client, the port delivers 1.80x where upstream delivered 2.12x, with the same TTFT, the same hit rate in the loaded phase (0.48 to 0.55 against 0.57), the same session churn and the same pause cadence.
3. The difference is not a scheduling deviation in the port. It is upstream's phantom REASONING accounting after client-abandoned requests, triggered by the 600 s client in step 08, throttling the engine into a lighter, hotter regime in the last third of each run. The port handles abandoned requests correctly, so it does not get that accidental benefit.
4. Step 08's 2.12x and 0.685 therefore stand as measured but describe upstream with two artifacts stacked: a client that trimmed the workload in tr-decay's favor, and a router that kept dead sessions on its books. Under a patient client the port's 1.54x, and under step 08's client its 1.80x, are the numbers without those artifacts.
5. The accident points at a real tuning question: the engine ran better with fewer resident programs. Deliberately admitting less (a `utilThreshold` below 1.0, which upstream does not have) may beat the faithful configuration on this workload.

## Next step (step 11)

A `utilThreshold` sweep on the port, not a rerun of upstream: `epp-thunder` at 1.0 (measured), 0.8 and 0.6, three lanes each, 45 minutes, client timeout 1900 s so the workload is untrimmed and the result is about the scheduler. Prediction from the phantom episode: 0.8 or 0.6 lowers in-flight toward 25, empties KV toward 0.7 and lifts the steady-state hit rate toward 0.7 with higher throughput; if throughput falls instead, the tail regime in step 08 was a coincidence of which sessions got killed rather than a property of lighter occupancy. The admission-cadence knob stays available as a later arm.

The three lane EPPs are left running, idle, for the follow-ups (`teardown-lanes.sh` removes them).
