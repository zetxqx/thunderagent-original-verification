# AgentX sweep report

## Whole profiling window (AgentX)

| label   |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |
|:--------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|
| r1      |      1 |         272 |        0 |             2.6e+03  |                  18.6 |        269   |         1.66 |         16.2 |                  91.5 |              98   |                  98.1 |               8.78 |           0.00472 |             0 |                   149 |                        0.204 |      3.5  |             9.48 |
| r1      |      4 |         620 |        0 |             4.01e+03 |                  27.8 |        211   |         1.8  |         13.5 |                  95.8 |              97.7 |                  97.9 |              11.6  |           0.00469 |             0 |                   222 |                        0.69  |      4.6  |            10.5  |
| r1      |      8 |        1328 |        0 |             7e+03    |                  51.3 |        152   |         1.55 |         12.8 |                  86.7 |              97.5 |                  97.8 |              21.5  |           0.0245  |             0 |                   411 |                        1.07  |      6.84 |            12.5  |
| r1      |     12 |        1653 |        0 |             8.02e+03 |                  62.6 |        135   |         1.63 |         14.7 |                  67.6 |              97   |                  97.4 |              28    |           0.0755  |             1 |                   501 |                        1.42  |      9.02 |            14.1  |
| r1      |     16 |        2328 |        0 |             1.14e+04 |                  79   |         87.8 |         6.13 |         18.4 |                  33.7 |              97.1 |                  97.3 |              49.6  |           0.812   |             2 |                   632 |                        2     |     12.5  |            17.8  |

## Steady state: requests started after minute 5 (sweep figures use these)

| label   |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:--------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| r1      |      1 |            240 |                2.41e+03 |                     19.5 |             344 |           267   |           1.04  |            1.68 |                      156 |                 97.8 |                  9.07 |              0.00515 |
| r1      |      4 |            540 |                4.17e+03 |                     28.4 |             296 |           217   |           0.646 |            1.83 |                      228 |                 97.9 |                 12.2  |              0.00481 |
| r1      |      8 |           1285 |                7.49e+03 |                     53.5 |             237 |           151   |           0.575 |            1.56 |                      428 |                 97.6 |                 23    |              0.0261  |
| r1      |     12 |           1517 |                8.29e+03 |                     65.5 |             206 |           135   |           0.636 |            1.65 |                      524 |                 97.1 |                 29.9  |              0.0814  |
| r1      |     16 |           2219 |                1.21e+04 |                     81.3 |             161 |            87.6 |           0.79  |            6.3  |                      650 |                 97.2 |                 53.3  |              0.884   |

## Validity checks

- r1 c=1: light load: hit rate above 85% and KV peak below 80% (BENCHMARK-METRICS calibration rule)
- r1 c=4: working set peaked at 1.01x the KV pool (expect evictions); light load: hit rate above 85% and KV peak below 80% (BENCHMARK-METRICS calibration rule)
- r1 c=8: working set peaked at 1.52x the KV pool (expect evictions)
- r1 c=12: in-flight working set peaked at 1.25x the KV pool; working set peaked at 2.00x the KV pool (expect evictions)
- r1 c=16: in-flight working set peaked at 1.84x the KV pool; working set peaked at 2.69x the KV pool (expect evictions)
