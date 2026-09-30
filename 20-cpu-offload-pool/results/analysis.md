# Step 20: CPU KV offloading (400 GiB) on single vLLM replicas

One cell per arm and point; the three lanes of a point ran at the same time on three replicas. Hit rates and CPU traffic are from vLLM's counters; the CPU hit rate is external hits over all prompt tokens queried. Working set: each live session's latest prompt size, summed. Phase A has offloading off, so its CPU rows must be 0.

## Phase A, c=32 (offload off, window 30 min, warm-up 10 min)

Run `rep-20260930-050907-c32-t1900`.

| metric | llm-d default (lane a) | lease, GPU capacity (lane b) | lease, GPU capacity (lane c) |
|---|---|---|---|
| node | trwg | 91qy | zhnf |
| output throughput (tok/s) | 359 | 520 | 511 |
| requests completed / errors | 877 / 0 | 1218 / 0 | 1195 / 0 |
| sessions ended in window / turns not issued at stage end | 8 / 0 | 10 / 0 | 11 / 0 |
| GPU hit rate, steady | 0.045 | 0.795 | 0.747 |
| CPU hit rate, steady | 0.000 | 0.000 | 0.000 |
| total reuse (GPU + CPU), steady | 0.045 | 0.795 | 0.747 |
| GPU / CPU / total, whole window | 0.448 / 0.000 / 0.448 | 0.808 / 0.000 / 0.808 | 0.784 / 0.000 / 0.784 |
| prefill tokens computed (M) | 28.5 | 14.3 | 15.7 |
| prefill tok/s (k) | 15.8 | 7.9 | 8.7 |
| TTFT p50 / p90 / p99 (s) | 3.9 / 25.6 / 33.6 | 0.5 / 6.6 / 107.4 | 0.5 / 6.7 / 193.0 |
| E2E latency p50 / p90 (s) | 38.2 / 168.6 | 21.5 / 106.8 | 22.2 / 112.2 |
| vLLM running / waiting, mean steady | 26.0 / 3.8 | 23.9 / 0.3 | 23.3 / 0.2 |
| vLLM GPU KV usage, mean steady | 0.88 | 0.84 | 0.81 |
| vLLM preemptions | 4 | 2 | 2 |
| CPU tier stored / loaded (GB) | 0 / 0 | 0 / 0 | 0 / 0 |
| CPU tier load time (s) / allocation failures | 0 / 0 | 0 / 0 | 0 / 0 |
| working set, mean steady (M tokens) | 2.23 | 2.28 | 2.48 |
| working set / GPU KV / CPU tier | 1.00 / 0.25 | 1.02 / 0.26 | 1.11 / 0.28 |
| gate capacity (M tokens) | - | 2.24 | 2.24 |
| gate working set / capacity, mean steady | - | 0.99 | 0.99 |
| gate holds / pauses / forced admissions | 0 / 0 / 0 | 74 / 94 / 0 | 86 / 108 / 0 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.24 | 0.48 | 0.46 |
| session SLO attainment, strict | 0.45 | 0.71 | 0.60 |
| per-session worst TTFT, p90 (s) | 37 | 490 | 538 |

## Phase A, c=128 (offload off, window 30 min, warm-up 10 min)

Run `rep-20260930-054855-c128-t1900`.

| metric | lease, GPU capacity (lane a) | llm-d default (lane b) | lease, GPU capacity (lane c) |
|---|---|---|---|
| node | trwg | 91qy | zhnf |
| output throughput (tok/s) | 511 | 284 | 485 |
| requests completed / errors | 1430 / 4 | 954 / 1 | 1278 / 0 |
| sessions ended in window / turns not issued at stage end | 2 / 0 | 1 / 0 | 2 / 0 |
| GPU hit rate, steady | 0.674 | 0.000 | 0.633 |
| CPU hit rate, steady | 0.000 | 0.000 | 0.000 |
| total reuse (GPU + CPU), steady | 0.674 | 0.000 | 0.633 |
| GPU / CPU / total, whole window | 0.574 / 0.000 / 0.574 | 0.000 / 0.000 / 0.000 | 0.547 / 0.000 / 0.547 |
| prefill tokens computed (M) | 27.5 | 42.1 | 26.9 |
| prefill tok/s (k) | 15.3 | 23.4 | 14.9 |
| TTFT p50 / p90 / p99 (s) | 2.3 / 73.7 / 1111.3 | 174.2 / 250.0 / 266.5 | 3.1 / 77.1 / 1805.6 |
| E2E latency p50 / p90 (s) | 34.1 / 217.3 | 231.8 / 362.4 | 39.5 / 248.2 |
| vLLM running / waiting, mean steady | 33.1 / 1.1 | 34.4 / 82.9 | 29.7 / 1.2 |
| vLLM GPU KV usage, mean steady | 0.89 | 0.89 | 0.86 |
| vLLM preemptions | 8 | 8 | 7 |
| CPU tier stored / loaded (GB) | 0 / 0 | 0 / 0 | 0 / 0 |
| CPU tier load time (s) / allocation failures | 0 / 0 | 0 / 0 | 0 / 0 |
| working set, mean steady (M tokens) | 3.37 | 5.99 | 3.70 |
| working set / GPU KV / CPU tier | 1.50 / 0.39 | 2.68 / 0.69 | 1.65 / 0.42 |
| gate capacity (M tokens) | 2.24 | - | 2.24 |
| gate working set / capacity, mean steady | 1.10 | - | 1.07 |
| gate holds / pauses / forced admissions | 187 / 268 / 27 | 0 / 0 / 0 | 153 / 240 / 23 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.57 | 0.00 | 0.45 |
| session SLO attainment, strict | 0.50 | 0.00 | 0.51 |
| per-session worst TTFT, p90 (s) | 441 | 266 | 538 |

## Phase A, c=256 (offload off, window 45 min, warm-up 15 min)

Run `rep-20260930-062909-c256-t1900`.

| metric | lease, GPU capacity (lane a) | lease, GPU capacity (lane b) | llm-d default (lane c) |
|---|---|---|---|
| node | trwg | 91qy | zhnf |
| output throughput (tok/s) | 357 | 376 | 286 |
| requests completed / errors | 1545 / 133 | 1705 / 68 | 1472 / 1 |
| sessions ended in window / turns not issued at stage end | 129 / 0 | 66 / 0 | 1 / 0 |
| GPU hit rate, steady | 0.410 | 0.355 | 0.000 |
| CPU hit rate, steady | 0.000 | 0.000 | 0.000 |
| total reuse (GPU + CPU), steady | 0.410 | 0.355 | 0.000 |
| GPU / CPU / total, whole window | 0.316 / 0.000 / 0.316 | 0.260 / 0.000 / 0.260 | 0.000 / 0.000 / 0.000 |
| prefill tokens computed (M) | 43.7 | 50.0 | 62.2 |
| prefill tok/s (k) | 16.2 | 18.5 | 23.0 |
| TTFT p50 / p90 / p99 (s) | 11.1 / 355.7 / 1860.7 | 28.9 / 820.2 / 1837.5 | 421.9 / 549.9 / 564.5 |
| E2E latency p50 / p90 (s) | 75.4 / 444.8 | 88.4 / 838.0 | 472.9 / 644.4 |
| vLLM running / waiting, mean steady | 30.0 / 12.3 | 34.0 / 7.8 | 37.1 / 207.2 |
| vLLM GPU KV usage, mean steady | 0.86 | 0.89 | 0.92 |
| vLLM preemptions | 8 | 10 | 16 |
| CPU tier stored / loaded (GB) | 0 / 0 | 0 / 0 | 0 / 0 |
| CPU tier load time (s) / allocation failures | 0 / 0 | 0 / 0 | 0 / 0 |
| working set, mean steady (M tokens) | 6.79 | 6.17 | 11.12 |
| working set / GPU KV / CPU tier | 3.03 / 0.78 | 2.76 / 0.71 | 4.97 / 1.27 |
| gate capacity (M tokens) | 2.24 | 2.24 | - |
| gate working set / capacity, mean steady | 1.34 | 1.20 | - |
| gate holds / pauses / forced admissions | 460 / 471 / 177 | 317 / 497 / 129 | 0 / 0 / 0 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.26 | 0.37 | 0.00 |
| session SLO attainment, strict | 0.14 | 0.21 | 0.00 |
| per-session worst TTFT, p90 (s) | 367 | 850 | 563 |

## Phase B, c=32 (offload 400 GiB, window 30 min, warm-up 10 min)

Run `rep-20260930-010845-c32-t1900`.

| metric | llm-d default (lane a) | lease, GPU capacity (lane b) | lease, CPU-tier capacity (lane c) |
|---|---|---|---|
| node | trwg | 91qy | zhnf |
| output throughput (tok/s) | 567 | 570 | 560 |
| requests completed / errors | 1257 / 0 | 1266 / 0 | 1254 / 0 |
| sessions ended in window / turns not issued at stage end | 11 / 0 | 9 / 0 | 11 / 0 |
| GPU hit rate, steady | 0.030 | 0.769 | 0.043 |
| CPU hit rate, steady | 0.886 | 0.143 | 0.869 |
| total reuse (GPU + CPU), steady | 0.916 | 0.912 | 0.912 |
| GPU / CPU / total, whole window | 0.292 / 0.603 / 0.895 | 0.792 / 0.100 / 0.892 | 0.298 / 0.597 / 0.895 |
| prefill tokens computed (M) | 8.6 | 8.7 | 8.7 |
| prefill tok/s (k) | 4.8 | 4.9 | 4.8 |
| TTFT p50 / p90 / p99 (s) | 5.1 / 19.8 / 34.2 | 0.5 / 4.9 / 184.3 | 5.1 / 21.2 / 34.9 |
| E2E latency p50 / p90 (s) | 27.8 / 102.2 | 20.6 / 102.3 | 28.5 / 101.6 |
| vLLM running / waiting, mean steady | 22.6 / 5.5 | 21.3 / 0.1 | 21.0 / 5.2 |
| vLLM GPU KV usage, mean steady | 0.86 | 0.78 | 0.80 |
| vLLM preemptions | 310 | 22 | 239 |
| CPU tier stored / loaded (GB) | 428 / 2444 | 446 / 400 | 431 / 2414 |
| CPU tier load time (s) / allocation failures | 89 / 0 | 29 / 0 | 88 / 0 |
| working set, mean steady (M tokens) | 2.50 | 2.59 | 2.52 |
| working set / GPU KV / CPU tier | 1.12 / 0.29 | 1.16 / 0.30 | 1.13 / 0.29 |
| gate capacity (M tokens) | - | 2.24 | 8.74 |
| gate working set / capacity, mean steady | - | 0.99 | 0.41 |
| gate holds / pauses / forced admissions | 0 / 0 / 0 | 85 / 110 / 0 | 0 / 0 / 0 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.48 | 0.49 | 0.49 |
| session SLO attainment, strict | 0.43 | 0.54 | 0.59 |
| per-session worst TTFT, p90 (s) | 39 | 711 | 41 |

## Phase B, c=64 (offload 400 GiB, window 30 min, warm-up 10 min)

Run `rep-20260930-014820-c64-t1900`.

| metric | lease, CPU-tier capacity (lane a) | llm-d default (lane b) | lease, GPU capacity (lane c) |
|---|---|---|---|
| node | trwg | 91qy | zhnf |
| output throughput (tok/s) | 585 | 545 | 637 |
| requests completed / errors | 1384 / 0 | 1342 / 0 | 1550 / 0 |
| sessions ended in window / turns not issued at stage end | 5 / 0 | 4 / 0 | 7 / 0 |
| GPU hit rate, steady | 0.005 | 0.005 | 0.679 |
| CPU hit rate, steady | 0.917 | 0.914 | 0.202 |
| total reuse (GPU + CPU), steady | 0.922 | 0.919 | 0.881 |
| GPU / CPU / total, whole window | 0.003 / 0.871 / 0.874 | 0.003 / 0.868 / 0.871 | 0.672 / 0.183 / 0.855 |
| prefill tokens computed (M) | 10.7 | 10.5 | 11.9 |
| prefill tok/s (k) | 5.9 | 5.8 | 6.6 |
| TTFT p50 / p90 / p99 (s) | 43.8 / 78.1 / 95.2 | 44.9 / 81.1 / 101.7 | 0.6 / 17.7 / 647.3 |
| E2E latency p50 / p90 (s) | 74.5 / 144.5 | 75.5 / 150.2 | 22.1 / 131.6 |
| vLLM running / waiting, mean steady | 23.2 / 29.9 | 24.7 / 32.0 | 24.6 / 0.3 |
| vLLM GPU KV usage, mean steady | 0.83 | 0.89 | 0.79 |
| vLLM preemptions | 271 | 176 | 80 |
| CPU tier stored / loaded (GB) | 524 / 3642 | 520 / 3528 | 638 / 791 |
| CPU tier load time (s) / allocation failures | 132 / 0 | 255 / 0 | 29 / 0 |
| working set, mean steady (M tokens) | 4.62 | 4.51 | 3.21 |
| working set / GPU KV / CPU tier | 2.07 / 0.53 | 2.01 / 0.52 | 1.43 / 0.37 |
| gate capacity (M tokens) | 8.74 | - | 2.24 |
| gate working set / capacity, mean steady | 0.60 | - | 1.00 |
| gate holds / pauses / forced admissions | 0 / 0 / 0 | 0 / 0 / 0 | 199 / 253 / 1 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.00 | 0.00 | 0.56 |
| session SLO attainment, strict | 0.00 | 0.00 | 0.49 |
| per-session worst TTFT, p90 (s) | 97 | 105 | 645 |

## Phase B, c=128 (offload 400 GiB, window 30 min, warm-up 10 min)

Run `rep-20260930-022937-c128-t1900`.

| metric | lease, GPU capacity (lane a) | lease, CPU-tier capacity (lane b) | llm-d default (lane c) |
|---|---|---|---|
| node | trwg | 91qy | zhnf |
| output throughput (tok/s) | 631 | 568 | 562 |
| requests completed / errors | 1625 / 0 | 1532 / 0 | 1526 / 0 |
| sessions ended in window / turns not issued at stage end | 3 / 0 | - / - | - / - |
| GPU hit rate, steady | 0.641 | 0.002 | 0.002 |
| CPU hit rate, steady | 0.219 | 0.870 | 0.835 |
| total reuse (GPU + CPU), steady | 0.860 | 0.872 | 0.837 |
| GPU / CPU / total, whole window | 0.579 / 0.229 / 0.807 | 0.002 / 0.799 / 0.801 | 0.002 / 0.776 / 0.778 |
| prefill tokens computed (M) | 15.2 | 15.5 | 17.1 |
| prefill tok/s (k) | 8.4 | 8.6 | 9.5 |
| TTFT p50 / p90 / p99 (s) | 1.3 / 81.5 / 1708.9 | 105.5 / 181.9 / 206.5 | 102.5 / 191.4 / 262.3 |
| E2E latency p50 / p90 (s) | 29.9 / 193.4 | 138.5 / 228.4 | 132.5 / 238.7 |
| vLLM running / waiting, mean steady | 26.3 / 0.4 | 27.5 / 78.4 | 29.1 / 89.5 |
| vLLM GPU KV usage, mean steady | 0.80 | 0.84 | 0.91 |
| vLLM preemptions | 286 | 265 | 406 |
| CPU tier stored / loaded (GB) | 764 / 896 | 787 / 3185 | 875 / 3089 |
| CPU tier load time (s) / allocation failures | 33 / 0 | 230 / 0 | 112 / 0 |
| working set, mean steady (M tokens) | 4.33 | 7.03 | 6.92 |
| working set / GPU KV / CPU tier | 1.94 / 0.50 | 3.14 / 0.80 | 3.10 / 0.79 |
| gate capacity (M tokens) | 2.24 | 8.74 | - |
| gate working set / capacity, mean steady | 1.00 | 0.96 | - |
| gate holds / pauses / forced admissions | 217 / 301 / 15 | 29 / 43 / 0 | 0 / 0 / 0 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.62 | 0.00 | 0.00 |
| session SLO attainment, strict | 0.47 | 0.00 | 0.00 |
| per-session worst TTFT, p90 (s) | 568 | 208 | 272 |

## Phase B, c=192 (offload 400 GiB, window 45 min, warm-up 15 min)

Run `rep-20260930-031014-c192-t1900`.

| metric | llm-d default (lane a) | lease, GPU capacity (lane b) | lease, CPU-tier capacity (lane c) |
|---|---|---|---|
| node | trwg | 91qy | zhnf |
| output throughput (tok/s) | 361 | 560 | 576 |
| requests completed / errors | 1572 / 0 | 2221 / 22 | 2198 / 26 |
| sessions ended in window / turns not issued at stage end | - / - | 25 / 0 | 23 / 0 |
| GPU hit rate, steady | 0.000 | 0.450 | 0.001 |
| CPU hit rate, steady | 0.073 | 0.312 | 0.810 |
| total reuse (GPU + CPU), steady | 0.073 | 0.762 | 0.811 |
| GPU / CPU / total, whole window | 0.000 / 0.248 / 0.248 | 0.428 / 0.308 / 0.737 | 0.001 / 0.736 / 0.737 |
| prefill tokens computed (M) | 53.7 | 26.7 | 27.8 |
| prefill tok/s (k) | 19.9 | 9.9 | 10.3 |
| TTFT p50 / p90 / p99 (s) | 235.5 / 445.9 / 503.2 | 3.1 / 318.6 / 1830.8 | 148.2 / 210.8 / 288.2 |
| E2E latency p50 / p90 (s) | 275.9 / 537.4 | 40.7 / 355.4 | 184.6 / 287.7 |
| vLLM running / waiting, mean steady | 31.8 / 143.0 | 28.4 / 3.2 | 30.7 / 101.3 |
| vLLM GPU KV usage, mean steady | 0.88 | 0.82 | 0.90 |
| vLLM preemptions | 443 | 253 | 265 |
| CPU tier stored / loaded (GB) | 2740 / 915 | 1426 / 1656 | 1387 / 3914 |
| CPU tier load time (s) / allocation failures | 33 / 0 | 120 / 0 | 142 / 0 |
| working set, mean steady (M tokens) | 9.31 | 7.50 | 9.25 |
| working set / GPU KV / CPU tier | 4.16 / 1.07 | 3.35 / 0.86 | 4.13 / 1.06 |
| gate capacity (M tokens) | - | 2.24 | 8.74 |
| gate working set / capacity, mean steady | - | 1.09 | 1.00 |
| gate holds / pauses / forced admissions | 0 / 0 / 0 | 383 / 483 / 108 | 226 / 315 / 27 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.00 | 0.51 | 0.00 |
| session SLO attainment, strict | 0.00 | 0.34 | 0.00 |
| per-session worst TTFT, p90 (s) | 503 | 1244 | 265 |

## Phase B, c=256 (offload 400 GiB, window 45 min, warm-up 15 min)

Run `rep-20260930-040640-c256-t1900`.

| metric | lease, CPU-tier capacity (lane a) | llm-d default (lane b) | lease, GPU capacity (lane c) |
|---|---|---|---|
| node | trwg | 91qy | zhnf |
| output throughput (tok/s) | 535 | 286 | 527 |
| requests completed / errors | 2198 / 69 | 1459 / 0 | 2179 / 64 |
| sessions ended in window / turns not issued at stage end | 62 / 0 | - / - | 66 / 0 |
| GPU hit rate, steady | 0.001 | 0.000 | 0.412 |
| CPU hit rate, steady | 0.759 | 0.000 | 0.273 |
| total reuse (GPU + CPU), steady | 0.760 | 0.000 | 0.684 |
| GPU / CPU / total, whole window | 0.001 / 0.661 / 0.661 | 0.000 / 0.002 / 0.002 | 0.393 / 0.276 / 0.669 |
| prefill tokens computed (M) | 32.6 | 61.3 | 28.8 |
| prefill tok/s (k) | 12.1 | 22.7 | 10.7 |
| TTFT p50 / p90 / p99 (s) | 167.3 / 274.4 / 677.0 | 415.0 / 556.5 / 588.7 | 9.5 / 430.4 / 1851.0 |
| E2E latency p50 / p90 (s) | 202.0 / 353.8 | 477.4 / 649.4 | 52.3 / 500.4 |
| vLLM running / waiting, mean steady | 30.4 / 109.4 | 36.9 / 207.8 | 28.8 / 7.4 |
| vLLM GPU KV usage, mean steady | 0.86 | 0.93 | 0.83 |
| vLLM preemptions | 781 | 151 | 318 |
| CPU tier stored / loaded (GB) | 1621 / 3193 | 3122 / 9 | 1669 / 1390 |
| CPU tier load time (s) / allocation failures | 116 / 0 | 1 / 0 | 51 / 0 |
| working set, mean steady (M tokens) | 10.73 | 11.05 | 8.05 |
| working set / GPU KV / CPU tier | 4.80 / 1.23 | 4.94 / 1.26 | 3.60 / 0.92 |
| gate capacity (M tokens) | 8.74 | - | 2.24 |
| gate working set / capacity, mean steady | 1.00 | - | 1.21 |
| gate holds / pauses / forced admissions | 332 / 452 / 72 | 0 / 0 / 0 | 471 / 624 / 172 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.00 | 0.00 | 0.41 |
| session SLO attainment, strict | 0.00 | 0.00 | 0.19 |
| per-session worst TTFT, p90 (s) | 346 | 579 | 669 |
