# Benchmark run results (2026-09-15)

Command: `./run-benchmark.sh` (defaults: 12 sessions x 5 turns, ~900-word unique preamble per session, max_tokens 120, 0.5s think time, probe every 2s). Artifacts: `results/run-20260915-133113/`.

Figure: `figures/run-20260915-133113.png` (and `.pdf`), rendered with `figures/make_figure.py results/run-20260915-133113`. Four panels: (a) per-backend interval prefix-cache hit rate with the run aggregate line, (b) per-backend KV cache utilization, (c) program lifecycle counts (total/REASONING/ACTING/paused), (d) per-turn latency scatter with median.

## Outcome: all 5 checks PASS

| Check | Result |
|---|---|
| All requests succeeded | 60/60 HTTP 200 |
| Sticky routing (one backend per program, over all probe samples) | 12/12 programs, none moved |
| Aggregate prefix-cache hit rate >= 0.3 | **0.799** (74,240 / 92,877 tokens over the run window) |
| KV cache utilization rose above 0 | peak 0.0008 |
| All sessions tracked and released | 12/12 |

Makespan 5.8s; turn latency p50/mean/max = 0.415 / 0.539 / 1.604s. Max paused programs: 0.

## What the time series show

`metrics-backends.csv` (one row per backend per 2s sample):

- Interval prefix-cache hit rate climbs from ~0.50-0.67 during the first turns (each session's unique preamble is a compulsory miss) to ~0.97-0.98 in later turns, when every turn's whole history is a cache hit on the sticky backend. This is the paper's mechanism working: hit rate is bounded only by the new tokens per turn.
- The scheduler spread the 12 sessions evenly, 3 per backend (~5.2k program tokens each in `active_program_tokens`).
- `capacity_overflow` stayed 0 everywhere.

`metrics-router.csv` shows the program lifecycle: 0 programs -> 12 (6 REASONING / 6 ACTING mid-prefill) -> 0 REASONING / 12 ACTING as turns complete, then released.

## Reading the numbers correctly

- The expected hit rate for this shape is ~0.75-0.8 (sum of reused prefixes over sum of prompts across 5 growing turns), so 0.799 matches theory, not just "some caching happened".
- `paused_count` stayed 0 and peak KV usage was 0.08%: expected. Each backend has 2,237,040 tokens of KV; 12 sessions x ~1.7k tokens is nowhere near pressure. This run verifies correctness of the router (proxying, program tracking, sticky placement, cache reuse, metrics), not the admission-control behavior. To see pauses (the `tr` scheduler actually holding programs), the workload must approach per-backend capacity - e.g. `--sessions 48 --turns 8 --preamble-words 20000`-scale or a weka-trace replay; that is the next step.
- Backend `10.100.15.12` has huge cumulative counters (1.15B queries) from earlier EPP experiments; the script uses deltas over the run window, so this does not distort the hit rate.

## Files per run

- `summary.json` - config, latency stats, hit rate, per-program backend map, check results
- `metrics-backends.csv` - per-backend time series (KV usage, interval hit rate, queue depth, program token accounting)
- `metrics-router.csv` - program count / REASONING / ACTING / paused time series
- `requests.csv` - per-turn status, latency, token usage
- `programs-final.json` - `/programs` snapshot before release
