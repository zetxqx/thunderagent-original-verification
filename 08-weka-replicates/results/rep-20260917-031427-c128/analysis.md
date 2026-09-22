# Repeated A/B: 3 runs of the same configuration

Each cell shows mean (min-max) over runs.

| metric | default | tr-decay | ratio of means |
|---|---|---|---|
| throughput (output tok/s) | 221 (210-242) | 469 (464-476) | 2.12x |
| requests completed | 1059 (1033-1108) | 1994 (1978-2011) | 1.88x |
| hit rate, whole window | 0.057 (0.037-0.077) | 0.615 (0.603-0.622) | 10.82x |
| hit rate, first 10 min (warm-up) | 0.197 (0.124-0.258) | 0.188 (0.117-0.310) | 0.96x |
| hit rate, after 10 min (STEADY) | 0.008 (0.007-0.009) | 0.685 (0.661-0.698) | 84.56x |
| TTFT p50 (s) | 52.7 (45.9-58.0) | 3.0 (2.9-3.2) | 0.06x |
| TTFT p90 (s) | 92.5 (70.2-104.5) | 18.0 (17.4-19.1) | 0.19x |
| TTFT p99 (s) | 106.6 (79.3-122.2) | 204.2 (147.4-251.3) | 1.92x |
| requests with zero cache hit | 0.88 (0.86-0.91) | 0.36 (0.35-0.40) | 0.41x |
| errors | 17 (15-20) | 47 (45-50) | 2.69x |

## Same sessions only (turns completed)

Restricted to the sessions BOTH arms of a run started, so the faster arm pulling extra traces out of the corpus cannot flatter it.

| run | shared sessions | turns: default | turns: tr-decay | ratio |
|---|---|---|---|---|
| r1 | 54 | 853 | 1068 | 1.25x |
| r2 | 54 | 927 | 1041 | 1.12x |
| r3 | 46 | 777 | 1196 | 1.54x |
