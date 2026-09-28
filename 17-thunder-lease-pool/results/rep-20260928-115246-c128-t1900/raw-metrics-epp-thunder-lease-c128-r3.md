# Raw metric deltas, epp-thunder-lease-c128-r3

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2576 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6590 |  |
| `http_request_duration_highr_seconds_sum` | 187205 | 28.41 |
| `http_request_duration_seconds_count` | 6590 |  |
| `http_request_duration_seconds_sum` | 187205 | 28.41 |
| `http_request_size_bytes_count` | 6590 |  |
| `http_requests_total` | 6590 |  |
| `http_response_size_bytes_count` | 6590 |  |
| `http_response_size_bytes_sum` | 1.0506e+06 | 159.4 |
| `process_cpu_seconds_total` | 1986 |  |
| `python_gc_collections_total` | 1141 |  |
| `python_gc_objects_collected_total` | 1900 |  |
| `vllm:e2e_request_latency_seconds_count` | 4504 |  |
| `vllm:e2e_request_latency_seconds_sum` | 183486 | 40.74 |
| `vllm:generation_tokens_total` | 3.70264e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.69811e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 178603 | 0.0483 |
| `vllm:iteration_tokens_total_count` | 177398 |  |
| `vllm:iteration_tokens_total_sum` | 5.62908e+07 | 317.3 |
| `vllm:num_preemptions_total` | 8 |  |
| `vllm:prefix_cache_hits_total` | 2.52238e+08 |  |
| `vllm:prefix_cache_queries_total` | 3.05024e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 3.04827e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.52238e+08 |  |
| `vllm:prompt_tokens_total` | 3.04827e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4504 |  |
| `vllm:request_decode_time_seconds_sum` | 175080 | 38.87 |
| `vllm:request_generation_tokens_count` | 4504 |  |
| `vllm:request_generation_tokens_sum` | 3.63184e+06 | 806.4 |
| `vllm:request_inference_time_seconds_count` | 4504 |  |
| `vllm:request_inference_time_seconds_sum` | 178010 | 39.52 |
| `vllm:request_max_num_generation_tokens_count` | 4504 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.63184e+06 | 806.4 |
| `vllm:request_params_max_tokens_count` | 4504 |  |
| `vllm:request_params_max_tokens_sum` | 3.63184e+06 | 806.4 |
| `vllm:request_params_n_count` | 4504 |  |
| `vllm:request_params_n_sum` | 4504 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4504 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 5.12666e+07 | 1.138e+04 |
| `vllm:request_prefill_time_seconds_count` | 4504 |  |
| `vllm:request_prefill_time_seconds_sum` | 2930.49 | 0.6506 |
| `vllm:request_prompt_tokens_count` | 4504 |  |
| `vllm:request_prompt_tokens_sum` | 3.0256e+08 | 6.718e+04 |
| `vllm:request_queue_time_seconds_count` | 4504 |  |
| `vllm:request_queue_time_seconds_sum` | 4446.03 | 0.9871 |
| `vllm:request_success_total` | 4504 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4504 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 241.795 | 0.05368 |
| `vllm:time_to_first_token_seconds_count` | 4528 |  |
| `vllm:time_to_first_token_seconds_sum` | 8542.2 | 1.887 |

## EPP (2576 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.20764 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 58.6045 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 22.3703 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 25.4035 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 108.586 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 80382 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00105268 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.477848 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.4789 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 82427.2 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1936.11 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3498 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3498 |  |
| `go_gc_duration_seconds_count` | 3498 |  |
| `go_gc_duration_seconds_sum` | 1.23388 | 0.0003527 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.45282e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.65043e+11 | 47.8 |
| `go_gc_heap_allocs_bytes_total` | 1.65043e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.45282e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.45275e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.65037e+11 | 47.8 |
| `go_gc_heap_frees_bytes_total` | 1.65037e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.45275e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.15704e+08 |  |
| `go_gc_pauses_seconds_count` | 6996 |  |
| `go_gc_pauses_seconds_sum` | 0.393651 | 5.627e-05 |
| `go_memstats_alloc_bytes_total` | 1.65043e+11 |  |
| `go_memstats_frees_total` | 3.76846e+09 |  |
| `go_memstats_mallocs_total` | 3.76853e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 32299 |  |
| `go_sched_latencies_seconds_count` | 2.89978e+06 |  |
| `go_sched_latencies_seconds_sum` | 41.5502 | 1.433e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6996 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.265299 | 3.792e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6996 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.393651 | 5.627e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 31.3295 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.42755e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 265.337 | 0.0001093 |
| `llm_d_epp_flow_control_requests_total` | 4530 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 7.44212e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 40.8411 | 5.488e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4504 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.51293e+08 | 5.579e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4504 |  |
| `llm_d_epp_request_duration_seconds_sum` | 228254 | 50.68 |
| `llm_d_epp_request_input_tokens_count` | 4504 |  |
| `llm_d_epp_request_input_tokens_sum` | 3.0256e+08 | 6.718e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4504 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 473.651 | 0.1052 |
| `llm_d_epp_request_output_tokens_count` | 4504 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.63184e+06 | 806.4 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4530 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 55118.6 | 12.17 |
| `llm_d_epp_request_size_bytes_count` | 4530 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.22808e+09 | 2.711e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.69389e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 178481 | 0.04832 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4504 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 240.916 | 0.05349 |
| `llm_d_epp_request_total` | 4530 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4504 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 53295.7 | 11.83 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4529 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 79.437 | 0.01754 |
| `llm_d_epp_response_size_bytes_count` | 4504 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.79956e+08 | 2.176e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4530 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4530 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.16596 | 3.664e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 246 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 334 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4530 |  |
| `process_cpu_seconds_total` | 1860.17 |  |
| `process_network_receive_bytes_total` | 2.15511e+10 |  |
| `process_network_transmit_bytes_total` | 1.35404e+10 |  |
| `rest_client_requests_total` | 71 |  |
