# Raw metric deltas, epp-thunder-min-hl10-s1-c128

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2554 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6554 |  |
| `http_request_duration_highr_seconds_sum` | 205832 | 31.41 |
| `http_request_duration_seconds_count` | 6554 |  |
| `http_request_duration_seconds_sum` | 205832 | 31.41 |
| `http_request_size_bytes_count` | 6554 |  |
| `http_requests_total` | 6554 |  |
| `http_response_size_bytes_count` | 6554 |  |
| `http_response_size_bytes_sum` | 1.04244e+06 | 159.1 |
| `process_cpu_seconds_total` | 1901.72 |  |
| `python_gc_collections_total` | 1131 |  |
| `python_gc_objects_collected_total` | 1353 |  |
| `vllm:e2e_request_latency_seconds_count` | 4471 |  |
| `vllm:e2e_request_latency_seconds_sum` | 198333 | 44.36 |
| `vllm:generation_tokens_total` | 3.49206e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.48755e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 196687 | 0.0564 |
| `vllm:iteration_tokens_total_count` | 140707 |  |
| `vllm:iteration_tokens_total_sum` | 7.09131e+07 | 504 |
| `vllm:num_preemptions_total` | 8 |  |
| `vllm:prefix_cache_hits_total` | 2.21294e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.88715e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.88715e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.21294e+08 |  |
| `vllm:prompt_tokens_total` | 2.88715e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4471 |  |
| `vllm:request_decode_time_seconds_sum` | 189452 | 42.37 |
| `vllm:request_generation_tokens_count` | 4471 |  |
| `vllm:request_generation_tokens_sum` | 3.36112e+06 | 751.8 |
| `vllm:request_inference_time_seconds_count` | 4471 |  |
| `vllm:request_inference_time_seconds_sum` | 193208 | 43.21 |
| `vllm:request_max_num_generation_tokens_count` | 4471 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.36112e+06 | 751.8 |
| `vllm:request_params_max_tokens_count` | 4471 |  |
| `vllm:request_params_max_tokens_sum` | 3.36112e+06 | 751.8 |
| `vllm:request_params_n_count` | 4471 |  |
| `vllm:request_params_n_sum` | 4471 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4471 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 6.53281e+07 | 1.461e+04 |
| `vllm:request_prefill_time_seconds_count` | 4471 |  |
| `vllm:request_prefill_time_seconds_sum` | 3756.57 | 0.8402 |
| `vllm:request_prompt_tokens_count` | 4471 |  |
| `vllm:request_prompt_tokens_sum` | 2.84645e+08 | 6.366e+04 |
| `vllm:request_queue_time_seconds_count` | 4471 |  |
| `vllm:request_queue_time_seconds_sum` | 4118.48 | 0.9212 |
| `vllm:request_success_total` | 4471 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4471 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 261.701 | 0.05853 |
| `vllm:time_to_first_token_seconds_count` | 4510 |  |
| `vllm:time_to_first_token_seconds_sum` | 9102.1 | 2.018 |

## EPP (2554 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.31999 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 59.8594 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 19.8409 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 23.8756 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 105.896 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 79814.5 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.464966 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.464966 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 81723.2 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1802.33 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3399 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3399 |  |
| `go_gc_duration_seconds_count` | 3399 |  |
| `go_gc_duration_seconds_sum` | 1.17019 | 0.0003443 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.38139e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.54888e+11 | 45.81 |
| `go_gc_heap_allocs_bytes_total` | 1.54888e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.38139e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.38136e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.54883e+11 | 45.81 |
| `go_gc_heap_frees_bytes_total` | 1.54883e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.38136e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.13647e+08 |  |
| `go_gc_pauses_seconds_count` | 6798 |  |
| `go_gc_pauses_seconds_sum` | 0.368658 | 5.423e-05 |
| `go_memstats_alloc_bytes_total` | 1.54888e+11 |  |
| `go_memstats_frees_total` | 3.695e+09 |  |
| `go_memstats_mallocs_total` | 3.69504e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 31829 |  |
| `go_sched_latencies_seconds_count` | 2.6937e+06 |  |
| `go_sched_latencies_seconds_sum` | 39.8821 | 1.481e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6798 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.252189 | 3.71e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6798 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.368658 | 5.423e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 30.3903 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.38717e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 229.792 | 9.626e-05 |
| `llm_d_epp_flow_control_requests_total` | 4510 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 7.02601e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 37.2701 | 5.305e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4471 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.19317e+08 | 4.905e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4471 |  |
| `llm_d_epp_request_duration_seconds_sum` | 231379 | 51.75 |
| `llm_d_epp_request_input_tokens_count` | 4471 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.84645e+08 | 6.366e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4471 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 533.707 | 0.1194 |
| `llm_d_epp_request_output_tokens_count` | 4471 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.36112e+06 | 751.8 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4510 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 40032.9 | 8.876 |
| `llm_d_epp_request_size_bytes_count` | 4510 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.15217e+09 | 2.555e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.48596e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 196569 | 0.05639 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4471 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 260.894 | 0.05835 |
| `llm_d_epp_request_total` | 4510 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4471 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 42042.8 | 9.403 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4510 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 74.1114 | 0.01643 |
| `llm_d_epp_response_size_bytes_count` | 4471 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.0627e+08 | 2.027e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4510 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4510 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.166373 | 3.689e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 398 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 572 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4510 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 493 |  |
| `process_cpu_seconds_total` | 1740.71 |  |
| `process_network_receive_bytes_total` | 2.08712e+10 |  |
| `process_network_transmit_bytes_total` | 1.29315e+10 |  |
| `rest_client_requests_total` | 70 |  |
