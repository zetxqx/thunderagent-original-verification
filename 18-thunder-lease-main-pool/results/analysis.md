# Step 18: the lease thunder-agent rebuilt on the minimal ledger

Single-pod run: `rep-20260929-024837-c32-t1900`. Pool run: `rep-20260929-040322-c128-t1900`. Step 18 columns are one cell each; step 16 and 17 columns are mean (min-max) over three cells.

## Single vLLM pod, c=32

One EPP pinned to one vLLM pod (lane a), 32 sessions, the pool's per-pod load.

| metric | single pod, lease 30 s | single pod, lease 10 s |
|---|---|---|
| output throughput (tok/s) | 375 | 398 |
| requests completed | 932 | 978 |
| request errors | 0 | 0 |
| turns not issued at stage end (inference-perf dropped_requests) | 0 | 0 |
| sessions ended in window / failed | 10 / 0 | 8 / 0 |
| hit rate, whole window | 0.522 | 0.578 |
| hit rate, warm-up (first 10 min) | 0.811 | 0.803 |
| hit rate, steady state | 0.211 | 0.376 |
| requests with zero cache hit | 0.42 | 0.39 |
| prefill tokens computed (M) | 26.2 | 24.8 |
| prompt tokens per request, mean (k) | 59.0 | 60.2 |
| TTFT p50 / p90 / p99 (s) | 1.8 / 17.5 / 98.3 | 1.3 / 16.4 / 119.6 |
| E2E latency p50 / p90 / p99 (s) | 33.3 / 147.2 / 490.0 | 30.4 / 139.1 / 433.4 |
| TPOT p50 / p90 (ms) | 62 / 117 | 55 / 115 |
| ITL p50 / p90 (ms) | 64 / 127 | 59 / 123 |
| vLLM KV usage, mean steady / max | 0.86 / 1.00 | 0.88 / 1.00 |
| vLLM running, mean steady / max | 25 / 33 | 26 / 33 |
| vLLM waiting, mean steady / max | 1.9 / 19.0 | 1.8 / 21.0 |
| vLLM preemptions | 3 | 4 |
| EPP undecayed working set / capacity, mean steady | 0.99 | 0.99 |
| EPP decayed working set / capacity, mean steady | - | - |
| share of samples with working set over capacity | 0.11 | 0.18 |
| EPP sessions running / idle / paused, mean | 25 / 3 / 6 | 26 / 2 / 6 |
| EPP max sessions paused at once | 17 | 17 |
| EPP releases reasoning / paused / new | 854 / 38 / 42 | 906 / 35 / 40 |
| EPP holds paused / new | 37 / 3 | 34 / 4 |
| EPP pauses / resumes | 55 / 38 | 52 / 35 |
| EPP forced admissions | 0 | 0 |
| EPP mean queue wait (s) | 2.1 | 2.8 |
| EPP max queue size | 6 | 8 |
| EPP CPU cores, mean / max | 1.01 / 6.93 | 1.02 / 8.02 |
| pod KV usage, steady mean, min-max over pods | - / - | - / - |
| pod running requests, steady mean, min-max over pods | - / - | - / - |
| pod steady hit rate, min-max over pods | - / - | - / - |
| pod undecayed working set / capacity, min-max over pods | - / - | - / - |
| sessions in the steady-state population | 42 | 40 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 0.28 | 0.32 |
| session SLO attainment, strict / lenient | 0.50 / 0.55 | 0.55 / 0.65 |
| turns per session after warm-up, p10 / p50 / p90 | 2 / 9 / 18 | 3 / 9 / 24 |
| share of turns over the SLO | 0.059 | 0.039 |
| per-session worst TTFT, p90 (s) | 233 | 235 |
| sessions whose worst turn exceeded 60 s | 0.21 | 0.30 |

## 4-pod pool, c=128

One EPP over the four vLLM pods, the step 16 and 17 protocol.

| metric | step 18 pool, lease 30 s | step 18 pool, lease 10 s | step 17 lease 30 s (3 cells) | step 17 lease 5 s (3 cells) | step 16 half-life 10 s, sweep 1 s (3 cells) |
|---|---|---|---|---|---|
| output throughput (tok/s) | 1477 | 1647 | 1931 (1871-2018) | 1859 (1839-1874) | 1945 (1867-2019) |
| requests completed | 3681 | 3862 | 4410 (4313-4504) | 4383 (4345-4416) | 4590 (4471-4776) |
| request errors | 1 | 1 | 0 (0-0) | 1 (0-1) | 0 (0-1) |
| turns not issued at stage end (inference-perf dropped_requests) | 0 | 0 | 0 (0-0) | 0 (0-0) | 0 (0-0) |
| sessions ended in window / failed | 27 / 1 | 27 / 1 | 33 (29-35) / 0 (0-0) | 32 (31-32) / 0 (0-0) | 36 (28-41) / 0 (0-1) |
| hit rate, whole window | 0.582 | 0.656 | 0.806 (0.780-0.827) | 0.767 (0.749-0.778) | 0.790 (0.766-0.804) |
| hit rate, warm-up (first 10 min) | 0.659 | 0.714 | 0.780 (0.775-0.784) | 0.799 (0.792-0.804) | 0.782 (0.774-0.794) |
| hit rate, steady state | 0.539 | 0.621 | 0.819 (0.778-0.849) | 0.749 (0.724-0.766) | 0.795 (0.752-0.820) |
| requests with zero cache hit | 0.37 | 0.31 | 0.19 (0.18-0.20) | 0.20 (0.20-0.21) | 0.20 (0.19-0.20) |
| prefill tokens computed (M) | 97.6 | 84.7 | 56.0 (51.3-62.0) | 65.3 (63.3-69.3) | 60.7 (57.4-65.3) |
| prompt tokens per request, mean (k) | 63.7 | 64.1 | 66.6 (65.6-67.2) | 64.7 (63.5-65.4) | 64.3 (63.7-64.7) |
| TTFT p50 / p90 / p99 (s) | 1.5 / 18.4 / 125.2 | 0.7 / 14.2 / 128.6 | 0.5 (0.5-0.5) / 7.3 (6.5-8.5) / 242.3 (220.2-279.3) | 0.6 (0.6-0.6) / 8.6 (8.4-8.9) / 138.5 (121.8-163.8) | 0.5 (0.5-0.5) / 7.0 (6.3-8.0) / 140.6 (119.4-173.2) |
| E2E latency p50 / p90 / p99 (s) | 32.9 / 146.1 / 507.6 | 28.6 / 143.8 / 513.9 | 21.1 (20.2-22.5) / 117.1 (111.1-121.9) / 456.6 (423.4-498.0) | 23.8 (22.9-24.8) / 121.0 (118.4-123.5) / 437.8 (386.1-467.2) | 22.2 (21.5-23.4) / 113.2 (108.5-118.0) / 415.7 (409.6-422.7) |
| TPOT p50 / p90 (ms) | 63 / 139 | 53 / 126 | 46 (44-48) / 82 (79-86) | 52 (51-53) / 82 (81-83) | 49 (47-53) / 81 (81-82) |
| ITL p50 / p90 (ms) | 66 / 147 | 55 / 131 | 47 (46-50) / 88 (85-92) | 53 (52-55) / 88 (87-89) | 51 (49-54) / 88 (87-88) |
| vLLM KV usage, mean steady / max | 0.69 / 0.98 | 0.67 / 0.99 | 0.61 (0.59-0.63) / 0.98 (0.97-0.98) | 0.65 (0.64-0.65) / 0.99 (0.98-0.99) | 0.63 (0.59-0.66) / 0.99 (0.99-1.00) |
| vLLM running, mean steady / max | 80 / 130 | 76 / 130 | 65 (63-68) / 122 (115-128) | 71 (70-72) / 125 (122-128) | 70 (68-72) / 128 (125-131) |
| vLLM waiting, mean steady / max | 4.9 / 70.0 | 3.1 / 73.0 | 0.9 (0.7-1.2) / 61.3 (55.0-68.0) | 1.1 (0.9-1.2) / 67.0 (64.0-69.0) | 0.7 (0.6-1.0) / 62.3 (58.0-68.0) |
| vLLM preemptions | 12 | 15 | 7 (6-8) | 14 (10-20) | 7 (5-8) |
| EPP undecayed working set / capacity, mean steady | 0.99 | 0.98 | 0.98 (0.97-0.99) | 0.98 (0.98-0.98) | 0.97 (0.96-0.98) |
| EPP decayed working set / capacity, mean steady | 0.00 | 0.00 | 0.00 (0.00-0.00) | 0.00 (0.00-0.00) | 0.67 (0.63-0.70) |
| share of samples with working set over capacity | 0.01 | 0.05 | 0.16 (0.06-0.26) | 0.12 (0.06-0.17) | 0.04 (0.01-0.07) |
| EPP sessions running / idle / paused, mean | 81 / 22 / 26 | 77 / 22 / 31 | 67 (65-69) / 25 (23-26) / 43 (38-47) | 72 (72-74) / 21 (20-21) / 41 (40-43) | 71 (70-73) / 21 (19-24) / 45 (41-48) |
| EPP max sessions paused at once | 56 | 65 | 72 (66-75) | 75 (73-79) | 84 (79-87) |
| EPP releases reasoning / paused / new | 3426 / 113 / 155 | 3596 / 120 / 155 | 4026 (3930-4109) / 245 (233-259) / 161 (157-163) | 3857 (3811-3884) / 389 (333-437) / 160 (159-160) | 4013 (3861-4184) / 449 (403-493) / 164 (156-169) |
| EPP holds paused / new | 109 / 1 | 115 / 1 | 230 (222-244) / 1 (0-2) | 348 (301-383) / 1 (1-2) | 365 (331-397) / 0 (0-0) |
| EPP pauses / resumes | 169 / 113 | 184 / 120 | 316 (307-334) / 0 (0-0) | 464 (406-511) / 0 (0-0) | 532 (487-572) / 448 (402-493) |
| EPP forced admissions | 0 | 0 | 0 (0-1) | 1 (0-2) | 0 (0-0) |
| EPP mean queue wait (s) | - | - | - | - | - |
| EPP max queue size | 21 | 31 | 40 (38-43) | 36 (34-37) | 36 (35-37) |
| EPP CPU cores, mean / max | 1.92 / 8.89 | 1.93 / 8.90 | 2.01 (1.95-2.06) / 8.51 (7.88-8.97) | 1.92 (1.88-1.94) / 8.05 (8.04-8.07) | 1.94 (1.92-1.97) / 8.28 (7.75-8.98) |
| pod KV usage, steady mean, min-max over pods | 0.63 / 0.72 | 0.62 / 0.70 | 0.55 (0.52-0.59) / 0.65 (0.65-0.66) | 0.63 (0.61-0.64) / 0.67 (0.65-0.69) | 0.58 (0.52-0.63) / 0.67 (0.64-0.68) |
| pod running requests, steady mean, min-max over pods | 14.5 / 24.5 | 16.5 / 21.6 | 12.8 (12.2-14.0) / 19.9 (19.5-20.1) | 15.6 (14.8-17.2) / 20.6 (18.7-22.2) | 15.1 (13.3-17.5) / 19.7 (18.8-20.4) |
| pod steady hit rate, min-max over pods | 0.183 / 0.912 | 0.300 / 0.891 | 0.711 (0.682-0.737) / 0.915 (0.862-0.956) | 0.693 (0.661-0.738) / 0.798 (0.764-0.830) | 0.716 (0.705-0.730) / 0.848 (0.780-0.883) |
| pod undecayed working set / capacity, min-max over pods | 0.98 / 1.00 | 0.97 / 0.99 | 0.96 (0.96-0.97) / 1.00 (0.99-1.00) | 0.97 (0.97-0.98) / 0.99 (0.99-0.99) | 0.95 (0.93-0.96) / 0.98 (0.97-0.99) |
| sessions in the steady-state population | 149 | 152 | 150 (148-151) | 153 (145-158) | 154 (150-158) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 1.40 | 1.39 | 1.72 (1.60-1.79) | 1.62 (1.54-1.69) | 1.77 (1.64-1.94) |
| session SLO attainment, strict / lenient | 0.61 / 0.64 | 0.62 / 0.66 | 0.67 (0.61-0.70) / 0.71 (0.67-0.74) | 0.61 (0.59-0.63) / 0.68 (0.65-0.72) | 0.64 (0.57-0.70) / 0.69 (0.65-0.72) |
| turns per session after warm-up, p10 / p50 / p90 | 3 / 11 / 27 | 2 / 12 / 25 | 2 (2-3) / 14 (13-15) / 30 (28-31) | 4 (3-5) / 13 (13-13) / 29 (28-29) | 3 (2-4) / 14 (13-14) / 31 (29-33) |
| share of turns over the SLO | 0.038 | 0.037 | 0.028 (0.025-0.034) | 0.038 (0.034-0.042) | 0.032 (0.027-0.042) |
| per-session worst TTFT, p90 (s) | 398 | 293 | 353 (291-435) | 359 (298-394) | 275 (226-367) |
| sessions whose worst turn exceeded 60 s | 0.23 | 0.26 | 0.22 (0.19-0.23) | 0.27 (0.24-0.30) | 0.24 (0.20-0.31) |
