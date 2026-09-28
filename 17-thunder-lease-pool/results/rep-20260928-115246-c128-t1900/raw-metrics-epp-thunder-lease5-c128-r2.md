# Raw metric deltas, epp-thunder-lease5-c128-r2

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2563 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6455 |  |
| `http_request_duration_highr_seconds_sum` | 208533 | 32.31 |
| `http_request_duration_seconds_count` | 6455 |  |
| `http_request_duration_seconds_sum` | 208533 | 32.31 |
| `http_request_size_bytes_count` | 6455 |  |
| `http_requests_total` | 6455 |  |
| `http_response_size_bytes_count` | 6455 |  |
| `http_response_size_bytes_sum` | 1.04499e+06 | 161.9 |
| `process_cpu_seconds_total` | 1878.66 |  |
| `python_gc_collections_total` | 1018 |  |
| `python_gc_objects_collected_total` | 3616 |  |
| `vllm:e2e_request_latency_seconds_count` | 4388 |  |
| `vllm:e2e_request_latency_seconds_sum` | 205384 | 46.81 |
| `vllm:generation_tokens_total` | 3.42587e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.42146e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 198930 | 0.05814 |
| `vllm:iteration_tokens_total_count` | 137750 |  |
| `vllm:iteration_tokens_total_sum` | 7.37068e+07 | 535.1 |
| `vllm:num_preemptions_total` | 20 |  |
| `vllm:prefix_cache_hits_total` | 2.09926e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.80207e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.80207e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.09926e+08 |  |
| `vllm:prompt_tokens_total` | 2.80207e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4388 |  |
| `vllm:request_decode_time_seconds_sum` | 195919 | 44.65 |
| `vllm:request_generation_tokens_count` | 4388 |  |
| `vllm:request_generation_tokens_sum` | 3.37242e+06 | 768.6 |
| `vllm:request_inference_time_seconds_count` | 4388 |  |
| `vllm:request_inference_time_seconds_sum` | 199831 | 45.54 |
| `vllm:request_max_num_generation_tokens_count` | 4388 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.37242e+06 | 768.6 |
| `vllm:request_params_max_tokens_count` | 4388 |  |
| `vllm:request_params_max_tokens_sum` | 3.37242e+06 | 768.6 |
| `vllm:request_params_n_count` | 4388 |  |
| `vllm:request_params_n_sum` | 4388 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4388 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 6.92828e+07 | 1.579e+04 |
| `vllm:request_prefill_time_seconds_count` | 4388 |  |
| `vllm:request_prefill_time_seconds_sum` | 3911.82 | 0.8915 |
| `vllm:request_prompt_tokens_count` | 4388 |  |
| `vllm:request_prompt_tokens_sum` | 2.78513e+08 | 6.347e+04 |
| `vllm:request_queue_time_seconds_count` | 4388 |  |
| `vllm:request_queue_time_seconds_sum` | 4529.34 | 1.032 |
| `vllm:request_success_total` | 4388 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4388 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 260.8 | 0.05943 |
| `vllm:time_to_first_token_seconds_count` | 4406 |  |
| `vllm:time_to_first_token_seconds_sum` | 9562.17 | 2.17 |

## EPP (2563 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 1.9797 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 58.8634 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 18.5547 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 22.3941 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 101.792 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 80182.9 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.56794 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.56794 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 82012.8 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1727.57 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3421 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3421 |  |
| `go_gc_duration_seconds_count` | 3421 |  |
| `go_gc_duration_seconds_sum` | 1.09485 | 0.00032 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.40317e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.58432e+11 | 46.55 |
| `go_gc_heap_allocs_bytes_total` | 1.58432e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.40317e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.40288e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.58417e+11 | 46.55 |
| `go_gc_heap_frees_bytes_total` | 1.58417e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.40288e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.13508e+08 |  |
| `go_gc_pauses_seconds_count` | 6842 |  |
| `go_gc_pauses_seconds_sum` | 0.370578 | 5.416e-05 |
| `go_memstats_alloc_bytes_total` | 1.58432e+11 |  |
| `go_memstats_frees_total` | 3.71639e+09 |  |
| `go_memstats_mallocs_total` | 3.71668e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 31476 |  |
| `go_sched_latencies_seconds_count` | 2.64453e+06 |  |
| `go_sched_latencies_seconds_sum` | 38.6761 | 1.462e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 6842 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.244808 | 3.578e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 6842 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.370578 | 5.416e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 24.8282 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.40902e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 219.402 | 9.108e-05 |
| `llm_d_epp_flow_control_requests_total` | 4407 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 6.89344e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 36.2889 | 5.264e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4388 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.09231e+08 | 4.768e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4388 |  |
| `llm_d_epp_request_duration_seconds_sum` | 238162 | 54.28 |
| `llm_d_epp_request_input_tokens_count` | 4388 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.78513e+08 | 6.347e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4388 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 471.85 | 0.1075 |
| `llm_d_epp_request_output_tokens_count` | 4388 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.37242e+06 | 768.6 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4407 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 36516.7 | 8.286 |
| `llm_d_epp_request_size_bytes_count` | 4407 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.12038e+09 | 2.542e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.42029e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 198815 | 0.05813 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4388 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 260.043 | 0.05926 |
| `llm_d_epp_request_total` | 4407 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4388 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 42355.7 | 9.653 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4406 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 69.8817 | 0.01586 |
| `llm_d_epp_response_size_bytes_count` | 4388 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.09508e+08 | 2.073e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4407 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4407 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.152897 | 3.469e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 388 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 511 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4407 |  |
| `process_cpu_seconds_total` | 1688.69 |  |
| `process_network_receive_bytes_total` | 2.07795e+10 |  |
| `process_network_transmit_bytes_total` | 1.27819e+10 |  |
| `rest_client_requests_total` | 69 |  |
