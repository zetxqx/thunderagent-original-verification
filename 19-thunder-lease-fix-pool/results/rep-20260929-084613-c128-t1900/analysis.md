# Step 19: lease thunder-agent after the in-flight accounting fix, pool, c=128

Step 19 and 18 columns are one cell each; step 16 and 17 columns are mean (min-max) over three cells.

| metric | step 19 lease 30 s, fixed accounting | step 18 lease 30 s, before the fix | step 17 lease 30 s (3 cells) | step 16 half-life 10 s, sweep 1 s (3 cells) |
|---|---|---|---|---|
| output throughput (tok/s) | 2042 | 1477 | 1931 (1871-2018) | 1945 (1867-2019) |
| requests completed | 4632 | 3681 | 4410 (4313-4504) | 4590 (4471-4776) |
| request errors | 0 | 1 | 0 (0-0) | 0 (0-1) |
| turns not issued at stage end (inference-perf dropped_requests) | 0 | 0 | 0 (0-0) | 0 (0-0) |
| sessions ended in window / failed | 38 / 0 | 27 / 1 | 33 (29-35) / 0 (0-0) | 36 (28-41) / 0 (0-1) |
| hit rate, whole window | 0.825 | 0.582 | 0.806 (0.780-0.827) | 0.790 (0.766-0.804) |
| hit rate, warm-up (first 10 min) | 0.786 | 0.659 | 0.780 (0.775-0.784) | 0.782 (0.774-0.794) |
| hit rate, steady state | 0.844 | 0.539 | 0.819 (0.778-0.849) | 0.795 (0.752-0.820) |
| requests with zero cache hit | 0.19 | 0.37 | 0.19 (0.18-0.20) | 0.20 (0.19-0.20) |
| prefill tokens computed (M) | 52.6 | 97.6 | 56.0 (51.3-62.0) | 60.7 (57.4-65.3) |
| prompt tokens per request, mean (k) | 65.6 | 63.7 | 66.6 (65.6-67.2) | 64.3 (63.7-64.7) |
| TTFT p50 / p90 / p99 (s) | 0.5 / 5.8 / 218.8 | 1.5 / 18.4 / 125.2 | 0.5 (0.5-0.5) / 7.3 (6.5-8.5) / 242.3 (220.2-279.3) | 0.5 (0.5-0.5) / 7.0 (6.3-8.0) / 140.6 (119.4-173.2) |
| E2E latency p50 / p90 / p99 (s) | 21.3 / 106.8 / 449.7 | 32.9 / 146.1 / 507.6 | 21.1 (20.2-22.5) / 117.1 (111.1-121.9) / 456.6 (423.4-498.0) | 22.2 (21.5-23.4) / 113.2 (108.5-118.0) / 415.7 (409.6-422.7) |
| TPOT p50 / p90 (ms) | 47 / 78 | 63 / 139 | 46 (44-48) / 82 (79-86) | 49 (47-53) / 81 (81-82) |
| ITL p50 / p90 (ms) | 48 / 82 | 66 / 147 | 47 (46-50) / 88 (85-92) | 51 (49-54) / 88 (87-88) |
| vLLM KV usage, mean steady / max | 0.59 / 0.99 | 0.69 / 0.98 | 0.61 (0.59-0.63) / 0.98 (0.97-0.98) | 0.63 (0.59-0.66) / 0.99 (0.99-1.00) |
| vLLM running, mean steady / max | 64 / 123 | 80 / 130 | 65 (63-68) / 122 (115-128) | 70 (68-72) / 128 (125-131) |
| vLLM waiting, mean steady / max | 0.6 / 68.0 | 4.9 / 70.0 | 0.9 (0.7-1.2) / 61.3 (55.0-68.0) | 0.7 (0.6-1.0) / 62.3 (58.0-68.0) |
| vLLM preemptions | 5 | 12 | 7 (6-8) | 7 (5-8) |
| EPP undecayed working set / capacity, mean steady | 0.97 | 0.99 | 0.98 (0.97-0.99) | 0.97 (0.96-0.98) |
| EPP decayed working set / capacity, mean steady | 0.00 | 0.00 | 0.00 (0.00-0.00) | 0.67 (0.63-0.70) |
| share of samples with working set over capacity | 0.03 | 0.01 | 0.16 (0.06-0.26) | 0.04 (0.01-0.07) |
| EPP sessions running / idle / paused, mean | 66 / 25 / 47 | 81 / 22 / 26 | 67 (65-69) / 25 (23-26) / 43 (38-47) | 71 (70-73) / 21 (19-24) / 45 (41-48) |
| EPP max sessions paused at once | 78 | 56 | 72 (66-75) | 84 (79-87) |
| EPP releases reasoning / paused / new | 4179 / 306 / 166 | 3426 / 113 / 155 | 4026 (3930-4109) / 245 (233-259) / 161 (157-163) | 4013 (3861-4184) / 449 (403-493) / 164 (156-169) |
| EPP holds paused / new | 281 / 0 | 109 / 1 | 230 (222-244) / 1 (0-2) | 365 (331-397) / 0 (0-0) |
| EPP pauses / resumes | 384 / 306 | 169 / 113 | 316 (307-334) / 0 (0-0) | 532 (487-572) / 448 (402-493) |
| EPP forced admissions | 1 | 0 | 0 (0-1) | 0 (0-0) |
| EPP mean queue wait (s) | - | - | - | - |
| EPP max queue size | 37 | 21 | 40 (38-43) | 36 (35-37) |
| EPP CPU cores, mean / max | 2.04 / 9.20 | 1.92 / 8.89 | 2.01 (1.95-2.06) / 8.51 (7.88-8.97) | 1.94 (1.92-1.97) / 8.28 (7.75-8.98) |
| pod KV usage, steady mean, min-max over pods | 0.55 / 0.63 | 0.63 / 0.72 | 0.55 (0.52-0.59) / 0.65 (0.65-0.66) | 0.58 (0.52-0.63) / 0.67 (0.64-0.68) |
| pod running requests, steady mean, min-max over pods | 12.4 / 18.9 | 14.5 / 24.5 | 12.8 (12.2-14.0) / 19.9 (19.5-20.1) | 15.1 (13.3-17.5) / 19.7 (18.8-20.4) |
| pod steady hit rate, min-max over pods | 0.766 / 0.925 | 0.183 / 0.912 | 0.711 (0.682-0.737) / 0.915 (0.862-0.956) | 0.716 (0.705-0.730) / 0.848 (0.780-0.883) |
| pod undecayed working set / capacity, min-max over pods | 0.92 / 1.00 | 0.98 / 1.00 | 0.96 (0.96-0.97) / 1.00 (0.99-1.00) | 0.95 (0.93-0.96) / 0.98 (0.97-0.99) |
| sessions in the steady-state population | 157 | 149 | 150 (148-151) | 154 (150-158) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 1.87 | 1.40 | 1.72 (1.60-1.79) | 1.77 (1.64-1.94) |
| session SLO attainment, strict / lenient | 0.64 / 0.72 | 0.61 / 0.64 | 0.67 (0.61-0.70) / 0.71 (0.67-0.74) | 0.64 (0.57-0.70) / 0.69 (0.65-0.72) |
| turns per session after warm-up, p10 / p50 / p90 | 3 / 14 / 34 | 3 / 11 / 27 | 2 (2-3) / 14 (13-15) / 30 (28-31) | 3 (2-4) / 14 (13-14) / 31 (29-33) |
| share of turns over the SLO | 0.026 | 0.038 | 0.028 (0.025-0.034) | 0.032 (0.027-0.042) |
| per-session worst TTFT, p90 (s) | 420 | 398 | 353 (291-435) | 275 (226-367) |
| sessions whose worst turn exceeded 60 s | 0.20 | 0.23 | 0.22 (0.19-0.23) | 0.24 (0.20-0.31) |
