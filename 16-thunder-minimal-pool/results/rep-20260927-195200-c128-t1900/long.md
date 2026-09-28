# Step 16 long window: c=128 for 90 minutes, 30-minute slices

Slice 1 includes the 10-minute warm-up. The last column is thunder-min / origin-only within the slice.

## throughput (tok/s)

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 981 | 1238 | 1536 | 1436 | 0.93x |
| 2 | 761 | 1101 | 1167 | 1305 | 1.12x |
| 3 | 972 | 1164 | 1287 | 1329 | 1.03x |

## prefix-cache hit rate

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 0.333 | 0.482 | 0.688 | 0.645 | 0.94x |
| 2 | 0.002 | 0.328 | 0.515 | 0.589 | 1.14x |
| 3 | 0.124 | 0.327 | 0.501 | 0.503 | 1.01x |

## TTFT p50 (s)

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 5.8 | 2.2 | 1.1 | 1.3 | 1.18x |
| 2 | 41.2 | 4.6 | 5.6 | 3.6 | 0.64x |
| 3 | 18.2 | 3.6 | 3.7 | 3.6 | 0.97x |

## TTFT p90 (s)

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 32.2 | 8.9 | 11.2 | 12.6 | 1.13x |
| 2 | 66.6 | 13.8 | 27.2 | 18.2 | 0.67x |
| 3 | 52.8 | 12.9 | 21.1 | 20.6 | 0.98x |

## mean prompt tokens

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 60045 | 60151 | 63177 | 63054 | 1.00x |
| 2 | 79254 | 76344 | 79442 | 78161 | 0.98x |
| 3 | 62524 | 61864 | 63570 | 63146 | 0.99x |

## goodput within SLO (turns/s)

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 1.40 | 1.93 | 2.15 | 2.06 | 0.96x |
| 2 | 0.12 | 1.03 | 1.06 | 1.16 | 1.10x |
| 3 | 0.98 | 1.54 | 1.64 | 1.63 | 1.00x |

## session SLO attainment, strict

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 0.16 | 0.87 | 0.67 | 0.54 | 0.81x |
| 2 | 0.01 | 0.70 | 0.45 | 0.44 | 0.99x |
| 3 | 0.06 | 0.67 | 0.49 | 0.43 | 0.87x |

## session SLO attainment, lenient

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 0.24 | 0.89 | 0.78 | 0.74 | 0.94x |
| 2 | 0.01 | 0.72 | 0.51 | 0.49 | 0.97x |
| 3 | 0.07 | 0.70 | 0.56 | 0.51 | 0.92x |

## sessions active in the slice

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 143 | 150 | 156 | 156 | 1.00x |
| 2 | 147 | 152 | 148 | 147 | 0.99x |
| 3 | 242 | 247 | 254 | 256 | 1.01x |

## EPP sessions on the books: running, mean

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | - | 39 | 47 | 107 | 2.27x |
| 2 | - | 24 | 21 | 94 | 4.51x |
| 3 | - | 29 | 29 | 115 | 3.91x |

## EPP sessions on the books: idle, mean (includes finished, kept until the TTL)

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | - | 2 | 3 | 4 | 1.26x |
| 2 | - | 1 | 1 | 1 | 1.92x |
| 3 | - | 1 | 1 | 2 | 2.20x |

## EPP sessions on the books: paused, mean

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | - | 20 | 31 | 28 | 0.92x |
| 2 | - | 65 | 76 | 71 | 0.93x |
| 3 | - | 146 | 155 | 149 | 0.96x |

## EPP undecayed working set / capacity (v4: first pod only)

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | - | 0.97 | 0.96 | 0.96 | 0.99x |
| 2 | - | 0.99 | 0.99 | 1.01 | 1.02x |
| 3 | - | 0.99 | 0.99 | 1.02 | 1.03x |

## EPP pauses in the slice

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | - | 1755 | 1639 | 487 | 0.30x |
| 2 | - | 1381 | 1486 | 429 | 0.29x |
| 3 | - | 2081 | 2181 | 719 | 0.33x |

## EPP holds in the slice

| slice | step 13 llm-d default | step 13 v4 most-room | step 13 v4 origin-only | step 16 thunder-min | min / origin |
|---|---|---|---|---|---|
| 1 | 0 | 660 | 1024 | 368 | 0.36x |
| 2 | 0 | 637 | 1078 | 344 | 0.32x |
| 3 | 0 | 838 | 1378 | 532 | 0.39x |
