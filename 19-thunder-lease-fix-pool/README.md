# Step 19: the lease thunder-agent after the in-flight accounting fix

Question: step 18 found the lease gate rebuilt on the minimal ledger regressed against step 17 (pool lease 30 s: 1477 tok/s and hit rate 0.539 against 1871-2018 and 0.778-0.849), and traced it to the ledger keeping one in-flight estimate per session, which undercounts sessions with overlapping turns by about 8 to 10 percent of pool capacity. Does counting each in-flight turn fix it?

The build is llm-d-router branch `thunder-agent-lease-main` at `44544c04` (one fix commit on step 18's `1a98a6c5`; upstream draft PR [#3076](https://github.com/llm-d/llm-d-router/pull/3076)), image `thunder-agent-lease-44544c04` (`results/epp-image.txt`), pinned by the annotated tag of the same name on `zetxqx/llm-d-router`. The fix: PreRequest adds each turn's estimate to the session's in-flight tokens and stashes it on the request; ResponseBody removes only that turn's estimate; the gate sizes a session as its turns in flight plus the new one. Nothing else changes.

## What runs

One cell, `epp-thunder-lease-main-c128`: step 17 and 18's pool protocol through `../12-llm-d-router-pool/run-pool.sh` (one EPP over the four vLLM pods, prefix-cache reset and a fresh EPP, c=128, 30 min window with 10 min warm-up, client timeout 1900 s, bench image `inference-perf:session-id-v1`), arm `thunder-lease-main` (`idleLeaseSeconds` 30, the step 18 config). The main release was saved before the step (`results/main-release-before.yaml`, revision 97, identical to step 18's saved state) and is restored afterwards.

## Pass criteria (written before the run)

- Correctness, as in step 18: the gate engages; EPP running sessions track vLLM running requests; vLLM waiting near 0 in steady state (step 16 and 17: 0.7 to 1.2); no EPP error other than requests cancelled at stage end (checked by `"severity_text"`); forced admissions and request errors at 0 to 1; the working set at or below capacity.
- The fix works: throughput, steady-state hit rate and prefill tokens inside or near step 17's lease 30 s range (1871-2018 tok/s, 0.778-0.849, 51.3-62.0 M), and every pod's steady hit rate near step 17's per-pod range (0.68 to 0.96) rather than step 18's 0.18.

## Files

- `smoke-test.sh [image-tag]`: deploys the arm on the main release and runs 22 checks (build and config, metric set, scraped capacity on all four pods, session tracking, class accounting, EPP log by `"severity_text"`).
- `run-cells.sh <arm:cell-tag> ...`: the cells through `run-pool.sh`, then the restore and the analysis, with kubectl and helm pinned to bobbm.
- `analyze.py <run>`: `analysis.md` against step 18 (before the fix), step 17 and step 16, `raw-metrics-<cell>.md`, `timeseries.png`.

## Smoke test (2026-09-29)

All 22 checks pass (`results/smoke-test-output.txt`): `llm_d_epp_info` reports commit `44544c04`; the live ConfigMap has `idleLeaseSeconds: 30`; the metric set is as in step 18; all four pods report their scraped capacity (2,237,040 tokens); three turns answered; two sessions tracked, none running or paused after the turns; releases new +2 and admitted +1; no holds or pauses on an idle pool; no ERROR line in the EPP log.

## Result (2026-09-29, one cell)

Run `results/rep-20260929-084613-c128-t1900`, cell `epp-thunder-lease-main-c128` (08:47 to 09:33 PDT): complete, not preempted, 338 corpus traces, reports complete. The main release was restored to revision 97's manifest at 09:34. Full table in `analysis.md`, series in `timeseries.png`.

| metric | step 19, fixed accounting | step 18, before the fix | step 17 lease 30 s (3 cells) |
|---|---|---|---|
| output throughput (tok/s) | **2042** | 1477 | 1931 (1871-2018) |
| steady-state hit rate | **0.844** | 0.539 | 0.819 (0.778-0.849) |
| prefill tokens computed (M) | **52.6** | 97.6 | 56.0 (51.3-62.0) |
| TTFT p50 / p90 / p99 (s) | 0.5 / 5.8 / 219 | 1.5 / 18.4 / 125 | 0.5 / 7.3 / 242 |
| pod steady hit rate, min-max over pods | **0.77-0.93** | 0.18-0.91 | 0.71-0.92 |
| vLLM running / waiting, mean steady | 64 / 0.6 | 80 / 4.9 | 65 / 0.9 |
| pauses / holds (paused + new) | 384 / 281 | 169 / 110 | 316 / 231 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 1.87 | 1.40 | 1.72 (1.60-1.79) |
| strict session SLO attainment | 0.64 | 0.61 | 0.67 (0.61-0.70) |
| per-session worst TTFT, p90 (s) | 420 | 398 | 353 (291-435) |
| forced admissions / request errors | 1 / 0 | 0 / 1 | 0-1 / 0 |

Against the pass criteria:

- Correctness: all hold. The gate engages (384 pauses, 281 holds); the ledger tracks running requests (61.2 EPP running sessions against 64 vLLM running requests; a session with parallel turns is one session but several requests); vLLM waiting 0.6; the only EPP ERROR lines are 3 requests still held in the gate when the stage ended (2008 s after the bench pod started); one forced admission, no request errors; the working set stays at or below capacity (steady per-pod means 0.92 to 1.00).
- **The fix works.** Throughput 2042 tok/s is at the top of step 17's range (just above its best cell, 2018), hit rate 0.844 and prefill work 52.6 M sit inside it, and every pod's hit rate is back in step 17's per-pod range (0.77 to 0.93, against step 18's 0.18 on the worst pod).

Readings:

1. **Step 18's cause is confirmed.** One commit that only changes how a session's in-flight turns are counted moves the rebuilt lease gate from 1477 to 2042 tok/s and from hit rate 0.539 to 0.844. With each turn counted, the gate no longer overfills the pods that hold sessions with overlapping turns: no pod falls behind (per-pod running 12.4 to 18.9, step 18 up to 24.5), and vLLM's queue is back near zero.
2. **The rebuilt ledger now behaves like step 17's.** With the minimal ledger's other differences still in place (capacity fallback key, idle TTL key, maintenance in the request hooks and at scrape, fixed 4 bytes per token, which step 18 measured as correct for this workload), the results match step 17's lease 30 s build, so none of those differences matters here.
3. The wait tail is unchanged in kind: TTFT p99 219 s and per-session worst TTFT p90 420 s, where step 17's lease 30 s was (220 to 279 s and 291 to 435 s); step 17's tail analysis still applies.

Caveats: one cell, against step 17's three cells from the day before on the same four pods.
