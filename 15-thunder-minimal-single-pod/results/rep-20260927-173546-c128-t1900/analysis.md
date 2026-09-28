# Step 15: minimal thunder-agent on one pod, against step 10

step 15 cells: epp-thunder-min-r1; step 10 reference: `rep-20260917-173839-c128-t1900` (sticky and thunder v3, three lanes each). Step 10 columns are mean (min-max). The last column is thunder-min / thunder v3 of the means, and whether the thunder-min value lies inside the v3 min-max range.

| metric | step 10 sticky | step 10 thunder v3 | step 15 thunder-min | min / v3 |
|---|---|---|---|---|
| output throughput (tok/s) | 227 (221-236) | 351 (327-367) | 397 | 1.13x (out) |
| requests completed | 979 (965-987) | 1398 (1319-1469) | 1580 | 1.13x (out) |
| request errors | 0 (0-0) | 6 (5-6) | 1 | 0.18x (out) |
| turns not issued at stage end (inference-perf dropped_requests) | 5549 | 7665 (4771-9247) | 8953 | 1.17x (in) |
| sessions ended in window / failed | 5 / 0 | 11 (9-13) / 4 (3-5) | 11 / 1 |  |
| hit rate, whole window | 0.066 (0.030-0.111) | 0.486 (0.460-0.506) | 0.575 | 1.18x (out) |
| hit rate, warm-up (first 10 min) | 0.225 (0.110-0.373) | 0.470 (0.372-0.521) | 0.582 | 1.24x (out) |
| hit rate, steady state | 0.003 (0.002-0.003) | 0.489 (0.482-0.502) | 0.573 | 1.17x (out) |
| requests with zero cache hit | 0.86 (0.83-0.89) | 0.38 (0.36-0.41) | 0.33 | 0.87x (out) |
| prefill tokens computed (M) | 53.6 (52.0-55.1) | 41.5 (40.9-42.8) | 38.5 | 0.93x (out) |
| prompt tokens per request, mean (k) | 58.8 (57.8-59.5) | 59.1 (57.7-61.0) | 58.5 | 0.99x (in) |
| TTFT p50 / p90 / p99 (s) | 49.4 (28.4-68.6) / 113.5 (88.2-136.6) / 146.6 (117.8-168.3) | 4.0 (3.6-4.6) / 22.0 (19.8-24.1) / 409.7 (352.9-462.7) | 2.2 / 15.0 / 712.4 |  |
| E2E latency p50 / p90 / p99 (s) | 106.1 (87.3-125.1) / 262.8 (247.6-273.6) / 689.9 (682.4-704.6) | 38.8 (38.3-39.3) / 170.8 (157.3-181.6) / 655.7 (635.2-674.6) | 33.9 / 157.3 / 832.3 |  |
| TPOT p50 / p90 (ms) | 133 (132-136) / 183 (172-203) | 85 (83-88) / 128 (122-132) | 74 / 112 |  |
| ITL p50 / p90 (ms) | 136 (135-138) / 194 (183-211) | 87 (85-90) / 139 (133-146) | 75 / 119 |  |
| vLLM KV usage, mean steady / max | 0.92 (0.92-0.92) / 1.00 (1.00-1.00) | 0.89 (0.89-0.90) / 1.00 (1.00-1.00) | 0.90 / 1.00 |  |
| vLLM running, mean steady / max | 28 (28-29) / 44 (40-48) | 29 (28-30) / 43 (41-45) | 28 / 45 |  |
| vLLM waiting, mean steady / max | 20.4 (14.1-26.2) / 34.3 (32.0-38.0) | 0.3 (0.3-0.4) / 34.0 (30.0-38.0) | 0.5 / 30.0 |  |
| vLLM preemptions | 8 (5-12) | 1 (0-3) | 6 | 4.50x (out) |
| EPP undecayed working set / capacity, mean steady | - | 0.97 (0.96-0.99) | 1.01 | 1.04x (out) |
| EPP decayed working set / capacity, mean steady | - | - | 0.94 |  |
| share of samples with working set over capacity | - | 0.24 (0.23-0.26) | 0.65 | 2.72x (out) |
| EPP sessions running / idle / paused, mean | - / - / - | 8 (7-8) / 1 (0-1) / 24 (20-27) | 28 / 2 / 20 |  |
| EPP max sessions paused at once | 0 (0-0) | 50 (42-57) | 34 | 0.68x (out) |
| EPP releases reasoning / paused / new | 0 (0-0) / 0 (0-0) / 0 (0-0) | 454 (421-517) / 921 (886-953) / 62 (60-63) | 1235 / 311 / 56 |  |
| EPP holds paused / new | 0 (0-0) / 0 (0-0) | 645 (613-671) / 3 (2-4) | 263 / 2 |  |
| EPP pauses / resumes | 0 (0-0) / 0 (0-0) | 971 (938-1009) / 921 (886-952) | 345 / 311 |  |
| EPP forced admissions | 0 (0-0) | 10 (8-11) | 7 | 0.72x (out) |
| EPP mean queue wait (s) | - | 8.0 (3.6-13.6) | 12.5 | 1.57x (in) |
| EPP max queue size | 0 (0-0) | 50 (40-60) | 22 | 0.44x (out) |
| EPP CPU cores, mean / max | 0.86 (0.84-0.88) / 7.61 (7.03-7.94) | 1.05 (1.01-1.07) / 7.38 (6.44-7.88) | 0.90 / 3.87 |  |
