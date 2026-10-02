# Step 20: CPU KV offloading (400 GiB) on single vLLM replicas

The three lanes of a run ran at the same time on three replicas. Where an arm has several cells at a point (phase B replicates, or phase A's two lease cells), values are mean (min-max). Hit rates and CPU traffic are from vLLM's counters; the CPU hit rate is external hits over all prompt tokens queried. Working set: each live session's latest prompt size, summed. Phase A has offloading off, so its CPU rows must be 0.

## Phase A, c=32 (offload off, window 30 min, warm-up 10 min)

Runs: `rep-20260930-050907-c32-t1900`.

| metric | llm-d default (n=1) | lease, GPU capacity (n=2) |
|---|---|---|
| pods (node) | trwg | 91qy, zhnf |
| output throughput (tok/s) | 359 | 516 (511-520) |
| requests completed / errors | 877 / 0 | 1206 (1195-1218) / 0 (0-0) |
| sessions ended in window / turns not issued at stage end | 8 / 0 | 10 (10-11) / 0 (0-0) |
| GPU hit rate, steady | 0.045 | 0.771 (0.747-0.795) |
| CPU hit rate, steady | 0.000 | 0.000 (0.000-0.000) |
| total reuse (GPU + CPU), steady | 0.045 | 0.771 (0.747-0.795) |
| GPU / CPU / total, whole window | 0.448 / 0.000 / 0.448 | 0.796 (0.784-0.808) / 0.000 (0.000-0.000) / 0.796 (0.784-0.808) |
| prefill tokens computed (M) | 28.5 | 15.0 (14.3-15.7) |
| prefill tok/s (k) | 15.8 | 8.3 (7.9-8.7) |
| TTFT p50 / p90 / p99 (s) | 3.9 / 25.6 / 33.6 | 0.5 (0.5-0.5) / 6.7 (6.6-6.7) / 150.2 (107.4-193.0) |
| E2E latency p50 / p90 (s) | 38.2 / 168.6 | 21.9 (21.5-22.2) / 109.5 (106.8-112.2) |
| vLLM running / waiting, mean steady | 26.0 / 3.8 | 23.6 (23.3-23.9) / 0.3 (0.2-0.3) |
| vLLM GPU KV usage, mean steady | 0.88 | 0.83 (0.81-0.84) |
| vLLM preemptions | 4 | 2 (2-2) |
| CPU tier stored / loaded (GB) | 0 / 0 | 0 (0-0) / 0 (0-0) |
| CPU tier load time (s) / allocation failures | 0 / 0 | 0 (0-0) / 0 (0-0) |
| working set, mean steady (M tokens) | 2.23 | 2.38 (2.28-2.48) |
| working set / GPU KV / CPU tier | 1.00 / 0.25 | 1.06 (1.02-1.11) / 0.27 (0.26-0.28) |
| gate capacity (M tokens) | - | 2.24 (2.24-2.24) |
| gate working set / capacity, mean steady | - | 0.99 (0.99-0.99) |
| gate holds / pauses / forced admissions | 0 / 0 / 0 | 80 (74-86) / 101 (94-108) / 0 (0-0) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.24 | 0.47 (0.46-0.48) |
| session SLO attainment, strict | 0.45 | 0.66 (0.60-0.71) |
| per-session worst TTFT, p90 (s) | 37 | 514 (490-538) |

## Phase A, c=128 (offload off, window 30 min, warm-up 10 min)

Runs: `rep-20260930-054855-c128-t1900`.

| metric | llm-d default (n=1) | lease, GPU capacity (n=2) |
|---|---|---|
| pods (node) | 91qy | trwg, zhnf |
| output throughput (tok/s) | 284 | 498 (485-511) |
| requests completed / errors | 954 / 1 | 1354 (1278-1430) / 2 (0-4) |
| sessions ended in window / turns not issued at stage end | 1 / 0 | 2 (2-2) / 0 (0-0) |
| GPU hit rate, steady | 0.000 | 0.654 (0.633-0.674) |
| CPU hit rate, steady | 0.000 | 0.000 (0.000-0.000) |
| total reuse (GPU + CPU), steady | 0.000 | 0.654 (0.633-0.674) |
| GPU / CPU / total, whole window | 0.000 / 0.000 / 0.000 | 0.560 (0.547-0.574) / 0.000 (0.000-0.000) / 0.560 (0.547-0.574) |
| prefill tokens computed (M) | 42.1 | 27.2 (26.9-27.5) |
| prefill tok/s (k) | 23.4 | 15.1 (14.9-15.3) |
| TTFT p50 / p90 / p99 (s) | 174.2 / 250.0 / 266.5 | 2.7 (2.3-3.1) / 75.4 (73.7-77.1) / 1458.5 (1111.3-1805.6) |
| E2E latency p50 / p90 (s) | 231.8 / 362.4 | 36.8 (34.1-39.5) / 232.8 (217.3-248.2) |
| vLLM running / waiting, mean steady | 34.4 / 82.9 | 31.4 (29.7-33.1) / 1.1 (1.1-1.2) |
| vLLM GPU KV usage, mean steady | 0.89 | 0.88 (0.86-0.89) |
| vLLM preemptions | 8 | 8 (7-8) |
| CPU tier stored / loaded (GB) | 0 / 0 | 0 (0-0) / 0 (0-0) |
| CPU tier load time (s) / allocation failures | 0 / 0 | 0 (0-0) / 0 (0-0) |
| working set, mean steady (M tokens) | 5.99 | 3.53 (3.37-3.70) |
| working set / GPU KV / CPU tier | 2.68 / 0.69 | 1.58 (1.50-1.65) / 0.40 (0.39-0.42) |
| gate capacity (M tokens) | - | 2.24 (2.24-2.24) |
| gate working set / capacity, mean steady | - | 1.08 (1.07-1.10) |
| gate holds / pauses / forced admissions | 0 / 0 / 0 | 170 (153-187) / 254 (240-268) / 25 (23-27) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.00 | 0.51 (0.45-0.57) |
| session SLO attainment, strict | 0.00 | 0.50 (0.50-0.51) |
| per-session worst TTFT, p90 (s) | 266 | 490 (441-538) |

## Phase A, c=256 (offload off, window 45 min, warm-up 15 min)

Runs: `rep-20260930-062909-c256-t1900`.

| metric | llm-d default (n=1) | lease, GPU capacity (n=2) |
|---|---|---|
| pods (node) | zhnf | trwg, 91qy |
| output throughput (tok/s) | 286 | 367 (357-376) |
| requests completed / errors | 1472 / 1 | 1625 (1545-1705) / 100 (68-133) |
| sessions ended in window / turns not issued at stage end | 1 / 0 | 98 (66-129) / 0 (0-0) |
| GPU hit rate, steady | 0.000 | 0.382 (0.355-0.410) |
| CPU hit rate, steady | 0.000 | 0.000 (0.000-0.000) |
| total reuse (GPU + CPU), steady | 0.000 | 0.382 (0.355-0.410) |
| GPU / CPU / total, whole window | 0.000 / 0.000 / 0.000 | 0.288 (0.260-0.316) / 0.000 (0.000-0.000) / 0.288 (0.260-0.316) |
| prefill tokens computed (M) | 62.2 | 46.8 (43.7-50.0) |
| prefill tok/s (k) | 23.0 | 17.3 (16.2-18.5) |
| TTFT p50 / p90 / p99 (s) | 421.9 / 549.9 / 564.5 | 20.0 (11.1-28.9) / 588.0 (355.7-820.2) / 1849.1 (1837.5-1860.7) |
| E2E latency p50 / p90 (s) | 472.9 / 644.4 | 81.9 (75.4-88.4) / 641.4 (444.8-838.0) |
| vLLM running / waiting, mean steady | 37.1 / 207.2 | 32.0 (30.0-34.0) / 10.0 (7.8-12.3) |
| vLLM GPU KV usage, mean steady | 0.92 | 0.87 (0.86-0.89) |
| vLLM preemptions | 16 | 9 (8-10) |
| CPU tier stored / loaded (GB) | 0 / 0 | 0 (0-0) / 0 (0-0) |
| CPU tier load time (s) / allocation failures | 0 / 0 | 0 (0-0) / 0 (0-0) |
| working set, mean steady (M tokens) | 11.12 | 6.48 (6.17-6.79) |
| working set / GPU KV / CPU tier | 4.97 / 1.27 | 2.90 (2.76-3.03) / 0.74 (0.71-0.78) |
| gate capacity (M tokens) | - | 2.24 (2.24-2.24) |
| gate working set / capacity, mean steady | - | 1.27 (1.20-1.34) |
| gate holds / pauses / forced admissions | 0 / 0 / 0 | 388 (317-460) / 484 (471-497) / 153 (129-177) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.00 | 0.31 (0.26-0.37) |
| session SLO attainment, strict | 0.00 | 0.18 (0.14-0.21) |
| per-session worst TTFT, p90 (s) | 563 | 608 (367-850) |

## Phase B, c=32 (offload 400 GiB, window 30 min, warm-up 10 min)

Runs: `rep-20260930-010845-c32-t1900`, `rep-20261001-150156-c32-t1900`, `rep-20261001-185457-c32-t1900`.

| metric | llm-d default (n=3) | lease, GPU capacity (n=3) | lease, CPU-tier capacity (n=3) |
|---|---|---|---|
| pods (node) | trwg, zhnf, 91qy | 91qy, trwg, zhnf | zhnf, 91qy, trwg |
| output throughput (tok/s) | 560 (551-567) | 578 (570-584) | 554 (546-560) |
| requests completed / errors | 1244 (1228-1257) / 0 (0-0) | 1272 (1256-1293) / 0 (0-0) | 1236 (1222-1254) / 0 (0-0) |
| sessions ended in window / turns not issued at stage end | 11 (11-11) / 0 (0-0) | 9 (9-10) / 0 (0-0) | 11 (11-11) / 0 (0-0) |
| GPU hit rate, steady | 0.035 (0.028-0.047) | 0.779 (0.769-0.792) | 0.035 (0.029-0.043) |
| CPU hit rate, steady | 0.878 (0.861-0.887) | 0.132 (0.127-0.143) | 0.877 (0.869-0.881) |
| total reuse (GPU + CPU), steady | 0.913 (0.909-0.916) | 0.912 (0.905-0.919) | 0.911 (0.909-0.913) |
| GPU / CPU / total, whole window | 0.299 (0.292-0.311) / 0.595 (0.582-0.603) / 0.894 (0.893-0.895) | 0.800 (0.792-0.808) / 0.092 (0.086-0.100) / 0.892 (0.887-0.897) | 0.296 (0.294-0.298) / 0.598 (0.596-0.600) / 0.894 (0.893-0.895) |
| prefill tokens computed (M) | 8.6 (8.5-8.7) | 8.7 (8.5-8.9) | 8.6 (8.6-8.7) |
| prefill tok/s (k) | 4.8 (4.7-4.8) | 4.8 (4.7-5.0) | 4.8 (4.8-4.8) |
| TTFT p50 / p90 / p99 (s) | 4.9 (4.6-5.1) / 21.5 (19.8-22.7) / 35.1 (34.2-36.9) | 0.5 (0.5-0.5) / 4.9 (4.5-5.2) / 198.4 (163.0-247.8) | 5.3 (5.1-5.5) / 21.7 (21.2-22.6) / 36.2 (34.9-37.0) |
| E2E latency p50 / p90 (s) | 28.2 (27.8-28.6) / 103.3 (102.2-104.3) | 20.4 (20.0-20.6) / 101.9 (101.1-102.3) | 28.9 (28.5-29.2) / 104.0 (101.6-106.4) |
| vLLM running / waiting, mean steady | 22.3 (21.9-22.6) / 5.4 (5.1-5.7) | 21.2 (21.0-21.4) / 0.1 (0.1-0.2) | 21.7 (21.0-22.4) / 5.5 (5.2-5.9) |
| vLLM GPU KV usage, mean steady | 0.85 (0.83-0.86) | 0.78 (0.77-0.78) | 0.83 (0.80-0.86) |
| vLLM preemptions | 207 (143-310) | 32 (7-67) | 159 (106-239) |
| CPU tier stored / loaded (GB) | 428 (425-430) / 2383 (2277-2444) | 444 (434-453) / 364 (334-400) | 429 (425-431) / 2382 (2339-2414) |
| CPU tier load time (s) / allocation failures | 114 (88-165) / 0 (0-0) | 18 (12-29) / 0 (0-0) | 115 (87-169) / 0 (0-0) |
| working set, mean steady (M tokens) | 2.51 (2.50-2.53) | 2.57 (2.51-2.61) | 2.51 (2.51-2.52) |
| working set / GPU KV / CPU tier | 1.12 (1.12-1.13) / 0.29 (0.29-0.29) | 1.15 (1.12-1.17) / 0.29 (0.29-0.30) | 1.12 (1.12-1.13) / 0.29 (0.29-0.29) |
| gate capacity (M tokens) | - | 2.24 (2.24-2.24) | 8.74 (8.74-8.74) |
| gate working set / capacity, mean steady | - | 0.99 (0.99-1.00) | 0.40 (0.40-0.41) |
| gate holds / pauses / forced admissions | 0 (0-0) / 0 (0-0) / 0 (0-0) | 81 (73-86) / 105 (94-112) / 0 (0-0) | 0 (0-0) / 0 (0-0) / 0 (0-0) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.47 (0.46-0.48) | 0.50 (0.49-0.51) | 0.47 (0.46-0.49) |
| session SLO attainment, strict | 0.48 (0.43-0.52) | 0.53 (0.50-0.56) | 0.50 (0.40-0.59) |
| per-session worst TTFT, p90 (s) | 39 (35-41) | 711 (665-757) | 44 (41-46) |

## Phase B, c=64 (offload 400 GiB, window 30 min, warm-up 10 min)

Runs: `rep-20260930-014820-c64-t1900`, `rep-20261001-154127-c64-t1900`, `rep-20261001-193521-c64-t1900`.

| metric | llm-d default (n=3) | lease, GPU capacity (n=3) | lease, CPU-tier capacity (n=3) |
|---|---|---|---|
| pods (node) | 91qy, trwg, zhnf | zhnf, 91qy, trwg | trwg, zhnf, 91qy |
| output throughput (tok/s) | 565 (545-584) | 636 (627-643) | 566 (538-585) |
| requests completed / errors | 1363 (1342-1376) / 0 (0-0) | 1535 (1497-1558) / 0 (0-0) | 1365 (1334-1384) / 0 (0-0) |
| sessions ended in window / turns not issued at stage end | 5 (4-5) / 0 (0-0) | 7 (6-9) / 0 (0-0) | 5 (5-5) / 0 (0-0) |
| GPU hit rate, steady | 0.005 (0.004-0.005) | 0.700 (0.679-0.712) | 0.005 (0.005-0.005) |
| CPU hit rate, steady | 0.916 (0.914-0.917) | 0.176 (0.163-0.202) | 0.916 (0.916-0.917) |
| total reuse (GPU + CPU), steady | 0.921 (0.919-0.922) | 0.876 (0.872-0.881) | 0.921 (0.921-0.922) |
| GPU / CPU / total, whole window | 0.003 (0.003-0.003) / 0.870 (0.868-0.871) / 0.873 (0.871-0.874) | 0.688 (0.672-0.697) / 0.162 (0.150-0.183) / 0.850 (0.846-0.855) | 0.003 (0.003-0.003) / 0.870 (0.869-0.871) / 0.873 (0.872-0.874) |
| prefill tokens computed (M) | 10.6 (10.5-10.6) | 12.3 (11.9-12.8) | 10.6 (10.3-10.7) |
| prefill tok/s (k) | 5.9 (5.8-5.9) | 6.8 (6.6-7.1) | 5.9 (5.7-5.9) |
| TTFT p50 / p90 / p99 (s) | 45.1 (44.6-45.6) / 80.7 (78.9-82.0) / 102.4 (101.0-104.4) | 0.6 (0.6-0.6) / 22.5 (17.7-29.3) / 808.6 (647.3-916.7) | 43.8 (43.5-44.1) / 80.1 (78.1-81.4) / 98.7 (95.2-103.3) |
| E2E latency p50 / p90 (s) | 74.8 (74.3-75.5) / 148.1 (145.7-150.2) | 22.7 (22.1-23.0) / 138.3 (131.6-146.0) | 74.9 (74.3-75.9) / 145.6 (144.3-148.1) |
| vLLM running / waiting, mean steady | 23.7 (23.0-24.7) / 30.8 (30.1-32.0) | 25.9 (24.6-26.9) / 0.3 (0.2-0.3) | 23.5 (23.2-23.8) / 30.3 (29.9-30.5) |
| vLLM GPU KV usage, mean steady | 0.85 (0.83-0.89) | 0.82 (0.79-0.84) | 0.85 (0.83-0.86) |
| vLLM preemptions | 252 (176-335) | 94 (67-135) | 280 (238-331) |
| CPU tier stored / loaded (GB) | 521 (520-522) / 3585 (3528-3618) | 641 (632-653) / 680 (618-791) | 522 (515-526) / 3591 (3503-3642) |
| CPU tier load time (s) / allocation failures | 173 (131-255) / 0 (0-0) | 32 (23-45) / 0 (0-0) | 172 (132-253) / 0 (0-0) |
| working set, mean steady (M tokens) | 4.56 (4.51-4.63) | 3.61 (3.21-3.82) | 4.56 (4.46-4.62) |
| working set / GPU KV / CPU tier | 2.04 (2.01-2.07) / 0.52 (0.52-0.53) | 1.61 (1.43-1.71) / 0.41 (0.37-0.44) | 2.04 (1.99-2.07) / 0.52 (0.51-0.53) |
| gate capacity (M tokens) | - | 2.24 (2.24-2.24) | 8.74 (8.74-8.74) |
| gate working set / capacity, mean steady | - | 0.99 (0.99-1.00) | 0.60 (0.59-0.60) |
| gate holds / pauses / forced admissions | 0 (0-0) / 0 (0-0) / 0 (0-0) | 193 (181-199) / 246 (233-253) / 1 (0-1) | 0 (0-0) / 0 (0-0) / 0 (0-0) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.00 (0.00-0.00) | 0.58 (0.56-0.59) | 0.00 (0.00-0.00) |
| session SLO attainment, strict | 0.00 (0.00-0.00) | 0.44 (0.41-0.49) | 0.00 (0.00-0.00) |
| per-session worst TTFT, p90 (s) | 105 (103-107) | 797 (645-899) | 101 (97-106) |

## Phase B, c=128 (offload 400 GiB, window 30 min, warm-up 10 min)

Runs: `rep-20260930-022937-c128-t1900`, `rep-20261001-162102-c128-t1900`, `rep-20261001-201532-c128-t1900`.

| metric | llm-d default (n=3) | lease, GPU capacity (n=3) | lease, CPU-tier capacity (n=3) |
|---|---|---|---|
| pods (node) | zhnf, 91qy, trwg | trwg, zhnf, 91qy | 91qy, trwg, zhnf |
| output throughput (tok/s) | 567 (561-578) | 635 (624-649) | 579 (568-585) |
| requests completed / errors | 1533 (1519-1555) / 0 (0-0) | 1623 (1620-1625) / 2 (0-4) | 1557 (1532-1573) / 0 (0-0) |
| sessions ended in window / turns not issued at stage end | - / - | 3 (2-5) / 0 (0-0) | - / - |
| GPU hit rate, steady | 0.002 (0.002-0.002) | 0.686 (0.641-0.719) | 0.002 (0.002-0.002) |
| CPU hit rate, steady | 0.853 (0.835-0.865) | 0.178 (0.147-0.219) | 0.872 (0.870-0.876) |
| total reuse (GPU + CPU), steady | 0.856 (0.837-0.867) | 0.865 (0.860-0.868) | 0.875 (0.872-0.878) |
| GPU / CPU / total, whole window | 0.002 (0.002-0.002) / 0.789 (0.776-0.800) / 0.791 (0.778-0.801) | 0.611 (0.579-0.627) / 0.202 (0.189-0.229) / 0.813 (0.807-0.816) | 0.002 (0.002-0.002) / 0.803 (0.799-0.808) / 0.805 (0.801-0.809) |
| prefill tokens computed (M) | 16.1 (15.6-17.1) | 14.7 (14.4-15.2) | 15.6 (15.5-15.7) |
| prefill tok/s (k) | 9.0 (8.6-9.5) | 8.2 (8.0-8.4) | 8.7 (8.6-8.7) |
| TTFT p50 / p90 / p99 (s) | 102.8 (102.1-103.9) / 193.0 (189.8-197.9) / 237.2 (212.2-262.3) | 1.1 (1.0-1.3) / 85.2 (81.5-90.7) / 1680.8 (1638.0-1708.9) | 103.5 (100.3-105.5) / 178.7 (173.2-181.9) / 201.8 (198.8-206.5) |
| E2E latency p50 / p90 (s) | 134.5 (132.5-137.3) / 238.7 (231.0-246.3) | 29.4 (28.8-29.9) / 190.9 (186.3-193.4) | 135.5 (134.0-138.5) / 224.5 (219.0-228.4) |
| vLLM running / waiting, mean steady | 28.7 (28.2-29.1) / 87.2 (83.4-89.5) | 26.6 (26.3-26.9) / 0.4 (0.3-0.4) | 28.0 (27.5-29.1) / 80.5 (78.4-84.4) |
| vLLM GPU KV usage, mean steady | 0.89 (0.86-0.91) | 0.80 (0.80-0.81) | 0.86 (0.84-0.90) |
| vLLM preemptions | 418 (403-444) | 210 (127-286) | 278 (265-304) |
| CPU tier stored / loaded (GB) | 831 (805-875) / 3162 (3089-3271) | 756 (750-764) / 805 (756-896) | 790 (786-796) / 3271 (3185-3334) |
| CPU tier load time (s) / allocation failures | 152 (112-226) / 0 (0-0) | 38 (28-55) / 0 (0-0) | 157 (120-230) / 0 (0-0) |
| working set, mean steady (M tokens) | 7.07 (6.92-7.15) | 4.07 (3.89-4.33) | 7.10 (7.03-7.18) |
| working set / GPU KV / CPU tier | 3.16 (3.10-3.20) / 0.81 (0.79-0.82) | 1.82 (1.74-1.94) / 0.47 (0.45-0.50) | 3.18 (3.14-3.21) / 0.81 (0.80-0.82) |
| gate capacity (M tokens) | - | 2.24 (2.24-2.24) | 8.74 (8.74-8.74) |
| gate working set / capacity, mean steady | - | 1.04 (1.00-1.11) | 0.96 (0.95-0.96) |
| gate holds / pauses / forced admissions | 0 (0-0) / 0 (0-0) / 0 (0-0) | 218 (214-223) / 304 (293-317) / 18 (15-20) | 30 (29-31) / 41 (39-43) / 0 (0-0) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.00 (0.00-0.00) | 0.60 (0.58-0.62) | 0.00 (0.00-0.00) |
| session SLO attainment, strict | 0.00 (0.00-0.00) | 0.44 (0.39-0.47) | 0.00 (0.00-0.00) |
| per-session worst TTFT, p90 (s) | 242 (216-272) | 577 (542-621) | 203 (200-208) |

## Phase B, c=192 (offload 400 GiB, window 45 min, warm-up 15 min)

Runs: `rep-20260930-031014-c192-t1900`, `rep-20261001-170100-c192-t1900`, `rep-20261001-205538-c192-t1900`.

| metric | llm-d default (n=3) | lease, GPU capacity (n=3) | lease, CPU-tier capacity (n=3) |
|---|---|---|---|
| pods (node) | trwg, zhnf, 91qy | 91qy, trwg, zhnf | zhnf, 91qy, trwg |
| output throughput (tok/s) | 366 (361-370) | 551 (535-560) | 569 (564-576) |
| requests completed / errors | 1582 (1572-1590) / 0 (0-1) | 2202 (2187-2221) / 30 (22-42) | 2194 (2156-2228) / 23 (20-26) |
| sessions ended in window / turns not issued at stage end | 1 / 0 | 33 (25-45) / 0 (0-0) | 19 (17-23) / 0 (0-0) |
| GPU hit rate, steady | 0.000 (0.000-0.000) | 0.470 (0.450-0.496) | 0.001 (0.001-0.002) |
| CPU hit rate, steady | 0.093 (0.073-0.110) | 0.274 (0.247-0.312) | 0.808 (0.795-0.818) |
| total reuse (GPU + CPU), steady | 0.093 (0.073-0.110) | 0.744 (0.710-0.762) | 0.809 (0.797-0.819) |
| GPU / CPU / total, whole window | 0.000 (0.000-0.000) / 0.267 (0.248-0.280) / 0.268 (0.248-0.280) | 0.454 (0.428-0.472) / 0.270 (0.240-0.308) / 0.724 (0.703-0.737) | 0.001 (0.001-0.002) / 0.735 (0.723-0.745) / 0.736 (0.724-0.745) |
| prefill tokens computed (M) | 52.8 (52.0-53.7) | 27.1 (26.7-27.8) | 27.7 (27.1-28.3) |
| prefill tok/s (k) | 19.6 (19.3-19.9) | 10.0 (9.9-10.3) | 10.3 (10.0-10.5) |
| TTFT p50 / p90 / p99 (s) | 230.9 (226.3-235.5) / 457.5 (445.9-467.3) / 505.1 (503.2-508.5) | 2.9 (2.7-3.1) / 293.3 (253.5-318.6) / 1834.7 (1830.8-1836.9) | 152.3 (148.2-156.1) / 205.3 (187.1-217.9) / 304.9 (288.2-336.7) |
| E2E latency p50 / p90 (s) | 273.2 (266.1-277.5) / 540.3 (536.3-547.1) | 42.3 (40.7-45.1) / 347.6 (317.2-370.2) | 186.1 (181.2-192.5) / 287.6 (278.5-296.7) |
| vLLM running / waiting, mean steady | 32.0 (31.2-33.0) / 144.7 (142.4-148.8) | 28.0 (27.4-28.4) / 3.4 (3.1-4.0) | 30.5 (29.9-30.9) / 99.8 (96.1-102.1) |
| vLLM GPU KV usage, mean steady | 0.89 (0.88-0.92) | 0.82 (0.82-0.83) | 0.88 (0.85-0.90) |
| vLLM preemptions | 297 (166-443) | 252 (184-318) | 451 (265-565) |
| CPU tier stored / loaded (GB) | 2696 (2654-2740) / 994 (915-1044) | 1487 (1426-1572) / 1446 (1254-1656) | 1388 (1363-1413) / 3880 (3722-4005) |
| CPU tier load time (s) / allocation failures | 49 (33-76) / 0 (0-0) | 73 (46-120) / 0 (0-0) | 189 (135-290) / 0 (0-0) |
| working set, mean steady (M tokens) | 9.35 (9.31-9.39) | 7.42 (7.17-7.59) | 9.16 (9.08-9.25) |
| working set / GPU KV / CPU tier | 4.18 (4.16-4.20) / 1.07 (1.07-1.08) | 3.32 (3.20-3.39) / 0.85 (0.82-0.87) | 4.09 (4.06-4.13) / 1.05 (1.04-1.06) |
| gate capacity (M tokens) | - | 2.24 (2.24-2.24) | 8.74 (8.74-8.74) |
| gate working set / capacity, mean steady | - | 1.09 (1.07-1.11) | 1.00 (1.00-1.00) |
| gate holds / pauses / forced admissions | 0 (0-0) / 0 (0-0) / 0 (0-0) | 409 (383-435) / 523 (483-551) / 111 (108-117) | 235 (226-244) / 320 (312-333) / 23 (20-27) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.00 (0.00-0.00) | 0.49 (0.47-0.51) | 0.00 (0.00-0.00) |
| session SLO attainment, strict | 0.00 (0.00-0.00) | 0.30 (0.23-0.34) | 0.00 (0.00-0.00) |
| per-session worst TTFT, p90 (s) | 504 (503-507) | 1001 (798-1244) | 250 (217-267) |

## Phase B, c=256 (offload 400 GiB, window 45 min, warm-up 15 min)

Runs: `rep-20260930-040640-c256-t1900`, `rep-20261001-175759-c256-t1900`, `rep-20261001-215239-c256-t1900`.

| metric | llm-d default (n=3) | lease, GPU capacity (n=3) | lease, CPU-tier capacity (n=3) |
|---|---|---|---|
| pods (node) | 91qy, trwg, zhnf | zhnf, 91qy, trwg | trwg, zhnf, 91qy |
| output throughput (tok/s) | 288 (286-292) | 516 (500-527) | 533 (530-535) |
| requests completed / errors | 1468 (1459-1474) / 0 (0-1) | 2233 (2179-2284) / 69 (64-77) | 2235 (2198-2285) / 69 (66-71) |
| sessions ended in window / turns not issued at stage end | 1 / 0 | 72 (66-80) / 0 (0-0) | 63 (61-67) / 0 (0-0) |
| GPU hit rate, steady | 0.000 (0.000-0.000) | 0.413 (0.388-0.441) | 0.001 (0.001-0.001) |
| CPU hit rate, steady | 0.000 (0.000-0.000) | 0.279 (0.256-0.307) | 0.770 (0.759-0.780) |
| total reuse (GPU + CPU), steady | 0.000 (0.000-0.000) | 0.692 (0.684-0.697) | 0.770 (0.760-0.781) |
| GPU / CPU / total, whole window | 0.000 (0.000-0.000) / 0.003 (0.001-0.005) / 0.003 (0.001-0.005) | 0.385 (0.358-0.402) / 0.288 (0.267-0.321) / 0.673 (0.669-0.680) | 0.001 (0.000-0.001) / 0.667 (0.661-0.674) / 0.668 (0.661-0.674) |
| prefill tokens computed (M) | 61.9 (61.3-62.2) | 29.3 (28.8-29.7) | 32.9 (32.2-34.0) |
| prefill tok/s (k) | 22.9 (22.7-23.0) | 10.8 (10.7-11.0) | 12.2 (11.9-12.6) |
| TTFT p50 / p90 / p99 (s) | 416.8 (415.0-418.1) / 551.9 (546.3-556.5) / 576.4 (568.1-588.7) | 7.3 (5.8-9.5) / 393.6 (340.6-430.4) / 1851.7 (1847.3-1856.7) | 161.7 (158.1-167.3) / 270.0 (262.5-274.4) / 653.2 (584.6-697.8) |
| E2E latency p50 / p90 (s) | 471.3 (467.0-477.4) / 644.8 (641.8-649.4) | 51.2 (50.1-52.3) / 469.4 (431.1-500.4) | 194.2 (185.5-202.0) / 351.1 (346.1-353.8) |
| vLLM running / waiting, mean steady | 36.4 (35.8-36.9) / 206.1 (202.1-208.4) | 29.0 (28.8-29.5) / 7.5 (7.3-7.9) | 31.3 (30.4-32.5) / 109.0 (105.2-112.4) |
| vLLM GPU KV usage, mean steady | 0.91 (0.90-0.93) | 0.83 (0.83-0.84) | 0.87 (0.85-0.89) |
| vLLM preemptions | 190 (151-220) | 321 (262-382) | 648 (562-781) |
| CPU tier stored / loaded (GB) | 3147 (3122-3163) / 16 (9-26) | 1681 (1663-1712) / 1479 (1375-1671) | 1641 (1599-1704) / 3328 (3193-3457) |
| CPU tier load time (s) / allocation failures | 1 (0-1) / 0 (0-0) | 71 (51-100) / 0 (0-0) | 161 (116-242) / 0 (0-0) |
| working set, mean steady (M tokens) | 11.09 (11.05-11.15) | 8.09 (7.70-8.53) | 10.60 (10.35-10.73) |
| working set / GPU KV / CPU tier | 4.96 (4.94-4.99) / 1.27 (1.26-1.28) | 3.62 (3.44-3.81) / 0.93 (0.88-0.98) | 4.74 (4.63-4.80) / 1.21 (1.18-1.23) |
| gate capacity (M tokens) | - | 2.24 (2.24-2.24) | 8.74 (8.74-8.74) |
| gate working set / capacity, mean steady | - | 1.20 (1.19-1.21) | 1.00 (1.00-1.00) |
| gate holds / pauses / forced admissions | 0 (0-0) / 0 (0-0) / 0 (0-0) | 491 (471-501) / 628 (622-637) / 163 (157-172) | 331 (325-336) / 463 (452-477) / 73 (71-77) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.00 (0.00-0.00) | 0.44 (0.41-0.46) | 0.00 (0.00-0.00) |
| session SLO attainment, strict | 0.00 (0.00-0.00) | 0.19 (0.19-0.19) | 0.00 (0.00-0.00) |
| per-session worst TTFT, p90 (s) | 571 (567-579) | 745 (669-785) | 305 (282-346) |
