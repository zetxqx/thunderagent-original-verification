# Single-node A/B: default vs tr

| metric | default (pure proxy) | tr (ThunderAgent) |
|---|---|---|
| requests ok | 240/240 | 240/240 |
| makespan (s) | 457.3 | 304.6 |
| prefix-cache hit rate | 0.000 | 0.362 |
| prefilled (miss) tokens (M) | 14.71 | 9.38 |
| turn latency p50 (s) | 150.7 | 67.3 |
| turn latency p95 (s) | 160.5 | 204.9 |
| turn-0 latency p50 (s) | 80.9 | 81.0 |
| max concurrent paused | 0 | 47 |
| peak vLLM waiting queue | 75 | 38 |
| vLLM preemptions during run | 0 | 0 |
| peak KV utilization | 0.27 | 0.99 |

tr / default ratios: prefill 0.64x, makespan 0.67x, p50 0.45x, p95 1.28x (lower is better)
