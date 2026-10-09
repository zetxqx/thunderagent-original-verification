# AgentX sweep report

## Whole profiling window (AgentX)

| label               |   conc |   completed |   errors |   total_tput_per_gpu |   output_tput_per_gpu |   p90_intvty |   p90_ttft_s |   p90_e2el_s |   p90_e2e_norm_intvty |   overall_hit_pct |   theoretical_hit_pct |   kv_usage_avg_pct |   waiting_avg_sum |   preemptions |   goodput_output_tput |   working_set_over_pool_mean |   batch_B |   step_time_T_ms |   gate_delayed_dispatches |   gate_pauses |   gate_starvation_promotions |   epp_queue_wait_p90_s |
|:--------------------|-------:|------------:|---------:|---------------------:|----------------------:|-------------:|-------------:|-------------:|----------------------:|------------------:|----------------------:|-------------------:|------------------:|--------------:|----------------------:|-----------------------------:|----------:|-----------------:|--------------------------:|--------------:|-----------------------------:|-----------------------:|
| offload-thunder-60m |     96 |        1627 |        0 |             1.63e+04 |                   168 |         14.2 |          205 |          356 |                  1.92 |              79.5 |                  94.6 |               87.6 |              25.1 |            23 |                   280 |                         4.25 |      23.4 |             60.2 |                       324 |           365 |                           75 |               0.000926 |

## Steady state: requests started after minute 5 (sweep figures use these)

| label               |   conc |   ss_completed |   ss_total_tput_per_gpu |   ss_output_tput_per_gpu |   ss_p50_intvty |   ss_p90_intvty |   ss_p50_ttft_s |   ss_p90_ttft_s |   ss_goodput_output_tput |   ss_overall_hit_pct |   ss_kv_usage_avg_pct |   ss_waiting_avg_sum |
|:--------------------|-------:|---------------:|------------------------:|-------------------------:|----------------:|----------------:|----------------:|----------------:|-------------------------:|---------------------:|----------------------:|---------------------:|
| offload-thunder-60m |     96 |           1336 |                1.48e+04 |                      144 |            21.5 |              15 |           0.664 |             218 |                      239 |                 78.7 |                  89.4 |                 27.3 |

## Validity checks

- offload-thunder-60m c=96: server hit 79.5% is 15.1 points below theoretical 94.6%; in-flight working set peaked at 6.10x the KV pool; working set peaked at 6.12x the KV pool (expect evictions); 75 forced admissions: demand is past the pool's capacity
