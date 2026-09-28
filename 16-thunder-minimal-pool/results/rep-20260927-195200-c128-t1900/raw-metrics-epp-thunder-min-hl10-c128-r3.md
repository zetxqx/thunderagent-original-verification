# Raw metric deltas, epp-thunder-min-hl10-c128-r3

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2565 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6506 |  |
| `http_request_duration_highr_seconds_sum` | 205899 | 31.65 |
| `http_request_duration_seconds_count` | 6506 |  |
| `http_request_duration_seconds_sum` | 205899 | 31.65 |
| `http_request_size_bytes_count` | 6506 |  |
| `http_requests_total` | 6506 |  |
| `http_response_size_bytes_count` | 6506 |  |
| `http_response_size_bytes_sum` | 1.04652e+06 | 160.9 |
| `process_cpu_seconds_total` | 1895.55 |  |
| `python_gc_collections_total` | 1107 |  |
| `python_gc_objects_collected_total` | 1018 |  |
| `vllm:e2e_request_latency_seconds_count` | 4429 |  |
| `vllm:e2e_request_latency_seconds_sum` | 201313 | 45.45 |
| `vllm:generation_tokens_total` | 3.47109e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.46663e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 196383 | 0.05665 |
| `vllm:iteration_tokens_total_count` | 137752 |  |
| `vllm:iteration_tokens_total_sum` | 6.88969e+07 | 500.2 |
| `vllm:num_preemptions_total` | 6 |  |
| `vllm:prefix_cache_hits_total` | 2.22706e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.88131e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.88131e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.22706e+08 |  |
| `vllm:prompt_tokens_total` | 2.88131e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4429 |  |
| `vllm:request_decode_time_seconds_sum` | 191944 | 43.34 |
| `vllm:request_generation_tokens_count` | 4429 |  |
| `vllm:request_generation_tokens_sum` | 3.39186e+06 | 765.8 |
| `vllm:request_inference_time_seconds_count` | 4429 |  |
| `vllm:request_inference_time_seconds_sum` | 195686 | 44.18 |
| `vllm:request_max_num_generation_tokens_count` | 4429 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.39186e+06 | 765.8 |
| `vllm:request_params_max_tokens_count` | 4429 |  |
| `vllm:request_params_max_tokens_sum` | 3.39186e+06 | 765.8 |
| `vllm:request_params_n_count` | 4429 |  |
| `vllm:request_params_n_sum` | 4429 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4429 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 6.41151e+07 | 1.448e+04 |
| `vllm:request_prefill_time_seconds_count` | 4429 |  |
| `vllm:request_prefill_time_seconds_sum` | 3742.08 | 0.8449 |
| `vllm:request_prompt_tokens_count` | 4429 |  |
| `vllm:request_prompt_tokens_sum` | 2.85739e+08 | 6.452e+04 |
| `vllm:request_queue_time_seconds_count` | 4429 |  |
| `vllm:request_queue_time_seconds_sum` | 4612.89 | 1.042 |
| `vllm:request_success_total` | 4429 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4429 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 259.689 | 0.05863 |
| `vllm:time_to_first_token_seconds_count` | 4454 |  |
| `vllm:time_to_first_token_seconds_sum` | 9473.44 | 2.127 |

## EPP (2565 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.38181 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 58.4497 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 20.321 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 25.0061 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 106.159 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 80101.3 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00073142 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.448407 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.449139 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 82081.6 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1873.61 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3427 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3427 |  |
| `go_gc_duration_seconds_count` | 3427 |  |
| `go_gc_duration_seconds_sum` | 1.21543 | 0.0003547 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.39316e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.55049e+11 | 45.69 |
| `go_gc_heap_allocs_bytes_total` | 1.55049e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.39316e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.39307e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.55042e+11 | 45.69 |
| `go_gc_heap_frees_bytes_total` | 1.55042e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.39307e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.14959e+08 |  |
| `go_gc_pauses_seconds_count` | 6854 |  |
| `go_gc_pauses_seconds_sum` | 0.386517 | 5.639e-05 |
| `go_memstats_alloc_bytes_total` | 1.55049e+11 |  |
| `go_memstats_frees_total` | 3.70803e+09 |  |
| `go_memstats_mallocs_total` | 3.70812e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 31662 |  |
| `go_sched_latencies_seconds_count` | 2.66786e+06 |  |
| `go_sched_latencies_seconds_sum` | 41.5808 | 1.559e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6854 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.261734 | 3.819e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6854 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.386517 | 5.639e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 34.8186 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.40184e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 243.488 | 0.0001014 |
| `llm_d_epp_flow_control_requests_total` | 4455 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.98442e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 38.3275 | 5.488e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4429 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.21624e+08 | 5.004e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4429 |  |
| `llm_d_epp_request_duration_seconds_sum` | 235128 | 53.09 |
| `llm_d_epp_request_input_tokens_count` | 4429 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.85739e+08 | 6.452e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4429 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 522.762 | 0.118 |
| `llm_d_epp_request_output_tokens_count` | 4429 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.39186e+06 | 765.8 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4455 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 38461.5 | 8.633 |
| `llm_d_epp_request_size_bytes_count` | 4455 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.14918e+09 | 2.58e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.46549e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 196267 | 0.05663 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4429 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 258.908 | 0.05846 |
| `llm_d_epp_request_total` | 4455 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4429 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 43298.3 | 9.776 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4454 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 76.7123 | 0.01722 |
| `llm_d_epp_response_size_bytes_count` | 4429 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.14161e+08 | 2.064e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4455 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4455 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.171823 | 3.857e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 269 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 386 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4455 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 308 |  |
| `process_cpu_seconds_total` | 1793.38 |  |
| `process_network_receive_bytes_total` | 2.08849e+10 |  |
| `process_network_transmit_bytes_total` | 1.29137e+10 |  |
| `rest_client_requests_total` | 70 |  |
