# Single-node A/B comparison

| metric | default (pure proxy) | tr + acting decay (no release) | tr, no decay (no release) |
|---|---|---|---|
| requests ok | 240/240 | 240/240 | 240/240 |
| makespan (s) | 457.8 | 345.7 | 3718.9 |
| prefix-cache hit rate | 0.000 | 0.278 | 0.348 |
| prefilled (miss) tokens (M) | 14.71 | 10.62 | 9.59 |
| turn latency p50 (s) | 150.8 | 64.3 | 60.6 |
| turn latency p95 (s) | 160.9 | 264.0 | 1857.0 |
| turn latency max (s) | 162.9 | 331.8 | 1880.4 |
| turn-0 latency p50 (s) | 81.0 | 81.0 | 81.0 |
| max concurrent paused | 0 | 52 | 48 |
| peak vLLM waiting queue | 75 | 38 | 37 |
| peak KV utilization | 0.27 | 0.39 | 0.45 |

tr + acting decay (no release) vs default (pure proxy): prefill 0.72x, makespan 0.75x, p50 0.43x, p95 1.64x (lower is better)

tr, no decay (no release) vs default (pure proxy): prefill 0.65x, makespan 8.12x, p50 0.40x, p95 11.54x (lower is better)
