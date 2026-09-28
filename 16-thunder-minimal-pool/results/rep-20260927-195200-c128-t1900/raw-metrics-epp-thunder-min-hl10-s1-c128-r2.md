# Raw metric deltas, epp-thunder-min-hl10-s1-c128-r2

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2546 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6599 |  |
| `http_request_duration_highr_seconds_sum` | 197418 | 29.92 |
| `http_request_duration_seconds_count` | 6599 |  |
| `http_request_duration_seconds_sum` | 197418 | 29.92 |
| `http_request_size_bytes_count` | 6599 |  |
| `http_requests_total` | 6599 |  |
| `http_response_size_bytes_count` | 6599 |  |
| `http_response_size_bytes_sum` | 1.03989e+06 | 157.6 |
| `process_cpu_seconds_total` | 1932.15 |  |
| `python_gc_collections_total` | 1118 |  |
| `python_gc_objects_collected_total` | 760 |  |
| `vllm:e2e_request_latency_seconds_count` | 4524 |  |
| `vllm:e2e_request_latency_seconds_sum` | 190637 | 42.14 |
| `vllm:generation_tokens_total` | 3.60294e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.59838e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 188810 | 0.05247 |
| `vllm:iteration_tokens_total_count` | 159702 |  |
| `vllm:iteration_tokens_total_sum` | 6.27162e+07 | 392.7 |
| `vllm:num_preemptions_total` | 7 |  |
| `vllm:prefix_cache_hits_total` | 2.36901e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.96015e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.96015e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.36901e+08 |  |
| `vllm:prompt_tokens_total` | 2.96015e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4524 |  |
| `vllm:request_decode_time_seconds_sum` | 182205 | 40.28 |
| `vllm:request_generation_tokens_count` | 4524 |  |
| `vllm:request_generation_tokens_sum` | 3.50586e+06 | 774.9 |
| `vllm:request_inference_time_seconds_count` | 4524 |  |
| `vllm:request_inference_time_seconds_sum` | 185528 | 41.01 |
| `vllm:request_max_num_generation_tokens_count` | 4524 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.50586e+06 | 774.9 |
| `vllm:request_params_max_tokens_count` | 4524 |  |
| `vllm:request_params_max_tokens_sum` | 3.50586e+06 | 774.9 |
| `vllm:request_params_n_count` | 4524 |  |
| `vllm:request_params_n_sum` | 4524 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4524 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 5.74263e+07 | 1.269e+04 |
| `vllm:request_prefill_time_seconds_count` | 4524 |  |
| `vllm:request_prefill_time_seconds_sum` | 3323.64 | 0.7347 |
| `vllm:request_prompt_tokens_count` | 4524 |  |
| `vllm:request_prompt_tokens_sum` | 2.92684e+08 | 6.47e+04 |
| `vllm:request_queue_time_seconds_count` | 4524 |  |
| `vllm:request_queue_time_seconds_sum` | 4096.29 | 0.9055 |
| `vllm:request_success_total` | 4524 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4524 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 254.644 | 0.05629 |
| `vllm:time_to_first_token_seconds_count` | 4560 |  |
| `vllm:time_to_first_token_seconds_sum` | 8564.68 | 1.878 |

## EPP (2546 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.08462 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 56.9905 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 21.2229 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 24.5618 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 104.86 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 79489.7 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00051638 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.458817 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.459334 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 81468.8 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1873.86 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3326 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3326 |  |
| `go_gc_duration_seconds_count` | 3326 |  |
| `go_gc_duration_seconds_sum` | 1.19092 | 0.0003581 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.3817e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.5545e+11 | 45.97 |
| `go_gc_heap_allocs_bytes_total` | 1.5545e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.3817e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.38164e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.55444e+11 | 45.97 |
| `go_gc_heap_frees_bytes_total` | 1.55444e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.38164e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.1329e+08 |  |
| `go_gc_pauses_seconds_count` | 6652 |  |
| `go_gc_pauses_seconds_sum` | 0.370725 | 5.573e-05 |
| `go_memstats_alloc_bytes_total` | 1.5545e+11 |  |
| `go_memstats_frees_total` | 3.69493e+09 |  |
| `go_memstats_mallocs_total` | 3.69499e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 32301 |  |
| `go_sched_latencies_seconds_count` | 2.78471e+06 |  |
| `go_sched_latencies_seconds_sum` | 41.1174 | 1.477e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6652 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.252122 | 3.79e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6652 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.370725 | 5.573e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 31.8807 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.38619e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 247.575 | 0.0001038 |
| `llm_d_epp_flow_control_requests_total` | 4563 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 7.24708e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 38.8808 | 5.365e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4524 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.35257e+08 | 5.2e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4524 |  |
| `llm_d_epp_request_duration_seconds_sum` | 223378 | 49.38 |
| `llm_d_epp_request_error_total` | 2 |  |
| `llm_d_epp_request_input_tokens_count` | 4524 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.92684e+08 | 6.47e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4524 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 520.991 | 0.1152 |
| `llm_d_epp_request_output_tokens_count` | 4524 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.50586e+06 | 774.9 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4563 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 45300 | 9.928 |
| `llm_d_epp_request_size_bytes_count` | 4561 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.18162e+09 | 2.591e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.59619e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 188691 | 0.05247 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4524 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 253.941 | 0.05613 |
| `llm_d_epp_request_total` | 4561 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4524 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 41290.9 | 9.127 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4560 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 78.164 | 0.01714 |
| `llm_d_epp_response_size_bytes_count` | 4524 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.45263e+08 | 2.089e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4561 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4561 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.172478 | 3.782e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 332 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 487 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4562 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 402 |  |
| `process_cpu_seconds_total` | 1797.04 |  |
| `process_network_receive_bytes_total` | 2.10674e+10 |  |
| `process_network_transmit_bytes_total` | 1.32482e+10 |  |
| `rest_client_requests_total` | 72 |  |
