# Raw metric deltas, epp-thunder-lease5-c128-r3

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2549 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6405 |  |
| `http_request_duration_highr_seconds_sum` | 200387 | 31.29 |
| `http_request_duration_seconds_count` | 6405 |  |
| `http_request_duration_seconds_sum` | 200387 | 31.29 |
| `http_request_size_bytes_count` | 6405 |  |
| `http_requests_total` | 6405 |  |
| `http_response_size_bytes_count` | 6405 |  |
| `http_response_size_bytes_sum` | 1.03938e+06 | 162.3 |
| `process_cpu_seconds_total` | 1893.75 |  |
| `python_gc_collections_total` | 1076 |  |
| `python_gc_objects_collected_total` | 238 |  |
| `vllm:e2e_request_latency_seconds_count` | 4345 |  |
| `vllm:e2e_request_latency_seconds_sum` | 196019 | 45.11 |
| `vllm:generation_tokens_total` | 3.3823e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.37793e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 190224 | 0.05631 |
| `vllm:iteration_tokens_total_count` | 146879 |  |
| `vllm:iteration_tokens_total_sum` | 6.80051e+07 | 463 |
| `vllm:num_preemptions_total` | 11 |  |
| `vllm:prefix_cache_hits_total` | 2.2159e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.86213e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.86213e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.2159e+08 |  |
| `vllm:prompt_tokens_total` | 2.86213e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4345 |  |
| `vllm:request_decode_time_seconds_sum` | 186037 | 42.82 |
| `vllm:request_generation_tokens_count` | 4345 |  |
| `vllm:request_generation_tokens_sum` | 3.31079e+06 | 762 |
| `vllm:request_inference_time_seconds_count` | 4345 |  |
| `vllm:request_inference_time_seconds_sum` | 189743 | 43.67 |
| `vllm:request_max_num_generation_tokens_count` | 4345 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.31079e+06 | 762 |
| `vllm:request_params_max_tokens_count` | 4345 |  |
| `vllm:request_params_max_tokens_sum` | 3.31079e+06 | 762 |
| `vllm:request_params_n_count` | 4345 |  |
| `vllm:request_params_n_sum` | 4345 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4345 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 6.33829e+07 | 1.459e+04 |
| `vllm:request_prefill_time_seconds_count` | 4345 |  |
| `vllm:request_prefill_time_seconds_sum` | 3705.71 | 0.8529 |
| `vllm:request_prompt_tokens_count` | 4345 |  |
| `vllm:request_prompt_tokens_sum` | 2.84225e+08 | 6.541e+04 |
| `vllm:request_queue_time_seconds_count` | 4345 |  |
| `vllm:request_queue_time_seconds_sum` | 5237.75 | 1.205 |
| `vllm:request_success_total` | 4345 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4345 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 252.189 | 0.05804 |
| `vllm:time_to_first_token_seconds_count` | 4367 |  |
| `vllm:time_to_first_token_seconds_sum` | 10122.6 | 2.318 |

## EPP (2549 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.44237 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 61.7575 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 16.7635 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 23.0415 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 104.005 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 79617 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.44774 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.44774 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 81564.8 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1843.34 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3369 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3369 |  |
| `go_gc_duration_seconds_count` | 3369 |  |
| `go_gc_duration_seconds_sum` | 1.12825 | 0.0003349 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.39475e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.59127e+11 | 46.87 |
| `go_gc_heap_allocs_bytes_total` | 1.59127e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.39475e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.39458e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.59116e+11 | 46.87 |
| `go_gc_heap_frees_bytes_total` | 1.59116e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.39458e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.11883e+08 |  |
| `go_gc_pauses_seconds_count` | 6738 |  |
| `go_gc_pauses_seconds_sum` | 0.359803 | 5.34e-05 |
| `go_memstats_alloc_bytes_total` | 1.59127e+11 |  |
| `go_memstats_frees_total` | 3.70646e+09 |  |
| `go_memstats_mallocs_total` | 3.70663e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 31895 |  |
| `go_sched_latencies_seconds_count` | 2.65738e+06 |  |
| `go_sched_latencies_seconds_sum` | 39.5327 | 1.488e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6738 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.24019 | 3.565e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6738 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.359803 | 5.34e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 28.236 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.39827e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 258.32 | 0.0001077 |
| `llm_d_epp_flow_control_requests_total` | 4377 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.80405e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 37.2774 | 5.479e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4345 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.20842e+08 | 5.083e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4345 |  |
| `llm_d_epp_request_duration_seconds_sum` | 220383 | 50.72 |
| `llm_d_epp_request_error_total` | 9 |  |
| `llm_d_epp_request_input_tokens_count` | 4345 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.84225e+08 | 6.541e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4345 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 444.243 | 0.1022 |
| `llm_d_epp_request_output_tokens_count` | 4345 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.31079e+06 | 762 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4377 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 42356.9 | 9.677 |
| `llm_d_epp_request_size_bytes_count` | 4368 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.14554e+09 | 2.623e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.37582e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 190107 | 0.05631 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4345 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 251.464 | 0.05787 |
| `llm_d_epp_request_total` | 4368 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4345 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 34462.3 | 7.931 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4367 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 72.8475 | 0.01668 |
| `llm_d_epp_response_size_bytes_count` | 4345 |  |
| `llm_d_epp_response_size_bytes_sum` | 8.93188e+08 | 2.056e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4368 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4368 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.157841 | 3.614e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 302 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 406 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4368 |  |
| `llm_d_epp_thunder_agent_starvation_promotions_total` | 2 |  |
| `process_cpu_seconds_total` | 1785.27 |  |
| `process_network_receive_bytes_total` | 2.07708e+10 |  |
| `process_network_transmit_bytes_total` | 1.28426e+10 |  |
| `rest_client_requests_total` | 69 |  |
