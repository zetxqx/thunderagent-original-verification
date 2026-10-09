# AgentX sweep report

## Whole profiling window (AgentX)

| label        |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |
|:-------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|
| baseline-60m |     12 |        1361 |        0 |             1.88e+04 |                 170   |        39    |         1.33 |         40.3 |                33.3   |              93.3 |                  96   |               37.1 |            0.0525 |             0 |                 339   |                        0.723 |      6.06 |             17   |
| baseline-60m |     16 |        1156 |        0 |             1.65e+04 |                 144   |        15.2  |         9.18 |         96.9 |                10.7   |              84.7 |                  96.3 |               66.8 |            0.649  |             2 |                 287   |                        0.948 |      9.25 |             29.3 |
| baseline-60m |     20 |         985 |        0 |             1.24e+04 |                 109   |         6.78 |        48.4  |        165   |                 2.89  |              60.9 |                  95.6 |               83.2 |            2.64   |             2 |                 205   |                        1.18  |     12.5  |             52.8 |
| baseline-60m |     24 |         822 |        0 |             9.39e+03 |                  76.9 |         4.63 |        74.1  |        229   |                 1.69  |              29.7 |                  94.9 |               87.4 |            7.45   |             4 |                 122   |                        1.24  |     13.4  |             74.2 |
| baseline-60m |     32 |         899 |        0 |             9.6e+03  |                  75.8 |         5.37 |       154    |        283   |                 0.755 |              27.8 |                  94.3 |               87.3 |           23      |             3 |                  35.1 |                        1.67  |     12.9  |             73.3 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label        |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:-------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| baseline-60m |     12 |           1241 |                1.89e+04 |                    175   |           53.8  |           38.3  |           0.49  |            1.38 |                   350    |                 93.1 |                  39.4 |               0.0566 |
| baseline-60m |     16 |           1074 |                1.69e+04 |                    142   |           27.8  |           14.8  |           0.609 |           10.6  |                   284    |                 84.2 |                  71.9 |               0.708  |
| baseline-60m |     20 |            821 |                1.17e+04 |                    102   |           19.8  |            6.13 |           0.988 |           53    |                   191    |                 56.4 |                  89.1 |               2.87   |
| baseline-60m |     24 |            602 |                7.79e+03 |                     60.5 |            6.57 |            4.51 |          40.9   |           79.6  |                    86.9  |                 13   |                  93.3 |               8.12   |
| baseline-60m |     32 |            655 |                7.86e+03 |                     61.2 |            7.54 |            5.11 |         126     |          160    |                     1.57 |                 11.4 |                  93.4 |              25.1    |

## Validity checks

- baseline-60m c=12: light load: hit rate above 85% and KV peak below 80% (BENCHMARK-METRICS calibration rule)
- baseline-60m c=16: server hit 84.7% is 11.6 points below theoretical 96.3%; in-flight working set peaked at 1.14x the KV pool; working set peaked at 1.21x the KV pool (expect evictions)
- baseline-60m c=20: 8 requests cancelled when the grace period ended (not in the exports); server hit 60.9% is 34.7 points below theoretical 95.6%; in-flight working set peaked at 1.34x the KV pool; working set peaked at 1.44x the KV pool (expect evictions)
- baseline-60m c=24: 23 requests cancelled when the grace period ended (not in the exports); server hit 29.7% is 65.2 points below theoretical 94.9%; in-flight working set peaked at 1.46x the KV pool; working set peaked at 1.50x the KV pool (expect evictions)
- baseline-60m c=32: 42 requests cancelled when the grace period ended (not in the exports); server hit 27.8% is 66.6 points below theoretical 94.3%; in-flight working set peaked at 2.12x the KV pool; working set peaked at 2.15x the KV pool (expect evictions)
