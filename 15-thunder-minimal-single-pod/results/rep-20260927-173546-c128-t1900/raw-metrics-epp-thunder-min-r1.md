# Raw metric deltas, epp-thunder-min-r1

Every `_total`, `_sum` and `_count` series in the raw scrapes, summed over labels, last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM (3031 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 2209 |  |
| `http_request_duration_highr_seconds_sum` | 91560 | 41.45 |
| `http_request_duration_seconds_count` | 2209 |  |
| `http_request_duration_seconds_sum` | 91560 | 41.45 |
| `http_request_size_bytes_count` | 2209 |  |
| `http_requests_total` | 2209 |  |
| `http_response_size_bytes_count` | 2209 |  |
| `http_response_size_bytes_sum` | 309570 | 140.1 |
| `process_cpu_seconds_total` | 868 |  |
| `python_gc_collections_total` | 437 |  |
| `python_gc_objects_collected_total` | 34 |  |
| `vllm:e2e_request_latency_seconds_count` | 1580 |  |
| `vllm:e2e_request_latency_seconds_sum` | 87509.3 | 55.39 |
| `vllm:generation_tokens_total` | 1.1124e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 1.1108e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 86549.1 | 0.07792 |
| `vllm:iteration_tokens_total_count` | 35504 |  |
| `vllm:iteration_tokens_total_sum` | 4.12734e+07 | 1163 |
| `vllm:num_preemptions_total` | 6 |  |
| `vllm:prefix_cache_hits_total` | 5.43435e+07 |  |
| `vllm:prefix_cache_queries_total` | 9.45045e+07 |  |
| `vllm:prompt_tokens_by_source_total` | 9.45045e+07 |  |
| `vllm:prompt_tokens_cached_total` | 5.43435e+07 |  |
| `vllm:prompt_tokens_total` | 9.45045e+07 |  |
| `vllm:request_decode_time_seconds_count` | 1580 |  |
| `vllm:request_decode_time_seconds_sum` | 82652.7 | 52.31 |
| `vllm:request_generation_tokens_count` | 1580 |  |
| `vllm:request_generation_tokens_sum` | 1.07139e+06 | 678.1 |
| `vllm:request_inference_time_seconds_count` | 1580 |  |
| `vllm:request_inference_time_seconds_sum` | 84580.8 | 53.53 |
| `vllm:request_max_num_generation_tokens_count` | 1580 |  |
| `vllm:request_max_num_generation_tokens_sum` | 1.07139e+06 | 678.1 |
| `vllm:request_params_max_tokens_count` | 1580 |  |
| `vllm:request_params_max_tokens_sum` | 1.07139e+06 | 678.1 |
| `vllm:request_params_n_count` | 1580 |  |
| `vllm:request_params_n_sum` | 1580 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 1580 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 3.84818e+07 | 2.436e+04 |
| `vllm:request_prefill_time_seconds_count` | 1580 |  |
| `vllm:request_prefill_time_seconds_sum` | 1928.08 | 1.22 |
| `vllm:request_prompt_tokens_count` | 1580 |  |
| `vllm:request_prompt_tokens_sum` | 9.23526e+07 | 5.845e+04 |
| `vllm:request_queue_time_seconds_count` | 1580 |  |
| `vllm:request_queue_time_seconds_sum` | 2556.99 | 1.618 |
| `vllm:request_success_total` | 1580 |  |
| `vllm:request_time_per_output_token_seconds_count` | 1580 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 127.712 | 0.08083 |
| `vllm:time_to_first_token_seconds_count` | 1602 |  |
| `vllm:time_to_first_token_seconds_sum` | 4996.71 | 3.119 |

## EPP (3031 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 0.371622 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 13.7631 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 4.93414 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 4.31176 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 23.3806 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 96058.9 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00336302 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.377382 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.380745 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 96993.7 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 911.048 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 998 |  |
| `go_gc_cycles_total_gc_cycles_total` | 998 |  |
| `go_gc_duration_seconds_count` | 998 |  |
| `go_gc_duration_seconds_sum` | 0.230457 | 0.0002309 |
| `go_gc_heap_allocs_by_size_bytes_count` | 1.08878e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 5.35768e+10 | 49.21 |
| `go_gc_heap_allocs_bytes_total` | 5.35768e+10 |  |
| `go_gc_heap_allocs_objects_total` | 1.08878e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 1.08863e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 5.35681e+10 | 49.21 |
| `go_gc_heap_frees_bytes_total` | 5.35681e+10 |  |
| `go_gc_heap_frees_objects_total` | 1.08863e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 1.03127e+08 |  |
| `go_gc_pauses_seconds_count` | 1996 |  |
| `go_gc_pauses_seconds_sum` | 0.10087 | 5.054e-05 |
| `go_memstats_alloc_bytes_total` | 5.35768e+10 |  |
| `go_memstats_frees_total` | 1.19176e+09 |  |
| `go_memstats_mallocs_total` | 1.19191e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 30868 |  |
| `go_sched_latencies_seconds_count` | 1.07762e+06 |  |
| `go_sched_latencies_seconds_sum` | 14.8556 | 1.379e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 1996 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.0302277 | 1.514e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 1996 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.10087 | 5.054e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 9.68826 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.79167e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 196.544 | 7.04e-05 |
| `llm_d_epp_flow_control_request_enqueue_duration_seconds_count` | 585 |  |
| `llm_d_epp_flow_control_request_enqueue_duration_seconds_sum` | 0.00493395 | 8.434e-06 |
| `llm_d_epp_flow_control_request_queue_duration_seconds_count` | 585 |  |
| `llm_d_epp_flow_control_request_queue_duration_seconds_sum` | 7286.67 | 12.46 |
| `llm_d_epp_flow_control_requests_total` | 1602 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 2.24051e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 12.4505 | 5.557e-06 |
| `llm_d_epp_request_cached_tokens_count` | 1580 |  |
| `llm_d_epp_request_cached_tokens_sum` | 5.38707e+07 | 3.41e+04 |
| `llm_d_epp_request_duration_seconds_count` | 1580 |  |
| `llm_d_epp_request_duration_seconds_sum` | 123476 | 78.15 |
| `llm_d_epp_request_input_tokens_count` | 1580 |  |
| `llm_d_epp_request_input_tokens_sum` | 9.23526e+07 | 5.845e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 1580 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 432.046 | 0.2734 |
| `llm_d_epp_request_output_tokens_count` | 1580 |  |
| `llm_d_epp_request_output_tokens_sum` | 1.07139e+06 | 678.1 |
| `llm_d_epp_request_processing_duration_seconds_count` | 1602 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 42531 | 26.55 |
| `llm_d_epp_request_size_bytes_count` | 1602 |  |
| `llm_d_epp_request_size_bytes_sum` | 3.7857e+08 | 2.363e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 1.11066e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 86509.7 | 0.07789 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 1580 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 127.423 | 0.08065 |
| `llm_d_epp_request_total` | 1602 |  |
| `llm_d_epp_request_ttft_seconds_count` | 1580 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 40861.7 | 25.86 |
| `llm_d_epp_response_processing_duration_seconds_count` | 1602 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 23.8476 | 0.01489 |
| `llm_d_epp_response_size_bytes_count` | 1580 |  |
| `llm_d_epp_response_size_bytes_sum` | 2.894e+08 | 1.832e+05 |
| `llm_d_epp_scheduler_attempts_total` | 1602 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 1602 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.0534731 | 3.338e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 267 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 345 |  |
| `llm_d_epp_thunder_agent_releases_total` | 1602 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 311 |  |
| `llm_d_epp_thunder_agent_starvation_promotions_total` | 7 |  |
| `process_cpu_seconds_total` | 905.46 |  |
| `process_network_receive_bytes_total` | 6.39559e+09 |  |
| `process_network_transmit_bytes_total` | 6.33706e+09 |  |
| `rest_client_requests_total` | 69 |  |
