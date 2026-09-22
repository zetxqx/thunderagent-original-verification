# Wait cost: cached prefix fraction at the next turn vs how long the prefix sat idle

Per turn after warm-up, c=128. Idle age = this turn's first token minus the previous turn's end. Cached fraction = vLLM cached_tokens / prompt_tokens. Re-prefill = prompt tokens not cached.

## ThunderAgent (llm-d router)
most-room resume (3456 turns)

| idle age (s) | turns | share of turns | cached fraction, median | cached fraction, mean | turns with < 50% cached | re-prefill tokens, median | TTFT median (s) |
|---|---|---|---|---|---|---|---|
| 0-2 | 741 | 0.21 | 0.97 | 0.77 | 0.20 | 1708 | 0.4 |
| 2-5 | 807 | 0.23 | 0.08 | 0.46 | 0.53 | 17303 | 2.9 |
| 5-10 | 995 | 0.29 | 0.00 | 0.26 | 0.73 | 58980 | 5.7 |
| 10-15 | 486 | 0.14 | 0.00 | 0.07 | 0.94 | 74094 | 7.8 |
| 15-30 | 259 | 0.07 | 0.00 | 0.01 | 0.99 | 100816 | 15.6 |
| 30-60 | 44 | 0.01 | 0.00 | 0.00 | 1.00 | 113750 | 35.9 |
| 60-120 | 26 | 0.01 | 0.00 | 0.00 | 1.00 | 122480 | 73.5 |
| 120- | 51 | 0.01 | 0.00 | 0.00 | 1.00 | 127742 | 251.5 |

## ThunderAgent (llm-d router)
origin-only resume (4141 turns)

| idle age (s) | turns | share of turns | cached fraction, median | cached fraction, mean | turns with < 50% cached | re-prefill tokens, median | TTFT median (s) |
|---|---|---|---|---|---|---|---|
| 0-2 | 1624 | 0.39 | 0.99 | 0.87 | 0.11 | 981 | 0.4 |
| 2-5 | 900 | 0.22 | 0.98 | 0.81 | 0.15 | 1301 | 2.2 |
| 5-10 | 702 | 0.17 | 0.92 | 0.70 | 0.25 | 5259 | 5.0 |
| 10-15 | 376 | 0.09 | 0.17 | 0.34 | 0.66 | 53448 | 9.0 |
| 15-30 | 319 | 0.08 | 0.00 | 0.13 | 0.89 | 77834 | 15.6 |
| 30-60 | 77 | 0.02 | 0.00 | 0.02 | 1.00 | 103122 | 35.6 |
| 60-120 | 40 | 0.01 | 0.00 | 0.00 | 1.00 | 91044 | 69.8 |
| 120- | 57 | 0.01 | 0.00 | 0.03 | 0.96 | 91947 | 298.5 |

## ThunderAgent (llm-d router)
origin-only + age priority 15 s (1697 turns)

| idle age (s) | turns | share of turns | cached fraction, median | cached fraction, mean | turns with < 50% cached | re-prefill tokens, median | TTFT median (s) |
|---|---|---|---|---|---|---|---|
| 0-2 | 488 | 0.29 | 0.98 | 0.83 | 0.14 | 1309 | 0.4 |
| 2-5 | 271 | 0.16 | 0.97 | 0.78 | 0.18 | 1894 | 2.3 |
| 5-10 | 249 | 0.15 | 0.85 | 0.64 | 0.31 | 7286 | 5.3 |
| 10-15 | 115 | 0.07 | 0.13 | 0.33 | 0.63 | 47724 | 10.1 |
| 15-30 | 215 | 0.13 | 0.00 | 0.08 | 0.92 | 66454 | 20.2 |
| 30-60 | 197 | 0.12 | 0.00 | 0.01 | 0.99 | 76564 | 38.1 |
| 60-120 | 91 | 0.05 | 0.00 | 0.00 | 1.00 | 86503 | 79.2 |
| 120- | 54 | 0.03 | 0.00 | 0.03 | 0.96 | 101214 | 157.4 |

## ThunderAgent (llm-d router)
origin-only + urgent 15 s (move) (2982 turns)

| idle age (s) | turns | share of turns | cached fraction, median | cached fraction, mean | turns with < 50% cached | re-prefill tokens, median | TTFT median (s) |
|---|---|---|---|---|---|---|---|
| 0-2 | 405 | 0.14 | 0.96 | 0.77 | 0.19 | 1854 | 0.4 |
| 2-5 | 338 | 0.11 | 0.95 | 0.74 | 0.23 | 2350 | 2.9 |
| 5-10 | 396 | 0.13 | 0.67 | 0.56 | 0.42 | 11425 | 6.1 |
| 10-15 | 200 | 0.07 | 0.00 | 0.25 | 0.75 | 48863 | 10.6 |
| 15-30 | 868 | 0.29 | 0.00 | 0.02 | 0.98 | 68026 | 20.9 |
| 30-60 | 625 | 0.21 | 0.00 | 0.00 | 1.00 | 95201 | 35.9 |
| 60-120 | 85 | 0.03 | 0.00 | 0.00 | 1.00 | 124506 | 73.0 |
| 120- | 30 | 0.01 | 0.00 | 0.03 | 0.97 | 185643 | 173.8 |

## ThunderAgent (llm-d router)
origin-only + wait cap 8 s (5697 turns)

| idle age (s) | turns | share of turns | cached fraction, median | cached fraction, mean | turns with < 50% cached | re-prefill tokens, median | TTFT median (s) |
|---|---|---|---|---|---|---|---|
| 0-2 | 1497 | 0.26 | 0.98 | 0.84 | 0.13 | 1362 | 0.4 |
| 2-5 | 1063 | 0.19 | 0.96 | 0.77 | 0.19 | 2389 | 2.6 |
| 5-10 | 1261 | 0.22 | 0.70 | 0.59 | 0.39 | 17774 | 5.8 |
| 10-15 | 824 | 0.14 | 0.00 | 0.18 | 0.83 | 62976 | 10.1 |
| 15-30 | 735 | 0.13 | 0.00 | 0.03 | 0.98 | 93401 | 15.6 |
| 30-60 | 137 | 0.02 | 0.00 | 0.00 | 1.00 | 116755 | 34.8 |
| 60-120 | 46 | 0.01 | 0.00 | 0.00 | 1.00 | 124678 | 73.8 |
| 120- | 61 | 0.01 | 0.00 | 0.00 | 1.00 | 137999 | 298.0 |
