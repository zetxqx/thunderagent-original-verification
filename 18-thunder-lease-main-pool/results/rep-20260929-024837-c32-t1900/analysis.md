# Step 18: lease thunder-agent on the minimal ledger, single vLLM pod, c=32

Run `rep-20260929-024837-c32-t1900`, 2026-09-29, one cell per lease. The pool half of step 18 is `../rep-20260929-040322-c128-t1900`; the step's question, pass criteria and pool readings are in `../../README.md`.

## What ran

- Build: llm-d-router `thunder-agent-lease-main` at `1a98a6c5` (draft PR #3076), image `thunder-agent-lease-1a98a6c5`. Gate logic is step 17's; the ledger underneath is the minimal ledger of #2968 and #3052.
- Setup: step 10's lane protocol. One EPP (`thunder-lane-a-epp`) pinned to one vLLM pod (`program-aware-vllm-decode-9c9b54cb6-dk9ld`), a fresh EPP per cell, both cells on the same pod.
- Load: 32 sessions (the pool's per-pod load at c=128), `inference-perf:session-id-v1`, 30 min window (10 min warm-up), 1900 s client timeout, base seed 20260915.
- Arm config: five keys, `capacityTokens` 2237040, `evictionTtlSeconds` 3600, `utilThreshold` 1.0, `headWaitStarvationMs` 1800000, and `idleLeaseSeconds` 30 or 10 (checked in each cell's `epp-configmap.yaml`).

| cell | `idleLeaseSeconds` | EPP pod | time (PDT) |
|---|---|---|---|
| `epp-thunder-lease-main-r1` | 30 | `thunder-lane-a-epp-65cf7cf4cb-67n6t` | 02:50 to 03:25 |
| `epp-thunder-lease-main10-r1` | 10 | `thunder-lane-a-epp-685f4fbc64-dl52x` | 03:28 to 04:03 |

Both cells completed, not preempted, prober saw DONE, no ERROR line in either EPP log (checked by `"severity_text"`).

## Results

| metric | lease 30 s | lease 10 s |
|---|---|---|
| output throughput (tok/s) | 375 | 398 |
| requests completed | 932 | 978 |
| request errors | 0 | 0 |
| turns not issued at stage end (inference-perf dropped_requests) | 0 | 0 |
| sessions ended in window / failed | 10 / 0 | 8 / 0 |
| hit rate, whole window | 0.522 | 0.578 |
| hit rate, warm-up (first 10 min) | 0.811 | 0.803 |
| hit rate, steady state | 0.211 | 0.376 |
| requests with zero cache hit | 0.42 | 0.39 |
| prefill tokens computed (M) | 26.2 | 24.8 |
| prompt tokens per request, mean (k) | 59.0 | 60.2 |
| TTFT p50 / p90 / p99 (s) | 1.8 / 17.5 / 98.3 | 1.3 / 16.4 / 119.6 |
| E2E latency p50 / p90 / p99 (s) | 33.3 / 147.2 / 490.0 | 30.4 / 139.1 / 433.4 |
| TPOT p50 / p90 (ms) | 62 / 117 | 55 / 115 |
| ITL p50 / p90 (ms) | 64 / 127 | 59 / 123 |
| vLLM KV usage, mean steady / max | 0.86 / 1.00 | 0.88 / 1.00 |
| vLLM running, mean steady / max | 25 / 33 | 26 / 33 |
| vLLM waiting, mean steady / max | 1.9 / 19.0 | 1.8 / 21.0 |
| vLLM preemptions | 3 | 4 |
| EPP working set / capacity, mean steady | 0.99 | 0.99 |
| share of samples with working set over capacity | 0.11 | 0.18 |
| EPP sessions running / idle / paused, mean | 25 / 3 / 6 | 26 / 2 / 6 |
| EPP max sessions paused at once | 17 | 17 |
| EPP releases admitted / paused / new | 854 / 38 / 42 | 906 / 35 / 40 |
| EPP holds paused / new | 37 / 3 | 34 / 4 |
| EPP pauses / resumes | 55 / 38 | 52 / 35 |
| EPP forced admissions | 0 | 0 |
| EPP mean queue wait (s) | 2.1 | 2.8 |
| EPP max queue size | 6 | 8 |
| EPP CPU cores, mean / max | 1.01 / 6.93 | 1.02 / 8.02 |
| sessions in the steady-state population | 42 | 40 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.28 | 0.32 |
| session SLO attainment, strict / lenient | 0.50 / 0.55 | 0.55 / 0.65 |
| turns per session after warm-up, p10 / p50 / p90 | 2 / 9 / 18 | 3 / 9 / 24 |
| share of turns over the SLO | 0.059 | 0.039 |
| per-session worst TTFT, p90 (s) | 233 | 235 |
| sessions whose worst turn exceeded 60 s | 0.21 | 0.30 |

Time series: `../timeseries-single.png`. Raw EPP metrics: `../raw-metrics-epp-thunder-lease-main-r1.md`, `../raw-metrics-epp-thunder-lease-main10-r1.md`.

## Readings

1. **The gate works on one pod.** It engages in both cells (55 and 52 pauses, 40 and 38 holds). The ledger tracks the pod: 25 and 26 EPP running sessions against 25 and 26 vLLM running requests. No forced admissions, no request errors, no EPP error line. vLLM waiting averages about 2 in steady state, with peaks of 19 to 21.
2. **The working set is not always under capacity.** The ledger sits at 0.99 of capacity on average, but it is over capacity in 11 percent (lease 30 s) and 18 percent (lease 10 s) of samples.
3. **Lease 10 s beats lease 30 s on most metrics**, the same direction as on the pool: steady hit rate 0.376 against 0.211, throughput 398 against 375 tok/s, 1.4 M fewer prefill tokens, lower TTFT p50 and p90, strict session SLO attainment 0.55 against 0.50. TTFT p99 is worse (120 s against 98 s), and the per-session worst TTFT p90 is the same (235 s against 233 s).
4. **Hit rate collapses after warm-up in both cells.** It falls from 0.80 to 0.81 in the first 10 min to 0.21 and 0.38 in steady state, and about 40 percent of requests get no cache hit. The ledger says the pod is full (0.99) while the prefixes it counts as resident are being evicted. This matches the pool reading in the README: the ledger counts some sessions smaller than their real KV, likely because it assumes one in-flight request per session. With one pod, placement plays no part, so this cell points at the ledger and not at the pool's routing.
5. **This run says little about the lease model yet.** There is no earlier single-pod reference at c=32, and the same undercount applies here. The useful next step is to rerun these two cells after the ledger goes back to per-request in-flight accounting.

Caveats: one cell per lease, run back to back on the same pod (lease 30 s first), so order and pod state are not controlled for.

Note: at the end of a run, `run-replicates.sh` calls step 10's analyzer. That analyzer does not know the `thunder-lease*` arms, so it wrote an empty table and an empty plot (`replicates.png`, `replicates.pdf`). This file replaces the table, and the empty plot was deleted.
