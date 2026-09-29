# Raw metric deltas, epp-thunder-lease-main-r1

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 1 pods (2067 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 1348 |  |
| `http_request_duration_highr_seconds_sum` | 56092 | 41.61 |
| `http_request_duration_seconds_count` | 1348 |  |
| `http_request_duration_seconds_sum` | 56092 | 41.61 |
| `http_request_size_bytes_count` | 1348 |  |
| `http_requests_total` | 1348 |  |
| `http_response_size_bytes_count` | 1348 |  |
| `http_response_size_bytes_sum` | 211140 | 156.6 |
| `process_cpu_seconds_total` | 579.57 |  |
| `python_gc_collections_total` | 257 |  |
| `vllm:e2e_request_latency_seconds_count` | 932 |  |
| `vllm:e2e_request_latency_seconds_sum` | 55469.1 | 59.52 |
| `vllm:generation_tokens_total` | 696521 |  |
| `vllm:inter_token_latency_seconds_count` | 695587 |  |
| `vllm:inter_token_latency_seconds_sum` | 51032.4 | 0.07337 |
| `vllm:iteration_tokens_total_count` | 31908 |  |
| `vllm:iteration_tokens_total_sum` | 2.70618e+07 | 848.1 |
| `vllm:num_preemptions_total` | 3 |  |
| `vllm:prefix_cache_hits_total` | 2.87704e+07 |  |
| `vllm:prefix_cache_queries_total` | 5.51356e+07 |  |
| `vllm:prompt_tokens_by_source_total` | 5.51356e+07 |  |
| `vllm:prompt_tokens_cached_total` | 2.87704e+07 |  |
| `vllm:prompt_tokens_total` | 5.51356e+07 |  |
| `vllm:request_decode_time_seconds_count` | 932 |  |
| `vllm:request_decode_time_seconds_sum` | 50435.8 | 54.12 |
| `vllm:request_generation_tokens_count` | 932 |  |
| `vllm:request_generation_tokens_sum` | 675387 | 724.7 |
| `vllm:request_inference_time_seconds_count` | 932 |  |
| `vllm:request_inference_time_seconds_sum` | 51738.2 | 55.51 |
| `vllm:request_max_num_generation_tokens_count` | 932 |  |
| `vllm:request_max_num_generation_tokens_sum` | 675387 | 724.7 |
| `vllm:request_params_max_tokens_count` | 932 |  |
| `vllm:request_params_max_tokens_sum` | 675387 | 724.7 |
| `vllm:request_params_n_count` | 932 |  |
| `vllm:request_params_n_sum` | 932 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 932 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 2.62109e+07 | 2.812e+04 |
| `vllm:request_prefill_time_seconds_count` | 932 |  |
| `vllm:request_prefill_time_seconds_sum` | 1302.44 | 1.397 |
| `vllm:request_prompt_tokens_count` | 932 |  |
| `vllm:request_prompt_tokens_sum` | 5.49812e+07 | 5.899e+04 |
| `vllm:request_queue_time_seconds_count` | 932 |  |
| `vllm:request_queue_time_seconds_sum` | 3505.97 | 3.762 |
| `vllm:request_success_total` | 932 |  |
| `vllm:request_time_per_output_token_seconds_count` | 932 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 69.9992 | 0.07511 |
| `vllm:time_to_first_token_seconds_count` | 934 |  |
| `vllm:time_to_first_token_seconds_sum` | 5052.12 | 5.409 |

## EPP (2067 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 0.278771 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 10.7814 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 3.04869 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 3.45437 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 17.5632 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 65590.4 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.0012836 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.374874 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.376158 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 66134.6 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 526.243 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 880 |  |
| `go_gc_cycles_total_gc_cycles_total` | 880 |  |
| `go_gc_duration_seconds_count` | 880 |  |
| `go_gc_duration_seconds_sum` | 0.193314 | 0.0002197 |
| `go_gc_heap_allocs_by_size_bytes_count` | 7.06385e+08 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 3.33559e+10 | 47.22 |
| `go_gc_heap_allocs_bytes_total` | 3.33559e+10 |  |
| `go_gc_heap_allocs_objects_total` | 7.06385e+08 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 7.06163e+08 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 3.33448e+10 | 47.22 |
| `go_gc_heap_frees_bytes_total` | 3.33448e+10 |  |
| `go_gc_heap_frees_objects_total` | 7.06163e+08 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 6.62256e+07 |  |
| `go_gc_pauses_seconds_count` | 1760 |  |
| `go_gc_pauses_seconds_sum` | 0.0872929 | 4.96e-05 |
| `go_memstats_alloc_bytes_total` | 3.33559e+10 |  |
| `go_memstats_frees_total` | 7.72388e+08 |  |
| `go_memstats_mallocs_total` | 7.7261e+08 |  |
| `go_sched_goroutines_created_goroutines_total` | 16927 |  |
| `go_sched_latencies_seconds_count` | 710808 |  |
| `go_sched_latencies_seconds_sum` | 9.34384 | 1.315e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 1760 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.0230912 | 1.312e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 1760 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.0872929 | 4.96e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 4.29791 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 1.89508e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 77.045 | 4.066e-05 |
| `llm_d_epp_flow_control_request_enqueue_duration_seconds_count` | 441 |  |
| `llm_d_epp_flow_control_request_enqueue_duration_seconds_sum` | 0.00351114 | 7.962e-06 |
| `llm_d_epp_flow_control_request_queue_duration_seconds_count` | 441 |  |
| `llm_d_epp_flow_control_request_queue_duration_seconds_sum` | 939.569 | 2.131 |
| `llm_d_epp_flow_control_requests_total` | 934 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 1.40203e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 7.31842 | 5.22e-06 |
| `llm_d_epp_request_cached_tokens_count` | 932 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.87704e+07 | 3.087e+04 |
| `llm_d_epp_request_duration_seconds_count` | 932 |  |
| `llm_d_epp_request_duration_seconds_sum` | 58956.9 | 63.26 |
| `llm_d_epp_request_input_tokens_count` | 932 |  |
| `llm_d_epp_request_input_tokens_sum` | 5.49812e+07 | 5.899e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 932 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 136.949 | 0.1469 |
| `llm_d_epp_request_output_tokens_count` | 932 |  |
| `llm_d_epp_request_output_tokens_sum` | 675387 | 724.7 |
| `llm_d_epp_request_processing_duration_seconds_count` | 934 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 3666.43 | 3.926 |
| `llm_d_epp_request_size_bytes_count` | 934 |  |
| `llm_d_epp_request_size_bytes_sum` | 2.19786e+08 | 2.353e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 695410 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 51009.5 | 0.07335 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 932 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 69.8091 | 0.0749 |
| `llm_d_epp_request_total` | 934 |  |
| `llm_d_epp_request_ttft_seconds_count` | 932 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 8543.93 | 9.167 |
| `llm_d_epp_response_processing_duration_seconds_count` | 934 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 14.852 | 0.0159 |
| `llm_d_epp_response_size_bytes_count` | 932 |  |
| `llm_d_epp_response_size_bytes_sum` | 1.82185e+08 | 1.955e+05 |
| `llm_d_epp_scheduler_attempts_total` | 934 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 934 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.0278661 | 2.984e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 40 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 55 |  |
| `llm_d_epp_thunder_agent_releases_total` | 934 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 38 |  |
| `process_cpu_seconds_total` | 525.04 |  |
| `process_network_receive_bytes_total` | 4.20019e+09 |  |
| `process_network_transmit_bytes_total` | 3.32318e+09 |  |
| `rest_client_requests_total` | 43 |  |
