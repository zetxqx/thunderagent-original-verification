# AgentX sweep report

## Whole profiling window (AgentX)

| label                      |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |   gate_delayed_dispatches |   gate_pauses |   gate_starvation_promotions |   epp_queue_wait_p90_s |
|:---------------------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|--------------------------:|--------------:|-----------------------------:|-----------------------:|
| smoke-main-thunder-gpu-l10 |     24 |         999 |        0 |             1.28e+04 |                   115 |         86.5 |          2.8 |         19.6 |                    40 |              94.8 |                  95.2 |               49.4 |             0.282 |             0 |                   903 |                         1.56 |      19.7 |             20.7 |                        67 |           140 |                            0 |               0.000479 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label                      |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:---------------------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| smoke-main-thunder-gpu-l10 |     24 |            682 |                1.41e+04 |                      128 |             137 |            81.4 |           0.661 |            4.55 |                    1e+03 |                 95.3 |                  62.8 |                0.321 |

## Validity checks

- smoke-main-thunder-gpu-l10 c=24: 5 requests cancelled when the grace period ended (not in the exports), 3 of them without a first token (counted as SLO misses); in-flight working set peaked at 2.06x the KV pool; working set peaked at 2.64x the KV pool (expect evictions)
