# Plan: weka trace replay (inference-perf) through the original ThunderAgent router

Status: SCAFFOLDING COMPLETE, NOT EXECUTED. Awaiting go-ahead.

## Locked decisions (review round 1)

1. Two arms: `default` (pure proxy) vs `tr-decay` (tr + acting-token decay, NO release anywhere).
2. Concurrency sweep: 8 / 16 / 24 concurrent sessions -> 6 cells (2 arms x 3).
3. 45 min per cell (stage `timeout: 2700`), whole filtered corpus as work list, truncated.
4. Main-agent trace slice (first 60MB of the weka dataset, 39 complete traces).
5. One trial.
6. (Review round 2) OFFICIAL upstream inference-perf image - no custom/fork builds.
7. (Review round 3) PARALLEL lanes: each cell uses only one vLLM pod, and the cluster has 4 (3 on distinct nodes). Layout: one lane per concurrency; within a lane, `default-cN` then `tr-decay-cN` run SEQUENTIALLY on the SAME dedicated pod (preserves within-pair fairness: same hardware, cache reset between cells); the three lanes (c8/c16/c24 on 3 pods on 3 distinct nodes) run in parallel. Cross-lane comparisons are between-pod - acceptable because the primary judgment is within-pair.

Estimated wall time: smoke ~15 min + **~2 h** for the sweep (2 x 45 min per lane + per-cell overhead, 3 lanes in parallel).

## Versions - everything pinned (traceability)

| component | version | how pinned |
|---|---|---|
| inference-perf | **official** `quay.io/inference-perf/inference-perf:v0.7.0` (released 2026-09-15) | digest `sha256:d247e6ad725d...` hardcoded in `job-weka.yaml` |
| ThunderAgent router | upstream commit `7ddc861`, unmodified source | image `thunderagent-original:7ddc861`; runtime imageID recorded per cell |
| vLLM | `vllm/vllm-openai:v0.28.0` (existing pod, untouched) | runtime imageID recorded in global manifest |
| trace data | `semianalysisai/cc-traces-weka-with-subagents-060826-256k`, first 60MB range slice | URL + byte range + **sha256 of the downloaded slice** written to `trace-manifest.json` at run time, plus per-trace keep/drop list |
| replay seed | `base_seed: 20260915` | pinned in config template |
| configs | one template, rendered per cell | rendered copy saved in each cell dir + sha256 in cell `manifest.json` |

v0.7.0 feature check (each verified against the tag in git): weka_trace_replay with local `trace_directory` ✓, `session_id_header_key` ✓, `per_request_fields` (report-bloat fix #562) ✓, timed-out stages still produce reports (#662) ✓, datagen 10x (#623) ✓, stage `timeout` / `base_seed` / `use_server_output_tokens` / `storage.local_storage` ✓.

Fork features NOT available in the official image, and the mitigations:

| fork feature | needed? | mitigation |
|---|---|---|
| `session_close_path` / `session_final_header_key` | no | we intentionally never release (realistic clients) |
| `subagent_separate_session_id` | no | subagent requests inherit the parent's `x-session-id` -> counted as the parent program. This matches the paper's program abstraction (a program includes its subagents) and the main-agent slice has few subagents anyway. Documented modeling choice. |
| `context_window_clamp` | replaced | initContainer pre-filters traces to max input <= 245k tokens (server re-tokenization drifts ~2-3% over recorded counts; 262144 window) |

## Program identity mapping

Config sets `api.session_id_header_key: x-session-id`; the loadgen stamps one stable session id per replayed trace session. The original ThunderAgent reads that header as `program_id` (app.py `get_program_id`, resolution order 3). Zero code changes on either side. Smoke test asserts the mapping by checking `/programs` shows one program per active session.

## The time series you asked for (collected every 2s by a prober sidecar)

The prober runs as a second container in the bench Job (`prober.py`, stdlib-only), so it observes from inside the cluster with no port-forward distortion, and appends-with-flush so partial data survives any crash. Three CSVs per cell:

1. **`vllm-metrics.csv`** - scraped DIRECTLY from the lane's vLLM pod `/metrics` (not router-mediated): `kv_cache_usage_perc`, `num_requests_running`, `num_requests_waiting`, `num_preemptions_total`, cumulative prefix-cache queries/hits plus the **prefix-cache hit-rate time series** (2s interval rate from counter deltas; also a dedicated panel in the comparison figure).
2. **`router-health.csv`** - ThunderAgent `/health`: programs / reasoning / acting / **paused** counts (aggregate pause signal).
3. **`programs-timeline.csv`** - ThunderAgent `/programs` per program per sample: `status` (reasoning/acting), `state` (active/**paused** - the pause flag lives in `state`), backend. This yields each program's exact pause intervals.

Plus two pause-evidence backups per cell: the router log (`router.log`, saved per cell BEFORE teardown - per-program `Paused program <id> (tokens=N)` / resume / forced-resume events) and per-request `server_usage` in the inference-perf report.

## Workload configuration (rendered from `config-tmpl.yaml`)

- Corpus: 60MB slice filtered by initContainer to turns <= 400 and max input <= 245k; expected ~30-37 traces kept (exact keep/drop list in `trace-manifest.json`).
- Same corpus and same `base_seed` in every cell; only `concurrent_sessions` differs. 45-min truncation.
- Think-time realism: `trace_idle_gap_cap_seconds: 10` + `max_wait_ms: 10000` (the two caps interact; kept consistent). Real gaps up to 10s stress the 1s decay half-life - if decay-based admission is leaky on real think times, that is a finding, not a bug.
- Report: per-request lifecycle stores METRICS ONLY, no request/response text: `per_request_fields: {request: false, response: false, response_chunks: false, info: true, computed_metrics: true}` (mandatory; with raw text the report is ~1MB/request, ~3GB/run). Kept per request: timestamps, token counts, `server_usage` (incl. `cached_tokens`), TTFT. Plus `use_server_output_tokens: true` (also bypasses the client-side tokenization bottleneck, upstream #648).
- Bench resources: 4 CPU / 12Gi request, 8 CPU / 24Gi limit - sized so THREE bench jobs schedule concurrently (the 16Gi datagen guidance was for 500-entry corpora; ours is ~35 traces).

## Analysis (`pair.py`, written and ready)

METHODOLOGY RULE (from the close-session campaign): aggregates over timeout-truncated arms are unreliable - arms progress at different speeds and capture different request populations. Per concurrency, pair requests across arms on (`graph_event_id`, `prompt_tokens` within 1%) and judge PAIRED deltas:

- Primary: paired per-request cache-hit ratio delta (`server_usage.prompt_tokens_details.cached_tokens / prompt_tokens` - vLLM's own numbers).
- Paired TTFT delta (`computed_metrics.time_to_first_token`).
- Window progress: successful requests and output tokens per arm within the 45-min window (throughput proxy under truncation), reported separately from paired stats.

Decision rule fixed BEFORE running, per concurrency: tr-decay wins if paired median hit-ratio delta > +5 points AND window output tokens >= default's AND paired TTFT median not worse than +10%. Anything else reported as-is, including a tr loss.

Output: `analysis.md` + `comparison-weka.png`, six panels: (a) paired hit-ratio delta ECDFs per concurrency, (b) **prefix-cache hit-rate time series** (dashed=default, solid=tr), (c) KV utilization ts, (d) router paused-count ts, (e) engine queue-depth ts, (f) window output tokens per arm per concurrency.

## Execution order

1. **Smoke** (`./run-weka-ab.sh smoke`, ~15 min): 1 cell, tr-decay, c=3, 3 traces, 5-min stage. Gates: (a) `/programs` shows per-session programs (header mapping works), (b) report entries contain `server_usage` (streaming usage passes through the proxy), (c) prober CSVs non-empty, (d) router CPU < 80% (single-process Python proxy is the known bottleneck risk; bump CPU if hot), (e) no 400s.
2. **Full sweep** (`./run-weka-ab.sh`): 3 parallel lanes (c8/c16/c24), each on its own pod+router (`thunderagent-ab-cN`); within a lane default then tr-decay, prefix-cache reset + router redeploy between cells. Driver aborts if fewer than 3 decode pods on distinct nodes are Running.
3. `pair.py` -> analysis.md + figure -> results.md write-up.

Abort/retry rules: if the spot vLLM pod is replaced mid-cell, rerun that cell (manifest records the pod name per run). If smoke gate (d) fails, raise router CPU limit and re-smoke before the sweep.

## Files in this folder

- `PLAN.md` (this file)
- `config-tmpl.yaml` - inference-perf config template (all fields verified against v0.7.0)
- `filter_traces.py` - initContainer: slice download + filter + split + trace manifest
- `prober.py` - 2s time-series sidecar (the three CSVs above)
- `router-weka.yaml` - per-lane router template (name/mode/backend parameterized)
- `job-weka.yaml` - per-cell Job: fetch-traces init + bench (official image, digest-pinned) + prober
- `run-weka-ab.sh` - driver: smoke / 3-parallel-lane sweep, per-cell manifests, router log capture
- `pair.py` - paired analysis + figure
- `results/<ab-id>/` - created at run time: `manifest-global.json`, per cell `{config.yml, manifest.json, router.log, prober.log, results/{report/, vllm-metrics.csv, router-health.csv, programs-timeline.csv, trace-manifest.json, bench-stdout.log}}`
