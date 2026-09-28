# Step 16: minimal thunder-agent on the 4-pod pool, c=128, against step 13

Step 13 reference: `sweep-20260918-134248-t1900`. Cells: step 13 llm-d default: epp-baseline-c128, epp-baseline-c128-r2; step 13 v4 most-room: epp-thunder-c128, epp-thunder-c128-r2, epp-thunder-c128-r3; step 13 v4 origin-only: epp-thunder-origin-c128, epp-thunder-origin-c128-r2, epp-thunder-origin-c128-r3; step 16 thunder-min (half-life 1 s): epp-thunder-min-c128; step 16 thunder-min (half-life 10 s): epp-thunder-min-hl10-c128. Multi-cell columns are mean (min-max). The ratio columns compare each step 16 arm with step 13 origin-only (same placement policy) and say whether the value lies inside the origin-only min-max range.

| metric | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min (half-life 1 s) | step 16 thunder-min (half-life 10 s) | min / origin | min10 / origin |
|---|---|---|---|---|---|---|---|
| output throughput (tok/s) | 1154 (1151-1156) | 1370 (1362-1382) | 1693 (1571-1807) | 1752 | 1817 | 1.03x (in) | 1.07x (out) |
| requests completed | 3017 (3008-3026) | 3611 (3593-3641) | 4155 (4026-4289) | 4061 | 4472 | 0.98x (in) | 1.08x (out) |
| request errors | 0 (0-1) | 0 (0-1) | 0 (0-0) | 0 | 0 |  |  |
| turns not issued at stage end (inference-perf dropped_requests) | 0 (0-0) | 70 (0-209) | 0 (0-0) | 0 | 0 |  |  |
| sessions ended in window / failed | 13 (12-14) / 0 (0-1) | 24 (23-25) / 0 (0-1) | 30 (27-32) / 0 (0-0) | 28 / 0 | 32 / 0 |  |  |
| hit rate, whole window | 0.335 (0.335-0.336) | 0.469 (0.462-0.478) | 0.706 (0.670-0.744) | 0.708 | 0.762 | 1.00x (in) | 1.08x (out) |
| hit rate, warm-up (first 10 min) | 0.682 (0.671-0.693) | 0.675 (0.670-0.683) | 0.759 (0.739-0.787) | 0.738 | 0.809 | 0.97x (out) | 1.07x (out) |
| hit rate, steady state | 0.057 (0.040-0.073) | 0.347 (0.341-0.353) | 0.680 (0.629-0.722) | 0.691 | 0.733 | 1.02x (in) | 1.08x (out) |
| requests with zero cache hit | 0.58 (0.57-0.59) | 0.45 (0.45-0.46) | 0.24 (0.22-0.25) | 0.25 | 0.20 | 1.07x (out) | 0.86x (out) |
| prefill tokens computed (M) | 122.3 (121.9-122.7) | 116.6 (115.4-117.3) | 76.1 (69.0-83.2) | 75.4 | 67.5 | 0.99x (in) | 0.89x (out) |
| prompt tokens per request, mean (k) | 61.0 (61.0-61.1) | 60.9 (60.9-61.0) | 64.0 (63.9-64.1) | 64.2 | 64.3 | 1.00x (out) | 1.01x (out) |
| TTFT p50 / p90 / p99 (s) | 7.7 (7.3-8.2) / 33.9 (32.9-34.9) / 49.8 (49.8-49.9) | 2.4 (2.3-2.4) / 10.1 (9.9-10.2) / 77.7 (65.5-95.7) | 1.0 (0.6-1.3) / 11.4 (10.4-12.5) / 123.5 (102.4-136.9) | 0.9 / 10.4 / 149.4 | 0.6 / 8.2 / 129.0 |  |  |
| E2E latency p50 / p90 / p99 (s) | 44.9 (44.5-45.3) / 189.8 (188.8-190.7) / 562.7 (561.8-563.7) | 32.5 (32.0-33.4) / 157.4 (155.5-158.6) / 514.2 (499.3-527.9) | 25.7 (23.0-28.0) / 126.0 (122.7-130.2) / 455.9 (430.5-469.6) | 26.5 / 134.9 / 468.4 | 23.8 / 120.3 / 430.3 |  |  |
| TPOT p50 / p90 (ms) | 96 (95-97) / 160 (158-162) | 84 (83-85) / 129 (127-132) | 55 (44-65) / 102 (100-104) | 57 / 98 | 52 / 88 |  |  |
| ITL p50 / p90 (ms) | 98 (98-99) / 169 (169-170) | 86 (84-87) / 138 (137-139) | 57 (47-66) / 107 (107-108) | 60 / 103 | 53 / 92 |  |  |
| vLLM KV usage, mean steady / max | 0.69 (0.68-0.70) / 0.99 (0.99-0.99) | 0.63 (0.63-0.63) / 0.98 (0.97-0.98) | 0.57 (0.53-0.61) / 0.98 (0.97-0.98) | 0.64 / 0.98 | 0.65 / 0.99 |  |  |
| vLLM running, mean steady / max | 80 (79-81) / 134 (133-134) | 78 (77-78) / 135 (132-137) | 66 (60-70) / 125 (121-127) | 73 / 126 | 72 / 132 |  |  |
| vLLM waiting, mean steady / max | 14.8 (14.7-14.8) / 42.0 (39.0-45.0) | 1.1 (1.0-1.2) / 38.3 (31.0-50.0) | 0.6 (0.5-0.7) / 44.3 (44.0-45.0) | 1.2 / 81.0 | 1.4 / 63.0 |  |  |
| vLLM preemptions | 10 (9-11) | 4 (2-7) | 3 (1-4) | 9 | 10 | 3.38x (out) | 3.75x (out) |
| EPP undecayed working set / capacity, mean steady | - | 0.84 (0.81-0.89) | 0.77 (0.74-0.79) | 0.98 | 0.99 | 1.27x (out) | 1.29x (out) |
| EPP decayed working set / capacity, mean steady | - | - | - | 0.68 | 0.70 |  |  |
| share of samples with working set over capacity | - | 0.11 (0.10-0.13) | 0.09 (0.06-0.16) | 0.28 | 0.26 | 2.99x (out) | 2.75x (out) |
| EPP sessions running / idle / paused, mean | - / - / - | 24 (23-26) / 8 (7-10) / 42 (40-43) | 29 (27-30) / 10 (9-11) / 56 (51-62) | 73 / 21 / 38 | 74 / 22 / 40 |  |  |
| EPP max sessions paused at once | - | 120 (115-126) | 129 (126-133) | 73 | 74 | 0.57x (out) | 0.58x (out) |
| EPP releases reasoning / paused / new | 0 (0-0) / 0 (0-0) / 0 (0-0) | 1694 (1668-1713) / 1776 (1738-1797) / 152 (151-153) | 2513 (2141-2880) / 1524 (1285-1769) / 158 (155-160) | 3505 / 422 / 156 | 4027 / 317 / 160 |  |  |
| EPP holds paused / new | 0 (0-0) / 0 (0-0) | 710 (697-721) / 1 (0-2) | 971 (836-1079) / 0 (0-0) | 349 / 0 | 263 / 2 |  |  |
| EPP pauses / resumes | - / - | 1896 (1858-1919) / 1776 (1738-1797) | 1653 (1417-1895) / 1524 (1284-1769) | 495 / 422 | 391 / 317 |  |  |
| EPP forced admissions | - | 0 (0-0) | 0 (0-1) | 0 | 0 | 0.00x (in) | 0.00x (in) |
| EPP mean queue wait (s) | - | - | - | - | - |  |  |
| EPP max queue size | - | 45 (44-46) | 66 (60-72) | 33 | 36 | 0.50x (out) | 0.55x (out) |
| EPP CPU cores, mean / max | 1.59 (1.57-1.60) / 9.59 (8.63-10.55) | 2.10 (2.06-2.14) / 10.06 (9.70-10.46) | 2.21 (2.13-2.29) / 10.12 (9.30-10.62) | 1.94 / 7.55 | 1.88 / 7.68 |  |  |
| pod KV usage, steady mean, min-max over pods | 0.68 (0.67-0.69) / 0.70 (0.69-0.70) | 0.62 (0.62-0.63) / 0.64 (0.63-0.64) | 0.55 (0.51-0.60) / 0.60 (0.56-0.62) | 0.62 / 0.67 | 0.61 / 0.67 |  |  |
| pod running requests, steady mean, min-max over pods | 18.8 (18.8-18.9) / 21.1 (20.9-21.4) | 18.8 (18.6-19.0) / 20.1 (20.0-20.1) | 13.8 (13.2-15.0) / 20.7 (20.1-22.0) | 14.8 / 22.7 | 16.3 / 19.5 |  |  |
| pod steady hit rate, min-max over pods | 0.006 (0.002-0.010) / 0.117 (0.096-0.138) | 0.291 (0.272-0.301) / 0.401 (0.392-0.415) | 0.532 (0.489-0.573) / 0.802 (0.709-0.857) | 0.557 / 0.813 | 0.637 / 0.829 |  |  |
| pod undecayed working set / capacity, min-max over pods | - / - | - / - | - / - | 0.97 / 1.00 | 0.98 / 1.01 |  |  |
| sessions in the steady-state population | 138 | 150 (149-150) | 146 (140-151) | 149 | 156 | 1.02x (in) | 1.07x (out) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.57 | 1.28 (1.27-1.29) | 1.53 (1.53-1.53) | 1.50 | 1.63 | 0.98x (out) | 1.07x (out) |
| session SLO attainment, strict / lenient | 0.08 / 0.08 | 0.76 (0.75-0.77) / 0.78 (0.77-0.79) | 0.70 (0.69-0.72) / 0.75 (0.73-0.76) | 0.64 / 0.69 | 0.58 / 0.65 |  |  |
| turns per session after warm-up, p10 / p50 / p90 | 3 / 8 / 16 | 2 (2-2) / 10 (10-11) / 22 (22-23) | 3 (3-3) / 13 (12-14) / 28 (27-29) | 2 / 12 / 28 | 4 / 12 / 30 |  |  |
| share of turns over the SLO | 0.380 | 0.033 (0.030-0.036) | 0.037 (0.036-0.037) | 0.037 | 0.035 | 1.00x (in) | 0.95x (out) |
| per-session worst TTFT, p90 (s) | 52 | 167 (167-168) | 261 (219-302) | 268 | 319 | 1.03x (in) | 1.22x (out) |
| sessions whose worst turn exceeded 60 s | 0.02 | 0.14 (0.13-0.14) | 0.21 (0.21-0.21) | 0.23 | 0.28 | 1.11x (out) | 1.37x (out) |
