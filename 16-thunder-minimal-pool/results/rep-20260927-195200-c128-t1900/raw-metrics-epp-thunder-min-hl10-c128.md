# Raw metric deltas, epp-thunder-min-hl10-c128

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2557 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6548 |  |
| `http_request_duration_highr_seconds_sum` | 209453 | 31.99 |
| `http_request_duration_seconds_count` | 6548 |  |
| `http_request_duration_seconds_sum` | 209453 | 31.99 |
| `http_request_size_bytes_count` | 6548 |  |
| `http_requests_total` | 6548 |  |
| `http_response_size_bytes_count` | 6548 |  |
| `http_response_size_bytes_sum` | 1.04244e+06 | 159.2 |
| `process_cpu_seconds_total` | 1891.67 |  |
| `python_gc_collections_total` | 1056 |  |
| `python_gc_objects_collected_total` | 1331 |  |
| `vllm:e2e_request_latency_seconds_count` | 4472 |  |
| `vllm:e2e_request_latency_seconds_sum` | 201947 | 45.16 |
| `vllm:generation_tokens_total` | 3.3852e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.3807e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 199367 | 0.05897 |
| `vllm:iteration_tokens_total_count` | 129888 |  |
| `vllm:iteration_tokens_total_sum` | 7.26402e+07 | 559.3 |
| `vllm:num_preemptions_total` | 10 |  |
| `vllm:prefix_cache_hits_total` | 2.21653e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.90908e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.90908e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.21653e+08 |  |
| `vllm:prompt_tokens_total` | 2.90908e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4472 |  |
| `vllm:request_decode_time_seconds_sum` | 192082 | 42.95 |
| `vllm:request_generation_tokens_count` | 4472 |  |
| `vllm:request_generation_tokens_sum` | 3.26982e+06 | 731.2 |
| `vllm:request_inference_time_seconds_count` | 4472 |  |
| `vllm:request_inference_time_seconds_sum` | 195993 | 43.83 |
| `vllm:request_max_num_generation_tokens_count` | 4472 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.26982e+06 | 731.2 |
| `vllm:request_params_max_tokens_count` | 4472 |  |
| `vllm:request_params_max_tokens_sum` | 3.26982e+06 | 731.2 |
| `vllm:request_params_n_count` | 4472 |  |
| `vllm:request_params_n_sum` | 4472 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4472 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 6.75057e+07 | 1.51e+04 |
| `vllm:request_prefill_time_seconds_count` | 4472 |  |
| `vllm:request_prefill_time_seconds_sum` | 3911.01 | 0.8746 |
| `vllm:request_prompt_tokens_count` | 4472 |  |
| `vllm:request_prompt_tokens_sum` | 2.87695e+08 | 6.433e+04 |
| `vllm:request_queue_time_seconds_count` | 4472 |  |
| `vllm:request_queue_time_seconds_sum` | 4920.28 | 1.1 |
| `vllm:request_success_total` | 4472 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4472 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 272.284 | 0.06089 |
| `vllm:time_to_first_token_seconds_count` | 4504 |  |
| `vllm:time_to_first_token_seconds_sum` | 10041.9 | 2.23 |

## EPP (2557 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.30014 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 56.9711 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 20.9981 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 25.0124 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 105.282 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 79943 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00059956 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.527639 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.528239 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 81812.8 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1763.93 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3375 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3375 |  |
| `go_gc_duration_seconds_count` | 3375 |  |
| `go_gc_duration_seconds_sum` | 1.21502 | 0.00036 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.37564e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.54137e+11 | 45.66 |
| `go_gc_heap_allocs_bytes_total` | 1.54137e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.37564e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.37539e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.54124e+11 | 45.66 |
| `go_gc_heap_frees_bytes_total` | 1.54124e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.37539e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.13685e+08 |  |
| `go_gc_pauses_seconds_count` | 6750 |  |
| `go_gc_pauses_seconds_sum` | 0.38374 | 5.685e-05 |
| `go_memstats_alloc_bytes_total` | 1.54137e+11 |  |
| `go_memstats_frees_total` | 3.68907e+09 |  |
| `go_memstats_mallocs_total` | 3.68933e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 31473 |  |
| `go_sched_latencies_seconds_count` | 2.59347e+06 |  |
| `go_sched_latencies_seconds_sum` | 39.2731 | 1.514e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6750 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.260651 | 3.861e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6750 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.38374 | 5.685e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 28.7688 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.38927e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 222.697 | 9.321e-05 |
| `llm_d_epp_flow_control_requests_total` | 4504 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.81281e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 36.8161 | 5.404e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4472 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.20189e+08 | 4.924e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4472 |  |
| `llm_d_epp_request_duration_seconds_sum` | 231318 | 51.73 |
| `llm_d_epp_request_input_tokens_count` | 4472 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.87695e+08 | 6.433e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4472 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 491.012 | 0.1098 |
| `llm_d_epp_request_output_tokens_count` | 4472 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.26982e+06 | 731.2 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4504 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 35073.3 | 7.787 |
| `llm_d_epp_request_size_bytes_count` | 4504 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.16039e+09 | 2.576e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.3794e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 199251 | 0.05896 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4472 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 271.495 | 0.06071 |
| `llm_d_epp_request_total` | 4504 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4472 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 39350.7 | 8.799 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4504 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 71.1435 | 0.0158 |
| `llm_d_epp_response_size_bytes_count` | 4472 |  |
| `llm_d_epp_response_size_bytes_sum` | 8.81996e+08 | 1.972e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4504 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4504 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.156886 | 3.483e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 268 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 391 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4504 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 317 |  |
| `process_cpu_seconds_total` | 1705.47 |  |
| `process_network_receive_bytes_total` | 2.07513e+10 |  |
| `process_network_transmit_bytes_total` | 1.27948e+10 |  |
| `rest_client_requests_total` | 68 |  |
