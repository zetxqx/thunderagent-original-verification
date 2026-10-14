# Bundle format `agentic-bench/1`

One bundle is one JSON file for one experiment (usually one step): its arms, and for every point a summary row, validity checks, configuration, time series and distributions. `export_bundle.py` in the agentic-benchmark skill writes it from a step's `results/<label>/c<N>` folders; any other tool can write the same format.

Only `schema`, `title`, `arms` and `points[].{id, arm, conc, summary}` are required. Everything else is optional: charts whose data is missing say so and stay empty. Numbers are JSON numbers; missing values are `null` (no `NaN`).

## Top level

| Field | Type | Meaning |
|---|---|---|
| `schema` | string | `"agentic-bench/1"` |
| `title` | string | shown in the sidebar and the header |
| `description` | string | free text (hover the bundle name) |
| `created_utc` | string | ISO 8601 time of the export |
| `settings.ttft_slo_s` | number | TTFT SLO of the summary's goodput and SLO columns, drawn on the SLO chart |
| `settings.skip_minutes` | number | steady state starts this many minutes into profiling; `ss_*` columns use it, time series mark it |
| `settings.kv_bytes_per_token` | int or null | KV cache bytes per token over all TP ranks, used for `cpu_tier_tokens` (layers x 2 x KV heads x head dim x dtype bytes) |
| `arms` | array | one object per arm, in display order |
| `points` | array | one object per point |

## `arms[]`

| Field | Type | Meaning |
|---|---|---|
| `id` | string | arm id, referenced by `points[].arm` (the label without a replicate suffix) |
| `name` | string | display name |
| `baseline` | bool | drawn in red and used for ratios unless the user picks another |

## `points[]`

| Field | Type | Meaning |
|---|---|---|
| `id` | string | unique in the bundle, e.g. `thunder-60m/c32` |
| `arm` | string | `arms[].id` |
| `conc` | int | client concurrency |
| `replicate` | int or null | replicate number; replicates of one arm and concurrency are shown as mean with min-max bars |
| `duration_min` | number | profiling window length |
| `kv_pool_tokens` | int | GPU KV pool of the point's vLLM pods (reference line on token charts) |
| `cpu_tier_tokens` | int or null | CPU offload tier in tokens (`--kv-offloading-size` / `kv_bytes_per_token`), null without offload. vLLM's offloading connector copies every computed block to CPU, so this is about the most KV a pod keeps, not GPU plus CPU |
| `summary` | object | flat map of columns, see below |
| `turns_by_trace` | object | completed turns per AgentX trace (`source_trace_id`) in the profiling window; the dashboard's session progress compares it with the baseline point at the same concurrency |
| `checks` | string[] | validity warnings (analyze.py `checks()`) |
| `config` | object | how the point was run, see below |
| `series` | object | time series, see below |
| `dists` | object | `{whole: {...}, steady: {...}}` quantiles, see below |
| `slo_curve` | object | `{whole: {...}, steady: {...}}`, see below |

### `summary`

The columns of analyze.py's `summary.csv` for this point (column meanings: the skill's references/metrics.md). Steady-state values have the prefix `ss_`; with the "steady state" window the dashboard uses `ss_<key>` when it exists and `<key>` otherwise. Percentile columns are `<pct>_<metric>` with pct in `mean p50 p75 p90 p95 p99` (e.g. `p90_ttft_s`; for `intvty` and `e2e_norm_intvty` p90 is the slowest 10%, the AgentX convention). `dashboard/metrics.js` lists the columns that have labels; other numeric columns appear under "Other".

### `config`

Free-form; the Configuration tab flattens it to dotted keys and compares arms. The exporter writes:

| Key | Content |
|---|---|
| `point` | the run's `meta/point.json` (label, mode, lane, model, dataset, image, URLs, start time) |
| `finish` | `meta/finish.json` (job status, pod changed) |
| `client` | aiperf `image`, full `command`, `flags` without the per-point ones (`--url`, `--concurrency`, `--server-metrics`, `--output-artifact-dir`), `env` |
| `model_server` | vLLM `image`, `command` (command + args), `resources`, `replicas`, `kv_cache` (from `vllm:cache_config_info`: KV size, blocks, offloading) |
| `router` | only with an EPP: `image`, `args`, `config_file`, `config` (the plugin YAML text), `envoy` (`image`, `ext_proc_message_timeout`, `idle_timeouts`) |

### `series`

Map from series key to `{"t": [...], "v": [...]}`: `t` in minutes since the first profiled request (bin centers), `v` the values, same length. Keys written by the exporter (labels in `metrics.js`):

| Key | Bin | Meaning |
|---|---|---|
| `client_requests`, `client_sessions` | 30 s | requests and session trees in flight at the client |
| `inflight_tokens`, `working_set_tokens` | 30 s | in-flight unique input tokens; working set incl. sessions between turns (tokens) |
| `ttft_p50_s`, `ttft_p90_s` | 60 s | TTFT percentiles of requests ending in the minute |
| `intvty_p50`, `intvty_p90` | 60 s | tok/s per user; p90 = slowest 10% |
| `completed_per_min` | 60 s | completed requests |
| `vllm_running`, `vllm_waiting` | 30 s | vLLM gauges, summed over pods |
| `kv_usage_pct` | 30 s | vLLM KV usage, mean over pods |
| `input_tps`, `output_tps` | 60 s | server prompt and generation tok/s |
| `src_gpu_hit_pct`, `src_cpu_hit_pct`, `src_computed_pct` | 60 s | prompt token source shares |
| `prefill_computed_tps` | 60 s | prompt tokens computed per second |
| `vllm_queue_time_s`, `vllm_prefill_time_s` | 60 s | mean vLLM queue and prefill time |
| `ms_per_output_token` | 60 s | engine step time |
| `gate_*_per_min`, `epp_requests_per_min`, `epp_request_errors_per_min` | 60 s | EPP counters per minute |
| `epp_queue_size` | 30 s | flow-control queue |
| `gate_working_set_tokens`, `gate_capacity_tokens` | 30 s | gate ledger summed over endpoints |
| `epp_wait_mean_s` | 60 s | mean router queue wait |

### `dists`

`dists.whole` and `dists.steady` map a key to an array of quantiles evenly spaced from 0 to 100 (201 values: p0, p0.5, ..., p100). Keys: `ttft_s` (per turn), `worst_ttft_s` (worst turn per session tree), `intvty` (tok/s per user), `isl`, `osl`.

### `slo_curve`

`slo_curve.whole` and `slo_curve.steady`: `targets_s` (TTFT targets, log spaced from 0.1 to 3600 s), `turns_pct` (share of turns with TTFT at or below each target; errors and the summary's `unserved` requests count as misses) and `goodput_pct` (share of output tokens from such turns), all the same length.

## `index.json`

`data/index.json` lists the bundles in `data/` for the dashboard served over HTTP: an array of `{file, title, created_utc, points}`. `export_bundle.py` updates it.
