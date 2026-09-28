# Raw metric deltas, epp-thunder-lease5-c128

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2583 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6508 |  |
| `http_request_duration_highr_seconds_sum` | 202934 | 31.18 |
| `http_request_duration_seconds_count` | 6508 |  |
| `http_request_duration_seconds_sum` | 202934 | 31.18 |
| `http_request_size_bytes_count` | 6508 |  |
| `http_requests_total` | 6508 |  |
| `http_response_size_bytes_count` | 6508 |  |
| `http_response_size_bytes_sum` | 1.05468e+06 | 162.1 |
| `process_cpu_seconds_total` | 1922.2 |  |
| `python_gc_collections_total` | 1076 |  |
| `python_gc_objects_collected_total` | 1152 |  |
| `vllm:e2e_request_latency_seconds_count` | 4416 |  |
| `vllm:e2e_request_latency_seconds_sum` | 197894 | 44.81 |
| `vllm:generation_tokens_total` | 3.44146e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.43702e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 193266 | 0.05623 |
| `vllm:iteration_tokens_total_count` | 145194 |  |
| `vllm:iteration_tokens_total_sum` | 6.77142e+07 | 466.4 |
| `vllm:num_preemptions_total` | 10 |  |
| `vllm:prefix_cache_hits_total` | 2.26211e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.90688e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.90484e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.26211e+08 |  |
| `vllm:prompt_tokens_total` | 2.90484e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4416 |  |
| `vllm:request_decode_time_seconds_sum` | 188377 | 42.66 |
| `vllm:request_generation_tokens_count` | 4416 |  |
| `vllm:request_generation_tokens_sum` | 3.35323e+06 | 759.3 |
| `vllm:request_inference_time_seconds_count` | 4416 |  |
| `vllm:request_inference_time_seconds_sum` | 192076 | 43.5 |
| `vllm:request_max_num_generation_tokens_count` | 4416 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.35323e+06 | 759.3 |
| `vllm:request_params_max_tokens_count` | 4416 |  |
| `vllm:request_params_max_tokens_sum` | 3.35323e+06 | 759.3 |
| `vllm:request_params_n_count` | 4416 |  |
| `vllm:request_params_n_sum` | 4416 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4416 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 6.32513e+07 | 1.432e+04 |
| `vllm:request_prefill_time_seconds_count` | 4416 |  |
| `vllm:request_prefill_time_seconds_sum` | 3698.63 | 0.8376 |
| `vllm:request_prompt_tokens_count` | 4416 |  |
| `vllm:request_prompt_tokens_sum` | 2.88427e+08 | 6.531e+04 |
| `vllm:request_queue_time_seconds_count` | 4416 |  |
| `vllm:request_queue_time_seconds_sum` | 4803.39 | 1.088 |
| `vllm:request_success_total` | 4416 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4416 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 259.664 | 0.0588 |
| `vllm:time_to_first_token_seconds_count` | 4439 |  |
| `vllm:time_to_first_token_seconds_sum` | 9617.76 | 2.167 |

## EPP (2583 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.08951 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 58.6889 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 20.6729 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 22.4401 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 103.891 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 80728.5 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.477317 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.477317 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 82659.3 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1826.42 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3503 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3503 |  |
| `go_gc_duration_seconds_count` | 3503 |  |
| `go_gc_duration_seconds_sum` | 1.09775 | 0.0003134 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.43519e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.60528e+11 | 46.73 |
| `go_gc_heap_allocs_bytes_total` | 1.60528e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.43519e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.43519e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.60525e+11 | 46.73 |
| `go_gc_heap_frees_bytes_total` | 1.60525e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.43519e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.15962e+08 |  |
| `go_gc_pauses_seconds_count` | 7006 |  |
| `go_gc_pauses_seconds_sum` | 0.380513 | 5.431e-05 |
| `go_memstats_alloc_bytes_total` | 1.60528e+11 |  |
| `go_memstats_frees_total` | 3.75116e+09 |  |
| `go_memstats_mallocs_total` | 3.75115e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 32080 |  |
| `go_sched_latencies_seconds_count` | 2.68256e+06 |  |
| `go_sched_latencies_seconds_sum` | 40.0961 | 1.495e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 7006 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.246073 | 3.512e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 7006 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.380513 | 5.431e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 29.6877 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.43206e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 249.383 | 0.0001025 |
| `llm_d_epp_flow_control_requests_total` | 4440 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.92424e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 37.6724 | 5.441e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4416 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.25176e+08 | 5.099e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4416 |  |
| `llm_d_epp_request_duration_seconds_sum` | 232320 | 52.61 |
| `llm_d_epp_request_input_tokens_count` | 4416 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.88427e+08 | 6.531e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4416 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 465.072 | 0.1053 |
| `llm_d_epp_request_output_tokens_count` | 4416 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.35323e+06 | 759.3 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4440 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 39942.6 | 8.996 |
| `llm_d_epp_request_size_bytes_count` | 4440 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.15969e+09 | 2.612e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.4355e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 193147 | 0.05622 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4416 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 258.852 | 0.05862 |
| `llm_d_epp_request_total` | 4440 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4416 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 44060.2 | 9.977 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4440 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 73.8288 | 0.01663 |
| `llm_d_epp_response_size_bytes_count` | 4416 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.04206e+08 | 2.048e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4440 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4440 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.160258 | 3.609e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 363 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 475 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4440 |  |
| `process_cpu_seconds_total` | 1773.12 |  |
| `process_network_receive_bytes_total` | 2.10313e+10 |  |
| `process_network_transmit_bytes_total` | 1.2979e+10 |  |
| `rest_client_requests_total` | 70 |  |
