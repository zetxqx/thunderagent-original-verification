# Step 32 follow-up: `closeSession` at c=32 and c=48, 3600 s per arm

Status: done (2026-10-21, 17:26 to 22:43 UTC). All four points valid: job succeeded, pods unchanged, 0 client errors, every response carries cached-token usage.

## Setup

Same as the 900 s sweep (nodes, server image, EPP image `thunder-sglang-close-7eec9d9c`, plugin files `b200/{baseline-lru,thunder-close}-plugins.yaml`; the gate reads capacity from SGLang `page_size x num_pages` = 3,516,892 tokens per pod), except:

- 3600 s per point, steady state = after minute 5. Each concurrency's two arms run back to back: c=48 `close=false` (17:26) then `close=true` (18:42); c=32 `close=true` (20:16) then `close=false` (21:30). SGLang cache flushed and EPP restarted before each point; same SGLang pods for all four (no restart).
- SGLang restarted once before all four with `--enable-cache-report` (per-request cached tokens) and `--uvicorn-access-log-exclude-prefixes /metrics /health` (keeps every `release_session` line). Server image `lmsysorg/sglang@sha256:ddae0e39...` (`0.0.0.dev1+g684fea8af`).
- Runners `b200/run-c48-1h.sh`, `b200/run-c32-1h.sh`; per-request analysis `b200/close_mechanism.py <results> <conc>`, output `report/close_mechanism-c{32,48}.txt`; `report/summary.csv`, `report/ratios.md`, fig1/2/5.

## Results (steady state)

| | c=32 off | c=32 on | ratio | c=48 off | c=48 on | ratio |
|---|---:|---:|---:|---:|---:|---:|
| completed (whole window) | 2,164 | 2,129 | 0.98 | 2,644 | 2,609 | 0.99 |
| effective concurrency | 25.7 | 26.1 | 1.02 | 41.3 | 42.1 | 1.02 |
| output tok/s/GPU | 60.82 | 59.45 | **0.978** | 69.05 | 66.32 | **0.960** |
| goodput tok/s (TTFT SLO 60 s) | 486.6 | 475.6 | 0.978 | 540.6 | 513.0 | 0.949 |
| hit, per-request token-weighted | 94.39% | 92.13% | **-2.3 pp** | 89.48% | 88.20% | **-1.3 pp** |
| uncached prompt tokens / request | 5,635 | 7,876 | **1.40** | 9,798 | 11,074 | **1.13** |
| TTFT p50 / p90 (s) | 0.52 / 1.31 | 0.54 / 1.53 | 1.04 / 1.17 | 0.51 / 3.72 | 0.55 / 5.97 | 1.08 / 1.61 |
| gate pauses / resumes | 159 / 40 | 138 / 17 | | 426 / 223 | 451 / 257 | |
| `close_session` sent = SGLang `release_session` | 0 | 144 | | 0 | 509 | |

## Mechanism: closed sessions come back cold

Hit rate of a session's request by idle gap since that session's previous request ended (steady state, turns after the first):

| idle gap | c=32 off | c=32 on | c=48 off | c=48 on |
|---|---:|---:|---:|---:|
| < 5 s | 96.1% (1542) | 95.5% (1510) | 96.7% (1816) | 96.3% (1795) |
| 5-30 s | 96.7% (158) | 94.0% (158) | 97.3% (211) | 96.7% (212) |
| 30-60 s | 91.6% (35) | 85.1% (31) | 85.6% (70) | 80.8% (52) |
| 60-120 s | 94.9% (35) | 95.5% (37) | 71.9% (61) | 59.7% (69) |
| 120-300 s | 96.3% (49) | **75.6%** (46) | 30.6% (75) | **15.0%** (74) |
| > 300 s | 81.6% (31) | **41.6%** (29) | 7.6% (37) | **0.0%** (36) |

- With close off, LRU keeps idle sessions' prefixes as long as there is room: at c=32 a session returning after 2 to 5 minutes still hits 96%; at c=48 the pool is fuller and it hits 31%.
- With close on, a closed session's KV becomes unreferenced, and SGLang's session radix cache evicts unreferenced KV before referenced KV. The paused session's prefix goes first, even when LRU would have kept it. At c=48, sessions returning after 2 to 5 minutes hit 15% (31% with close off). At c=32 the same bucket also drops (76% against 96%), but those turns mostly did not follow a close (see the split below).
- Uncached tokens per request: +40% at c=32, +13% at c=48. The split below shows that only the c=48 loss is concentrated on closed sessions.
- No gain offsets it: turns after short gaps (the sessions close is meant to protect) hit the same or slightly lower with close on, at both concurrencies.
- Close reaches most sessions: 134 of 185 sessions at c=32 and 275 of 296 at c=48 were released at least once (pause or move).

Split by whether the session was released during the gap (`release_session` between its previous request's end and this request's start):

| idle gap | c=32 off | c=32 on, not released | c=32 on, released | c=48 off | c=48 on, not released | c=48 on, released |
|---|---:|---:|---:|---:|---:|---:|
| < 30 s | 96.2% (1700) | 95.3% (1668) | - (0) | 96.7% (2027) | 96.4% (2007) | - (0) |
| 30-120 s | 93.4% (70) | 91.1% (68) | - (0) | 78.9% (131) | 94.9% (27) | 60.0% (94) |
| 120-300 s | 96.3% (49) | 75.6% (46) | - (0) | 30.6% (75) | 83.0% (2) | 14.1% (72) |
| > 300 s | 81.6% (31) | 51.9% (23) | 0.0% (6) | 7.6% (37) | - (0) | 0.0% (36) |

- c=48: nearly every long-idle session is paused (lease 30 s) and closed; the released ones come back colder than the baseline's idle sessions. The few unreleased ones hit 94.9% (30 to 120 s, n=27) against the baseline's 78.9%: a hint that session refs protect sessions that are not closed (small n, and they may sit on the less loaded pod).
- c=32: the mechanism above does not explain the loss. Only 6 steady-state turns follow a release; the extra uncached tokens (+4.0M) are spread over unreleased turns, including the 120 to 300 s bucket (75.6% against 96.3%, n=46). Possible causes are noise (few large prompts dominate a bucket), placement (a session moved to the other pod is cold there), or an effect of session refs; this data cannot tell them apart.

## Conclusion

On this deployment (2 x TP=4 SGLang, Qwen3.5-397B-A17B-FP8, AgentX), `closeSession: true` lowers output throughput by 2.2% (c=32) and 4.0% (c=48), lowers the token-weighted hit rate by 2.3 and 1.3 points, and lengthens the TTFT p90 by 17% and 61%. At c=48 the per-request data show the mechanism: closing a paused session moves its KV to the front of the eviction order (SGLang evicts every unreferenced node before any referenced one), and the session, which resumes after a p50 of 92 s, comes back to a cold prefix. At c=32 the loss is not concentrated on released sessions and its cause is open.

## Limits

- One replicate per arm. The throughput ratios (0.978, 0.960) are inside or at the edge of the 0.95 to 1.05 tie band. The hit-rate and per-gap differences are the stronger evidence: same direction in both concurrencies, opposite run orders (c=48 off first, c=32 on first), and they predict the throughput direction.
- The close arm also turns on session refs (`session_id` is injected only with `closeSession: true`), so this compares the PR #16 feature on against off. A refs-only arm (inject, never close) would keep paused sessions referenced; that is the natural next arm, and closing only on TTL eviction and moves (not on pause) the natural code change.
- Another team's Qwen3.5 P/D client jobs shared the namespace and the client node during c=48 `close=true` (18:56 to 20:03) and c=32 `close=true` (from 20:04). They use other GPU nodes; the client node stayed at 6% to 8% CPU.
- `analyze.py` fails in `point_figures.fig_timeline` on SGLang points (vLLM metric names); `summary.csv`, `ratios.md` and fig1/2/5 are written before the failure. aiperf's "counter reset" warnings come from the `/metrics` series it scraped through the EPP address (alternating pods); the per-pod series used here are unaffected.
- The c=48 SGLang log streams outlived their point (fixed before c=32); `close_mechanism.py` keeps only each arm's window.
