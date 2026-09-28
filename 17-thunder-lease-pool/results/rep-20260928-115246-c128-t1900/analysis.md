# Step 17: lease thunder-agent on the 4-pod pool, c=128, against step 16

Step 16 reference: `rep-20260927-195200-c128-t1900`. Cells: step 16 thunder-min (half-life 1 s): epp-thunder-min-c128, epp-thunder-min-c128-r2, epp-thunder-min-c128-r3; step 16 thunder-min (half-life 10 s): epp-thunder-min-hl10-c128, epp-thunder-min-hl10-c128-r2, epp-thunder-min-hl10-c128-r3; step 16 thunder-min (half-life 10 s, sweep 1 s): epp-thunder-min-hl10-s1-c128, epp-thunder-min-hl10-s1-c128-r2, epp-thunder-min-hl10-s1-c128-r3; step 17 thunder-lease (lease 30 s): epp-thunder-lease-c128; step 17 thunder-lease (lease 5 s): epp-thunder-lease5-c128. Multi-cell columns are mean (min-max). The ratio columns compare each step 17 arm with step 16's half-life 10 s, sweep 1 s arm and say whether the value lies inside that arm's min-max range. For the lease build the undecayed working set row is its only working-set view.

| metric | step 16 thunder-min (half-life 1 s) | step 16 thunder-min (half-life 10 s) | step 16 thunder-min (half-life 10 s, sweep 1 s) | step 17 thunder-lease (lease 30 s) | step 17 thunder-lease (lease 5 s) | lease / min10s1 | lease5 / min10s1 |
|---|---|---|---|---|---|---|---|
| output throughput (tok/s) | 1770 (1752-1790) | 1846 (1817-1884) | 1945 (1867-2019) | 1871 | 1863 | 0.96x (in) | 0.96x (out) |
| requests completed | 4144 (4061-4188) | 4419 (4356-4472) | 4590 (4471-4776) | 4313 | 4416 | 0.94x (out) | 0.96x (out) |
| request errors | 0 (0-1) | 0 (0-1) | 0 (0-1) | 0 | 0 | 0.00x (in) | 0.00x (in) |
| turns not issued at stage end (inference-perf dropped_requests) | 0 (0-0) | 0 (0-0) | 0 (0-0) | 0 | 0 |  |  |
| sessions ended in window / failed | 30 (28-32) / 0 (0-1) | 30 (29-32) / 0 (0-1) | 36 (28-41) / 0 (0-1) | 29 / 0 | 32 / 0 |  |  |
| hit rate, whole window | 0.717 (0.708-0.736) | 0.766 (0.762-0.773) | 0.790 (0.766-0.804) | 0.780 | 0.778 | 0.99x (in) | 0.98x (in) |
| hit rate, warm-up (first 10 min) | 0.733 (0.718-0.744) | 0.798 (0.775-0.811) | 0.782 (0.774-0.794) | 0.784 | 0.800 | 1.00x (in) | 1.02x (out) |
| hit rate, steady state | 0.708 (0.688-0.744) | 0.746 (0.733-0.756) | 0.795 (0.752-0.820) | 0.778 | 0.766 | 0.98x (in) | 0.96x (in) |
| requests with zero cache hit | 0.25 (0.25-0.25) | 0.20 (0.19-0.21) | 0.20 (0.19-0.20) | 0.20 | 0.20 | 1.02x (in) | 1.00x (in) |
| prefill tokens computed (M) | 74.1 (70.7-76.2) | 66.2 (64.1-67.5) | 60.7 (57.4-65.3) | 62.0 | 63.3 | 1.02x (in) | 1.04x (in) |
| prompt tokens per request, mean (k) | 64.1 (63.2-65.1) | 64.6 (64.3-64.9) | 64.3 (63.7-64.7) | 65.6 | 65.3 | 1.02x (out) | 1.02x (out) |
| TTFT p50 / p90 / p99 (s) | 0.8 (0.7-0.9) / 10.1 (9.1-10.8) / 154.2 (113.4-199.8) | 0.6 (0.5-0.6) / 8.5 (8.2-8.7) / 130.8 (126.1-137.3) | 0.5 (0.5-0.5) / 7.0 (6.3-8.0) / 140.6 (119.4-173.2) | 0.5 / 8.5 / 227.4 | 0.6 / 8.6 / 163.8 |  |  |
| E2E latency p50 / p90 / p99 (s) | 24.7 (22.7-26.5) / 128.2 (121.6-134.9) / 445.9 (420.7-468.4) | 24.2 (23.6-25.1) / 120.2 (117.5-122.9) / 456.6 (430.3-471.6) | 22.2 (21.5-23.4) / 113.2 (108.5-118.0) / 415.7 (409.6-422.7) | 22.5 / 121.9 / 498.0 | 23.6 / 121.0 / 460.0 |  |  |
| TPOT p50 / p90 (ms) | 52 (45-57) / 104 (98-109) | 52 (51-53) / 85 (83-88) | 49 (47-53) / 81 (81-82) | 48 / 86 | 51 / 81 |  |  |
| ITL p50 / p90 (ms) | 54 (47-60) / 109 (103-115) | 53 (52-55) / 92 (91-93) | 51 (49-54) / 88 (87-88) | 50 / 92 | 52 / 87 |  |  |
| vLLM KV usage, mean steady / max | 0.62 (0.58-0.66) / 0.97 (0.95-0.98) | 0.66 (0.65-0.66) / 0.99 (0.98-0.99) | 0.63 (0.59-0.66) / 0.99 (0.99-1.00) | 0.63 / 0.98 | 0.64 / 0.99 |  |  |
| vLLM running, mean steady / max | 70 (65-74) / 125 (117-131) | 72 (72-72) / 131 (129-132) | 70 (68-72) / 128 (125-131) | 68 / 128 | 70 / 124 |  |  |
| vLLM waiting, mean steady / max | 1.2 (1.2-1.2) / 76.0 (71.0-81.0) | 1.2 (1.1-1.4) / 62.0 (59.0-64.0) | 0.7 (0.6-1.0) / 62.3 (58.0-68.0) | 1.2 / 55.0 | 0.9 / 68.0 |  |  |
| vLLM preemptions | 9 (5-12) | 8 (6-10) | 7 (5-8) | 7 | 10 | 1.05x (in) | 1.50x (out) |
| EPP undecayed working set / capacity, mean steady | 0.98 (0.97-0.98) | 0.99 (0.98-0.99) | 0.97 (0.96-0.98) | 0.97 | 0.98 | 1.01x (in) | 1.02x (out) |
| EPP decayed working set / capacity, mean steady | 0.66 (0.60-0.69) | 0.70 (0.70-0.70) | 0.67 (0.63-0.70) | 0.00 | 0.00 | 0.00x (out) | 0.00x (out) |
| share of samples with working set over capacity | 0.20 (0.06-0.28) | 0.25 (0.24-0.26) | 0.04 (0.01-0.07) | 0.17 | 0.06 | 4.29x (out) | 1.61x (in) |
| EPP sessions running / idle / paused, mean | 72 (67-76) / 22 (20-25) / 40 (37-44) | 74 (73-74) / 21 (20-22) / 40 (38-42) | 71 (70-73) / 21 (19-24) / 45 (41-48) | 69 / 23 / 38 | 72 / 20 / 43 |  |  |
| EPP max sessions paused at once | 74 (73-76) | 74 (69-79) | 84 (79-87) | 66 | 79 | 0.79x (out) | 0.94x (in) |
| EPP releases reasoning / paused / new | 3601 (3505-3707) / 411 (350-460) / 158 (156-160) | 3963 (3874-4027) / 324 (308-348) / 158 (157-160) | 4013 (3861-4184) / 449 (403-493) / 164 (156-169) | 3930 / 242 / 157 | 3884 / 396 / 160 |  |  |
| EPP holds paused / new | 342 (295-381) / 0 (0-1) | 280 (263-312) / 2 (0-3) | 365 (331-397) / 0 (0-0) | 225 / 2 | 361 / 1 |  |  |
| EPP pauses / resumes | 485 (423-536) / 411 (350-460) | 398 (386-417) / 324 (308-348) | 532 (487-572) / 448 (402-493) | 308 / 0 | 475 / 0 |  |  |
| EPP forced admissions | 0 (0-1) | 0 (0-0) | 0 (0-0) | 0 | 0 |  |  |
| EPP mean queue wait (s) | - | - | - | - | - |  |  |
| EPP max queue size | 34 (31-38) | 36 (34-38) | 36 (35-37) | 38 | 34 | 1.05x (out) | 0.94x (out) |
| EPP CPU cores, mean / max | 1.92 (1.90-1.94) / 8.20 (7.55-8.98) | 1.92 (1.88-1.96) / 8.19 (7.68-8.60) | 1.94 (1.92-1.97) / 8.28 (7.75-8.98) | 2.06 / 7.88 | 1.94 / 8.07 |  |  |
| pod KV usage, steady mean, min-max over pods | 0.57 (0.48-0.62) / 0.68 (0.67-0.69) | 0.64 (0.61-0.65) / 0.67 (0.66-0.67) | 0.58 (0.52-0.63) / 0.67 (0.64-0.68) | 0.59 / 0.66 | 0.63 / 0.65 |  |  |
| pod running requests, steady mean, min-max over pods | 14.1 (12.2-15.4) / 21.9 (21.1-22.7) | 16.4 (15.6-17.2) / 19.8 (19.3-20.6) | 15.1 (13.3-17.5) / 19.7 (18.8-20.4) | 14.0 / 20.0 | 14.8 / 20.9 |  |  |
| pod steady hit rate, min-max over pods | 0.499 (0.395-0.557) / 0.848 (0.801-0.931) | 0.676 (0.637-0.696) / 0.820 (0.798-0.834) | 0.716 (0.705-0.730) / 0.848 (0.780-0.883) | 0.682 / 0.862 | 0.738 / 0.801 |  |  |
| pod undecayed working set / capacity, min-max over pods | 0.95 (0.94-0.97) / 1.00 (1.00-1.01) | 0.98 (0.97-0.98) / 1.00 (0.98-1.01) | 0.95 (0.93-0.96) / 0.98 (0.97-0.99) | 0.96 / 0.99 | 0.98 / 0.99 |  |  |
| sessions in the steady-state population | 150 (149-152) | 154 (153-156) | 154 (150-158) | 150 | 156 | 0.97x (in) | 1.01x (in) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 1.55 (1.50-1.60) | 1.62 (1.57-1.66) | 1.77 (1.64-1.94) | 1.60 | 1.69 | 0.90x (out) | 0.95x (in) |
| session SLO attainment, strict / lenient | 0.68 (0.64-0.72) / 0.72 (0.69-0.76) | 0.55 (0.53-0.58) / 0.61 (0.59-0.65) | 0.64 (0.57-0.70) / 0.69 (0.65-0.72) | 0.61 / 0.67 | 0.60 / 0.65 |  |  |
| turns per session after warm-up, p10 / p50 / p90 | 2 (2-3) / 12 (12-12) / 28 (25-30) | 4 (4-4) / 13 (12-13) / 28 (26-30) | 3 (2-4) / 14 (13-14) / 31 (29-33) | 3 / 13 / 28 | 3 / 13 / 29 |  |  |
| share of turns over the SLO | 0.035 (0.030-0.038) | 0.040 (0.035-0.043) | 0.032 (0.027-0.042) | 0.034 | 0.037 | 1.03x (in) | 1.13x (in) |
| per-session worst TTFT, p90 (s) | 256 (245-268) | 412 (319-459) | 275 (226-367) | 435 | 386 | 1.58x (out) | 1.40x (out) |
| sessions whose worst turn exceeded 60 s | 0.22 (0.21-0.23) | 0.31 (0.28-0.33) | 0.24 (0.20-0.31) | 0.23 | 0.30 | 0.96x (in) | 1.27x (in) |
