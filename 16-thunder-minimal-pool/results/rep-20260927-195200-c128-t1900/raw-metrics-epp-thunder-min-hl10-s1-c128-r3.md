# Raw metric deltas, epp-thunder-min-hl10-s1-c128-r3

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2647 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6919 |  |
| `http_request_duration_highr_seconds_sum` | 201556 | 29.13 |
| `http_request_duration_seconds_count` | 6919 |  |
| `http_request_duration_seconds_sum` | 201556 | 29.13 |
| `http_request_size_bytes_count` | 6919 |  |
| `http_requests_total` | 6919 |  |
| `http_response_size_bytes_count` | 6919 |  |
| `http_response_size_bytes_sum` | 1.07967e+06 | 156 |
| `process_cpu_seconds_total` | 2010.49 |  |
| `python_gc_collections_total` | 1204 |  |
| `python_gc_objects_collected_total` | 953 |  |
| `vllm:e2e_request_latency_seconds_count` | 4776 |  |
| `vllm:e2e_request_latency_seconds_sum` | 196703 | 41.19 |
| `vllm:generation_tokens_total` | 3.70984e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.70504e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 192906 | 0.05207 |
| `vllm:iteration_tokens_total_count` | 166355 |  |
| `vllm:iteration_tokens_total_sum` | 6.42148e+07 | 386 |
| `vllm:num_preemptions_total` | 5 |  |
| `vllm:prefix_cache_hits_total` | 2.50074e+08 |  |
| `vllm:prefix_cache_queries_total` | 3.10913e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 3.10579e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.50074e+08 |  |
| `vllm:prompt_tokens_total` | 3.10579e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4776 |  |
| `vllm:request_decode_time_seconds_sum` | 188218 | 39.41 |
| `vllm:request_generation_tokens_count` | 4776 |  |
| `vllm:request_generation_tokens_sum` | 3.63466e+06 | 761 |
| `vllm:request_inference_time_seconds_count` | 4776 |  |
| `vllm:request_inference_time_seconds_sum` | 191552 | 40.11 |
| `vllm:request_max_num_generation_tokens_count` | 4776 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.63466e+06 | 761 |
| `vllm:request_params_max_tokens_count` | 4776 |  |
| `vllm:request_params_max_tokens_sum` | 3.63466e+06 | 761 |
| `vllm:request_params_n_count` | 4776 |  |
| `vllm:request_params_n_sum` | 4776 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4776 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 5.94943e+07 | 1.246e+04 |
| `vllm:request_prefill_time_seconds_count` | 4776 |  |
| `vllm:request_prefill_time_seconds_sum` | 3334.15 | 0.6981 |
| `vllm:request_prompt_tokens_count` | 4776 |  |
| `vllm:request_prompt_tokens_sum` | 3.08555e+08 | 6.461e+04 |
| `vllm:request_queue_time_seconds_count` | 4776 |  |
| `vllm:request_queue_time_seconds_sum` | 4096.23 | 0.8577 |
| `vllm:request_success_total` | 4776 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4776 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 266.58 | 0.05582 |
| `vllm:time_to_first_token_seconds_count` | 4800 |  |
| `vllm:time_to_first_token_seconds_sum` | 8580.66 | 1.788 |

## EPP (2647 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.64803 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 67.9292 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 18.7569 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 27.0627 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 116.397 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 82624.8 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.474334 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.474334 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 84705.6 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1963.96 |  |
| `go_gc_cleanups_executed_cleanups_total` | 1 |  |
| `go_gc_cleanups_queued_cleanups_total` | 1 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3722 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3722 |  |
| `go_gc_duration_seconds_count` | 3722 |  |
| `go_gc_duration_seconds_sum` | 1.3235 | 0.0003556 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.51013e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.61502e+11 | 46.01 |
| `go_gc_heap_allocs_bytes_total` | 1.61502e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.51013e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.51016e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.61499e+11 | 46.01 |
| `go_gc_heap_frees_bytes_total` | 1.61499e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.51016e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.25886e+08 |  |
| `go_gc_pauses_seconds_count` | 7444 |  |
| `go_gc_pauses_seconds_sum` | 0.415577 | 5.583e-05 |
| `go_memstats_alloc_bytes_total` | 1.61502e+11 |  |
| `go_memstats_frees_total` | 3.83605e+09 |  |
| `go_memstats_mallocs_total` | 3.83602e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 33262 |  |
| `go_sched_latencies_seconds_count` | 2.90035e+06 |  |
| `go_sched_latencies_seconds_sum` | 43.5988 | 1.503e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 7444 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.281603 | 3.783e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 7444 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.415577 | 5.583e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 36.5221 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.47113e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 250.233 | 0.0001013 |
| `llm_d_epp_flow_control_requests_total` | 4803 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 7.46204e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 40.9108 | 5.483e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4776 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.49061e+08 | 5.215e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4776 |  |
| `llm_d_epp_request_duration_seconds_sum` | 231427 | 48.46 |
| `llm_d_epp_request_error_total` | 1 |  |
| `llm_d_epp_request_input_tokens_count` | 4776 |  |
| `llm_d_epp_request_input_tokens_sum` | 3.08555e+08 | 6.461e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4776 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 519.867 | 0.1088 |
| `llm_d_epp_request_output_tokens_count` | 4776 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.63466e+06 | 761 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4803 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 42920.2 | 8.936 |
| `llm_d_epp_request_size_bytes_count` | 4802 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.24683e+09 | 2.596e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.70222e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 192779 | 0.05207 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4776 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 265.755 | 0.05564 |
| `llm_d_epp_request_total` | 4802 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4776 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 43335.1 | 9.074 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4802 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 80.7719 | 0.01682 |
| `llm_d_epp_response_size_bytes_count` | 4776 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.79896e+08 | 2.052e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4802 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4802 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.18072 | 3.763e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 370 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 536 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4803 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 449 |  |
| `process_cpu_seconds_total` | 1884.85 |  |
| `process_network_receive_bytes_total` | 2.19342e+10 |  |
| `process_network_transmit_bytes_total` | 1.3852e+10 |  |
| `rest_client_requests_total` | 69 |  |
