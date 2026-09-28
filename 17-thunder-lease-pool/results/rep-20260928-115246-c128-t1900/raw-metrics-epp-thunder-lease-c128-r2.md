# Raw metric deltas, epp-thunder-lease-c128-r2

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2594 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6508 |  |
| `http_request_duration_highr_seconds_sum` | 184565 | 28.36 |
| `http_request_duration_seconds_count` | 6508 |  |
| `http_request_duration_seconds_sum` | 184565 | 28.36 |
| `http_request_size_bytes_count` | 6508 |  |
| `http_requests_total` | 6508 |  |
| `http_response_size_bytes_count` | 6508 |  |
| `http_response_size_bytes_sum` | 1.05672e+06 | 162.4 |
| `process_cpu_seconds_total` | 1935.25 |  |
| `python_gc_collections_total` | 1117 |  |
| `vllm:e2e_request_latency_seconds_count` | 4412 |  |
| `vllm:e2e_request_latency_seconds_sum` | 181929 | 41.24 |
| `vllm:generation_tokens_total` | 3.47188e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.46745e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 175180 | 0.05052 |
| `vllm:iteration_tokens_total_count` | 168775 |  |
| `vllm:iteration_tokens_total_sum` | 5.91411e+07 | 350.4 |
| `vllm:num_preemptions_total` | 6 |  |
| `vllm:prefix_cache_hits_total` | 2.41371e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.97135e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.9704e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.41371e+08 |  |
| `vllm:prompt_tokens_total` | 2.9704e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4412 |  |
| `vllm:request_decode_time_seconds_sum` | 172692 | 39.14 |
| `vllm:request_generation_tokens_count` | 4412 |  |
| `vllm:request_generation_tokens_sum` | 3.42566e+06 | 776.4 |
| `vllm:request_inference_time_seconds_count` | 4412 |  |
| `vllm:request_inference_time_seconds_sum` | 175955 | 39.88 |
| `vllm:request_max_num_generation_tokens_count` | 4412 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.42566e+06 | 776.4 |
| `vllm:request_params_max_tokens_count` | 4412 |  |
| `vllm:request_params_max_tokens_sum` | 3.42566e+06 | 776.4 |
| `vllm:request_params_n_count` | 4412 |  |
| `vllm:request_params_n_sum` | 4412 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4412 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 5.48928e+07 | 1.244e+04 |
| `vllm:request_prefill_time_seconds_count` | 4412 |  |
| `vllm:request_prefill_time_seconds_sum` | 3263.12 | 0.7396 |
| `vllm:request_prompt_tokens_count` | 4412 |  |
| `vllm:request_prompt_tokens_sum` | 2.95679e+08 | 6.702e+04 |
| `vllm:request_queue_time_seconds_count` | 4412 |  |
| `vllm:request_queue_time_seconds_sum` | 4941.19 | 1.12 |
| `vllm:request_success_total` | 4412 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4412 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 239.765 | 0.05434 |
| `vllm:time_to_first_token_seconds_count` | 4430 |  |
| `vllm:time_to_first_token_seconds_sum` | 9304.7 | 2.1 |

## EPP (2594 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.32 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 61.6133 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 21.388 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 23.9988 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 109.32 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 81025.1 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00167473 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.561644 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.563319 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 82996.8 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1861.85 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3570 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3570 |  |
| `go_gc_duration_seconds_count` | 3570 |  |
| `go_gc_duration_seconds_sum` | 1.1791 | 0.0003303 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.47293e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.65844e+11 | 47.75 |
| `go_gc_heap_allocs_bytes_total` | 1.65844e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.47293e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.4729e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.65838e+11 | 47.75 |
| `go_gc_heap_frees_bytes_total` | 1.65838e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.4729e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.17483e+08 |  |
| `go_gc_pauses_seconds_count` | 7140 |  |
| `go_gc_pauses_seconds_sum` | 0.392361 | 5.495e-05 |
| `go_memstats_alloc_bytes_total` | 1.65844e+11 |  |
| `go_memstats_frees_total` | 3.79038e+09 |  |
| `go_memstats_mallocs_total` | 3.79041e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 32411 |  |
| `go_sched_latencies_seconds_count` | 2.77343e+06 |  |
| `go_sched_latencies_seconds_sum` | 38.4705 | 1.387e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 7140 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.256494 | 3.592e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 7140 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.392361 | 5.495e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 26.914 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.44837e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 267.958 | 0.0001094 |
| `llm_d_epp_flow_control_requests_total` | 4439 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.98214e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 38.0622 | 5.451e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4412 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.40787e+08 | 5.458e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4412 |  |
| `llm_d_epp_request_duration_seconds_sum` | 221492 | 50.2 |
| `llm_d_epp_request_error_total` | 3 |  |
| `llm_d_epp_request_input_tokens_count` | 4412 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.95679e+08 | 6.702e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4412 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 498.595 | 0.113 |
| `llm_d_epp_request_output_tokens_count` | 4412 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.42566e+06 | 776.4 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4439 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 57623.8 | 12.98 |
| `llm_d_epp_request_size_bytes_count` | 4436 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.19141e+09 | 2.686e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.46447e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 175061 | 0.05053 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4412 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 239.017 | 0.05417 |
| `llm_d_epp_request_total` | 4436 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4412 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 48917.5 | 11.09 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4436 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 74.0322 | 0.01669 |
| `llm_d_epp_response_size_bytes_count` | 4412 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.23338e+08 | 2.093e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4436 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4436 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.154234 | 3.477e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 223 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 307 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4436 |  |
| `llm_d_epp_thunder_agent_starvation_promotions_total` | 1 |  |
| `process_cpu_seconds_total` | 1813 |  |
| `process_network_receive_bytes_total` | 2.12752e+10 |  |
| `process_network_transmit_bytes_total` | 1.32203e+10 |  |
| `rest_client_requests_total` | 71 |  |
