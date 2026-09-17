# Single-node A/B comparison

| metric | default (pure proxy) | tr + acting decay (no release) | tr, no decay (no release) |
|---|---|---|---|
| requests ok | 240/240 | 240/240 | 240/240 |
| makespan (s) | 457.5 | 315.3 | 3677.7 |
| prefix-cache hit rate | 0.000 | 0.345 | 0.462 |
| prefilled (miss) tokens (M) | 14.71 | 9.63 | 7.91 |
| turn latency p50 (s) | 150.7 | 57.0 | 50.4 |
| turn latency p95 (s) | 160.6 | 250.4 | 1851.9 |
| turn latency max (s) | 162.9 | 301.7 | 1864.7 |
| turn-0 latency p50 (s) | 81.0 | 80.9 | 81.0 |
| max concurrent paused | 0 | 49 | 47 |
| peak vLLM waiting queue | 75 | 38 | 37 |
| peak KV utilization | 0.27 | 0.77 | 0.88 |

tr + acting decay (no release) vs default (pure proxy): prefill 0.65x, makespan 0.69x, p50 0.38x, p95 1.56x (lower is better)

tr, no decay (no release) vs default (pure proxy): prefill 0.54x, makespan 8.04x, p50 0.33x, p95 11.53x (lower is better)
