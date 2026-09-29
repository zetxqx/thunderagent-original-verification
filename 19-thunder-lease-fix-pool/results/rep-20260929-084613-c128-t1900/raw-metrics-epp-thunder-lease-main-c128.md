# Raw metric deltas, epp-thunder-lease-main-c128

Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), last snapshot minus first. Histogram means are sum delta / count delta.

## vLLM, 4 pods (2640 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `http_request_duration_highr_seconds_count` | 6764 |  |
| `http_request_duration_highr_seconds_sum` | 191612 | 28.33 |
| `http_request_duration_seconds_count` | 6764 |  |
| `http_request_duration_seconds_sum` | 191612 | 28.33 |
| `http_request_size_bytes_count` | 6764 |  |
| `http_requests_total` | 6764 |  |
| `http_response_size_bytes_count` | 6764 |  |
| `http_response_size_bytes_sum` | 1.07763e+06 | 159.3 |
| `process_cpu_seconds_total` | 2002.2 |  |
| `python_gc_collections_total` | 1148 |  |
| `python_gc_objects_collected_total` | 887 |  |
| `vllm:e2e_request_latency_seconds_count` | 4632 |  |
| `vllm:e2e_request_latency_seconds_sum` | 188217 | 40.63 |
| `vllm:generation_tokens_total` | 3.73609e+06 |  |
| `vllm:inter_token_latency_seconds_count` | 3.73144e+06 |  |
| `vllm:inter_token_latency_seconds_sum` | 183422 | 0.04916 |
| `vllm:iteration_tokens_total_count` | 174695 |  |
| `vllm:iteration_tokens_total_sum` | 5.71808e+07 | 327.3 |
| `vllm:num_preemptions_total` | 5 |  |
| `vllm:prefix_cache_hits_total` | 2.52379e+08 |  |
| `vllm:prefix_cache_queries_total` | 3.05824e+08 |  |
| `vllm:prompt_tokens_by_source_total` | 3.05824e+08 |  |
| `vllm:prompt_tokens_cached_total` | 2.52379e+08 |  |
| `vllm:prompt_tokens_total` | 3.05824e+08 |  |
| `vllm:request_decode_time_seconds_count` | 4632 |  |
| `vllm:request_decode_time_seconds_sum` | 180138 | 38.89 |
| `vllm:request_generation_tokens_count` | 4632 |  |
| `vllm:request_generation_tokens_sum` | 3.67581e+06 | 793.6 |
| `vllm:request_inference_time_seconds_count` | 4632 |  |
| `vllm:request_inference_time_seconds_sum` | 183202 | 39.55 |
| `vllm:request_max_num_generation_tokens_count` | 4632 |  |
| `vllm:request_max_num_generation_tokens_sum` | 3.67581e+06 | 793.6 |
| `vllm:request_params_max_tokens_count` | 4632 |  |
| `vllm:request_params_max_tokens_sum` | 3.67581e+06 | 793.6 |
| `vllm:request_params_n_count` | 4632 |  |
| `vllm:request_params_n_sum` | 4632 | 1 |
| `vllm:request_prefill_kv_computed_tokens_count` | 4632 |  |
| `vllm:request_prefill_kv_computed_tokens_sum` | 5.26226e+07 | 1.136e+04 |
| `vllm:request_prefill_time_seconds_count` | 4632 |  |
| `vllm:request_prefill_time_seconds_sum` | 3064.04 | 0.6615 |
| `vllm:request_prompt_tokens_count` | 4632 |  |
| `vllm:request_prompt_tokens_sum` | 3.04033e+08 | 6.564e+04 |
| `vllm:request_queue_time_seconds_count` | 4632 |  |
| `vllm:request_queue_time_seconds_sum` | 3958.75 | 0.8547 |
| `vllm:request_success_total` | 4632 |  |
| `vllm:request_time_per_output_token_seconds_count` | 4632 |  |
| `vllm:request_time_per_output_token_seconds_sum` | 252.947 | 0.05461 |
| `vllm:time_to_first_token_seconds_count` | 4651 |  |
| `vllm:time_to_first_token_seconds_sum` | 8147.45 | 1.752 |

## EPP (2640 s between first and last snapshot)

| metric | delta | histogram mean |
|---|---|---|
| `go_cpu_classes_gc_mark_assist_cpu_seconds_total` | 2.45979 |  |
| `go_cpu_classes_gc_mark_dedicated_cpu_seconds_total` | 67.3818 |  |
| `go_cpu_classes_gc_mark_idle_cpu_seconds_total` | 21.7551 |  |
| `go_cpu_classes_gc_pause_cpu_seconds_total` | 28.0096 |  |
| `go_cpu_classes_gc_total_cpu_seconds_total` | 119.606 |  |
| `go_cpu_classes_idle_cpu_seconds_total` | 82377.8 |  |
| `go_cpu_classes_scavenge_assist_cpu_seconds_total` | 0.00010471 |  |
| `go_cpu_classes_scavenge_background_cpu_seconds_total` | 0.488722 |  |
| `go_cpu_classes_scavenge_total_cpu_seconds_total` | 0.488827 |  |
| `go_cpu_classes_total_cpu_seconds_total` | 84491.2 |  |
| `go_cpu_classes_user_cpu_seconds_total` | 1993.29 |  |
| `go_gc_cycles_automatic_gc_cycles_total` | 3721 |  |
| `go_gc_cycles_total_gc_cycles_total` | 3721 |  |
| `go_gc_duration_seconds_count` | 3721 |  |
| `go_gc_duration_seconds_sum` | 1.36398 | 0.0003666 |
| `go_gc_heap_allocs_by_size_bytes_count` | 3.52179e+09 |  |
| `go_gc_heap_allocs_by_size_bytes_sum` | 1.66479e+11 | 47.27 |
| `go_gc_heap_allocs_bytes_total` | 1.66479e+11 |  |
| `go_gc_heap_allocs_objects_total` | 3.52179e+09 |  |
| `go_gc_heap_frees_by_size_bytes_count` | 3.52172e+09 |  |
| `go_gc_heap_frees_by_size_bytes_sum` | 1.66472e+11 | 47.27 |
| `go_gc_heap_frees_bytes_total` | 1.66472e+11 |  |
| `go_gc_heap_frees_objects_total` | 3.52172e+09 |  |
| `go_gc_heap_tiny_allocs_objects_total` | 3.20524e+08 |  |
| `go_gc_pauses_seconds_count` | 7442 |  |
| `go_gc_pauses_seconds_sum` | 0.422875 | 5.682e-05 |
| `go_memstats_alloc_bytes_total` | 1.66479e+11 |  |
| `go_memstats_frees_total` | 3.84225e+09 |  |
| `go_memstats_mallocs_total` | 3.84232e+09 |  |
| `go_sched_goroutines_created_goroutines_total` | 32701 |  |
| `go_sched_latencies_seconds_count` | 2.91913e+06 |  |
| `go_sched_latencies_seconds_sum` | 42.5089 | 1.456e-05 |
| `go_sched_pauses_stopping_gc_seconds_count` | 7442 |  |
| `go_sched_pauses_stopping_gc_seconds_sum` | 0.281653 | 3.785e-05 |
| `go_sched_pauses_total_gc_seconds_count` | 7442 |  |
| `go_sched_pauses_total_gc_seconds_sum` | 0.422875 | 5.682e-05 |
| `go_sync_mutex_wait_total_seconds_total` | 34.0277 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_count` | 2.47594e+06 |  |
| `llm_d_epp_flow_control_dispatch_cycle_duration_seconds_sum` | 272.583 | 0.0001101 |
| `llm_d_epp_flow_control_requests_total` | 4654 |  |
| `llm_d_epp_plugin_duration_seconds_count` | 7.51362e+06 |  |
| `llm_d_epp_plugin_duration_seconds_sum` | 40.5445 | 5.396e-06 |
| `llm_d_epp_request_cached_tokens_count` | 4632 |  |
| `llm_d_epp_request_cached_tokens_sum` | 2.51411e+08 | 5.428e+04 |
| `llm_d_epp_request_duration_seconds_count` | 4632 |  |
| `llm_d_epp_request_duration_seconds_sum` | 229658 | 49.58 |
| `llm_d_epp_request_error_total` | 3 |  |
| `llm_d_epp_request_input_tokens_count` | 4632 |  |
| `llm_d_epp_request_input_tokens_sum` | 3.04033e+08 | 6.564e+04 |
| `llm_d_epp_request_ntpot_seconds_count` | 4632 |  |
| `llm_d_epp_request_ntpot_seconds_sum` | 469.48 | 0.1014 |
| `llm_d_epp_request_output_tokens_count` | 4632 |  |
| `llm_d_epp_request_output_tokens_sum` | 3.67581e+06 | 793.6 |
| `llm_d_epp_request_processing_duration_seconds_count` | 4654 |  |
| `llm_d_epp_request_processing_duration_seconds_sum` | 51362.3 | 11.04 |
| `llm_d_epp_request_size_bytes_count` | 4651 |  |
| `llm_d_epp_request_size_bytes_sum` | 1.2236e+09 | 2.631e+05 |
| `llm_d_epp_request_streaming_itl_seconds_count` | 3.72891e+06 |  |
| `llm_d_epp_request_streaming_itl_seconds_sum` | 183296 | 0.04916 |
| `llm_d_epp_request_streaming_tpot_seconds_count` | 4632 |  |
| `llm_d_epp_request_streaming_tpot_seconds_sum` | 252.205 | 0.05445 |
| `llm_d_epp_request_total` | 4651 |  |
| `llm_d_epp_request_ttft_seconds_count` | 4632 |  |
| `llm_d_epp_request_ttft_seconds_sum` | 49645 | 10.72 |
| `llm_d_epp_response_processing_duration_seconds_count` | 4651 |  |
| `llm_d_epp_response_processing_duration_seconds_sum` | 80.8568 | 0.01738 |
| `llm_d_epp_response_size_bytes_count` | 4632 |  |
| `llm_d_epp_response_size_bytes_sum` | 9.91171e+08 | 2.14e+05 |
| `llm_d_epp_scheduler_attempts_total` | 4651 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_count` | 4651 |  |
| `llm_d_epp_scheduler_e2e_duration_seconds_sum` | 0.167526 | 3.602e-05 |
| `llm_d_epp_thunder_agent_holds_total` | 281 |  |
| `llm_d_epp_thunder_agent_pauses_total` | 384 |  |
| `llm_d_epp_thunder_agent_releases_total` | 4651 |  |
| `llm_d_epp_thunder_agent_resumes_total` | 306 |  |
| `llm_d_epp_thunder_agent_starvation_promotions_total` | 1 |  |
| `process_cpu_seconds_total` | 1916.32 |  |
| `process_network_receive_bytes_total` | 2.19132e+10 |  |
| `process_network_transmit_bytes_total` | 1.29226e+10 |  |
| `rest_client_requests_total` | 72 |  |
