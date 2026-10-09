# AgentX sweep report

## Whole profiling window (AgentX)

| label                |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |
|:---------------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|
| offload-baseline-60m |     96 |         690 |        0 |             8.07e+03 |                  78.7 |         6.56 |          837 |          973 |                 0.183 |              30.5 |                  94.4 |               92.6 |               104 |           113 |                  48.8 |                         4.59 |        21 |              107 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label                |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:---------------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| offload-baseline-60m |     96 |            419 |                 5.9e+03 |                     57.1 |            8.63 |            6.26 |             805 |             849 |                        0 |                   12 |                  93.9 |                  113 |

## Validity checks

- offload-baseline-60m c=96: 129 requests cancelled when the grace period ended (not in the exports); server hit 30.5% is 63.9 points below theoretical 94.4%; in-flight working set peaked at 5.82x the KV pool; working set peaked at 5.85x the KV pool (expect evictions)
