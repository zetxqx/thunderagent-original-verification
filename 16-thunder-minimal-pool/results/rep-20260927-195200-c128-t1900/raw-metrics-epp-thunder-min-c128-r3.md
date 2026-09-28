# Raw metric deltas, epp-thunder-min-c128-r3

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2507 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6218 |  |
| `http_request_duration_highr_seconds_sum` | 206430 | 33.2 |
| `http_request_duration_seconds_count` | 6218 |  |
| `http_request_duration_seconds_sum` | 206430 | 33.2 |
| `http_request_size_bytes_count` | 6218 |  |
| `http_requests_total` | 6218 |  |
| `http_response_size_bytes_count` | 6218 |  |
| `http_response_size_bytes_sum` | 1.02408e+06 | 164.7 |
| `process_cpu_seconds_total` | 1819.77 |  |
| `python_gc_collections_total` | 1014 |  |
| `python_gc_objects_collected_total` | 187 |  |
| `vllm:e2e_request_latency_seconds_count` | 4188 |  |
| `vllm:e2e_request_latency_seconds_sum` | 203350 | 48.56 |
| `vllm:generation_tokens_total` | 3.22498e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.22077e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 195853 | 0.06081 |
| `vllm:iteration_tokens_total_count` | 143058 |  |
| `vllm:iteration_tokens_total_sum` | 8.07705e+07 | 564.6 |
| `vllm:num_preemptions_total` | 5 |  |
| `vllm:prefix_cache_hits_total` | 1.89002e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.66751e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.66547e+08 |  |
| `vllm:prompt_tokens_cached_total` | 1.89002e+08 |  |
| `vllm:prompt_tokens_total` | 2.66547e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4188 |  |
| `vllm:request_decode_time_seconds_sum` | 192952 | 46.07 |
| `vllm:request_generation_tokens_count` | 4188 |  |
| `vllm:request_generation_tokens_sum` | 3.18063e+06 | 759.5 |
| `vllm:request_inference_time_seconds_count` | 4188 |  |
| `vllm:request_inference_time_seconds_sum` | 197087 | 47.06 |
| `vllm:request_max_num_generation_tokens_count` | 4188 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.18063e+06 | 759.5 |
| `vllm:request_params_max_tokens_count` | 4188 |  |
| `vllm:request_params_max_tokens_sum` | 3.18063e+06 | 759.5 |
| `vllm:request_params_n_count` | 4188 |  |
| `vllm:request_params_n_sum` | 4188 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4188 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 7.61501e+07 | 1.818e+04 |
| `vllm:request_prefill_time_seconds_count` | 4188 |  |
| `vllm:request_prefill_time_seconds_sum` | 4134.96 | 0.9873 |
| `vllm:request_prompt_tokens_count` | 4188 |  |
| `vllm:request_prompt_tokens_sum` | 2.64584e+08 | 6.318e+04 |
| `vllm:request_queue_time_seconds_count` | 4188 |  |
| `vllm:request_queue_time_seconds_sum` | 5306.98 | 1.267 |
| `vllm:request_success_total` | 4188 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4188 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 267.597 | 0.0639 |
| `vllm:time_to_first_token_seconds_count` | 4209 |  |
| `vllm:time_to_first_token_seconds_sum` | 10509.1 | 2.497 |

## EPP (2507 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.05799 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 55.2128 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 18.3719 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 23.2731 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 98.9158 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 78353.3 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00095798 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.49406 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.495018 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 80217.6 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1764.83 |  |
| `go_gc_cleanups_executed_cleanups_total` | 1 |  |
| `go_gc_cleanups_queued_cleanups_total` | 1 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3182 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3182 |  |
| `go_gc_duration_seconds_count` | 3182 |  |
| `go_gc_duration_seconds_sum` | 1.12415 | 0.0003533 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.30854e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.50628e+11 | 45.53 |
| `go_gc_heap_allocs_bytes_total` | 1.50628e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.30854e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.30845e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.5062e+11 | 45.53 |
| `go_gc_heap_frees_bytes_total` | 1.5062e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.30845e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.07271e+08 |  |
| `go_gc_pauses_seconds_count` | 6364 |  |
| `go_gc_pauses_seconds_sum` | 0.354172 | 5.565e-05 |
| `go_memstats_alloc_bytes_total` | 1.50628e+11 |  |
| `go_memstats_frees_total` | 3.61572e+09 |  |
| `go_memstats_mallocs_total` | 3.61581e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 30723 |  |
| `go_sched_latencies_seconds_count` | 2.51313e+06 |  |
| `go_sched_latencies_seconds_sum` | 37.9994 | 1.512e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6364 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.243525 | 3.827e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6364 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.354172 | 5.565e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 29.3688 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.34224e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 227.549 | 9.715e-05 |
| `llm_d_epp_flow_control_requests_total` | 4210 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.48942e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 35.067 | 5.404e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4188 |  |
| `llm_d_epp_request_cached_tokens_sum` | 1.88434e+08 | 4.499e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4188 |  |
| `llm_d_epp_request_duration_seconds_sum` | 233199 | 55.68 |
| `llm_d_epp_request_input_tokens_count` | 4188 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.64584e+08 | 6.318e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4188 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 520.127 | 0.1242 |
| `llm_d_epp_request_output_tokens_count` | 4188 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.18063e+06 | 759.5 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4210 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 36742.1 | 8.727 |
| `llm_d_epp_request_size_bytes_count` | 4210 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.0668e+09 | 2.534e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.21946e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 195743 | 0.0608 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4188 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 266.832 | 0.06371 |
| `llm_d_epp_request_total` | 4210 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4188 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 40355.2 | 9.636 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4210 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 69.8706 | 0.0166 |
| `llm_d_epp_response_size_bytes_count` | 4188 |  |
| `llm_d_epp_response_size_bytes_sum` | 8.58057e+08 | 2.049e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4210 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4210 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.156183 | 3.71e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 384 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 536 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4210 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 460 |  |
| `process_cpu_seconds_total` | 1698.32 |  |
| `process_network_receive_bytes_total` | 2.00643e+10 |  |
| `process_network_transmit_bytes_total` | 1.22057e+10 |  |
| `rest_client_requests_total` | 69 |  |
