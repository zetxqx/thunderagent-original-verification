# Single-node A/B comparison

| metric | default (pure proxy) | tr + acting decay (no release) | tr, no decay (no release) |
|---|---|---|---|
| requests ok | 240/240 | 240/240 | 240/240 |
| makespan (s) | 457.5 | 315.0 | 3729.8 |
| prefix-cache hit rate | 0.000 | 0.344 | 0.352 |
| prefilled (miss) tokens (M) | 14.71 | 9.65 | 9.53 |
| turn latency p50 (s) | 150.7 | 68.5 | 59.7 |
| turn latency p95 (s) | 160.5 | 213.5 | 1855.6 |
| turn latency max (s) | 162.9 | 294.4 | 1880.4 |
| turn-0 latency p50 (s) | 81.0 | 81.0 | 81.0 |
| max concurrent paused | 0 | 47 | 49 |
| peak vLLM waiting queue | 75 | 38 | 37 |
| peak KV utilization | 0.27 | 0.88 | 0.63 |

tr + acting decay (no release) vs default (pure proxy): prefill 0.66x, makespan 0.69x, p50 0.45x, p95 1.33x (lower is better)

tr, no decay (no release) vs default (pure proxy): prefill 0.65x, makespan 8.15x, p50 0.40x, p95 11.56x (lower is better)
