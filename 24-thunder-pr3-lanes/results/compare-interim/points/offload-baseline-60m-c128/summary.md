# AgentX sweep report

## Whole profiling window (AgentX)

| label                |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |
|:---------------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|
| offload-baseline-60m |    128 |         785 |        0 |             7.68e+03 |                  93.2 |         5.98 |     1.17e+03 |     1.26e+03 |                 0.148 |              23.5 |                  92.5 |               92.7 |               176 |            87 |                  43.7 |                          5.6 |      25.4 |              109 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label                |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:---------------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| offload-baseline-60m |    128 |            484 |                5.92e+03 |                     64.8 |            8.41 |            5.74 |        1.04e+03 |        1.19e+03 |                        0 |                 12.6 |                  93.7 |                  189 |

## Validity checks

- offload-baseline-60m c=128: 255 requests cancelled when the grace period ended (not in the exports); server hit 23.5% is 69.0 points below theoretical 92.5%; in-flight working set peaked at 7.37x the KV pool; working set peaked at 7.51x the KV pool (expect evictions)
