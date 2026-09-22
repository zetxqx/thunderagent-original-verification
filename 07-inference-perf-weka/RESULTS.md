# Weka trace replay through the original ThunderAgent: results index

Everything for this experiment lives in this folder: tooling, calibration evidence, incident write-ups, and every run's raw artifacts under `results/`. This file says which run means what. For a self-contained write-up of the authoritative run, with the ThunderAgent background, the KV-capacity and over-subscription arithmetic, and the three figures, read `REPORT.md`.

## Headline

On real Claude Code traffic (weka trace replay) against a saturated single vLLM pod, with no client-side release signal, the original ThunderAgent's admission control delivers **2.0-2.4x the output-token throughput** of the same router used as a pure proxy, and lifts the prefix-cache hit rate from **0.04-0.10 to 0.54-0.69**. The three concurrency points span 2.0-2.4x, but see the caveat below: that spread is within known run-to-run variation, so do not read it as an upward trend.

`results/weka-20260916-185331-full`, 6 cells, all completed, no preemptions.

| metric | c=96 | c=128 | c=192 |
|---|---|---|---|
| output tokens, default -> tr | 575k -> **1123k** (1.95x) | 588k -> **1264k** (2.15x) | 572k -> **1388k** (2.43x) |
| successful requests | 1026 -> 1635 | 1056 -> 1972 | 1107 -> 1893 |
| prefix-cache hit rate (pod counters) | 0.095 -> **0.541** | 0.097 -> **0.555** | 0.037 -> **0.690** |
| median TTFT, default -> tr | 41s -> **4.1s** | 48s -> **4.2s** | 70s -> **2.5s** |
| p90 TTFT, default -> tr | 89s -> **18s** | 76s -> **18s** | 115s -> **18s** |
| peak concurrently paused programs | 55 | 78 | 66 |
| KV utilization peak | 1.00 both arms | 1.00 both | 1.00 both |
| errors | 20 -> 31 | 14 -> 49 | 15 -> 36 |

Both arms saturated the KV pool (peak 1.00) - the difference is what the pool was used *for*: under `default` it churns (90-96% of prompt tokens recomputed), under `tr-decay` it holds resident working sets that get reused.

### RETRACTED: the paired per-request analysis is unsound

The pre-registered primary metric matched requests across arms on (`graph_event_id`, prompt tokens within 1%). **`graph_event_id` is not unique per request**: it identifies a position inside a session's event graph, so `event_000_parent_turn_0` occurs once per session - 87 times in one cell (1929 requests, only 341 distinct ids). Matching on it pairs "turn 0 of some session" with "turn 0 of some other session".

The prompt-token filter was supposed to disambiguate, but measured on this data **57% of matches had more than one candidate** (up to 40), and the code silently took the first. Every paired number - the median/mean deltas, "better on 26-48% of requests" - is therefore unreliable and is withdrawn.

What survives untouched: every arm-level result. Throughput, aggregate hit rate (pod counters), TTFT distributions, KV utilization, paused counts, and the per-session stall analysis all measure one arm at a time and need no matching. The headline numbers above are unaffected.

Replacement analysis, in `fairness-weka.png`: each arm's per-request cache-hit distribution plotted on its own, no matching. It shows the same thing more honestly - under `default` 86-94% of requests get nothing at all from cache, under `tr-decay` that drops to 32-45%.

A correct pairing would need a session identifier in the per-request report. inference-perf does not emit one today (`info.labels` and `info.extra_info` are empty); the router's `programs-timeline.csv` has real program ids but no per-request detail. Worth requesting upstream.

### Fairness: does the 2x throughput come from starving some sessions?

No. Measured per session from the router's own program timeline (real session identity), taking each session's **longest continuous stretch with a request outstanding** - engine queueing for `default`, router hold plus engine queueing for `tr-decay`:

| | c=96 | c=128 | c=192 |
|---|---|---|---|
| sessions stalled >5 min, default -> tr | 97% -> **84%** | 91% -> **74%** | 91% -> **82%** |
| median worst stall, default -> tr | 896s -> **704s** | 815s -> 845s | 870s -> 840s |
| p90 worst stall, default -> tr | 2520s -> 2557s | 2474s -> 2667s | 2015s -> 2498s |

So `tr-decay` leaves **fewer** sessions badly stalled and has a similar or better median, while delivering roughly twice the work. Its p90 is somewhat worse (by 40-480s), i.e. the pain is a little more concentrated - but under `default` the pain is close to universal (91-97% of sessions stall more than five minutes).

Two caveats on this comparison: `tr-decay` served more distinct sessions (77-101 vs 64-75) because it got further through the corpus, and every stall figure here is inflated by the fact that both arms are heavily overloaded for the whole 45-minute window.

Starvation bound: no session was never admitted (0 in all cells), but the maximum single pause reached 1804-1880s at all three concurrencies - exactly upstream's hard-coded `_wait_for_resume(timeout=1800.0)` backstop. Median pause is 6-8s and p90 is 188-278s, so the distribution is extremely skewed: a handful of sessions absorb almost all the waiting, and only the 30-minute forced admission rescues them. For latency-sensitive deployments that backstop is far too loose, and pure FIFO queueing with a timeout is the weak point worth fixing upstream.

### Verdict against the pre-registered rule

The rule fixed before the run was: *paired median hit-ratio delta > +5 points, AND window output >= baseline, AND paired median TTFT not worse than +10%.*

Criterion 1 cannot be evaluated at all: it depends on the pairing that turned out to be unsound (see the retraction above). Criteria 2 and 3 pass overwhelmingly on arm-level data - window output 1.95-2.43x, and TTFT better rather than worse at every percentile (p50 10-28x, p90 5-6x, mean 4-6x).

So this is not a clean pass of the rule as written, because the rule's primary statistic was built on a broken matching key. Judged on the arm-level evidence the rule's other two criteria were meant to protect - is the throughput real, and is latency not being sacrificed - `tr-decay` wins decisively and consistently at all three concurrencies.

Replacement for criterion 1, unpaired and valid: the share of requests that got **nothing** from cache falls from 86-94% under `default` to 32-45% under `tr-decay`.

### What the time series show (`timeseries-weka.png`, one row per concurrency)

Splitting the series by concurrency - instead of overlaying six lines - makes the mechanism visible directly, and the same four-stage story repeats at all three loads:

1. **Both arms start identically and both collapse.** In the first 3-5 minutes each arm climbs to a ~0.85 hit rate as sessions build their prefixes, then falls to near zero as the pool fills. The onset of thrashing is not something `tr` avoids.
2. **Only `tr` recovers.** From roughly minute 10-25 onward the tr arm climbs back to 0.4-1.0 and stays there, oscillating as cohorts are admitted and released. The default arm stays pinned at ~0.00 for the remaining 40 minutes - once it is thrashing it never escapes, because every session keeps evicting every other session.
3. **The queue moves from the engine into the router.** Default's vLLM waiting queue grows to 20-35 and stays there; tr's stays near 0-5 while its paused-program count ramps to 54-78. Same work, held in a place where it costs nothing instead of in a place where it evicts cache.
4. **KV utilization diverges late.** Both pin at ~100% early, but tr's drops (most visibly at c=128, to 40-60% after minute 30) as admitted cohorts complete and release, while default stays saturated to the end - it is still holding everything and finishing less.

Hit rate in that figure is a 60s rolling ratio of summed hits to summed queries, not an average of per-interval ratios: 2s buckets carry very different token counts, so averaging ratios would over-weight near-empty buckets and produce the 0/1 sawtooth that made the first version of this figure unreadable.

### Caveats

- **Single trial per cell, and the apparent trend with load is probably not real.** ThunderAgent converges to the same admitted set at every offered load (32.8 / 34.8 / 31.9 active programs on average), so there is no mechanism for offered concurrency to change the steady state. The 415 / 468 / 514 tok/s spread is +-11% around its mean, the same order as the ~9% run-to-run variation measured for the tr arm in step 06, while the default arm was near-deterministic (213 / 218 / 212). Treat the result as "2.0-2.4x at all three loads", not as "the advantage grows with load".
- **tr had 2-3x more errors** (31/49/36 vs 20/14/15), still <2.5% of its requests. Not investigated; worth a look before publishing.
- Effective concurrency is limited by the load generator, not the configured value (see `UPSTREAM-ISSUES.md` issue 3): mean in-flight was 48-58 across all cells, so c=96/128/192 differ in *offered* load, not in achieved in-flight concurrency. The three points are still distinct regimes (baseline hit rate falls 0.095 -> 0.037 as offered load rises) but they are closer together than the labels suggest.
- Subagent requests inherit the parent session id, so a program includes its subagents. That matches the paper's program abstraction but differs from treating subagents as independent sessions.

| run | what it was | verdict |
|---|---|---|
| `results/weka-20260916-185331-full` | **the authoritative A/B**: default vs tr-decay at c=96/128/192, 45 min per cell, saturated | **valid**, results above; figure `fairness-weka.png`, per-cell paired stats `analysis.md` |
| `results/cal-20260916-134154` | single-cell re-verification after the hang fix (c=128) | **valid**: hit 0.097, KV 1.00, clean exit and self-collection |
| `results/cal-20260916-103627` | saturation scan c=64/128/192, baseline arm only | **valid for finding the regime**: hit 0.41/0.25/0.19, KV 1.00. Two cells hung at exit (see `HANG-INVESTIGATION.md`); their tail time series are artifacts and their session-level reports are missing |
| `results/cal-20260916-102112` | same scan, first attempt | **failed to launch**: 24-core bench pods unschedulable (GPU node taint) |
| `results/cal-20260916-093536` | first saturation scan, c=40/64/96, 8-core client | **superseded**: the client was the bottleneck (effective concurrency pinned at 17), so "not saturated" was partly a harness artifact |
| `results/weka-20260916-010706-full-SUPERSEDED-unsaturated` | first full A/B, c=8/16/24, with release semantics as configured then | **conclusions void**: the pod was never saturated (baseline hit 0.905, KV peak 46-61%), so tr had nothing to do. The measured null says nothing about the mechanism. Kept for the record; the c16 lane was also lost to a spot preemption |
| `results/weka-2026091*-smoke` | plumbing smoke tests | passed: header->program mapping, streaming usage passthrough, prober CSVs |

## What the final run will produce

Per cell (`results/<run>/<arm>-c<N>/`):

- `results/report/` - inference-perf reports. Per request: token counts, `server_usage` incl. `prompt_tokens_details.cached_tokens`, TTFT. No prompt/response text (`per_request_fields` drops it; raw text would be ~1MB/request).
- `results/vllm-metrics.csv` - 2s series scraped straight off the vLLM pod: KV utilization, running/waiting, preemptions, and prefix-cache hit rate computed from counter deltas.
- `results/router-health.csv` - 2s series of programs / reasoning / acting / **paused** counts.
- `results/programs-timeline.csv` - per program per sample: `status` (reasoning/acting) and `state` (active/**paused**) - the pause flag is in `state` - plus backend. Gives each program's exact pause intervals.
- `router.log` - per-program pause/resume events with token counts, saved before any teardown.
- `config.yml`, `manifest.json` - rendered config plus sha256, image digests, target pod name **and UID**, node placement, preemption flag, timings.

Analysis lands in this file, produced by `pair.py` (paired per-request deltas, plus `fairness-weka.png`).

## How to reproduce

```
./calibrate.sh 96 128 192     # optional: re-check the regime, ~15 min
./run-weka-ab.sh              # the A/B: 3 lanes in parallel, ~1h40m
python3 pair.py results/<run> # paired analysis + figure
```

If a lane reports `PREEMPTED` (spot node reclaimed mid-cell), rerun just that pair:

```
./rerun-lane.sh results/<run> <concurrency> <new-vllm-pod> <new-pod-ip>
```

## Design decisions worth knowing before reading numbers

- **Single vLLM pod per lane**, so there is no placement decision and the only difference between arms is admission control.
- **No `/programs/release` anywhere** - real clients do not signal completion. That makes `--use-acting-token-decay` mandatory for the tr arm; without it capacity never frees and the router is 8x slower than a plain proxy (measured in `../06-single-node-ab/results.md`).
- **Corpus filter is one rule**: keep traces with <= 400 requests. No token filter (the dataset is already 256k-capped, measured re-tokenization drift 0.24%). Every trace's keep/drop decision and the download sha256 are recorded in each cell's `trace-manifest.json`.
- **Paired analysis, not aggregates**: arms are truncated by a fixed window and progress at different speeds, so requests are matched across arms on (`graph_event_id`, prompt_tokens within 1%) and judged as paired deltas.
- **Decision rule fixed before the run**: tr wins a concurrency point only if the paired median hit-ratio delta exceeds +5 points AND window output tokens are at least the baseline's AND paired median TTFT is not worse by more than 10%. A hit-rate win bought by admitting fewer sessions is not a win.
