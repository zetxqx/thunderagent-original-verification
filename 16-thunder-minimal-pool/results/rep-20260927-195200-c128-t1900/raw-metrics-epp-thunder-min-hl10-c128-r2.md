# Raw metric deltas, epp-thunder-min-hl10-c128-r2

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2567 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6431 |  |
| `http_request_duration_highr_seconds_sum` | 208154 | 32.37 |
| `http_request_duration_seconds_count` | 6431 |  |
| `http_request_duration_seconds_sum` | 208154 | 32.37 |
| `http_request_size_bytes_count` | 6431 |  |
| `http_requests_total` | 6431 |  |
| `http_response_size_bytes_count` | 6431 |  |
| `http_response_size_bytes_sum` | 1.04652e+06 | 162.7 |
| `process_cpu_seconds_total` | 1887.52 |  |
| `python_gc_collections_total` | 1065 |  |
| `python_gc_objects_collected_total` | 826 |  |
| `vllm:e2e_request_latency_seconds_count` | 4356 |  |
| `vllm:e2e_request_latency_seconds_sum` | 202774 | 46.55 |
| `vllm:generation_tokens_total` | 3.42239e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.41801e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 198753 | 0.05815 |
| `vllm:iteration_tokens_total_count` | 136256 |  |
| `vllm:iteration_tokens_total_sum` | 7.10764e+07 | 521.6 |
| `vllm:num_preemptions_total` | 8 |  |
| `vllm:prefix_cache_hits_total` | 2.17232e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.84886e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.84886e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.17232e+08 |  |
| `vllm:prompt_tokens_total` | 2.84886e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4356 |  |
| `vllm:request_decode_time_seconds_sum` | 193469 | 44.41 |
| `vllm:request_generation_tokens_count` | 4356 |  |
| `vllm:request_generation_tokens_sum` | 3.30426e+06 | 758.6 |
| `vllm:request_inference_time_seconds_count` | 4356 |  |
| `vllm:request_inference_time_seconds_sum` | 197314 | 45.3 |
| `vllm:request_max_num_generation_tokens_count` | 4356 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.30426e+06 | 758.6 |
| `vllm:request_params_max_tokens_count` | 4356 |  |
| `vllm:request_params_max_tokens_sum` | 3.30426e+06 | 758.6 |
| `vllm:request_params_n_count` | 4356 |  |
| `vllm:request_params_n_sum` | 4356 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4356 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 6.71285e+07 | 1.541e+04 |
| `vllm:request_prefill_time_seconds_count` | 4356 |  |
| `vllm:request_prefill_time_seconds_sum` | 3844.43 | 0.8826 |
| `vllm:request_prompt_tokens_count` | 4356 |  |
| `vllm:request_prompt_tokens_sum` | 2.82852e+08 | 6.493e+04 |
| `vllm:request_queue_time_seconds_count` | 4356 |  |
| `vllm:request_queue_time_seconds_sum` | 4446.44 | 1.021 |
| `vllm:request_success_total` | 4356 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4356 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 263.608 | 0.06052 |
| `vllm:time_to_first_token_seconds_count` | 4379 |  |
| `vllm:time_to_first_token_seconds_sum` | 9359.51 | 2.137 |

## EPP (2567 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.4828 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 59.4694 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 21.3968 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 26.4774 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 109.826 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 80131.4 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00346779 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.490626 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.494093 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 82123.2 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1881.54 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3453 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3453 |  |
| `go_gc_duration_seconds_count` | 3453 |  |
| `go_gc_duration_seconds_sum` | 1.28089 | 0.0003709 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.39054e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.54657e+11 | 45.61 |
| `go_gc_heap_allocs_bytes_total` | 1.54657e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.39054e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.39021e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.54644e+11 | 45.61 |
| `go_gc_heap_frees_bytes_total` | 1.54644e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.39021e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.14904e+08 |  |
| `go_gc_pauses_seconds_count` | 6907 |  |
| `go_gc_pauses_seconds_sum` | 0.395819 | 5.731e-05 |
| `go_memstats_alloc_bytes_total` | 1.54657e+11 |  |
| `go_memstats_frees_total` | 3.70512e+09 |  |
| `go_memstats_mallocs_total` | 3.70544e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 31329 |  |
| `go_sched_latencies_seconds_count` | 2.63558e+06 |  |
| `go_sched_latencies_seconds_sum` | 41.1876 | 1.563e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6907 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.273209 | 3.956e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6907 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.395819 | 5.731e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 33.7418 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.40122e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 240.23 | 0.0001 |
| `llm_d_epp_flow_control_requests_total` | 4379 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.88534e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 37.8851 | 5.502e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4356 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.15723e+08 | 4.952e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4356 |  |
| `llm_d_epp_request_duration_seconds_sum` | 237894 | 54.61 |
| `llm_d_epp_request_input_tokens_count` | 4356 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.82852e+08 | 6.493e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4356 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 553.141 | 0.127 |
| `llm_d_epp_request_output_tokens_count` | 4356 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.30426e+06 | 758.6 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4379 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 35610.1 | 8.132 |
| `llm_d_epp_request_size_bytes_count` | 4379 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.13589e+09 | 2.594e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.41641e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 198638 | 0.05814 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4356 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 262.805 | 0.06033 |
| `llm_d_epp_request_total` | 4379 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4356 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 44538.8 | 10.22 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4379 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 75.787 | 0.01731 |
| `llm_d_epp_response_size_bytes_count` | 4356 |  |
| `llm_d_epp_response_size_bytes_sum` | 8.90801e+08 | 2.045e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4379 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4379 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.172681 | 3.943e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 316 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 417 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4379 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 348 |  |
| `process_cpu_seconds_total` | 1802.15 |  |
| `process_network_receive_bytes_total` | 2.0793e+10 |  |
| `process_network_transmit_bytes_total` | 1.27835e+10 |  |
| `rest_client_requests_total` | 72 |  |
