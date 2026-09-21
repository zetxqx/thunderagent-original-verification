# Long window: c128-w90 sliced into 30-minute windows

Slice 1 is the warm-up-plus-first-half; later slices see deeper sessions (longer prompts). Ratios are of the arms' values within the same slice.

## throughput (tok/s)

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 981 | 1238 | 1536 | 1157 | 1.26x | 1.24x | 0.75x | - |
| 2 | 761 | 1101 | 1167 | 913 | 1.45x | 1.06x | 0.78x | - |
| 3 | 972 | 1164 | 1287 | 1067 | 1.20x | 1.11x | 0.83x | - |

## prefix-cache hit rate

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.333 | 0.482 | 0.688 | 0.449 | 1.45x | 1.43x | 0.65x | - |
| 2 | 0.002 | 0.328 | 0.515 | 0.189 | 154.58x | 1.57x | 0.37x | - |
| 3 | 0.124 | 0.327 | 0.501 | 0.218 | 2.65x | 1.53x | 0.43x | - |

## TTFT p50 (s)

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 5.8 | 2.2 | 1.1 | 3.1 | 0.38x | 0.48x | 2.89x | - |
| 2 | 41.2 | 4.6 | 5.6 | 27.1 | 0.11x | 1.22x | 4.84x | - |
| 3 | 18.2 | 3.6 | 3.7 | 14.3 | 0.20x | 1.02x | 3.84x | - |

## TTFT p90 (s)

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 32.2 | 8.9 | 11.2 | 26.6 | 0.28x | 1.25x | 2.38x | - |
| 2 | 66.6 | 13.8 | 27.2 | 88.4 | 0.21x | 1.97x | 3.25x | - |
| 3 | 52.8 | 12.9 | 21.1 | 42.5 | 0.24x | 1.64x | 2.02x | - |

## mean prompt tokens

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 60045 | 60151 | 63177 | 59792 | 1.00x | 1.05x | 0.95x | - |
| 2 | 79254 | 76344 | 79442 | 77584 | 0.96x | 1.04x | 0.98x | - |
| 3 | 62524 | 61864 | 63570 | 61572 | 0.99x | 1.03x | 0.97x | - |

## turns per second

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.60 | 1.95 | 2.22 | 1.81 | 1.22x | 1.14x | 0.82x | - |
| 2 | 0.81 | 1.07 | 1.17 | 0.92 | 1.33x | 1.09x | 0.79x | - |
| 3 | 1.28 | 1.59 | 1.75 | 1.42 | 1.24x | 1.11x | 0.81x | - |

## goodput within SLO (turns/s)

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.40 | 1.93 | 2.15 | 1.67 | 1.38x | 1.12x | 0.78x | - |
| 2 | 0.12 | 1.03 | 1.06 | 0.48 | 8.67x | 1.02x | 0.45x | - |
| 3 | 0.98 | 1.54 | 1.64 | 1.16 | 1.57x | 1.07x | 0.71x | - |

## session SLO attainment, strict

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.16 | 0.87 | 0.67 | 0.45 | 5.39x | 0.78x | 0.67x | - |
| 2 | 0.01 | 0.70 | 0.45 | 0.09 | 102.51x | 0.64x | 0.20x | - |
| 3 | 0.06 | 0.67 | 0.49 | 0.24 | 11.55x | 0.73x | 0.49x | - |

## session SLO attainment, lenient

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.24 | 0.89 | 0.78 | 0.57 | 3.65x | 0.88x | 0.72x | - |
| 2 | 0.01 | 0.72 | 0.51 | 0.11 | 105.41x | 0.71x | 0.22x | - |
| 3 | 0.07 | 0.70 | 0.56 | 0.30 | 10.03x | 0.79x | 0.53x | - |

## sessions active in the slice

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 143 | 150 | 156 | 150 | 1.05x | 1.04x | 0.96x | - |
| 2 | 147 | 152 | 148 | 144 | 1.03x | 0.97x | 0.97x | - |
| 3 | 242 | 247 | 254 | 247 | 1.02x | 1.03x | 0.97x | - |

## sessions with zero turns in the slice

| slice | llm-d default | most-room | origin-only | origin + urgent 15 s | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.01 | 0.00 | 0.01 | 0.00 | 0.00x | - | 0.00x | - |
| 2 | 0.00 | 0.04 | 0.03 | 0.01 | - | 0.86x | 0.21x | - |
| 3 | 0.01 | 0.06 | 0.03 | 0.00 | 4.57x | 0.56x | 0.00x | - |
