# Step 32: SGLang session radix cache with ThunderAgent `closeSession` on 8x B200, AgentX workload

Status: done (2026-10-21). 900 s sweep at c = 16, 24, 32, 48, then 3600 s points at c = 32 and 48. Every point valid (job succeeded, pods unchanged, 0 client errors). **Main result: [results/compare-1h/REPORT.md](results/compare-1h/REPORT.md).**

## Takeaways

- PR #16's close path works end to end: every `POST /close_session` the EPP sends reaches SGLang and is logged as `release_session` (509 at c=48 and 144 at c=32 in one hour; 0 errors, 0 dropped).
- It does not help on this workload. 3600 s, steady state, close on against close off: output throughput 0.978x (c=32) and 0.960x (c=48), token-weighted hit rate -2.3 and -1.3 points, TTFT p90 1.17x and 1.61x. One replicate per arm; the throughput ratios sit inside or at the edge of the 0.95 to 1.05 tie band.
- At c=48 the cost has a measured mechanism: the gate pauses sessions idle for more than 30 s (`idleLeaseSeconds`), the close dereferences their KV, SGLang evicts every unreferenced node before any referenced one, and the sessions come back (release to next request p50 92 s) to a cold prefix: 60% hit after 30 to 120 s idle and 14% after 120 to 300 s, against 79% and 31% with close off. At c=32 the hit-rate loss is not concentrated on closed sessions; its cause is open.
- The 900 s sweep: ties at c = 16 to 32, close on 0.894x at c=48. Single 900 s points are too noisy to read more into.
- Next: close only on TTL eviction and moves (not on pause), and a refs-only arm (inject `session_id`, never close). At c=48 the few sessions that were not closed came back warmer than in the close-off arm (94.9% against 78.9% after 30 to 120 s, n=27), a hint that session refs alone may help.

## Question

Does `thunder-agent`'s `closeSession: true` (PR #16: inject `session_id` into requests to SGLang, `POST /close_session` when a session is paused, TTL-evicted or moved) change throughput, cache hit rate and TTFT against `closeSession: false`, on SGLang with `--enable-session-radix-cache`?

## Setup

| | |
|---|---|
| Model server | SGLang `lmsysorg/sglang@sha256:ddae0e39...` (`0.0.0.dev1+g684fea8af`), Qwen3.5-397B-A17B-FP8, TP=4, 2 pods (`b200/sglang-qwen35.yaml`, 8x B200 on nodes `13z6` and `0x6t`), `--enable-session-radix-cache --kv-cache-dtype fp8_e4m3 --mem-fraction-static 0.8 --chunked-prefill-size 16384 --enable-metrics --stream-response-default-include-usage`; for the 3600 s points also `--enable-cache-report` and `--uvicorn-access-log-exclude-prefixes /metrics /health` |
| KV capacity | 3,516,892 tokens per pod (`max_total_num_tokens`); the gate reads it from SGLang `page_size x num_pages` (`capacityTokens` is only the fallback) |
| Router | llm-d-router EPP image `thunder-sglang-close-7eec9d9c` (PR #16), `b200/thunder-close-plugins.yaml` and `b200/baseline-lru-plugins.yaml`; they differ only in `closeSession` (`utilThreshold: 0.85`, `idleLeaseSeconds: 30`, `headWaitStarvationMs: 1800000`, `evictionTtlSeconds: 3600`) |
| Client | AgentX harness `agentx-v1.0.6`, dataset `semianalysis_cc_traces_weka_062126_256k`, `X-Session-ID` from the correlation id |
| Method | SGLang cache flushed and EPP restarted before every point; steady state = requests started after minute 5 |
| Runs | 900 s: `b200/run-benchmark.sh` (all close-on points, then all close-off points). 3600 s: `b200/run-c48-1h.sh` (off, then on), `b200/run-c32-1h.sh` (on, then off) |

## Results

- 3600 s, c = 32 and 48: [results/compare-1h/REPORT.md](results/compare-1h/REPORT.md), `results/compare-1h/report/` (`summary.csv`, `ratios.md`, fig1/2/5, `close_mechanism-c{32,48}.txt` from `b200/close_mechanism.py`).
- 900 s, c = 16 to 48: `results/compare-report/summary.csv`, `results/compare-figures/` (`ratios.md`, fig1/2/5).

## Validity and caveats

- One replicate per arm and concurrency; the two arms of a concurrency ran back to back.
- The close-on arm also turns on session refs (`session_id` is injected only with `closeSession: true`), so the comparison is the PR #16 feature on against off.
- `analyze.py` fails in `point_figures.fig_timeline` on SGLang points (vLLM metric names); `summary.csv`, `ratios.md` and the across-arm figures are written before the failure. Its `usage_cache_read_pct` is empty for the 900 s points (no `--enable-cache-report`), and the `sglang:cache_hit_rate` gauge is not a token-weighted hit rate; use `sglang:cached_tokens / sglang:prompt_tokens` per pod from the parquet, excluding the series aiperf scraped through the EPP address.
- The 900 s points' SGLang logs (`meta/vllm-*.log.gz`) are truncated: the EPP's 20 Hz `/metrics` access lines rotate the container log. Fixed for the 3600 s points (access-log filter plus live `kubectl logs -f` streams in `results/streams/`).
- Another team's Qwen3.5 P/D client jobs shared the namespace and client node during parts of the 3600 s close-on points (other GPU nodes; client node at 6% to 8% CPU).
