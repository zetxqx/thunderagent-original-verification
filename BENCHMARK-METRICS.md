# Benchmark metrics: what to measure, from vLLM to the final report

A checklist distilled from steps 01 to 22. Use it before a run (is everything being collected?) and after it (is the cell valid, and what do we report?).

It replaces section 1 of [LESSONS.md](LESSONS.md), which was written after step 07 for the upstream Python router. The rest of LESSONS.md still applies.

The rule behind every line: if a number is needed to judge the result, collect it during the run. After the cell is torn down it is gone.

## 0. The four layers

| Layer | Source | Resolution | Question it answers |
|---|---|---|---|
| 1. vLLM engine | each vLLM pod's `/metrics`, scraped directly | full scrape every 10 s, key gauges every 2 s | Is the engine saturated, and by what: KV capacity, prefill, or decode bandwidth? |
| 2. Pod and router | Kubernetes API, EPP `/metrics`, logs | once per cell, plus every 10 s for EPP | Was the cell valid? What did the scheduler do? |
| 3. Client, per request | inference-perf per-request report | one record per turn | What did each user and session see? |
| 4. Cell summary | computed from layers 1 to 3 | one row per cell | The numbers we report and compare |

## 1. How to collect

- **Scrape each vLLM pod directly** (pod IP, port 8000), not through the gateway or the EPP. Router-side numbers are averages over pods and hide per-pod state.
- **Keep the full raw scrape**, gzipped (`raw-vllm-metrics.txt.gz`, `raw-epp-metrics.txt.gz`), next to a small CSV of key gauges. Later questions always need a metric that is not in the CSV: the step time fit in [THUNDER-AGENT-SUMMARY.md](summary-report/THUNDER-AGENT-SUMMARY.md) 3.1 used `vllm:iteration_tokens_total`, which no CSV had.
- **Counters: use deltas inside the window**, never cumulative values. One pod had 1.15 billion prefix cache queries left from earlier runs.
- **Results live in the cluster until collected.** The bench container ends with `touch /results/DONE; sleep 28800`, so a dead local driver loses nothing (LESSONS 2).
- **Copy logs and reports into per-cell files before any teardown** (LESSONS 4).

## 2. Layer 1: vLLM engine, per replica

Required server flag: `--enable-prompt-tokens-details`. Without it, responses have no `cached_tokens` and per-request cache analysis is impossible (LESSONS 3). Check one real response body before a long run.

### 2.1 KV cache and prefix cache

| Metric | How to use it | Why it matters |
|---|---|---|
| `vllm:cache_config_info` | `block_size x num_gpu_blocks` = GPU KV capacity in tokens | Denominator for the working set and for any admission gate capacity |
| `vllm:prefix_cache_queries_total`, `vllm:prefix_cache_hits_total` | interval hit rate = delta hits / delta queries | **The primary pressure signal.** If the baseline hit rate is already above 0.85, there is no recompute to save and no scheduler can help |
| `vllm:kv_cache_usage_perc` | mean and peak in the steady state | Secondary signal. It counts only blocks of running requests; cached blocks of finished requests sit in the free pool and are not counted. 50% usage can still mean "no pressure" |
| `vllm:external_prefix_cache_queries_total`, `_hits_total` | CPU tier hit rate | Only with KV offload |
| `vllm:prompt_tokens_by_source_total{source}` | split prompt tokens into `local_compute`, `local_cache_hit`, `external_kv_transfer` | Gives the prefill compute ratio (section 5.4) |

### 2.2 Queue and batch

| Metric | How to use it | Why it matters |
|---|---|---|
| `vllm:num_requests_running` | steady-state mean | The running batch. Bounded by GPU KV: with 60k to 90k token contexts only about 26 to 39 fit |
| `vllm:num_requests_waiting` | steady-state mean | Work queued inside the engine. With an admission gate, compare it with the EPP queue to see the wait move from engine to router |
| `vllm:num_requests_waiting_by_reason{reason}` | share of `capacity` vs `deferred` | Says why requests wait. In our runs 99.8% waited for KV `capacity`, not for `max_num_seqs` |
| `vllm:num_preemptions_total` | delta per cell | Shows whether pressure appears as preemption or as cache eviction |

### 2.3 Engine step: throughput = B / T

Each engine step produces one token per decoding request, so output throughput = `B / T`. Compute it per 10 s interval from counter deltas:

| Quantity | Formula |
|---|---|
| steps | delta `vllm:iteration_tokens_total_count` |
| `B`, decoding requests per step | delta `vllm:generation_tokens_total` / steps |
| prefill tokens per step | (delta `vllm:iteration_tokens_total_sum` - delta `vllm:generation_tokens_total`) / steps |
| `T`, step time | interval length / steps |

On our setup `T = 46 ms + 29 ms x (k prefill tokens per step)`, R² = 0.84. This one fit explains most differences between arms: the scheduler changes prefill per step, not `B` and not the 46 ms decode floor.

### 2.4 CPU KV offload (only when enabled)

| Metric | Why it matters |
|---|---|
| `vllm:kv_offload_load_bytes_total`, `vllm:kv_offload_load_time_total` | PCIe traffic and the share of time spent loading blocks back from host RAM |
| `vllm:kv_offload_store_bytes_total` | Write traffic into the tier |
| `vllm:kv_offload_cpu_cache_usage_perc` | Whether the CPU tier is full. When the working set outgrows the tier, hit rate collapses (CPU-OFFLOAD-BOTTLENECK, finding 6) |

### 2.5 Engine-side latency histograms (cross-check)

`vllm:time_to_first_token_seconds`, `vllm:inter_token_latency_seconds`, `vllm:request_queue_time_seconds`, `vllm:request_prefill_time_seconds`, `vllm:request_decode_time_seconds`, `vllm:e2e_request_latency_seconds`.

Use them to cross-check client numbers and to split TTFT into "waited in the engine queue" and "computed prefill".

### 2.6 GPU hardware: not collected so far

`vllm:estimated_flops_per_gpu_total` and `vllm:estimated_read_bytes_per_gpu_total` were always 0, because vLLM's utilization counters were not enabled, and we ran no DCGM exporter. The HBM bandwidth behind the 46 ms decode floor is therefore an estimate. Next time, collect either the vLLM utilization counters or DCGM metrics (SM activity, HBM bandwidth utilization, memory used) for each GPU.

## 3. Layer 2: pod and router

### 3.1 Pod identity and health (once per cell, in `manifest.json`)

| Item | Why it matters |
|---|---|
| vLLM pod name, uid, IP, node, at start and at end | Spot nodes take pods mid-run. A new uid means the cell is invalid: abort it and rename it `-PREEMPTED` |
| vLLM and EPP container restart counts, at start and at end | An OOM kill restarts the container in the same pod and empties every cache, without a new uid |
| cache reset before the cell (`reset.jsonl`: `POST /reset_prefix_cache`, plus `?reset_external=true` for the CPU tier) and its response | Every arm must start from a cold cache |
| CPU and memory of the vLLM and EPP pods (`cpu-usage.csv`, from `kubectl top`) | Shows the router is not the bottleneck (EPP used about 2 cores) |
| logs: `vllm.log.gz`, `epp.log`, `prober.log`, `bench-stdout.log` | Only source of event text, errors, and warnings |
| config hashes: vLLM image and full arg list, EPP image, `plugins.yaml` sha256, bench config sha256 | Server-side settings are part of the experiment config |

### 3.2 Per pod in a multi-pod pool

Keep every layer-1 metric **per pod**, not summed over the pool: hit rate, KV usage, running, waiting, preemptions. Sums hide imbalance, for example one pod thrashing while the others are idle. The EPP also exposes `llm_d_epp_per_endpoint_queue_size`.

### 3.3 EPP (router)

Standard EPP metrics:

| Metric | Why it matters |
|---|---|
| `llm_d_epp_request_total`, `llm_d_epp_request_error_total` | Request and error counts as the router sees them |
| `llm_d_epp_flow_control_queue_size`, `_queue_bytes`, `_request_queue_duration_seconds` | How much work waits in the router, and for how long |
| `llm_d_epp_flow_control_pool_saturation` | The router's view of pool saturation |
| `llm_d_epp_scheduler_e2e_duration_seconds`, `llm_d_epp_plugin_duration_seconds` | Scheduling overhead per request and per plugin |
| `llm_d_epp_request_ttft_seconds`, `llm_d_epp_request_streaming_itl_seconds` | Router-side latency, to cross-check the client |

Thunder-agent gate metrics (when the gate is in the plugin config):

| Metric | Why it matters |
|---|---|
| `llm_d_epp_thunder_agent_holds_total` (renamed `_delayed_dispatches_total` in PR3, step 23) | Requests held at the door. Proof that the gate engaged at all |
| `_pauses_total`, `_resumes_total`, `_releases_total` | Session churn caused by the gate |
| `_starvation_promotions_total` | Forced admissions after the 1800 s backstop. Any non-zero value means demand is past the pool's SLO capacity |
| `_endpoint_capacity_tokens`, `_endpoint_working_set_tokens`, `_endpoint_resident_tokens` | The gate's ledger per pod, to compare with vLLM's real KV state |
| `_sessions`, `_tier_drops_total` | Live sessions, and tier-budget drops (step 21) |

## 4. Layer 3: client, per request (inference-perf)

Fields every analysis needs, per turn:

| Field | Used for |
|---|---|
| `start_time`, `end_time` | steady-state window, session progress, working set |
| `session_id` | every session-level metric. Needs the session-id bench image (INFERENCE-PERF-BUGS issue 2) |
| `info.graph_event_id`, `server_usage.prompt_tokens` | pairing turns across arms when windows truncate (LESSONS 6) |
| `computed_metrics.time_to_first_token` | TTFT, SLO, goodput |
| `info.response_metrics.output_token_times` | ITL, and goodput counted by token timestamp |
| `server_usage.completion_tokens` | output tokens |
| `server_usage.prompt_tokens_details.cached_tokens` | per-request cache hit; needs the vLLM flag in section 2 |
| `error` | errors and timeouts by type |

Not needed, and about 70% of each file: `computed_metrics.inter_token_latencies`, `response_metrics.chunk_times` (mostly a copy of `output_token_times`), and the response text, stored twice in `output_text` and `output_message.content`. Pretty-printing adds another third. See INFERENCE-PERF-BUGS issue 5. Always set `per_request_fields` to drop `request`, `response` and `response_chunks`.

Also keep, per cell:

- `summary_lifecycle_metrics.json`, `validation.json`, and the session lifecycle report: sessions ended in the window, turns not issued at stage end.
- `trace-manifest.json`: corpus URL, slice sha256, filter rule, and the keep decision for every trace.

## 5. Layer 4: cell summary, what we report

All numbers are for the **steady state**: after the warm-up (10 minutes in our runs) and before the window ends. Say so when a number covers the whole window instead.

### 5.1 Throughput

- Output tokens per second.
- Turns per second.

### 5.2 Latency

- TTFT p50, p90, p99, per turn.
- ITL p50 and p90, from `output_token_times`.
- Per-session worst-turn TTFT, p90, and the share of sessions whose worst turn exceeded 60 s. Turn percentiles hide sessions that were held for a long time.

### 5.3 SLO

- **Goodput at TTFT <= X**: output tokens per second from turns that meet the SLO, counted by token timestamps ([22-slo-goodput/goodput.py](22-slo-goodput/goodput.py)).
- Turn SLO share: turns started in the steady state that meet X. An error counts as a miss.
- Session SLO attainment, strict (every turn meets X) and lenient (95% of turns).
- **Capacity at SLO**: the largest tested concurrency where the target holds there and at every smaller point.

Throughput alone can be the same across arms while goodput differs a lot (THUNDER-AGENT-SUMMARY 4.4).

### 5.4 Engine efficiency: why the numbers are what they are

- Hit rate: GPU, CPU tier, and total, from interval counter deltas.
- **Prefill compute ratio**: `local_compute` prompt tokens per output token.
- `B`, `T`, and prefill tokens per step (section 2.3).
- KV usage mean and peak, mean vLLM waiting queue, preemptions per cell.
- **Working set** (sum of the latest prompt size of every live session) against GPU KV capacity and the CPU tier size. See `working_set()` in [20-cpu-offload-pool/analyze.py](20-cpu-offload-pool/analyze.py).

### 5.5 Session progress and fairness

- **Effective concurrency**: time-weighted mean of sessions with a request in flight, against the configured `c`. They differ: sessions sit in tool gaps, and a corpus that runs out lets concurrency decay.
- Turns per session after warm-up, p10, p50, p90, and the share of sessions with zero turns.
- Sessions ended in the window, and turns not issued at stage end.
- Errors by type (client timeouts, 400s).

### 5.6 Gate behavior (only with an admission gate)

Holds, pauses, resumes, forced admissions, and EPP queue wait p90, per cell.

### 5.7 Repeats and ties

- Run at least 3 replicates at the points that carry a conclusion. Report mean (min to max), and paired ratios when arms share replicate indices.
- Cell-to-cell variance was 2% to 6%, so treat differences under about 5% as ties.

## 6. Validity checks: before trusting a cell

- [ ] **Calibration cell first** (10 minutes): baseline hit rate below 0.85 and KV peak at least 0.8. Otherwise the load is too light to show anything about scheduling (LESSONS 7).
- [ ] **Corpus size at least 3 x c**, and no trace replayed twice. Reused traces share hash ids and create fake cache hits.
- [ ] **Effective concurrency reached the target.** inference-perf v0.7.0 ran only half the sessions (INFERENCE-PERF-BUGS issue 4); use the fixed image.
- [ ] **The same client timeout in every arm, and above the forced-admission backstop** (1900 s against 1800 s). A shorter timeout measures workload trimming, not scheduling.
- [ ] Same vLLM pod uid from start to end, 0 restarts, not preempted.
- [ ] Cache reset at cell start returned success.
- [ ] `cached_tokens` present in responses.
- [ ] Config recorded: images, vLLM args, plugin and bench config hashes, corpus manifest.
- [ ] When windows truncate arms differently, compare paired turns (`graph_event_id` + `prompt_tokens` within 1%), and report the unpaired tail separately.
- [ ] Compare arms run on the same day and the same nodes. Ratios across steps show trends only.
- [ ] The decision rule (what counts as a win) is fixed before looking at the data.

## 7. Where everything lives in one cell directory

Example: `20-cpu-offload-pool/results/rep-20261001-201532-c128-t1900/epp-baseline-a/`.

| File | Layer | Content |
|---|---|---|
| `manifest.json` | 2 | pod names and uids, restarts, preempted flag, start and end time, config hashes |
| `reset.jsonl` | 2 | cache reset calls and responses |
| `cpu-usage.csv` | 2 | CPU and memory of the vLLM and EPP pods |
| `vllm.log.gz`, `epp.log`, `prober.log` | 2 | logs |
| `config.yml`, `plugins.yaml`, `epp-configmap.yaml`, `lane-values.yaml` | 2 | exact config of the cell |
| `results/vllm-metrics.csv` | 1 | key vLLM gauges and interval hit rate, every 2 s |
| `results/raw-vllm-metrics.txt.gz` | 1 | full vLLM scrape, every 10 s |
| `results/epp-metrics.csv`, `results/raw-epp-metrics.txt.gz` | 2 | EPP metrics |
| `results/report/per_request_lifecycle_metrics.json` | 3 | one record per turn |
| `results/report/summary_lifecycle_metrics.json`, `validation.json` | 3 | inference-perf summaries |
| `results/trace-manifest.json` | 3 | corpus provenance |
| `results/bench-stdout.log`, `results/DONE` | 3 | bench output and completion marker |

Analysis code that computes the section 5 numbers: [16-thunder-minimal-pool/analyze.py](16-thunder-minimal-pool/analyze.py) (cell statistics), [13-llm-d-router-sweep/analyze_replicates.py](13-llm-d-router-sweep/analyze_replicates.py) (session metrics), [20-cpu-offload-pool/analyze.py](20-cpu-offload-pool/analyze.py) (engine and working set), [22-slo-goodput/goodput.py](22-slo-goodput/goodput.py) (goodput), [summary-report/extract.py](summary-report/extract.py) (`B`, `T`, and the step time fit).
