# Step 32 follow-up: c=48, 3600 s per arm

> Superseded by [`../compare-1h/REPORT.md`](../compare-1h/REPORT.md) (c=32 and c=48 together).

Status: done (2026-10-21, 17:26 to 19:59 UTC). Both points valid: job succeeded, pods unchanged, 0 client errors.

## Setup

Same as the 900 s sweep (same pods' nodes, image, EPP image `thunder-sglang-close-7eec9d9c`, plugin files `b200/{baseline-lru,thunder-close}-plugins.yaml`; the gate capacity is read from SGLang `page_size x num_pages` = 3,516,892 tokens per pod), except:

- 3600 s per point (steady state = after minute 5), c=48 only, run back to back: `closeSession: false` (17:26) then `closeSession: true` (18:42); SGLang cache flushed and EPP restarted before each.
- SGLang restarted once before both points with `--enable-cache-report` (per-request cached tokens) and `--uvicorn-access-log-exclude-prefixes /metrics /health` (keeps every `release_session` line). Server image `lmsysorg/sglang@sha256:ddae0e39...` (`0.0.0.dev1+g684fea8af`).
- Runner `b200/run-c48-1h.sh`, log `results/run-c48-1h.log`; per-request analysis `b200/close_mechanism.py`, output `report/close_mechanism.txt`.

## Results (steady state)

| | close=false | close=true | ratio |
|---|---:|---:|---:|
| completed (whole window) | 2,644 | 2,609 | 0.99 |
| effective concurrency | 41.3 | 42.1 | 1.02 |
| output tok/s/GPU | 69.05 | 66.32 | **0.960** |
| goodput tok/s (TTFT SLO 60 s) | 540.6 | 513.0 | 0.949 |
| hit, per-request token-weighted | 89.48% | 88.20% | -1.3 pp |
| uncached prompt tokens / request | 9,798 | 11,074 | 1.13 |
| TTFT p50 / p90 / p99 (s) | 0.51 / 3.72 / 85.0 | 0.55 / 5.97 / 102.3 | 1.08 / 1.61 / 1.20 |
| TTFT mean (s) | 5.53 | 4.61 | 0.83 |
| E2E p50 / p90 (s) | 22.3 / 137.8 | 25.2 / 145.3 | 1.13 / 1.06 |
| gate pauses / resumes | 426 / 223 | 451 / 257 | |
| EPP queue wait mean (s) | 2.24 | 1.99 | 0.89 |
| `close_session` sent / SGLang `release_session` (TP0) | 0 / 0 | 509 / 509 (464 released KV) | |

## Where the cost comes from

First request of a session after its `release_session` (close arm, steady state): n=226, hit **29.9%**, 73,437 uncached tokens per turn, TTFT p50 13.3 s; all other non-first turns: hit 96.4%, 3,601 uncached tokens, TTFT p50 0.52 s. The release-to-next-request gap is p50 92 s, p90 414 s.

That alone is selection (paused sessions are idle ones). The counterfactual is the same idle gap in the baseline, where idle sessions also lose their prefix under LRU:

| idle gap since the session's previous request | close=false n / hit | close=true n / hit |
|---|---:|---:|
| < 5 s | 1816 / 96.7% | 1795 / 96.3% |
| 5-30 s | 211 / 97.3% | 212 / 96.7% |
| 30-60 s | 70 / 85.6% | 52 / 80.8% |
| 60-120 s | 61 / 71.9% | 69 / 59.7% |
| 120-300 s | 75 / 30.6% | 74 / 15.0% |
| > 300 s | 37 / 7.6% | 36 / 0.0% |

- Sessions that come back after 1 to 5 minutes find about half as much of their prefix with close on. With session refs, a released session's KV is the first to be evicted (SGLang evicts unreferenced KV before referenced KV), ahead of older but still-referenced sessions; under plain LRU it competes on recency.
- No offsetting gain is visible: turns after short gaps (the sessions close is meant to protect) hit the same in both arms (96.3% to 96.7%).
- Net: about +2.6M uncached prompt tokens per hour of steady state (27.1M against 24.5M), which matches the -4% output throughput and the TTFT p90 tail.

## Conclusion

At c=48 on this deployment, `closeSession: true` costs about 4% output throughput (5% goodput) and lengthens the TTFT tail, and the per-request data show the mechanism: paused sessions that resume after 1 to 5 minutes find their prefix evicted. The 900 s run pointed the same way (-10.6%); the 3600 s run gives a smaller, better-measured effect.

## Limits

- One replicate per arm, run back to back (not interleaved). The ratio sits at the edge of the 0.95 to 1.05 tie band; the per-gap table is the stronger evidence (same direction in every bucket from 30 s up).
- The close arm also turns on session refs (`session_id` is injected only with `closeSession: true`), so this compares the PR #16 feature on against off. A refs-only arm would keep paused sessions referenced; the post-release turns would then likely do better than in either arm here.
- `analyze.py` fails in `point_figures.fig_timeline` on SGLang points (vLLM metric names); `summary.csv`, `ratios.md` and fig1/2/5 were written before the failure. aiperf's "counter reset" warnings come from the `/metrics` series it scraped through the EPP address (alternating pods); the per-pod series used here are unaffected.
- `kubectl logs -f` streams in `results/streams/` outlived their point (the baseline files also hold the close run's lines after 18:42); `close_mechanism.py` keeps only each arm's window.
