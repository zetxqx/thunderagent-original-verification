# Raw metric deltas, epp-thunder-min-c128

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2612 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6174 |  |
| `http_request_duration_highr_seconds_sum` | 210043 | 34.02 |
| `http_request_duration_seconds_count` | 6174 |  |
| `http_request_duration_seconds_sum` | 210043 | 34.02 |
| `http_request_size_bytes_count` | 6174 |  |
| `http_requests_total` | 6174 |  |
| `http_response_size_bytes_count` | 6174 |  |
| `http_response_size_bytes_sum` | 1.06641e+06 | 172.7 |
| `process_cpu_seconds_total` | 1832.44 |  |
| `python_gc_collections_total` | 913 |  |
| `python_gc_objects_collected_total` | 714 |  |
| `vllm:e2e_request_latency_seconds_count` | 4061 |  |
| `vllm:e2e_request_latency_seconds_sum` | 206333 | 50.81 |
| `vllm:generation_tokens_total` | 3.21705e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.21297e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 199385 | 0.06206 |
| `vllm:iteration_tokens_total_count` | 134288 |  |
| `vllm:iteration_tokens_total_sum` | 7.99411e+07 | 595.3 |
| `vllm:num_preemptions_total` | 9 |  |
| `vllm:prefix_cache_hits_total` | 1.8568e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.62404e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.62404e+08 |  |
| `vllm:prompt_tokens_cached_total` | 1.8568e+08 |  |
| `vllm:prompt_tokens_total` | 2.62404e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4061 |  |
| `vllm:request_decode_time_seconds_sum` | 195788 | 48.21 |
| `vllm:request_generation_tokens_count` | 4061 |  |
| `vllm:request_generation_tokens_sum` | 3.15415e+06 | 776.7 |
| `vllm:request_inference_time_seconds_count` | 4061 |  |
| `vllm:request_inference_time_seconds_sum` | 199992 | 49.25 |
| `vllm:request_max_num_generation_tokens_count` | 4061 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.15415e+06 | 776.7 |
| `vllm:request_params_max_tokens_count` | 4061 |  |
| `vllm:request_params_max_tokens_sum` | 3.15415e+06 | 776.7 |
| `vllm:request_params_n_count` | 4061 |  |
| `vllm:request_params_n_sum` | 4061 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4061 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 7.54485e+07 | 1.858e+04 |
| `vllm:request_prefill_time_seconds_count` | 4061 |  |
| `vllm:request_prefill_time_seconds_sum` | 4203.91 | 1.035 |
| `vllm:request_prompt_tokens_count` | 4061 |  |
| `vllm:request_prompt_tokens_sum` | 2.60529e+08 | 6.415e+04 |
| `vllm:request_queue_time_seconds_count` | 4061 |  |
| `vllm:request_queue_time_seconds_sum` | 5366.25 | 1.321 |
| `vllm:request_success_total` | 4061 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4061 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 266.771 | 0.06569 |
| `vllm:time_to_first_token_seconds_count` | 4083 |  |
| `vllm:time_to_first_token_seconds_sum` | 10618.9 | 2.601 |

## EPP (2612 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.50399 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 65.2118 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 18.9983 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 27.9184 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 114.632 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 81660 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 2.2e-07 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.526836 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.526837 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 83576 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1800.82 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3660 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3660 |  |
| `go_gc_duration_seconds_count` | 3660 |  |
| `go_gc_duration_seconds_sum` | 1.35912 | 0.0003713 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.4376e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.55578e+11 | 45.26 |
| `go_gc_heap_allocs_bytes_total` | 1.55578e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.4376e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.43764e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.55576e+11 | 45.26 |
| `go_gc_heap_frees_bytes_total` | 1.55576e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.43764e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.19526e+08 |  |
| `go_gc_pauses_seconds_count` | 7320 |  |
| `go_gc_pauses_seconds_sum` | 0.407846 | 5.572e-05 |
| `go_memstats_alloc_bytes_total` | 1.55578e+11 |  |
| `go_memstats_frees_total` | 3.75716e+09 |  |
| `go_memstats_mallocs_total` | 3.75713e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 30894 |  |
| `go_sched_latencies_seconds_count` | 2.54669e+06 |  |
| `go_sched_latencies_seconds_sum` | 37.7506 | 1.482e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 7320 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.282947 | 3.865e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 7320 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.407846 | 5.572e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 29.0091 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.47868e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 230.726 | 9.308e-05 |
| `llm_d_epp_flow_control_requests_total` | 4083 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.47164e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 34.1467 | 5.276e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4061 |  |
| `llm_d_epp_request_cached_tokens_sum` | 1.8508e+08 | 4.558e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4061 |  |
| `llm_d_epp_request_duration_seconds_sum` | 236615 | 58.27 |
| `llm_d_epp_request_input_tokens_count` | 4061 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.60529e+08 | 6.415e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4061 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 594.755 | 0.1465 |
| `llm_d_epp_request_output_tokens_count` | 4061 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.15415e+06 | 776.7 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4083 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 34101.8 | 8.352 |
| `llm_d_epp_request_size_bytes_count` | 4083 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.04597e+09 | 2.562e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.21133e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 199274 | 0.06205 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4061 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 266.068 | 0.06552 |
| `llm_d_epp_request_total` | 4083 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4061 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 40937.3 | 10.08 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4083 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 68.3697 | 0.01674 |
| `llm_d_epp_response_size_bytes_count` | 4061 |  |
| `llm_d_epp_response_size_bytes_sum` | 8.50305e+08 | 2.094e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4083 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4083 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.146242 | 3.582e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 350 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 495 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4083 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 422 |  |
| `process_cpu_seconds_total` | 1741.54 |  |
| `process_network_receive_bytes_total` | 2.04685e+10 |  |
| `process_network_transmit_bytes_total` | 1.23247e+10 |  |
| `rest_client_requests_total` | 71 |  |
