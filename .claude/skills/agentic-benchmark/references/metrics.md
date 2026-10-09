# Metrics: what to collect and what to report

The rule behind every line: if a number is needed to judge the result, collect it during the run. After the point is torn down it is gone.

Sources this file is distilled from:
- InferenceX AgentX result processing (`SemiAnalysisAI/InferenceX` `inferencex-e2e/infx/results/agentic/`, commit `255b9b8`): the throughput, interactivity and cache formulas.
- The repo's `BENCHMARK-METRICS.md` (steps 01 to 22): engine step, working set, session, SLO and gate metrics, and the validity rules. Read it for the reasoning behind a rule.

Column names below are the ones `scripts/analyze.py` writes to `summary.csv`.

## 1. Raw data every point must keep

`scripts/run-point.sh` collects all of it. Check the list when you change the scripts.

| Data | File in `results/<label>/c<N>/` | Why |
|---|---|---|
| One record per request (warmup and profiling) | `aiperf_artifacts/profile_export.jsonl` | Latency, throughput, sessions, timelines |
| aiperf run summary and validity | `aiperf_artifacts/profile_export_aiperf.json` | `submission_valid`, theoretical hit, error counts |
| vLLM metrics per pod, 1 s, profiling window | `aiperf_artifacts/server_metrics_export.parquet` | KV, cache source, queues, engine step. Only the parquet: the `.csv` and `.json` counter totals include the warmup |
| EPP metrics, 10 s (pool mode) | `epp/raw-epp-metrics.txt.gz` | Gate activity, router queue wait, gate ledger |
| Pod identity at start and end (vLLM and EPP) | `meta/pods-start.txt`, `meta/pods-end.txt` | A new uid or a restart invalidates the point |
| Server config | `meta/vllm-deployment.yaml`, `meta/epp-deployment.yaml`, `meta/epp-configmap-*.yaml`, `meta/cache-config-*.txt`, `meta/model-server.txt` | Server settings are part of the experiment |
| Logs | `bench-stdout.log`, `epp-*.log`, `meta/vllm-*.log.gz`, `aiperf_artifacts/logs/aiperf.log` | Only source of warnings and error text |
| Point config | `meta/point.json`, `meta/job.yaml`, `meta/finish.json` | Reproduce and label the point |

Required server flag: `--enable-prompt-tokens-details` on vLLM. Without it responses carry no cached-token count.

## 2. Throughput (InferenceX definitions)

Only profiling-phase requests that finished without error or cancel.

| Column | Formula |
|---|---|
| `duration_s` | max(request_end) - min(request_start) |
| `input_tput`, `output_tput`, `total_tput` | sum(ISL), sum(OSL), both / duration. ISL includes prefix-cache hits |
| `*_tput_per_gpu` | / `num_gpus` (GPUs per pod x pods) |
| `*_tokens_per_dollar`, `*_cost_per_mtok` | `tput_per_gpu x 3600 / cost_hr`, `cost_hr x 1e6 / (3600 x tput_per_gpu)` (only with `--cost-per-gpu-hour`) |
| `completed` | closed loop: a faster server completes more requests, so this is itself a result |

AgentX inputs are about 142k tokens median and outputs about 444, so total throughput is almost all input, and mostly cache hits. Report output throughput next to it.

### Whole window and steady state (`ss_*`)

Every throughput, latency percentile and goodput column exists twice: once over the whole profiling window (AgentX's definition, comparable with InferenceX) and once as `ss_<column>` over the requests that started after `--skip-minutes` (default 5). Server-side `ss_overall_hit_pct`, `ss_gpu_hit_pct`, `ss_recompute_pct`, `ss_kv_usage_avg_pct`, `ss_running_avg_sum`, `ss_waiting_avg_sum` use the same window (counter increase from the last scrape before it).

Why: after warmup each lane waits out its recorded first-request gap, and nothing releases lanes until the 300 s per-tree idle cap fires (the system idle cap does not, as a few lanes are always busy). The first 5 minutes therefore run at a few requests in flight, and their fast requests bias whole-run percentiles, worst at high c where few requests finish later: on `lane-20m` c=32, 53% of completions came in the first 5 minutes and the p50 tok/s/user was 43.7 whole run against 7.7 after minute 5. `pareto.png` and `concurrency.png` plot the `ss_*` values; `summary.md` shows both tables. Quote the whole-window numbers when comparing with InferenceX, the steady state for how the server behaves under the load.

## 3. Latency

| Column | Formula |
|---|---|
| `{mean,p50,p75,p90,p95}_ttft_s` | TTFT distribution |
| `{...}_intvty` | interactivity = 1 / pXX(full ITL), full ITL = (latency - TTFT) / (OSL - 1). `p90_intvty` is the slow 10% |
| `{...}_e2el_s` | end-to-end latency |
| `{...}_e2e_norm_intvty` | 1 / pXX(latency / OSL): includes the prefill wait, which interactivity does not |

Interactivity alone hides TTFT. Always show TTFT or E2E normalized interactivity next to it.

## 4. SLO and sessions

A session is an AgentX session tree (main agent plus subagents, `root_correlation_id`). The SLO is `--ttft-slo` (default 60 s).

| Column | Meaning |
|---|---|
| `goodput_output_tput` | output tok/s from turns whose TTFT meets the SLO |
| `turn_slo_share_pct` | turns meeting the SLO; an error counts as a miss |
| `session_worst_ttft_p90_s`, `sessions_worst_ttft_over_slo_pct` | per-session worst turn. Turn percentiles hide sessions held for a long time |
| `turns_per_session_p10/p50/p90` | progress per session in the window |
| `lanes_seen`, `effective_conc_requests`, `effective_sessions_inflight` | how much of the configured concurrency was really on the server. Sessions sit in tool gaps, so this is well below `conc` |

Throughput can be equal across arms while goodput differs a lot. Capacity at SLO = the largest tested concurrency where the target holds there and at every smaller point.

## 5. Engine: why the numbers are what they are

From vLLM counters, summed over pods, per pod kept in the parquet.

| Column | Formula or source | Use |
|---|---|---|
| `gpu_hit_pct`, `cpu_hit_pct`, `recompute_pct`, `overall_hit_pct` | `vllm:prompt_tokens_by_source{source}` shares: `local_cache_hit`, `external_kv_transfer`, `local_compute` | The primary pressure signal |
| `theoretical_hit_pct` | aiperf, from trace hashes | Gap to `overall_hit_pct` = evictions or session moves between pods |
| `prefix_hits_over_queries_pct` | `vllm:prefix_cache_hits / queries` | Fallback hit rate |
| `usage_cache_read_pct` | client `usage` cached tokens / ISL | Cross-check |
| `kv_usage_avg_pct`, `kv_usage_max_pct`, `kv_usage_skew_pct` | `vllm:kv_cache_usage_perc` per pod | Counts only blocks of running requests, so it cannot see the working-set limit |
| `running_avg_sum`, `waiting_avg_sum`, `*_max_pod` | `vllm:num_requests_running/waiting` | Active-batch limit |
| `waiting_<reason>_share_pct` | `vllm:num_requests_waiting_by_reason` | Why requests wait (KV `capacity` or `deferred`) |
| `preemptions` | `vllm:num_preemptions` | Pressure shown as preemption |
| `batch_B`, `step_time_T_ms`, `prefill_tokens_per_step` | from `vllm:iteration_tokens_total` and `vllm:generation_tokens` deltas per 10 s bin, busy bins only | Output throughput = B / T |
| `step_fit_a_ms`, `step_fit_b_ms_per_k`, `step_fit_r2` | fit T = a + b x (k prefill tokens per step) | On our setup T = 46 ms + 29 ms per k prefill tokens. The scheduler changes prefill per step, not B |
| `prefill_compute_per_output_token` | `local_compute` prompt tokens / output tokens | Recompute cost |
| `engine_request_{queue,prefill,decode}_time_avg_s` | vLLM histograms | Split TTFT into queueing and prefill |
| `srv_prompt_tput`, `srv_generation_tput` | server counters / duration | Cross-check the client numbers |

## 6. Working set against KV capacity

| Column | Meaning |
|---|---|
| `kv_pool_tokens` | sum of `kv_cache_size_tokens` over pods (`vllm:cache_config_info`) |
| `inflight_unique_tokens_max`, `inflight_unique_over_pool_max` | AgentX definition: ISL of running requests, per conversation |
| `working_set_mean/max`, `working_set_over_pool_mean/max` | latest ISL of every live session, including those between turns. What a cache needs to make every next turn a hit |

Two limits, read them apart:
- Working-set limit: all session prefixes do not fit. Signals: `overall_hit_pct` drops, `recompute_pct` rises, `working_set_over_pool` above 1.
- Active limit: running requests do not fit. Signals: `waiting` grows, one pod's KV near 100%, preemptions, throughput flat in concurrency.

## 7. Router and gate (pool mode, from the EPP scrape)

| Column | Source | Use |
|---|---|---|
| `gate_delayed_dispatches` | `llm_d_epp_thunder_agent_delayed_dispatches_total` (`holds_total` before PR3) | Proof the gate engaged |
| `gate_pauses`, `gate_resumes`, `gate_releases` | `_pauses_total`, `_resumes_total`, `_releases_total` | Session churn caused by the gate |
| `gate_starvation_promotions` | `_starvation_promotions_total` | Forced admissions. Non-zero means demand is past the pool's capacity at this backstop |
| `gate_working_set_over_capacity_mean/max` | `_endpoint_working_set_tokens` / `_endpoint_capacity_tokens` | The gate's ledger. Compare with vLLM's real KV state |
| `epp_queue_wait_mean_s`, `_p90_s`, `_p99_s` | `llm_d_epp_flow_control_request_queue_duration_seconds` | Wait moved from the engine to the router. The p90 is often near 0; the held minority sets mean and p99 |
| `epp_queue_size_mean/max` | `llm_d_epp_flow_control_queue_size` | Work waiting in the router |
| `epp_requests`, `epp_request_errors` | `llm_d_epp_request_total`, `_error_total` | Router-side errors |

## 8. Validity: before trusting a point

`analyze.py` prints these per point in `summary.md` ("Validity checks"). A point with a problem cannot be compared directly with other points.

- [ ] `submission_valid` true (AgentX rules: coverage, failure rate, no `--unsafe-override`)
- [ ] job succeeded, same vLLM and EPP pod uid and 0 restarts from start to end
- [ ] errors, cancels and context overflows near 0 (overflow under 1%)
- [ ] server hit within 10 points of the theoretical hit, or the gap explained
- [ ] calibration: the baseline at the point carrying the conclusion has hit rate below 85% or KV peak above 80%; otherwise the load is too light to show anything about scheduling
- [ ] gate arms: `gate_delayed_dispatches` or `gate_pauses` above 0
- [ ] the same client timeout (`--benchmark-grace-period`, `AIPERF_HTTP_TCP_USER_TIMEOUT`) and dataset slug and seed in every arm
- [ ] the gate's forced-admission backstop below every timeout on the path (flow control request TTL, envoy `message_timeout`, client); otherwise the run measures timeouts, not scheduling
- [ ] concurrency above 393 reuses traces (allowed with cache-bust; say so)
- [ ] the decision rule (what counts as a win) written down before looking at the data
- [ ] at least 3 replicates at the points that carry a conclusion; differences under about 5% are ties
- [ ] compare arms run on the same day and nodes; ratios across steps show trends only
