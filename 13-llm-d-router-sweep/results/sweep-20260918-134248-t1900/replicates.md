# Step 13 replicates: most-room vs origin-only at c = 96, 128

Replicate 1 is the sweep's own cell (thunder-agent-v3 for most-room, v4 for origin-only, old bench image); replicates 2 and 3 are v4 for both arms with the session-id bench image. The llm-d default (baseline) has the sweep cell plus one session-id cell per level. Cells show mean (min-max) over the replicates present; ratio columns are ratios of means, with the range of the per-replicate paired ratios in brackets when both arms share replicate indices.

## Cell-level metrics

### throughput (tok/s)

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | 1569 (1541-1597) | 1531 (1500-1556) | 1830 (1804-1872) | 0.98x [0.94-1.00] | 1.20x [1.18-1.20] |
| 128 | 32 | 2 / 3 / 3 | 1154 (1151-1156) | 1370 (1362-1382) | 1693 (1571-1807) | 1.19x [1.18-1.20] | 1.24x [1.14-1.32] |

### steady-state hit rate

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | 0.655 (0.625-0.686) | 0.590 (0.547-0.621) | 0.824 (0.816-0.831) | 0.90x [0.80-0.96] | 1.40x [1.34-1.51] |
| 128 | 32 | 2 / 3 / 3 | 0.057 (0.040-0.073) | 0.347 (0.341-0.353) | 0.680 (0.629-0.722) | 6.12x [4.64-8.84] | 1.96x [1.78-2.08] |

### TTFT p50 (s)

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | 0.5 (0.5-0.5) | 0.5 (0.5-0.5) | 0.5 (0.5-0.5) | 1.00x [1.00-1.02] | 0.98x [0.96-1.02] |
| 128 | 32 | 2 / 3 / 3 | 7.7 (7.3-8.2) | 2.4 (2.3-2.4) | 1.0 (0.6-1.3) | 0.31x [0.28-0.33] | 0.41x [0.24-0.58] |

### TTFT p90 (s)

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | 12.8 (11.5-14.0) | 8.0 (7.5-8.2) | 5.9 (5.7-6.1) | 0.62x [0.58-0.71] | 0.74x [0.70-0.79] |
| 128 | 32 | 2 / 3 / 3 | 33.9 (32.9-34.9) | 10.1 (9.9-10.2) | 11.4 (10.4-12.5) | 0.30x [0.29-0.30] | 1.13x [1.02-1.26] |

### requests completed

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | 3666 (3578-3754) | 3581 (3518-3643) | 4063 (4017-4088) | 0.98x [0.94-1.00] | 1.13x [1.10-1.16] |
| 128 | 32 | 2 / 3 / 3 | 3017 (3008-3026) | 3611 (3593-3641) | 4155 (4026-4289) | 1.20x [1.19-1.20] | 1.15x [1.11-1.19] |

### waiting inside vLLM

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | 4 (3-4) | 1 (1-1) | 0 (0-0) | 0.25x [0.24-0.24] | 0.35x [0.27-0.44] |
| 128 | 32 | 2 / 3 / 3 | 15 (15-15) | 1 (1-1) | 1 (0-1) | 0.07x [0.06-0.08] | 0.56x [0.47-0.78] |

### errors

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | 0 (0-0) | 0 (0-0) | 0 (0-0) | - | - |
| 128 | 32 | 2 / 3 / 3 | 0 (0-1) | 0 (0-1) | 0 (0-0) | 0.67x | 0.00x |

### EPP holds

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | - | 275 (252-294) | 439 (437-444) | nanx [nan-nan] | 1.60x [1.51-1.73] |
| 128 | 32 | 2 / 3 / 3 | - | 711 (698-723) | 971 (836-1079) | nanx [nan-nan] | 1.37x [1.16-1.55] |

### EPP forced admissions

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | - | 0 (0-0) | 0 (0-0) | nanx [nan-nan] | - |
| 128 | 32 | 2 / 3 / 3 | - | 0 (0-0) | 0 (0-1) | nanx [nan-nan] | - |

### EPP rebinds

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | 0 (0-0) | 454 (421-479) | 0 (0-0) | - | 0.00x [0.00-0.00] |
| 128 | 32 | 2 / 3 / 3 | 0 (0-0) | 1091 (1074-1120) | 0 (0-0) | - | 0.00x [0.00-0.00] |

### EPP origin waits

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 2 / 3 / 3 | 0 (0-0) | 0 (0-0) | 544 (525-556) | - | - |
| 128 | 32 | 2 / 3 / 3 | 0 (0-0) | 0 (0-0) | 1105 (936-1231) | - | - |

## Session-level metrics (proposal Part 7; only cells with session ids, SLO = TTFT <= 30 s, after the 10-minute warm-up)

### sessions seen

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 1 / 2 / 2 | 112 | 110 (110-111) | 119 (118-120) | 0.99x | 1.08x [1.07-1.08] |
| 128 | 32 | 1 / 2 / 2 | 138 | 150 (149-150) | 146 (140-151) | 1.08x | 0.97x [0.93-1.01] |

### goodput within SLO (turns/s with TTFT <= 30 s)

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 1 / 2 / 2 | 1.22 | 1.09 (1.05-1.14) | 1.58 (1.54-1.62) | 0.90x | 1.44x [1.42-1.46] |
| 128 | 32 | 1 / 2 / 2 | 0.57 | 1.28 (1.27-1.29) | 1.53 (1.53-1.53) | 2.23x | 1.19x [1.18-1.20] |

### turns/s, all

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 1 / 2 / 2 | 1.27 | 1.12 (1.07-1.16) | 1.60 (1.56-1.64) | 0.88x | 1.44x [1.42-1.46] |
| 128 | 32 | 1 / 2 / 2 | 0.93 | 1.33 (1.32-1.33) | 1.59 (1.58-1.59) | 1.43x | 1.20x [1.19-1.20] |

### session SLO attainment, strict (all turns)

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 1 / 2 / 2 | 0.58 | 0.87 (0.86-0.87) | 0.82 (0.81-0.82) | 1.50x | 0.94x [0.92-0.95] |
| 128 | 32 | 1 / 2 / 2 | 0.08 | 0.76 (0.75-0.77) | 0.70 (0.69-0.72) | 9.57x | 0.92x [0.89-0.96] |

### session SLO attainment, lenient (95% of turns)

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 1 / 2 / 2 | 0.69 | 0.88 (0.88-0.88) | 0.85 (0.82-0.88) | 1.28x | 0.96x [0.93-0.99] |
| 128 | 32 | 1 / 2 / 2 | 0.08 | 0.78 (0.77-0.79) | 0.75 (0.73-0.76) | 9.78x | 0.96x [0.93-0.99] |

### turns per session after warm-up, p10

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 1 / 2 / 2 | 4 | 4 (3-4) | 4 (4-4) | 0.88x | 1.14x [1.00-1.33] |
| 128 | 32 | 1 / 2 / 2 | 3 | 2 (2-2) | 3 (3-3) | 0.67x | 1.50x [1.50-1.50] |

### turns per session after warm-up, p50

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 1 / 2 / 2 | 13 | 12 (12-12) | 16 (15-16) | 0.92x | 1.29x [1.25-1.33] |
| 128 | 32 | 1 / 2 / 2 | 8 | 10 (10-11) | 13 (12-14) | 1.31x | 1.24x [1.20-1.27] |

### turns per session after warm-up, p90

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 1 / 2 / 2 | 29 | 25 (24-26) | 35 (33-37) | 0.86x | 1.40x [1.38-1.42] |
| 128 | 32 | 1 / 2 / 2 | 16 | 22 (22-23) | 28 (27-29) | 1.41x | 1.24x [1.23-1.26] |

### sessions with zero turns after warm-up

| c | sessions/pod | n (llm-d default / most-room / origin-only) | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|---|
| 96 | 24 | 1 / 2 / 2 | 0.00 | 0.01 (0.01-0.02) | 0.03 (0.03-0.03) | - | 2.16x [1.40-3.70] |
| 128 | 32 | 1 / 2 / 2 | 0.01 | 0.04 (0.03-0.05) | 0.02 (0.01-0.03) | 5.54x | 0.52x [0.39-0.61] |
