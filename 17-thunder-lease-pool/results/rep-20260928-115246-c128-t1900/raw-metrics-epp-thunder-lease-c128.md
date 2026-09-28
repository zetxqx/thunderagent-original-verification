# Raw metric deltas, epp-thunder-lease-c128

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2536 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6360 |  |
| `http_request_duration_highr_seconds_sum` | 196450 | 30.89 |
| `http_request_duration_seconds_count` | 6360 |  |
| `http_request_duration_seconds_sum` | 196450 | 30.89 |
| `http_request_size_bytes_count` | 6360 |  |
| `http_requests_total` | 6360 |  |
| `http_response_size_bytes_count` | 6360 |  |
| `http_response_size_bytes_sum` | 1.03581e+06 | 162.9 |
| `process_cpu_seconds_total` | 1887.14 |  |
| `python_gc_collections_total` | 1037 |  |
| `python_gc_objects_collected_total` | 482 |  |
| `vllm:e2e_request_latency_seconds_count` | 4313 |  |
| `vllm:e2e_request_latency_seconds_sum` | 193862 | 44.95 |
| `vllm:generation_tokens_total` | 3.43256e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.42823e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 186640 | 0.05444 |
| `vllm:iteration_tokens_total_count` | 154019 |  |
| `vllm:iteration_tokens_total_sum` | 6.59983e+07 | 428.5 |
| `vllm:num_preemptions_total` | 7 |  |
| `vllm:prefix_cache_hits_total` | 2.21825e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.84391e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.84391e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.21825e+08 |  |
| `vllm:prompt_tokens_total` | 2.84391e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4313 |  |
| `vllm:request_decode_time_seconds_sum` | 184162 | 42.7 |
| `vllm:request_generation_tokens_count` | 4313 |  |
| `vllm:request_generation_tokens_sum` | 3.36743e+06 | 780.8 |
| `vllm:request_inference_time_seconds_count` | 4313 |  |
| `vllm:request_inference_time_seconds_sum` | 187748 | 43.53 |
| `vllm:request_max_num_generation_tokens_count` | 4313 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.36743e+06 | 780.8 |
| `vllm:request_params_max_tokens_count` | 4313 |  |
| `vllm:request_params_max_tokens_sum` | 3.36743e+06 | 780.8 |
| `vllm:request_params_n_count` | 4313 |  |
| `vllm:request_params_n_sum` | 4313 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4313 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 6.19843e+07 | 1.437e+04 |
| `vllm:request_prefill_time_seconds_count` | 4313 |  |
| `vllm:request_prefill_time_seconds_sum` | 3585.65 | 0.8314 |
| `vllm:request_prompt_tokens_count` | 4313 |  |
| `vllm:request_prompt_tokens_sum` | 2.83014e+08 | 6.562e+04 |
| `vllm:request_queue_time_seconds_count` | 4313 |  |
| `vllm:request_queue_time_seconds_sum` | 5098.27 | 1.182 |
| `vllm:request_success_total` | 4313 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4313 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 248.611 | 0.05764 |
| `vllm:time_to_first_token_seconds_count` | 4329 |  |
| `vllm:time_to_first_token_seconds_sum` | 9770.21 | 2.257 |

## EPP (2536 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 1.97384 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 54.6652 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 21.1335 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 22.1763 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 99.9489 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 79331.7 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.452719 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.452719 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 81137.6 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1705.51 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3409 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3409 |  |
| `go_gc_duration_seconds_count` | 3409 |  |
| `go_gc_duration_seconds_sum` | 1.08718 | 0.0003189 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.37768e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.58985e+11 | 47.07 |
| `go_gc_heap_allocs_bytes_total` | 1.58985e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.37768e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.37752e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.58976e+11 | 47.07 |
| `go_gc_heap_frees_bytes_total` | 1.58976e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.37752e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.09118e+08 |  |
| `go_gc_pauses_seconds_count` | 6818 |  |
| `go_gc_pauses_seconds_sum` | 0.371963 | 5.456e-05 |
| `go_memstats_alloc_bytes_total` | 1.58985e+11 |  |
| `go_memstats_frees_total` | 3.68664e+09 |  |
| `go_memstats_mallocs_total` | 3.68679e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 31177 |  |
| `go_sched_latencies_seconds_count` | 2.67156e+06 |  |
| `go_sched_latencies_seconds_sum` | 36.9913 | 1.385e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6818 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.24661 | 3.617e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6818 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.371963 | 5.456e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 22.5808 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.39594e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 231.268 | 9.652e-05 |
| `llm_d_epp_flow_control_requests_total` | 4329 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.90403e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 35.8154 | 5.188e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4313 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.21029e+08 | 5.125e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4313 |  |
| `llm_d_epp_request_duration_seconds_sum` | 235668 | 54.64 |
| `llm_d_epp_request_input_tokens_count` | 4313 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.83014e+08 | 6.562e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4313 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 667.209 | 0.1547 |
| `llm_d_epp_request_output_tokens_count` | 4313 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.36743e+06 | 780.8 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4329 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 45532.9 | 10.52 |
| `llm_d_epp_request_size_bytes_count` | 4329 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.13413e+09 | 2.62e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.42605e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 186523 | 0.05444 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4313 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 247.919 | 0.05748 |
| `llm_d_epp_request_total` | 4329 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4313 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 51620.9 | 11.97 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4329 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 69.699 | 0.0161 |
| `llm_d_epp_response_size_bytes_count` | 4313 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.07586e+08 | 2.104e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4329 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4329 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.14778 | 3.414e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 227 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 308 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4329 |  |
| `process_cpu_seconds_total` | 1672.47 |  |
| `process_network_receive_bytes_total` | 2.07025e+10 |  |
| `process_network_transmit_bytes_total` | 1.24979e+10 |  |
| `rest_client_requests_total` | 70 |  |
