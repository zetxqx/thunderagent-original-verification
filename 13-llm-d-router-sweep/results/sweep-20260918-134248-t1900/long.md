# Long window: c128-w90 sliced into 30-minute windows

Slice 1 is the warm-up-plus-first-half; later slices see deeper sessions (longer prompts). Ratios are of the arms' values within the same slice.

## throughput (tok/s)

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 981 | 1238 | 1536 | 1.26x | 1.24x |
| 2 | 761 | 1101 | 1167 | 1.45x | 1.06x |
| 3 | 972 | 1164 | 1287 | 1.20x | 1.11x |

## prefix-cache hit rate

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 0.333 | 0.482 | 0.688 | 1.45x | 1.43x |
| 2 | 0.002 | 0.328 | 0.515 | 154.58x | 1.57x |
| 3 | 0.124 | 0.327 | 0.501 | 2.65x | 1.53x |

## TTFT p50 (s)

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 5.8 | 2.2 | 1.1 | 0.38x | 0.48x |
| 2 | 41.2 | 4.6 | 5.6 | 0.11x | 1.22x |
| 3 | 18.2 | 3.6 | 3.7 | 0.20x | 1.02x |

## TTFT p90 (s)

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 32.2 | 8.9 | 11.2 | 0.28x | 1.25x |
| 2 | 66.6 | 13.8 | 27.2 | 0.21x | 1.97x |
| 3 | 52.8 | 12.9 | 21.1 | 0.24x | 1.64x |

## mean prompt tokens

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 60045 | 60151 | 63177 | 1.00x | 1.05x |
| 2 | 79254 | 76344 | 79442 | 0.96x | 1.04x |
| 3 | 62524 | 61864 | 63570 | 0.99x | 1.03x |

## turns per second

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 1.60 | 1.95 | 2.22 | 1.22x | 1.14x |
| 2 | 0.81 | 1.07 | 1.17 | 1.33x | 1.09x |
| 3 | 1.28 | 1.59 | 1.75 | 1.24x | 1.11x |

## goodput within SLO (turns/s)

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 1.40 | 1.93 | 2.15 | 1.38x | 1.12x |
| 2 | 0.12 | 1.03 | 1.06 | 8.67x | 1.02x |
| 3 | 0.98 | 1.54 | 1.64 | 1.57x | 1.07x |

## session SLO attainment, strict

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 0.16 | 0.87 | 0.67 | 5.39x | 0.78x |
| 2 | 0.01 | 0.70 | 0.45 | 102.51x | 0.64x |
| 3 | 0.06 | 0.67 | 0.49 | 11.55x | 0.73x |

## session SLO attainment, lenient

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 0.24 | 0.89 | 0.78 | 3.65x | 0.88x |
| 2 | 0.01 | 0.72 | 0.51 | 105.41x | 0.71x |
| 3 | 0.07 | 0.70 | 0.56 | 10.03x | 0.79x |

## sessions active in the slice

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 143 | 150 | 156 | 1.05x | 1.04x |
| 2 | 147 | 152 | 148 | 1.03x | 0.97x |
| 3 | 242 | 247 | 254 | 1.02x | 1.03x |

## sessions with zero turns in the slice

| slice | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|
| 1 | 0.01 | 0.00 | 0.01 | 0.00x | - |
| 2 | 0.00 | 0.04 | 0.03 | - | 0.86x |
| 3 | 0.01 | 0.06 | 0.03 | 4.57x | 0.56x |
