# AgentX sweep report

## Whole profiling window (AgentX)

| label   |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |
|:--------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|
| calib   |      1 |         106 |        0 |             2.84e+03 |                  12.9 |          283 |         1.44 |         9.42 |                  69.9 |              96.8 |                  96.9 |               4.26 |           0.00666 |             0 |                   103 |                         0.13 |      3.19 |             10.9 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label   |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:--------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| calib   |      1 |             74 |                1.88e+03 |                     15.1 |             327 |             278 |           0.464 |            1.56 |                      120 |                 93.6 |                  3.46 |              0.00998 |

## Validity checks

- calib c=1: light load: hit rate above 85% and KV peak below 80% (BENCHMARK-METRICS calibration rule)
