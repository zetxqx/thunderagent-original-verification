# Trial stability across 3 runs

Trials: ab-20260915-162856, ab-20260915-183059, ab-20260915-205919

## default

| metric | trial 1 | trial 2 | trial 3 | spread |
|---|---|---|---|---|
| requests ok | 240/240 | 240/240 | 240/240 | |
| makespan (s) | 457.5 | 457.5 | 457.8 | 0.1% |
| prefix-cache hit rate | 0.000 | 0.000 | 0.000 | 0.0% |
| prefilled tokens (M) | 14.71 | 14.71 | 14.71 | 0.0% |
| latency p50 (s) | 150.7 | 150.7 | 150.8 | 0.1% |
| latency p95 (s) | 160.6 | 160.5 | 160.9 | 0.2% |
| max concurrent paused | 0 | 0 | 0 | 0.0% |

## tr-decay

| metric | trial 1 | trial 2 | trial 3 | spread |
|---|---|---|---|---|
| requests ok | 240/240 | 240/240 | 240/240 | |
| makespan (s) | 315.3 | 315.0 | 345.7 | 9.4% |
| prefix-cache hit rate | 0.345 | 0.344 | 0.278 | 20.8% |
| prefilled tokens (M) | 9.63 | 9.65 | 10.62 | 9.9% |
| latency p50 (s) | 57.0 | 68.5 | 64.3 | 18.3% |
| latency p95 (s) | 250.4 | 213.5 | 264.0 | 20.8% |
| max concurrent paused | 49 | 47 | 52 | 10.1% |

## tr-nodecay

| metric | trial 1 | trial 2 | trial 3 | spread |
|---|---|---|---|---|
| requests ok | 240/240 | 240/240 | 240/240 | |
| makespan (s) | 3677.7 | 3729.8 | 3718.9 | 1.4% |
| prefix-cache hit rate | 0.462 | 0.352 | 0.348 | 29.5% |
| prefilled tokens (M) | 7.91 | 9.53 | 9.59 | 18.7% |
| latency p50 (s) | 50.4 | 59.7 | 60.6 | 18.0% |
| latency p95 (s) | 1851.9 | 1855.6 | 1857.0 | 0.3% |
| max concurrent paused | 47 | 49 | 48 | 4.2% |

## Gap vs run-to-run spread

- tr-decay vs default, makespan (s): 0.69x, 0.69x, 0.75x (per-trial ratios; consistent = gap is real)
- tr-decay vs default, latency p50 (s): 0.38x, 0.45x, 0.43x (per-trial ratios; consistent = gap is real)
- tr-decay vs default, latency p95 (s): 1.56x, 1.33x, 1.64x (per-trial ratios; consistent = gap is real)
- tr-nodecay vs default, makespan (s): 8.04x, 8.15x, 8.12x (per-trial ratios; consistent = gap is real)
- tr-nodecay vs default, latency p50 (s): 0.33x, 0.40x, 0.40x (per-trial ratios; consistent = gap is real)
- tr-nodecay vs default, latency p95 (s): 11.53x, 11.56x, 11.54x (per-trial ratios; consistent = gap is real)
