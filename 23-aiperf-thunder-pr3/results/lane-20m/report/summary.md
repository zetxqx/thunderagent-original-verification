# AgentX sweep report

## Whole profiling window (AgentX)

| label    |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |
|:---------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|
| lane-20m |     12 |         594 |        0 |             2.27e+04 |                 178   |        35.3  |         1.22 |         36.6 |                  29.5 |              94.2 |                  96   |               36.7 |            0.0459 |             0 |                   355 |                        0.566 |      6.36 |             17.1 |
| lane-20m |     16 |         524 |        0 |             1.94e+04 |                 167   |        18.8  |         2.07 |         49.1 |                  15.8 |              91.9 |                  94.9 |               57.2 |            0.142  |             0 |                   334 |                        0.701 |      8.08 |             21.9 |
| lane-20m |     20 |         655 |        0 |             2.26e+04 |                 169   |        17.4  |         2.78 |         61.7 |                  13.9 |              88.6 |                  95.1 |               61.8 |            0.68   |             0 |                   334 |                        0.808 |     10.1  |             26.7 |
| lane-20m |     24 |         439 |        0 |             1.3e+04  |                  87.2 |         4.57 |        35.4  |        141   |                   2.1 |              51.3 |                  93.4 |               72.6 |            5.22   |             1 |                   166 |                        0.89  |      9.47 |             42.3 |
| lane-20m |     32 |         410 |        0 |             1.19e+04 |                  90.8 |         6.34 |       105    |        191   |                   1.2 |              47.8 |                  93.2 |               73.2 |           14.6    |             2 |                   103 |                        1.16  |      8.58 |             38.5 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label    |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:---------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| lane-20m |     12 |            474 |                2.42e+04 |                    199   |           46.8  |           34.3  |           0.466 |            1.35 |                   398    |                 93.9 |                  44.8 |               0.0574 |
| lane-20m |     16 |            442 |                2.19e+04 |                    169   |           25.1  |           18.2  |           0.563 |            2.25 |                   337    |                 91.6 |                  72.2 |               0.187  |
| lane-20m |     20 |            484 |                2.3e+04  |                    164   |           22.7  |           17    |           0.54  |            3.29 |                   321    |                 88.2 |                  76   |               0.885  |
| lane-20m |     24 |            227 |                9.01e+03 |                     44.4 |            5.61 |            3.93 |          25.4   |           45.3  |                    77.6  |                 21.8 |                  88.6 |               6.84   |
| lane-20m |     32 |            170 |                6.75e+03 |                     44.2 |            7.82 |            5.91 |          85.8   |          124    |                     1.35 |                 10.1 |                  90.4 |              19.3    |

## Validity checks

- lane-20m c=12: 3 requests cancelled when the grace period ended (not in the exports); light load: hit rate above 85% and KV peak below 80% (BENCHMARK-METRICS calibration rule)
- lane-20m c=16: 5 requests cancelled when the grace period ended (not in the exports); working set peaked at 1.12x the KV pool (expect evictions)
- lane-20m c=20: 12 requests cancelled when the grace period ended (not in the exports); in-flight working set peaked at 1.09x the KV pool; working set peaked at 1.22x the KV pool (expect evictions)
- lane-20m c=24: 23 requests cancelled when the grace period ended (not in the exports); server hit 51.3% is 42.1 points below theoretical 93.4%; in-flight working set peaked at 1.28x the KV pool; working set peaked at 1.33x the KV pool (expect evictions)
- lane-20m c=32: 31 requests cancelled when the grace period ended (not in the exports); server hit 47.8% is 45.4 points below theoretical 93.2%; in-flight working set peaked at 1.76x the KV pool; working set peaked at 1.76x the KV pool (expect evictions)
