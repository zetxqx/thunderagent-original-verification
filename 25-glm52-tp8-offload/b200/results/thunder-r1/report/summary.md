# AgentX sweep report

## Whole profiling window (AgentX)

| label      |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |   gate_delayed_dispatches |   gate_pauses |   gate_starvation_promotions |   epp_queue_wait_p90_s |
|:-----------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|--------------------------:|--------------:|-----------------------------:|-----------------------:|
| thunder-r1 |     12 |        1639 |        0 |             7.85e+03 |                  61.8 |          140 |         1.76 |         15.2 |                  70.2 |              97   |                  97.4 |               25.9 |            0.0567 |             0 |                   494 |                         1.41 |      8.99 |             13.9 |                        46 |           205 |                            0 |               0.000447 |
| thunder-r1 |     16 |        2288 |        0 |             1.02e+04 |                  75   |          109 |         2.46 |         17.6 |                  51.9 |              96.9 |                  97.1 |               34.1 |            0.109  |             0 |                   583 |                         1.94 |     10.5  |             15.4 |                       131 |           287 |                            0 |               0.000477 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label      |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:-----------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| thunder-r1 |     12 |           1498 |                8.09e+03 |                     64.5 |             209 |             140 |           0.627 |            1.81 |                      516 |                 97.1 |                  27.6 |               0.0603 |
| thunder-r1 |     16 |           2178 |                1.08e+04 |                     77.2 |             186 |             109 |           0.635 |            2.47 |                      600 |                 97   |                  36.4 |               0.117  |

## Validity checks

- thunder-r1 c=12: in-flight working set peaked at 1.11x the KV pool; working set peaked at 1.87x the KV pool (expect evictions)
- thunder-r1 c=16: 1 requests cancelled when the grace period ended (not in the exports), 1 of them without a first token (counted as SLO misses); in-flight working set peaked at 2.11x the KV pool; working set peaked at 2.54x the KV pool (expect evictions)
