# Raw metric deltas, epp-thunder-lease-main-c128

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2436 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 5641 |  |
| `http_request_duration_highr_seconds_sum` | 222021 | 39.36 |
| `http_request_duration_seconds_count` | 5641 |  |
| `http_request_duration_seconds_sum` | 222021 | 39.36 |
| `http_request_size_bytes_count` | 5641 |  |
| `http_requests_total` | 5641 |  |
| `http_response_size_bytes_count` | 5641 |  |
| `http_response_size_bytes_sum` | 993480 | 176.1 |
| `process_cpu_seconds_total` | 1683.58 |  |
| `python_gc_collections_total` | 861 |  |
| `python_gc_objects_collected_total` | 381 |  |
| `vllm:e2e_request_latency_seconds_count` | 3681 |  |
| `vllm:e2e_request_latency_seconds_sum` | 216874 | 58.92 |
| `vllm:generation_tokens_total` | 2.74112e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 2.73742e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 202617 | 0.07402 |
| `vllm:iteration_tokens_total_count` | 120633 |  |
| `vllm:iteration_tokens_total_sum` | 1.01039e+08 | 837.6 |
| `vllm:num_preemptions_total` | 12 |  |
| `vllm:prefix_cache_hits_total` | 1.37053e+08 |  |
| `vllm:prefix_cache_queries_total` | 2.35351e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 2.35351e+08 |  |
| `vllm:prompt_tokens_cached_total` | 1.37053e+08 |  |
| `vllm:prompt_tokens_total` | 2.35351e+08 |  |
| `vllm:request_decode_time_seconds_count` | 3681 |  |
| `vllm:request_decode_time_seconds_sum` | 197632 | 53.69 |
| `vllm:request_generation_tokens_count` | 3681 |  |
| `vllm:request_generation_tokens_sum` | 2.65774e+06 | 722 |
| `vllm:request_inference_time_seconds_count` | 3681 |  |
| `vllm:request_inference_time_seconds_sum` | 202686 | 55.06 |
| `vllm:request_max_num_generation_tokens_count` | 3681 |  |
| `vllm:request_max_num_generation_tokens_sum` | 2.65774e+06 | 722 |
| `vllm:request_params_max_tokens_count` | 3681 |  |
| `vllm:request_params_max_tokens_sum` | 2.65774e+06 | 722 |
| `vllm:request_params_n_count` | 3681 |  |
| `vllm:request_params_n_sum` | 3681 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 3681 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 9.75859e+07 | 2.651e+04 |
| `vllm:request_prefill_time_seconds_count` | 3681 |  |
| `vllm:request_prefill_time_seconds_sum` | 5054.73 | 1.373 |
| `vllm:request_prompt_tokens_count` | 3681 |  |
| `vllm:request_prompt_tokens_sum` | 2.34473e+08 | 6.37e+04 |
| `vllm:request_queue_time_seconds_count` | 3681 |  |
| `vllm:request_queue_time_seconds_sum` | 13286.6 | 3.61 |
| `vllm:request_success_total` | 3681 |  |
| `vllm:request_time_per_output_token_seconds_count` | 3681 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 289.672 | 0.07869 |
| `vllm:time_to_first_token_seconds_count` | 3693 |  |
| `vllm:time_to_first_token_seconds_sum` | 19367.3 | 5.244 |

## EPP (2436 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.02768 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 51.4199 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 19.9667 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 21.2617 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 94.676 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 76128.9 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.0005348 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.542512 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.543047 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 77939.1 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1715 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 2947 |  |
| `go_gc_cycles_total_gc_cycles_total` | 2947 |  |
| `go_gc_duration_seconds_count` | 2947 |  |
| `go_gc_duration_seconds_sum` | 1.02815 | 0.0003489 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.19605e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.45139e+11 | 45.41 |
| `go_gc_heap_allocs_bytes_total` | 1.45139e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.19605e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.196e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.45134e+11 | 45.41 |
| `go_gc_heap_frees_bytes_total` | 1.45134e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.196e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 2.94064e+08 |  |
| `go_gc_pauses_seconds_count` | 5894 |  |
| `go_gc_pauses_seconds_sum` | 0.328206 | 5.568e-05 |
| `go_memstats_alloc_bytes_total` | 1.45139e+11 |  |
| `go_memstats_frees_total` | 3.49006e+09 |  |
| `go_memstats_mallocs_total` | 3.49011e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 28108 |  |
| `go_sched_latencies_seconds_count` | 2.22228e+06 |  |
| `go_sched_latencies_seconds_sum` | 35.08 | 1.579e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 5894 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.219368 | 3.722e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 5894 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.328206 | 5.568e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 27.571 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.3012e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 207.93 | 9.036e-05 |
| `llm_d_epp_flow_control_requests_total` | 3694 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 5.51589e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 32.196 | 5.837e-06 |
| `llm_d_epp_request_cached_tokens_count` | 3681 |  |
| `llm_d_epp_request_cached_tokens_sum` | 1.36887e+08 | 3.719e+04 |
| `llm_d_epp_request_duration_seconds_count` | 3681 |  |
| `llm_d_epp_request_duration_seconds_sum` | 240330 | 65.29 |
| `llm_d_epp_request_input_tokens_count` | 3681 |  |
| `llm_d_epp_request_input_tokens_sum` | 2.34473e+08 | 6.37e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 3681 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 578.956 | 0.1573 |
| `llm_d_epp_request_output_tokens_count` | 3681 |  |
| `llm_d_epp_request_output_tokens_sum` | 2.65774e+06 | 722 |
| `llm_d_epp_request_processing_duration_seconds_count` | 3694 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 23981.4 | 6.492 |
| `llm_d_epp_request_size_bytes_count` | 3694 |  |
| `llm_d_epp_request_size_bytes_sum` | 9.39978e+08 | 2.545e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 2.73579e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 202523 | 0.07403 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 3681 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 289.114 | 0.07854 |
| `llm_d_epp_request_total` | 3694 |  |
| `llm_d_epp_request_ttft_seconds_count` | 3681 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 42791.3 | 11.62 |
| `llm_d_epp_response_processing_duration_seconds_count` | 3693 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 65.222 | 0.01766 |
| `llm_d_epp_response_size_bytes_count` | 3681 |  |
| `llm_d_epp_response_size_bytes_sum` | 7.16679e+08 | 1.947e+05 |
| `llm_d_epp_scheduler_attempts_total` | 3694 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 3694 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.143598 | 3.887e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 111 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 169 |  |
| `llm_d_epp_thunder_agent_releases_total` | 3694 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 113 |  |
| `process_cpu_seconds_total` | 1653.24 |  |
| `process_network_receive_bytes_total` | 1.88198e+10 |  |
| `process_network_transmit_bytes_total` | 1.04436e+10 |  |
| `rest_client_requests_total` | 68 |  |
