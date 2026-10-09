# AgentX sweep report

## Whole profiling window (AgentX)

| label                |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |
|:---------------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|
| offload-baseline-60m |     32 |        1594 |        0 |             2.08e+04 |                   173 |           18 |         67.7 |          134 |                   1.9 |              95.3 |                  95.8 |               89.9 |              16.6 |           171 |                   280 |                         1.88 |      14.1 |             39.3 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label                |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:---------------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| offload-baseline-60m |     32 |           1350 |                2.02e+04 |                      167 |            21.1 |            17.7 |              43 |            70.7 |                      261 |                 95.5 |                  96.3 |                 18.1 |

## Validity checks

- offload-baseline-60m c=32: in-flight working set peaked at 2.13x the KV pool; working set peaked at 2.37x the KV pool (expect evictions)
