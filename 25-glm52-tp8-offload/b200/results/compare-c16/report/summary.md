# AgentX sweep report

## Whole profiling window (AgentX)

| label              |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |   gate_delayed_dispatches |   gate_pauses |   gate_starvation_promotions |   epp_queue_wait_p90_s |
|:-------------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|--------------------------:|--------------:|-----------------------------:|-----------------------:|
| r1                 |     16 |        2328 |        0 |             1.14e+04 |                  79   |         87.8 |         6.13 |         18.4 |                  33.7 |              97.1 |                  97.3 |               49.6 |             0.812 |             2 |                   632 |                         2    |      12.5 |             17.8 |                       nan |           nan |                          nan |             nan        |
| thunder-cpu-l10-r1 |     16 |        2323 |        0 |             1.14e+04 |                  78.7 |         86.8 |         5.6  |         19.1 |                  32.4 |              97.1 |                  97.3 |               50   |             0.813 |             7 |                   630 |                         2    |      12.4 |             17.8 |                         0 |           178 |                            0 |               0.00045  |
| thunder-r1         |     16 |        2288 |        0 |             1.02e+04 |                  75   |        109   |         2.46 |         17.6 |                  51.9 |              96.9 |                  97.1 |               34.1 |             0.109 |             0 |                   583 |                         1.94 |      10.5 |             15.4 |                       131 |           287 |                            0 |               0.000477 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label              |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:-------------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| r1                 |     16 |           2219 |                1.21e+04 |                     81.3 |             161 |            87.6 |           0.79  |            6.3  |                      650 |                 97.2 |                  53.3 |                0.884 |
| thunder-cpu-l10-r1 |     16 |           2215 |                1.2e+04  |                     81   |             162 |            86.7 |           0.833 |            5.66 |                      648 |                 97.2 |                  53.8 |                0.885 |
| thunder-r1         |     16 |           2178 |                1.08e+04 |                     77.2 |             186 |           109   |           0.635 |            2.47 |                      600 |                 97   |                  36.4 |                0.117 |

## Validity checks

- r1 c=16: in-flight working set peaked at 1.84x the KV pool; working set peaked at 2.69x the KV pool (expect evictions)
- thunder-cpu-l10-r1 c=16: in-flight working set peaked at 1.74x the KV pool; working set peaked at 2.70x the KV pool (expect evictions)
- thunder-r1 c=16: 1 requests cancelled when the grace period ended (not in the exports), 1 of them without a first token (counted as SLO misses); in-flight working set peaked at 2.11x the KV pool; working set peaked at 2.54x the KV pool (expect evictions)
