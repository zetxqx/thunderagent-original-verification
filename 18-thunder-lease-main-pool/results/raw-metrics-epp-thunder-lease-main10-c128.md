# Raw metric deltas, epp-thunder-lease-main10-c128

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2512 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 5880 |  |
| `http_request_duration_highr_seconds_sum` | 215667 | 36.68 |
| `http_request_duration_seconds_count` | 5880 |  |
| `http_request_duration_seconds_sum` | 215667 | 36.68 |
| `http_request_size_bytes_count` | 5880 |  |
| `http_requests_total` | 5880 |  |
| `http_response_size_bytes_count` | 5880 |  |
| `http_response_size_bytes_sum` | 1.0251e+06 | 174.3 |
| `process_cpu_seconds_total` | 1751.88 |  |
| `python_gc_collections_total` | 902 |  |
| `python_gc_objects_collected_total` | 101 |  |
| `vllm:e2e_request_latency_seconds_count` | 3862 |  |
| `vllm:e2e_request_latency_seconds_sum` | 213528 | 55.29 |
| `vllm:generation_tokens_total` | 2.99927e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 2.9954e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 200569 | 0.06696 |
| `vllm:iteration_tokens_total_count` | 126343 |  |
| `vllm:iteration_tokens_total_sum` | 8.83574e+07 | 699.3 |
| `vllm:num_preemptions_total` | 15 |  |
| `vllm:prefix_cache_hits_total` | 1.63007e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.48365e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.48365e+08 |  |
| `vllm:prompt_tokens_cached_total` | 1.63007e+08 |  |
| `vllm:prompt_tokens_total` | 2.48365e+08 |  |
| `vllm:request_decode_time_seconds_count` | 3862 |  |
| `vllm:request_decode_time_seconds_sum` | 198532 | 51.41 |
| `vllm:request_generation_tokens_count` | 3862 |  |
| `vllm:request_generation_tokens_sum` | 2.96544e+06 | 767.8 |
| `vllm:request_inference_time_seconds_count` | 3862 |  |
| `vllm:request_inference_time_seconds_sum` | 203013 | 52.57 |
| `vllm:request_max_num_generation_tokens_count` | 3862 |  |
| `vllm:request_max_num_generation_tokens_sum` | 2.96544e+06 | 767.8 |
| `vllm:request_params_max_tokens_count` | 3862 |  |
| `vllm:request_params_max_tokens_sum` | 2.96544e+06 | 767.8 |
| `vllm:request_params_n_count` | 3862 |  |
| `vllm:request_params_n_sum` | 3862 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 3862 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 8.47272e+07 | 2.194e+04 |
| `vllm:request_prefill_time_seconds_count` | 3862 |  |
| `vllm:request_prefill_time_seconds_sum` | 4481.12 | 1.16 |
| `vllm:request_prompt_tokens_count` | 3862 |  |
| `vllm:request_prompt_tokens_sum` | 2.47509e+08 | 6.409e+04 |
| `vllm:request_queue_time_seconds_count` | 3862 |  |
| `vllm:request_queue_time_seconds_sum` | 9594.97 | 2.484 |
| `vllm:request_success_total` | 3862 |  |
| `vllm:request_time_per_output_token_seconds_count` | 3862 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 271.135 | 0.07021 |
| `vllm:time_to_first_token_seconds_count` | 3870 |  |
| `vllm:time_to_first_token_seconds_sum` | 15061.4 | 3.892 |

## EPP (2512 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.21836 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 58.6166 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 22.1775 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 22.8912 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 105.904 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 78551.6 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.581783 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.581783 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 80360 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1701.94 |  |
| `go_gc_cleanups_executed_cleanups_total` | 1 |  |
| `go_gc_cleanups_queued_cleanups_total` | 1 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3237 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3237 |  |
| `go_gc_duration_seconds_count` | 3237 |  |
| `go_gc_duration_seconds_sum` | 1.10804 | 0.0003423 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.30346e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.50561e+11 | 45.58 |
| `go_gc_heap_allocs_bytes_total` | 1.50561e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.30346e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.3033e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.50552e+11 | 45.58 |
| `go_gc_heap_frees_bytes_total` | 1.50552e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.3033e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.03707e+08 |  |
| `go_gc_pauses_seconds_count` | 6474 |  |
| `go_gc_pauses_seconds_sum` | 0.359608 | 5.555e-05 |
| `go_memstats_alloc_bytes_total` | 1.50561e+11 |  |
| `go_memstats_frees_total` | 3.60701e+09 |  |
| `go_memstats_mallocs_total` | 3.60716e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 29048 |  |
| `go_sched_latencies_seconds_count` | 2.37635e+06 |  |
| `go_sched_latencies_seconds_sum` | 35.6182 | 1.499e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6474 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.240428 | 3.714e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6474 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.359608 | 5.555e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 24.0234 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.34477e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 206.296 | 8.798e-05 |
| `llm_d_epp_flow_control_requests_total` | 3871 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.03482e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 32.8729 | 5.447e-06 |
| `llm_d_epp_request_cached_tokens_count` | 3862 |  |
| `llm_d_epp_request_cached_tokens_sum` | 1.62781e+08 | 4.215e+04 |
| `llm_d_epp_request_duration_seconds_count` | 3862 |  |
| `llm_d_epp_request_duration_seconds_sum` | 238606 | 61.78 |
| `llm_d_epp_request_input_tokens_count` | 3862 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.47509e+08 | 6.409e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 3862 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 542.94 | 0.1406 |
| `llm_d_epp_request_output_tokens_count` | 3862 |  |
| `llm_d_epp_request_output_tokens_sum` | 2.96544e+06 | 767.8 |
| `llm_d_epp_request_processing_duration_seconds_count` | 3871 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 26883.6 | 6.945 |
| `llm_d_epp_request_size_bytes_count` | 3871 |  |
| `llm_d_epp_request_size_bytes_sum` | 9.91109e+08 | 2.56e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 2.99419e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 200473 | 0.06695 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 3862 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 270.47 | 0.07003 |
| `llm_d_epp_request_total` | 3871 |  |
| `llm_d_epp_request_ttft_seconds_count` | 3862 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 40170.2 | 10.4 |
| `llm_d_epp_response_processing_duration_seconds_count` | 3870 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 66.2319 | 0.01711 |
| `llm_d_epp_response_size_bytes_count` | 3862 |  |
| `llm_d_epp_response_size_bytes_sum` | 7.99508e+08 | 2.07e+05 |
| `llm_d_epp_scheduler_attempts_total` | 3871 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 3871 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.141517 | 3.656e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 117 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 184 |  |
| `llm_d_epp_thunder_agent_releases_total` | 3871 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 120 |  |
| `process_cpu_seconds_total` | 1669.65 |  |
| `process_network_receive_bytes_total` | 1.96541e+10 |  |
| `process_network_transmit_bytes_total` | 1.10678e+10 |  |
| `rest_client_requests_total` | 68 |  |
