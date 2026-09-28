# Raw metric deltas, epp-thunder-min-c128-r2

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2618 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6309 |  |
| `http_request_duration_highr_seconds_sum` | 194115 | 30.77 |
| `http_request_duration_seconds_count` | 6309 |  |
| `http_request_duration_seconds_sum` | 194115 | 30.77 |
| `http_request_size_bytes_count` | 6309 |  |
| `http_requests_total` | 6309 |  |
| `http_response_size_bytes_count` | 6309 |  |
| `http_response_size_bytes_sum` | 1.06743e+06 | 169.2 |
| `process_cpu_seconds_total` | 1884.95 |  |
| `python_gc_collections_total` | 1044 |  |
| `python_gc_objects_collected_total` | 2647 |  |
| `vllm:e2e_request_latency_seconds_count` | 4183 |  |
| `vllm:e2e_request_latency_seconds_sum` | 187312 | 44.78 |
| `vllm:generation_tokens_total` | 3.29997e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.29576e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 183485 | 0.05567 |
| `vllm:iteration_tokens_total_count` | 160045 |  |
| `vllm:iteration_tokens_total_sum` | 7.58595e+07 | 474 |
| `vllm:num_preemptions_total` | 12 |  |
| `vllm:prefix_cache_hits_total` | 2.02102e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.74773e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.74661e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.02102e+08 |  |
| `vllm:prompt_tokens_total` | 2.74661e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4183 |  |
| `vllm:request_decode_time_seconds_sum` | 176916 | 42.29 |
| `vllm:request_generation_tokens_count` | 4183 |  |
| `vllm:request_generation_tokens_sum` | 3.22131e+06 | 770.1 |
| `vllm:request_inference_time_seconds_count` | 4183 |  |
| `vllm:request_inference_time_seconds_sum` | 180702 | 43.2 |
| `vllm:request_max_num_generation_tokens_count` | 4183 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.22131e+06 | 770.1 |
| `vllm:request_params_max_tokens_count` | 4183 |  |
| `vllm:request_params_max_tokens_sum` | 3.22131e+06 | 770.1 |
| `vllm:request_params_n_count` | 4183 |  |
| `vllm:request_params_n_sum` | 4183 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4183 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 7.07485e+07 | 1.691e+04 |
| `vllm:request_prefill_time_seconds_count` | 4183 |  |
| `vllm:request_prefill_time_seconds_sum` | 3786.05 | 0.9051 |
| `vllm:request_prompt_tokens_count` | 4183 |  |
| `vllm:request_prompt_tokens_sum` | 2.72208e+08 | 6.507e+04 |
| `vllm:request_queue_time_seconds_count` | 4183 |  |
| `vllm:request_queue_time_seconds_sum` | 5638.21 | 1.348 |
| `vllm:request_success_total` | 4183 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4183 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 257.232 | 0.06149 |
| `vllm:time_to_first_token_seconds_count` | 4214 |  |
| `vllm:time_to_first_token_seconds_sum` | 10577.5 | 2.51 |

## EPP (2618 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.10492 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 63.2629 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 20.853 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 26.4565 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 112.677 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 81802.4 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.529046 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.529046 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 83793.6 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1877.94 |  |
| `go_gc_cleanups_executed_cleanups_total` | 1 |  |
| `go_gc_cleanups_queued_cleanups_total` | 1 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3657 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3657 |  |
| `go_gc_duration_seconds_count` | 3657 |  |
| `go_gc_duration_seconds_sum` | 1.29225 | 0.0003534 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.46872e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.58172e+11 | 45.6 |
| `go_gc_heap_allocs_bytes_total` | 1.58172e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.46872e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.46864e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.58166e+11 | 45.6 |
| `go_gc_heap_frees_bytes_total` | 1.58166e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.46864e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.21162e+08 |  |
| `go_gc_pauses_seconds_count` | 7314 |  |
| `go_gc_pauses_seconds_sum` | 0.40976 | 5.602e-05 |
| `go_memstats_alloc_bytes_total` | 1.58172e+11 |  |
| `go_memstats_frees_total` | 3.7898e+09 |  |
| `go_memstats_mallocs_total` | 3.78988e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 31716 |  |
| `go_sched_latencies_seconds_count` | 2.65973e+06 |  |
| `go_sched_latencies_seconds_sum` | 38.6622 | 1.454e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 7314 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.275014 | 3.76e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 7314 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.40976 | 5.602e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 30.8778 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.48298e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 257.366 | 0.0001037 |
| `llm_d_epp_flow_control_requests_total` | 4217 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.63477e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 36.0295 | 5.43e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4183 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.0146e+08 | 4.816e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4183 |  |
| `llm_d_epp_request_duration_seconds_sum` | 220912 | 52.81 |
| `llm_d_epp_request_input_tokens_count` | 4183 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.72208e+08 | 6.507e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4183 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 746.624 | 0.1785 |
| `llm_d_epp_request_output_tokens_count` | 4183 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.22131e+06 | 770.1 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4217 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 50457.1 | 11.97 |
| `llm_d_epp_request_size_bytes_count` | 4217 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.09923e+09 | 2.607e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.2921e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 183371 | 0.0557 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4183 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 256.424 | 0.0613 |
| `llm_d_epp_request_total` | 4217 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4183 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 44109.3 | 10.54 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4215 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 72.1942 | 0.01713 |
| `llm_d_epp_response_size_bytes_count` | 4183 |  |
| `llm_d_epp_response_size_bytes_sum` | 8.67986e+08 | 2.075e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4217 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4217 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.153484 | 3.64e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 296 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 423 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4217 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 350 |  |
| `llm_d_epp_thunder_agent_starvation_promotions_total` | 1 |  |
| `process_cpu_seconds_total` | 1810.37 |  |
| `process_network_receive_bytes_total` | 2.08646e+10 |  |
| `process_network_transmit_bytes_total` | 1.27329e+10 |  |
| `rest_client_requests_total` | 73 |  |
