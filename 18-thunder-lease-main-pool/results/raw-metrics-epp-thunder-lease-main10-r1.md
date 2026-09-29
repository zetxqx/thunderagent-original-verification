# Raw metric deltas, epp-thunder-lease-main10-r1

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 1 pods (2072 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 1396 |  |
| `http_request_duration_highr_seconds_sum` | 56703.8 | 40.62 |
| `http_request_duration_seconds_count` | 1396 |  |
| `http_request_duration_seconds_sum` | 56703.8 | 40.62 |
| `http_request_size_bytes_count` | 1396 |  |
| `http_requests_total` | 1396 |  |
| `http_response_size_bytes_count` | 1396 |  |
| `http_response_size_bytes_sum` | 211650 | 151.6 |
| `process_cpu_seconds_total` | 598.85 |  |
| `python_gc_collections_total` | 260 |  |
| `python_gc_objects_collected_total` | 67 |  |
| `vllm:e2e_request_latency_seconds_count` | 978 |  |
| `vllm:e2e_request_latency_seconds_sum` | 55905.2 | 57.16 |
| `vllm:generation_tokens_total` | 739935 |  |
| `vllm:inter_token_latency_seconds_count` | 738954 |  |
| `vllm:inter_token_latency_seconds_sum` | 51901 | 0.07024 |
| `vllm:iteration_tokens_total_count` | 29996 |  |
| `vllm:iteration_tokens_total_sum` | 2.57141e+07 | 857.3 |
| `vllm:num_preemptions_total` | 4 |  |
| `vllm:prefix_cache_hits_total` | 3.41766e+07 |  |
| `vllm:prefix_cache_queries_total` | 5.91508e+07 |  |
| `vllm:prompt_tokens_by_source_total` | 5.91508e+07 |  |
| `vllm:prompt_tokens_cached_total` | 3.41766e+07 |  |
| `vllm:prompt_tokens_total` | 5.91508e+07 |  |
| `vllm:request_decode_time_seconds_count` | 978 |  |
| `vllm:request_decode_time_seconds_sum` | 51132.2 | 52.28 |
| `vllm:request_generation_tokens_count` | 978 |  |
| `vllm:request_generation_tokens_sum` | 717048 | 733.2 |
| `vllm:request_inference_time_seconds_count` | 978 |  |
| `vllm:request_inference_time_seconds_sum` | 52357.3 | 53.54 |
| `vllm:request_max_num_generation_tokens_count` | 978 |  |
| `vllm:request_max_num_generation_tokens_sum` | 717048 | 733.2 |
| `vllm:request_params_max_tokens_count` | 978 |  |
| `vllm:request_params_max_tokens_sum` | 717048 | 733.2 |
| `vllm:request_params_n_count` | 978 |  |
| `vllm:request_params_n_sum` | 978 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 978 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 2.48172e+07 | 2.538e+04 |
| `vllm:request_prefill_time_seconds_count` | 978 |  |
| `vllm:request_prefill_time_seconds_sum` | 1225.17 | 1.253 |
| `vllm:request_prompt_tokens_count` | 978 |  |
| `vllm:request_prompt_tokens_sum` | 5.89091e+07 | 6.023e+04 |
| `vllm:request_queue_time_seconds_count` | 978 |  |
| `vllm:request_queue_time_seconds_sum` | 3329.06 | 3.404 |
| `vllm:request_success_total` | 978 |  |
| `vllm:request_time_per_output_token_seconds_count` | 978 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 70.7986 | 0.07239 |
| `vllm:time_to_first_token_seconds_count` | 981 |  |
| `vllm:time_to_first_token_seconds_sum` | 4794.48 | 4.887 |

## EPP (2072 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 0.220812 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 10.848 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 3.10753 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 3.57679 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 17.7531 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 65721 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00327474 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.3987 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.401974 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 66300.9 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 561.735 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 861 |  |
| `go_gc_cycles_total_gc_cycles_total` | 861 |  |
| `go_gc_duration_seconds_count` | 861 |  |
| `go_gc_duration_seconds_sum` | 0.19718 | 0.000229 |
| `go_gc_heap_allocs_by_size_bytes_count` | 7.0926e+08 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 3.37764e+10 | 47.62 |
| `go_gc_heap_allocs_bytes_total` | 3.37764e+10 |  |
| `go_gc_heap_allocs_objects_total` | 7.0926e+08 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 7.09192e+08 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 3.3772e+10 | 47.62 |
| `go_gc_heap_frees_bytes_total` | 3.3772e+10 |  |
| `go_gc_heap_frees_objects_total` | 7.09192e+08 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 6.64174e+07 |  |
| `go_gc_pauses_seconds_count` | 1722 |  |
| `go_gc_pauses_seconds_sum` | 0.0848527 | 4.928e-05 |
| `go_memstats_alloc_bytes_total` | 3.37764e+10 |  |
| `go_memstats_frees_total` | 7.75609e+08 |  |
| `go_memstats_mallocs_total` | 7.75678e+08 |  |
| `go_sched_goroutines_created_goroutines_total` | 16948 |  |
| `go_sched_latencies_seconds_count` | 738484 |  |
| `go_sched_latencies_seconds_sum` | 10.0518 | 1.361e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 1722 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.0241842 | 1.404e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 1722 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.0848527 | 4.928e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 5.15092 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 1.91956e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 84.6574 | 4.41e-05 |
| `llm_d_epp_flow_control_request_enqueue_duration_seconds_count` | 594 |  |
| `llm_d_epp_flow_control_request_enqueue_duration_seconds_sum` | 0.00451501 | 7.601e-06 |
| `llm_d_epp_flow_control_request_queue_duration_seconds_count` | 594 |  |
| `llm_d_epp_flow_control_request_queue_duration_seconds_sum` | 1687.64 | 2.841 |
| `llm_d_epp_flow_control_requests_total` | 981 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 1.48875e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 7.94745 | 5.338e-06 |
| `llm_d_epp_request_cached_tokens_count` | 978 |  |
| `llm_d_epp_request_cached_tokens_sum` | 3.40919e+07 | 3.486e+04 |
| `llm_d_epp_request_duration_seconds_count` | 978 |  |
| `llm_d_epp_request_duration_seconds_sum` | 59423.2 | 60.76 |
| `llm_d_epp_request_input_tokens_count` | 978 |  |
| `llm_d_epp_request_input_tokens_sum` | 5.89091e+07 | 6.023e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 978 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 129.815 | 0.1327 |
| `llm_d_epp_request_output_tokens_count` | 978 |  |
| `llm_d_epp_request_output_tokens_sum` | 717048 | 733.2 |
| `llm_d_epp_request_processing_duration_seconds_count` | 981 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 3674.36 | 3.746 |
| `llm_d_epp_request_size_bytes_count` | 981 |  |
| `llm_d_epp_request_size_bytes_sum` | 2.36499e+08 | 2.411e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 738489 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 51875.8 | 0.07025 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 978 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 70.6098 | 0.0722 |
| `llm_d_epp_request_total` | 981 |  |
| `llm_d_epp_request_ttft_seconds_count` | 978 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 8316.1 | 8.503 |
| `llm_d_epp_response_processing_duration_seconds_count` | 981 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 16.04 | 0.01635 |
| `llm_d_epp_response_size_bytes_count` | 978 |  |
| `llm_d_epp_response_size_bytes_sum` | 1.93333e+08 | 1.977e+05 |
| `llm_d_epp_scheduler_attempts_total` | 981 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 981 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.029232 | 2.98e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 38 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 52 |  |
| `llm_d_epp_thunder_agent_releases_total` | 981 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 35 |  |
| `process_cpu_seconds_total` | 558.45 |  |
| `process_network_receive_bytes_total` | 4.30497e+09 |  |
| `process_network_transmit_bytes_total` | 3.42017e+09 |  |
| `rest_client_requests_total` | 44 |  |
