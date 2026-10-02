# Step 20: CPU KV offloading (400 GiB) on single vLLM replicas

The three lanes of a run ran at the same time on three replicas. Where an arm has several cells at a point (phase B replicates, or phase A's two lease cells), values are mean (min-max). Hit rates and CPU traffic are from vLLM's counters; the CPU hit rate is external hits over all prompt tokens queried. Working set: each live session's latest prompt size, summed. Phase A has offloading off, so its CPU rows must be 0.

## Phase T, c=64 (offload 400 GiB, window 30 min, warm-up 10 min)

Runs: `rep-20261002-003700-c64-t1900`.

| metric | lease + tier budget, lease 30 s (n=1) | lease + tier budget, lease 5 s (n=1) | lease, GPU capacity, lease 5 s (n=1) |
|---|---|---|---|
| pods (node) | trwg | 91qy | zhnf |
| output throughput (tok/s) | 612 | 593 | 633 |
| requests completed / errors | 1458 / 0 | 1411 / 0 | 1585 / 3 |
| sessions ended in window / turns not issued at stage end | 6 / 0 | 5 / 0 | 9 / 0 |
| GPU hit rate, steady | 0.693 | 0.686 | 0.713 |
| CPU hit rate, steady | 0.199 | 0.189 | 0.172 |
| total reuse (GPU + CPU), steady | 0.892 | 0.875 | 0.885 |
| GPU / CPU / total, whole window | 0.679 / 0.180 / 0.859 | 0.677 / 0.169 / 0.845 | 0.699 / 0.156 / 0.855 |
| prefill tokens computed (M) | 11.6 | 12.0 | 12.8 |
| prefill tok/s (k) | 6.4 | 6.7 | 7.1 |
| TTFT p50 / p90 / p99 (s) | 0.6 / 31.4 / 1019.7 | 0.7 / 32.3 / 986.9 | 0.5 / 30.1 / 1127.3 |
| E2E latency p50 / p90 (s) | 23.3 / 153.3 | 24.6 / 155.0 | 23.1 / 144.0 |
| vLLM running / waiting, mean steady | 23.7 / 0.3 | 24.1 / 0.2 | 26.5 / 0.2 |
| vLLM GPU KV usage, mean steady | 0.79 | 0.82 | 0.85 |
| vLLM preemptions | 91 | 20 | 28 |
| CPU tier stored / loaded (GB) | 583 / 729 | 619 / 661 | 643 / 677 |
| CPU tier load time (s) / allocation failures | 53 / 0 | 48 / 0 | 25 / 0 |
| working set, mean steady (M tokens) | 4.46 | 4.08 | 4.34 |
| working set / GPU KV / CPU tier | 1.99 / 0.51 | 1.83 / 0.47 | 1.94 / 0.50 |
| gate capacity (M tokens) | 2.24 | 2.24 | 2.24 |
| gate working set / capacity, mean steady | 0.99 | 0.97 | 0.98 |
| gate holds / pauses / forced admissions | 195 / 245 / 1 | 221 / 278 / 1 | 232 / 297 / 0 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.53 | 0.49 | 0.58 |
| session SLO attainment, strict | 0.33 | 0.36 | 0.34 |
| per-session worst TTFT, p90 (s) | 815 | 749 | 925 |

## Phase T, c=128 (offload 400 GiB, window 30 min, warm-up 10 min)

Runs: `rep-20261002-011632-c128-t1900`.

| metric | lease + tier budget, lease 30 s (n=1) | lease + tier budget, lease 5 s (n=1) | lease, GPU capacity, lease 5 s (n=1) |
|---|---|---|---|
| pods (node) | 91qy | zhnf | trwg |
| output throughput (tok/s) | 608 | 650 | 632 |
| requests completed / errors | 1509 / 0 | 1675 / 1 | 1684 / 3 |
| sessions ended in window / turns not issued at stage end | 4 / 0 | 4 / 0 | 5 / 0 |
| GPU hit rate, steady | 0.715 | 0.690 | 0.687 |
| CPU hit rate, steady | 0.151 | 0.181 | 0.182 |
| total reuse (GPU + CPU), steady | 0.866 | 0.871 | 0.869 |
| GPU / CPU / total, whole window | 0.642 / 0.159 / 0.801 | 0.635 / 0.183 / 0.818 | 0.616 / 0.203 / 0.819 |
| prefill tokens computed (M) | 14.4 | 13.8 | 14.1 |
| prefill tok/s (k) | 8.0 | 7.7 | 7.8 |
| TTFT p50 / p90 / p99 (s) | 1.0 / 93.4 / 1638.0 | 0.8 / 80.4 / 1182.8 | 1.1 / 80.4 / 1363.0 |
| E2E latency p50 / p90 (s) | 31.5 / 188.1 | 27.2 / 171.1 | 27.8 / 193.4 |
| vLLM running / waiting, mean steady | 25.9 / 0.4 | 26.6 / 0.4 | 29.5 / 0.5 |
| vLLM GPU KV usage, mean steady | 0.81 | 0.81 | 0.87 |
| vLLM preemptions | 120 | 179 | 119 |
| CPU tier stored / loaded (GB) | 736 / 585 | 742 / 734 | 759 / 835 |
| CPU tier load time (s) / allocation failures | 42 / 0 | 27 / 0 | 60 / 0 |
| working set, mean steady (M tokens) | 4.05 | 3.76 | 3.82 |
| working set / GPU KV / CPU tier | 1.81 / 0.46 | 1.68 / 0.43 | 1.71 / 0.44 |
| gate capacity (M tokens) | 2.24 | 2.24 | 2.24 |
| gate working set / capacity, mean steady | 1.02 | 1.01 | 1.01 |
| gate holds / pauses / forced admissions | 172 / 273 / 16 | 237 / 345 / 16 | 270 / 372 / 16 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.58 | 0.57 | 0.61 |
| session SLO attainment, strict | 0.54 | 0.42 | 0.47 |
| per-session worst TTFT, p90 (s) | 445 | 729 | 509 |

## Phase T, c=192 (offload 400 GiB, window 45 min, warm-up 15 min)

Runs: `rep-20261002-015625-c192-t1900`.

| metric | lease + tier budget, lease 30 s (n=1) | lease + tier budget, lease 5 s (n=1) | lease, GPU capacity, lease 5 s (n=1) |
|---|---|---|---|
| pods (node) | zhnf | trwg | 91qy |
| output throughput (tok/s) | 546 | 544 | 554 |
| requests completed / errors | 2079 / 49 | 2201 / 19 | 2287 / 43 |
| sessions ended in window / turns not issued at stage end | 49 / 0 | 20 / 0 | 43 / 0 |
| GPU hit rate, steady | 0.388 | 0.462 | 0.458 |
| CPU hit rate, steady | 0.369 | 0.317 | 0.296 |
| total reuse (GPU + CPU), steady | 0.757 | 0.779 | 0.754 |
| GPU / CPU / total, whole window | 0.402 / 0.340 / 0.742 | 0.446 / 0.300 / 0.746 | 0.448 / 0.287 / 0.734 |
| prefill tokens computed (M) | 23.4 | 26.2 | 25.7 |
| prefill tok/s (k) | 8.7 | 9.7 | 9.5 |
| TTFT p50 / p90 / p99 (s) | 2.8 / 311.7 / 1831.6 | 2.9 / 291.3 / 1839.8 | 2.3 / 228.2 / 1823.1 |
| E2E latency p50 / p90 (s) | 41.6 / 409.4 | 39.3 / 364.5 | 40.5 / 258.5 |
| vLLM running / waiting, mean steady | 26.1 / 5.0 | 29.6 / 4.0 | 28.6 / 3.6 |
| vLLM GPU KV usage, mean steady | 0.83 | 0.88 | 0.83 |
| vLLM preemptions | 229 | 302 | 213 |
| CPU tier stored / loaded (GB) | 1359 / 1777 | 1398 / 1647 | 1475 / 1583 |
| CPU tier load time (s) / allocation failures | 65 / 0 | 119 / 0 | 115 / 0 |
| working set, mean steady (M tokens) | 6.71 | 6.95 | 6.88 |
| working set / GPU KV / CPU tier | 3.00 / 0.77 | 3.11 / 0.80 | 3.08 / 0.79 |
| gate capacity (M tokens) | 2.24 | 2.24 | 2.24 |
| gate working set / capacity, mean steady | 1.15 | 1.12 | 1.10 |
| gate holds / pauses / forced admissions | 436 / 520 / 111 | 350 / 498 / 104 | 442 / 552 / 112 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.43 | 0.50 | 0.52 |
| session SLO attainment, strict | 0.21 | 0.24 | 0.30 |
| per-session worst TTFT, p90 (s) | 1186 | 665 | 620 |

## Phase T, c=256 (offload 400 GiB, window 45 min, warm-up 15 min)

Runs: `rep-20261002-025316-c256-t1900`.

| metric | lease + tier budget, lease 30 s (n=1) | lease + tier budget, lease 5 s (n=1) | lease, GPU capacity, lease 5 s (n=1) |
|---|---|---|---|
| pods (node) | trwg | 91qy | zhnf |
| output throughput (tok/s) | 504 | 507 | 535 |
| requests completed / errors | 2093 / 102 | 2281 / 74 | 2348 / 82 |
| sessions ended in window / turns not issued at stage end | 104 / 0 | 77 / 0 | 80 / 58 |
| GPU hit rate, steady | 0.430 | 0.451 | 0.394 |
| CPU hit rate, steady | 0.297 | 0.249 | 0.314 |
| total reuse (GPU + CPU), steady | 0.727 | 0.700 | 0.708 |
| GPU / CPU / total, whole window | 0.422 / 0.280 / 0.702 | 0.427 / 0.258 / 0.685 | 0.347 / 0.350 / 0.697 |
| prefill tokens computed (M) | 24.3 | 28.2 | 27.2 |
| prefill tok/s (k) | 9.0 | 10.4 | 10.1 |
| TTFT p50 / p90 / p99 (s) | 5.9 / 548.7 / 1846.6 | 3.9 / 577.3 / 1848.0 | 6.3 / 302.3 / 1840.2 |
| E2E latency p50 / p90 (s) | 51.1 / 587.9 | 49.9 / 596.2 | 47.3 / 366.7 |
| vLLM running / waiting, mean steady | 26.7 / 9.0 | 29.9 / 6.5 | 31.6 / 7.7 |
| vLLM GPU KV usage, mean steady | 0.84 | 0.84 | 0.89 |
| vLLM preemptions | 153 | 202 | 365 |
| CPU tier stored / loaded (GB) | 1531 / 1439 | 1648 / 1355 | 1646 / 1906 |
| CPU tier load time (s) / allocation failures | 104 / 0 | 98 / 0 | 69 / 0 |
| working set, mean steady (M tokens) | 7.87 | 7.99 | 7.49 |
| working set / GPU KV / CPU tier | 3.52 / 0.90 | 3.57 / 0.91 | 3.35 / 0.86 |
| gate capacity (M tokens) | 2.24 | 2.24 | 2.24 |
| gate working set / capacity, mean steady | 1.25 | 1.16 | 1.22 |
| gate holds / pauses / forced admissions | 513 / 641 / 170 | 612 / 694 / 154 | 546 / 687 / 148 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.35 | 0.46 | 0.48 |
| session SLO attainment, strict | 0.17 | 0.16 | 0.20 |
| per-session worst TTFT, p90 (s) | 864 | 1074 | 605 |
