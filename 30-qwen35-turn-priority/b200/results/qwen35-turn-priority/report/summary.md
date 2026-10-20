# AgentX sweep report

## Whole profiling window (AgentX)

| label                |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p99_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |   epp_queue_wait_p90_s |
|:---------------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|-----------------------:|
| qwen35-turn-priority |     32 |        4640 |        0 |             3.48e+04 |                   304 |         46.6 |         1.44 |         25.4 |           85 |                 34.7  |              93   |                  96.5 |               36.6 |             0.136 |             0 |              1.22e+03 |                        0.863 |      34.5 |             28   |                0.00049 |
| qwen35-turn-priority |     48 |        6241 |        0 |             4.06e+04 |                   402 |         39.2 |         4.72 |         36.3 |          106 |                 22    |              91.3 |                  95.6 |               66.6 |             0.616 |             0 |              1.61e+03 |                        1.36  |      72   |             44.4 |                2.25    |
| qwen35-turn-priority |     64 |        6537 |        0 |             4.01e+04 |                   419 |         29.4 |        22.6  |         55.6 |          146 |                  6.57 |              88.3 |                  95.3 |               86.7 |             5.74  |            58 |              1.68e+03 |                        1.78  |      93.5 |             55.4 |               21.7     |

## Steady state: requests started after minute 5 (sweep figures use these)

| label                |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_e2e_norm_intvty |   ss_p90_e2e_norm_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_p90_e2el_s |   ss_p99_e2el_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:---------------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|-------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| qwen35-turn-priority |     32 |           4361 |                3.62e+04 |                      319 |            95.6 |            46.2 |                     76.2 |                    34.3  |           0.767 |            1.45 |            26   |            85.7 |                 1.28e+03 |                 93.2 |                  39.3 |                0.147 |
| qwen35-turn-priority |     48 |           5941 |                4.25e+04 |                      417 |            61.1 |            39   |                     48.2 |                    21.8  |           1.19  |            4.84 |            37.1 |           107   |                 1.67e+03 |                 91.4 |                  71.1 |                0.667 |
| qwen35-turn-priority |     64 |           6189 |                4.14e+04 |                      434 |            48.2 |            29.1 |                     21.3 |                     6.33 |          11.3   |           23    |            57.3 |           153   |                 1.73e+03 |                 88.2 |                  93   |                6.25  |

## Validity checks

- qwen35-turn-priority c=32: working set peaked at 1.17x the KV pool (expect evictions)
- qwen35-turn-priority c=48: 1 requests cancelled when the grace period ended (not in the exports); in-flight working set peaked at 1.20x the KV pool; working set peaked at 1.65x the KV pool (expect evictions)
- qwen35-turn-priority c=64: 5 requests cancelled when the grace period ended (not in the exports); in-flight working set peaked at 1.61x the KV pool; working set peaked at 2.22x the KV pool (expect evictions)
