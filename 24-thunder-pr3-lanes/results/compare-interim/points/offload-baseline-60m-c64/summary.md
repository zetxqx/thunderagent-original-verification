# AgentX sweep report

## Whole profiling window (AgentX)

| label                |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |
|:---------------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|
| offload-baseline-60m |     64 |        1601 |        0 |             1.96e+04 |                   177 |           16 |          205 |          262 |                 0.642 |              92.5 |                  95.1 |               92.4 |              60.4 |           287 |                  53.3 |                         3.48 |      19.3 |             47.5 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label                |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:---------------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| offload-baseline-60m |     64 |           1362 |                1.86e+04 |                      168 |            20.4 |            15.8 |             150 |             210 |                     6.84 |                 92.6 |                  96.3 |                 65.8 |

## Validity checks

- offload-baseline-60m c=64: in-flight working set peaked at 3.99x the KV pool; working set peaked at 4.19x the KV pool (expect evictions)
