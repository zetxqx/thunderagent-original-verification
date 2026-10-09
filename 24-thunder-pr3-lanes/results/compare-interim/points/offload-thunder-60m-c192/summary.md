# AgentX sweep report

## Whole profiling window (AgentX)

| label               |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |   gate_delayed_dispatches |   gate_pauses |   gate_starvation_promotions |   epp_queue_wait_p90_s |
|:--------------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|--------------------------:|--------------:|-----------------------------:|-----------------------:|
| offload-thunder-60m |    192 |        2536 |        0 |             1.75e+04 |                   227 |           13 |          167 |          261 |                  2.08 |              76.9 |                  92.7 |               82.7 |              78.9 |            22 |                   384 |                          6.1 |      33.6 |               62 |                       828 |           831 |                          243 |                  0.175 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label               |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:--------------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| offload-thunder-60m |    192 |           2094 |                1.56e+04 |                      209 |            21.7 |            15.5 |           0.537 |             104 |                      355 |                 76.9 |                    84 |                 85.7 |

## Validity checks

- offload-thunder-60m c=192: server hit 76.9% is 15.8 points below theoretical 92.7%; in-flight working set peaked at 9.45x the KV pool; working set peaked at 9.60x the KV pool (expect evictions); 243 forced admissions: demand is past the pool's capacity
