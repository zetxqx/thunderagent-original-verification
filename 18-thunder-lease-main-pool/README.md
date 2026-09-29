# Step 18: the lease thunder-agent rebuilt on the minimal ledger, one pod and four pods

Question: does the lease gate still work, and give step 17's results, after it was rebuilt on the minimal ledger? And how do a 30 s and a 10 s lease compare, on one pod (where placement plays no part) and on the 4-pod pool?

The build is llm-d-router branch `thunder-agent-lease-main` at `1a98a6c5` (upstream draft PR [#3076](https://github.com/llm-d/llm-d-router/pull/3076)), image `thunder-agent-lease-1a98a6c5` (`sha256:f7f6c85d1ae5...`, `results/epp-image.txt`), pinned by the annotated tag of the same name on `zetxqx/llm-d-router`. Its gate logic is step 17's; what changed underneath is the ledger of [#2968](https://github.com/llm-d/llm-d-router/pull/2968) and [#3052](https://github.com/llm-d/llm-d-router/pull/3052): a `capacityTokens` fallback and an `evictionTtlSeconds` key, maintenance in the request hooks and at metrics scrape, one in-flight request per session, a fixed 4 bytes per token estimate, and renamed metrics (`sessions{state}`, `endpoint_working_set_tokens{endpoint}`, `endpoint_capacity_tokens{endpoint}`, class `admitted` instead of `reasoning`).

## What runs

Four cells, one per setup and lease, all with the fixed load generator (`inference-perf:session-id-v1`, the step 12 to 17 image), a 30 min window (10 min warm-up) and a 1900 s client timeout:

| cell | setup | `idleLeaseSeconds` |
|---|---|---|
| `epp-thunder-lease-main-r1` | single vLLM pod: step 10's lane protocol (one EPP pinned to one pod by label, `lane a`), c=32 | 30 |
| `epp-thunder-lease-main10-r1` | same | 10 |
| `epp-thunder-lease-main10-c128` | 4-pod pool: step 12's `run-pool.sh` on the main release, c=128 | 10 |
| `epp-thunder-lease-main-c128` | same | 30 |

- c=32 on one pod is the pool's per-pod load at c=128 (32 sessions per pod), so the two setups differ only in having one pod or four. This is not step 15's single-pod protocol (c=128 with the v0.7.0 generator, which started only about half the sessions); there is no earlier single-pod reference at this load.
- Lease 10 s sits at the replay's tool-call gap cap (`trace_idle_gap_cap_seconds: 10`); the step 17 tail analysis suggested a lease there could shorten the wait tail without losing as much hit rate as 5 s.
- Order: single pod lease 30 then 10, pool lease 10 then 30.
- Arm configs: `thunder-lease-main-plugins.yaml` and `thunder-lease-main10-plugins.yaml` in both `../12-llm-d-router-pool/` and `../10-llm-d-router-replicates/`, five keys (`capacityTokens` 2237040, `evictionTtlSeconds` 3600, `utilThreshold` 1.0, `idleLeaseSeconds`, `headWaitStarvationMs` 1800000); both load with the build's strict decoder (checked with its sample-config test before the run).
- The main release was saved before this step (`results/main-release-before.yaml`, revision 94, image `thunder-agent-v7`, identical to step 17's saved state) and is restored afterwards.

Tooling changes, shared with earlier steps (earlier results unchanged): both probers read the renamed metrics as a fallback after the old names; `run-replicates.sh` checks `thunder-lease*` arms (flow control, the arm's image, the arm's lease in the live ConfigMap); both drivers' live summaries read the renamed session gauge.

## Pass criteria (written before the run)

Correctness, every cell: the gate engages (pauses and holds above 0); EPP running sessions track vLLM running requests; vLLM waiting stays near 0 in steady state; no error in the EPP log other than requests cancelled at stage end (checked by `"severity_text"`, see the step 17 correction); forced admissions and request errors at 0 to 1 per cell; the working set stays at or below capacity.

Consistency with step 17 (pool, lease 30 s): throughput, steady-state hit rate and TTFT p99 inside or near step 17's three-cell range (1871-2018 tok/s, 0.778-0.849, 220-279 s).

Predictions: on the pool, lease 10 s lands between step 17's 30 s and 5 s leases on hit rate, with a shorter TTFT p99 than 30 s. On one pod, the two leases differ in the same direction.

## Files

- `deploy-lane.sh [arm] [image]`, `teardown-lane.sh`: the single-pod lane.
- `smoke-test.sh [commit]`: 22 checks on the lane (build and config, the renamed metric set, scraped capacity, session tracking, class accounting, EPP log by `"severity_text"`).
- `run-all.sh`: the four cells in order, then the restore and the analysis, with kubectl and helm pinned to bobbm.
- `analyze.py`: `analysis.md` (single-pod and pool tables), `raw-metrics-<cell>.md`, `timeseries-single.png`, `timeseries-pool.png`.

## Smoke test (2026-09-29)

22 checks pass on the lane (`results/smoke-test-output.txt`): `llm_d_epp_info` reports commit `1a98a6c5`; the live ConfigMap has `idleLeaseSeconds: 30`; the renamed metric set is exported and the old names are gone; the lane pod reports its scraped capacity (2,237,040 tokens); three turns answered; two sessions tracked, none running or paused after the turns; releases new +2 and admitted +1; no holds or pauses; no ERROR line in the EPP log. The first run (`results/smoke-test-output-first-run.txt`) failed two checks by the test's own design: it looked for `holds_total` and `releases_total` before any traffic, but labeled counters appear only once incremented. Those two checks were removed (step 7 covers releases, the run covers holds) and the test was rerun on a fresh EPP.

## Results (2026-09-29, one cell each)

Single-pod run `results/rep-20260929-024837-c32-t1900` (lane on pod `dk9ld`, 02:48 to 04:03 PDT), pool run `results/rep-20260929-040322-c128-t1900` (04:03 to 05:33). All four cells complete, not preempted, 338 corpus traces, reports complete, no ERROR line in any EPP log (checked by `"severity_text"`). The lane was removed and the main release restored to revision 94's manifest at 05:33. Full tables in `results/analysis.md`, series in `timeseries-single.png` and `timeseries-pool.png`.

**Single vLLM pod, c=32**

| metric | lease 30 s | lease 10 s |
|---|---|---|
| output throughput (tok/s) | 375 | 398 |
| steady-state hit rate | 0.211 | 0.376 |
| prefill tokens computed (M) | 26.2 | 24.8 |
| TTFT p50 / p90 / p99 (s) | 1.8 / 17.5 / 98 | 1.3 / 16.4 / 120 |
| vLLM running / waiting, mean steady | 25 / 1.9 | 26 / 1.8 |
| pauses / holds (paused + new) | 55 / 40 | 52 / 38 |
| strict session SLO attainment | 0.50 | 0.55 |
| per-session worst TTFT, p90 (s) | 233 | 235 |
| forced admissions / request errors | 0 / 0 | 0 / 0 |

**4-pod pool, c=128**

| metric | lease 30 s | lease 10 s | step 17 lease 30 s (3 cells) | step 17 lease 5 s (3 cells) |
|---|---|---|---|---|
| output throughput (tok/s) | **1477** | **1647** | 1931 (1871-2018) | 1859 (1839-1874) |
| steady-state hit rate | **0.539** | **0.621** | 0.819 (0.778-0.849) | 0.749 (0.724-0.766) |
| prefill tokens computed (M) | 97.6 | 84.7 | 56.0 (51.3-62.0) | 65.3 (63.3-69.3) |
| TTFT p50 / p90 / p99 (s) | 1.5 / 18.4 / 125 | 0.7 / 14.2 / 129 | 0.5 / 7.3 / 242 | 0.6 / 8.6 / 139 |
| vLLM running / waiting, mean steady | 80 / 4.9 | 76 / 3.1 | 65 / 0.9 | 71 / 1.1 |
| pod steady hit rate, min-max over pods | 0.18-0.91 | 0.30-0.89 | 0.71-0.92 | 0.69-0.80 |
| share of samples with working set over capacity | 0.01 | 0.05 | 0.16 | 0.12 |
| pauses / holds (paused + new) | 169 / 110 | 184 / 116 | 316 / 231 | 464 / 349 |
| strict session SLO attainment | 0.61 | 0.62 | 0.67 | 0.61 |
| forced admissions / request errors | 0 / 1 | 0 / 1 | 0-1 / 0 | 0-2 / 0-1 |

Against the pass criteria:

- Correctness: the gate engages in every cell; the ledger tracks running requests (pool lease 30 s: 79.5 EPP running sessions against 80 vLLM running requests); no forced admissions, at most one request error per cell, no EPP error line; the ledger's working set stays at or below capacity. **vLLM waiting is not near 0 on the pool** (3.1 and 4.9 against step 16 and 17's 0.7 to 1.2).
- **Consistency with step 17: fails.** Pool lease 30 s has throughput 1477 against 1871-2018, hit rate 0.539 against 0.778-0.849, and 97.6 M prefill tokens against 51.3-62.0.
- Predictions: lease 10 s beats lease 30 s on hit rate in both setups (0.376 against 0.211 on one pod, 0.621 against 0.539 on the pool), as predicted, but both are far below step 17.

Readings:

1. **The rebuild regressed, and the gate logic is not the suspect.** The gate is step 17's; what changed is the ledger underneath. Per pod, the ledger says every pool pod is full (steady working set 0.97 to 1.00 of capacity) while two pods run about 30 percent more requests than the other two and their hit rate falls to 0.18 to 0.45. The ledger counts some sessions smaller than their real KV, so the gate admits too many onto those pods, their prefixes are evicted, and the extra prefill slows everything (more requests running at once, more waiting).
2. **Rejected: the fixed 4 bytes per token estimate.** The rebuilt ledger no longer learns the bytes-per-token ratio. Measured on the pool lease 10 s cell (queued request bytes from the EPP's per-session `flow_control_queue_bytes` against the same request's prompt tokens, clocks aligned by the EPP log), the real ratio is 3.98 (p10 3.95, p90 4.11): the replay synthesizes text at about 4 bytes per token, so the fixed estimate is right for this workload.
3. **Likely cause: one in-flight request per session.** The rebuilt ledger (#2968) assumes a session has at most one request in flight: a new request overwrites the in-flight estimate, and any completion clears it and sets the session's size to that request's total. The weka traces have sessions with overlapping requests (about 6 to 8 percent of requests start while another request of the same session runs). When a small request finishes while a larger one of the same session still runs, the session's size drops to the small total until the large one ends. From the per-request reports, that would undercount **8.4 percent (lease 10 s) and 9.6 percent (lease 30 s) of the pool's KV capacity on average**, concentrated in about 20 sessions, so on whichever pods they sit. The step 17 build summed per-request estimates, so it would not have undercounted these same events (7.5 to 9.3 percent of capacity in its own cells). This fits every symptom above but is not yet proven; the test is to restore per-request in-flight accounting in the ledger and rerun. **Confirmed in step 19**: with per-turn accounting (`44544c04`) the same arm reaches 2042 tok/s and hit rate 0.844 (`../19-thunder-lease-fix-pool/README.md`).
4. **Single pod.** The two leases rank the same way as on the pool, but there is no earlier single-pod reference at c=32, and the same undercount applies to the one pod, so these cells say little about the lease model until the ledger is fixed.

Caveats: one cell per setup and lease; the pool comparison is against step 17 cells from the day before on the same four pods; the undercount figure is computed from request timings and sizes, not measured inside the EPP.
