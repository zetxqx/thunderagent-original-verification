# Bugs found in inference-perf v0.7.0

Canonical list for this campaign. Found while replaying the weka agentic trace corpus (391 real Claude Code sessions, ~65k-token prompts) against a saturated vLLM 0.28 pod, 2026-09-16/17. Every issue below was hit in normal use, not by fuzzing.

**Version**: official image `quay.io/inference-perf/inference-perf:v0.7.0`, digest `sha256:d247e6ad725dc5bb56df71d115abc8ca455bba9f0ccd4110e14bbb56504250ec`. Source references are to the `v0.7.0` tag of `kubernetes-sigs/inference-perf`.

**Environment**: GKE, Qwen3-Coder-30B-A3B-Instruct-FP8 on H100 TP2, `load.type: trace_session_replay`, `data.type: weka_trace_replay`, `api.type: chat` with streaming. Raw evidence in `07-inference-perf-weka/` and `08-weka-replicates/`.

Status: none filed yet. Each section is written to be pasted into an issue as-is.

| # | Issue | Severity | Impact on us |
|---|---|---|---|
| 1 | Process never exits after a timeout-truncated stage | High | Blocked an unattended sweep; 2 of 3 cells hung for 30+ min after finishing |
| 2 | No session identifier in the per-request report | High (analysis) | Invalidated and forced retraction of our primary paired analysis |
| 3 | Session-lifecycle reports silently missing | Medium | Report schema varies run to run with no error |
| 4 | `concurrent_sessions` silently not achieved | Medium | Two sweeps measured a load level that was never actually applied; root cause found: parked events hold worker permits, fixed in `d5a7c8c` |
| 5 | `per_request_fields` cannot exclude per-token arrays | Medium | 50-123 MB per per-request report; 25 reports = 1.6 GB, over GitHub's 100 MB file limit |

---

## Issue 1: benchmark process never exits after a timeout-truncated stage

**Severity**: high for unattended or CI use - the run produces completely correct results, writes every report, and then blocks forever.

### Symptom

A `trace_session_replay` stage with `timeout` set ends while thousands of requests are still in flight. All reports are written, the summary table prints, and the process never exits. Observed alive 31+ minutes after the last report file, blocked rather than spinning (6m49s CPU over ~60 min wall).

Anything keyed off process exit hangs with it: `cmd && touch DONE`, a CI step, a Kubernetes Job completion.

### Reproduction

One stage, `concurrent_sessions: 64`, `timeout: 600`, `num_workers: 24`, `request_timeout: 600`, over 338 local weka traces against a single saturated backend. Two of three otherwise identical cells (c=64, c=128) hung; the third (c=192) exited normally, so it is a race.

### Evidence

```
17:50:13  [Worker 19] cancelling 96 tasks still running at stage teardown
17:50:14  Stage 0: dropped 3100 request(s) that were never dispatched to the model server
17:50:40  Report saved to: /results/report/summary_lifecycle_metrics.json
17:50:41  Report saved to: /results/report/validation.json     <- last output, ever
          (process still alive at 18:22, killed at ~18:45)
```

Inside the hung container - note **no worker processes remain**, only the parent:

```
PID 1  /bin/sh -c inference-perf ... ; touch /results/DONE ; sleep 28800
PID 7  inference-perf --config_file /etc/config/config.yml      TIME 6:49
```

The cells that hung are exactly the ones where some workers never logged completion of their teardown:

| cell | workers reporting "cancelling N tasks" | tasks cancelled | exited? |
|---|---|---|---|
| c=64 | 21 of 24 | 1858 | no |
| c=128 | 23 of 24 | 2164 | no |
| c=192 | 24 of 24 | 2299 | yes |

### Analysis

Ruled out by evidence: report generation (all files written), waiting on children (none alive, and workers are `daemon=True`, `load_generator.py:217`), and `LoadGenerator.stop()` (explicitly bounded: `join(timeout=1.0)` -> `terminate()` -> `join(timeout=0.0)`, `load_generator.py:1604-1609`).

That leaves a non-daemon thread blocking interpreter shutdown. The most likely candidate is the `multiprocessing.Queue` feeder thread of `RequestQueue` (`load_generator.py:1347`): the parent is the producer, workers are terminated at stage teardown while requests are still queued, nothing drains the pipe, and once the pipe buffer is full the feeder thread blocks in `write()`. Interpreter exit then joins that thread with no timeout.

Supporting detail: `cancel_join_thread` - the standard remedy for exactly this situation - appears **zero times** in the repository at v0.7.0.

Not confirmed with a stack dump (pods were deleted before one could be taken); `py-spy dump` on the parent during a recurrence would settle it.

### Suggested fix

After terminating workers in the shutdown path:

```python
request_queue.cancel_join_thread()   # a full pipe must not block interpreter exit
request_queue.close()
```

and/or exit explicitly once reports are saved (`os._exit(0)` after `perfrunner.stop()` in `main.py`), so a stuck background thread can never turn a successful run into a hang.

### Workaround we used

```sh
timeout -s INT $((STAGE_TIMEOUT + 900)) inference-perf --config_file /etc/config/config.yml &
# validation.json is the last report written; once it exists, stop waiting for an exit
# that may never come, then mark completion unconditionally.
```

---

## Issue 2: the per-request report carries no session identifier

**Fix (2026-09-20, local, not yet upstream)**: `RequestLifecycleMetric.session_id` is already populated by the load generator for session-based runs; `build_per_request_lifecycle_entry` in `inference_perf/reportgen/base.py` simply never wrote it. Two lines add `entry["session_id"]` when set, plus two unit tests. Built as image `inference-perf:session-id-v1` (digest `sha256:f7381b01...`, on top of the permit fix `d5a7c8c`, change uncommitted at build time); used by every cell from the step 13 replicates on. Cells before that have only `info.graph_event_id`.

**Severity**: high for anyone analysing session-based replay. This one silently invalidated a whole analysis for us.

### Symptom

`per_request_lifecycle_metrics.json` has no field identifying which session a request belongs to. `info.labels` and `info.extra_info` are both empty dicts. The only session-ish field is `info.graph_event_id`, and **it is not unique**: it names a position inside a session's event graph, so the same id recurs once per session.

Measured in one cell: 1929 requests, **341 distinct `graph_event_id` values**, with `event_000_parent_turn_0` appearing **87 times** - once per replayed session.

### Why it matters

A/B comparison of two truncated runs requires pairing requests across arms; without a session id there is no key to pair on. We used (`graph_event_id`, `prompt_tokens` within 1%) as a substitute and it failed: **57% of matches had more than one candidate** (up to 40), so the pairing silently matched "turn 3 of some session" with "turn 3 of a different session". Every paired statistic we computed had to be retracted.

It also blocks basic per-session analysis: "how many turns did each session complete", "which sessions were slowest", "did both arms work on the same sessions". We could only recover these by scraping the router's own `/programs` endpoint on a 2-second timer, which is not something a benchmark user should have to build.

### Suggested fix

Emit the wire session id (the value sent via `api.session_id_header_key`) on each per-request entry, e.g. `info.session_id`. The loadgen already knows it - it stamps it on the request. Alternatively make `graph_event_id` globally unique by prefixing the session id.

---

## Issue 3: session-lifecycle reports silently disappear on truncated runs

**Severity**: medium - breaks any consumer that expects a fixed report set, with nothing in the log to explain it.

Three cells, identical config apart from `concurrent_sessions`:

| cell | report files produced |
|---|---|
| c=192 (clean exit) | config.yaml, inference-perf.partial.stage_0.yaml, per_request_lifecycle_metrics.json, stage_0_lifecycle_metrics.json, **stage_0_session_lifecycle_metrics.json**, summary_lifecycle_metrics.json, **summary_session_lifecycle_metrics.json**, validation.json |
| c=64, c=128 (hung, see issue 1) | the same set **minus both session files** |

No warning or error was logged. `validation.json` reported `0 error(s), 2 warning(s)`, both about unrelated token mismatches. A consumer opening `stage_0_session_lifecycle_metrics.json` just gets `FileNotFoundError` with no explanation anywhere.

Likely the same root cause as issue 1 (session aggregation appears to need every worker to have reported), so fixing that may fix this. Listed separately because the *silence* is its own defect: if the reports legitimately cannot be produced, that should be logged as an error, not omitted quietly.

---

## Issue 4: `concurrent_sessions` is silently not achieved

**Severity**: medium as a bug, high as a documentation gap - it is very easy to mistake a client-side limit for a server-side result, and we did exactly that for two full sweeps.

### Symptom

The configured session concurrency is never reached, and nothing reports this. With `concurrent_sessions: 128`, `num_workers: 24`, `worker_max_concurrency: 100`:

| | sessions dispatched (from the loadgen's own log) | sessions that ever sent a request | requests in flight, steady state |
|---|---|---|---|
| cell A | 143 | **68** | ~48-58 |
| cell B | 183 | **109** | ~48-58 |

The loadgen logs "Dispatching session" for all 128 at t=0 (confirmed: 128 dispatch lines within the same second), yet **only 46 of them had sent a first request after 5 minutes**; the rest trickled in across the whole 45-minute run. Sessions that never sent anything cannot have been waiting on the server.

Earlier, with `num_workers: 8` and an 8-core limit, in-flight requests pinned at **17** whether we configured 40, 64 or 96 sessions - three "different" load levels that were the same experiment. Raising to 24 workers / 24-32 cores moved the ceiling to ~48, which again did not move with offered concurrency.

### On the cause

This looks related to the open #648 (client-side per-event work), but our CPU measurements do **not** support a simple "the client is CPU-saturated" explanation:

| component | median CPU | peak |
|---|---|---|
| bench pod (24 CPU requested, 32 limit) | **1.27 cores** | 8.0 cores |
| router being benchmarked | 0.06-0.11 cores | 0.23 cores |
| vLLM pod | 2.3-2.8 cores | 3.1 cores |

1.27 cores used out of 24 available, with 24 worker processes, while the achieved concurrency is a third of what was configured. That points at a serialized path (single-threaded dispatch or prompt construction in the parent) rather than a resource limit, but we did not profile it - a `py-spy` sample of the parent during a run would identify it quickly.

### Suggested fix

Two parts, and the second is worth doing even if the first is hard:

1. Find and parallelise (or document) whatever serializes session admission to the wire.
2. **Report the discrepancy.** Track sustained in-flight concurrency and warn when it stays far below `concurrent_sessions` - something like `configured 128, achieved 48 (38%); the load generator, not the server, is the limit`. Without this, a user reading only the report concludes the *server* saturated at 48 concurrent requests. Our first two sweeps drew exactly that wrong conclusion and cost about four hours of cluster time.

Worth documenting alongside it: `num_workers` defaults to `cpu_count()`, which inside a container reports the **node's** core count rather than the cgroup limit. On our 103-core nodes with a `limits.cpu: 8` container, the default would spawn 103 worker processes.

---

### Root cause, found 2026-09-18 (after steps 09 and 10)

The ceiling is not CPU. In v0.7.0 a worker acquires a `worker_max_concurrency` permit before it pulls each event from its queue, and an event that then parks waiting for its predecessors keeps that permit. A session's events are all enqueued at dispatch and sessions are pinned to a worker by hash, so the first one or two sessions on a worker fill its 100 permits with parked turns, and the worker never reads the first turn of the other sessions pinned to it. Evidence in every cell of steps 07 to 10: each worker reports "cancelling 98 to 100 tasks still running at stage teardown" (exactly the permit count), and only 51 to 109 of the 128 to 183 dispatched sessions ever issued their first event. Effective concurrency was therefore about 55 to 65 concurrently active sessions in the 1900 s runs and 65 to 100 in the 600 s runs, for both routers alike, not 128. The fix (release the permit while parked, re-acquire before dispatch) is commit `d5a7c8c` on `zetxqx/inference-perf`, branch `fix-session-replay-permits`, with a regression test; it is not in v0.7.0 (released 2026-09-15). Comparisons within a run stay valid because every arm ran under the same limitation, but the absolute load must be restated and any future run needs an image built from the fix.

## Issue 5: `per_request_fields` cannot exclude the per-token arrays, so per-request reports stay huge

**Severity**: medium - the field filter exists precisely to keep this report small, but the coarse switches leave 98% of the bytes in place.

### Symptom

We set the documented filter to drop raw text:

```yaml
report:
  request_lifecycle:
    per_request: true
    per_request_fields:
      request: false
      response: false
      response_chunks: false
      info: true
      computed_metrics: true
```

The filter works as documented (`request`, `response` and `response_chunks` are absent), yet `per_request_lifecycle_metrics.json` is still 50-123 MB per 45-minute cell. Measured on one file (2023 requests, 1.28M output tokens, 110.5 MB on disk, 73.2 MB as compact JSON):

| field | share of bytes | content |
|---|---|---|
| `computed_metrics.inter_token_latencies` | 33% | one float per output token |
| `info.response_metrics.chunk_times` | 26% | one timestamp per streamed chunk |
| `info.response_metrics.output_token_times` | 26% | one timestamp per output token (near-duplicate of the above) |
| `info.output_text` + `info.output_message.content` | 13% | generated text, stored twice |
| everything else (scalar latencies, `server_usage`, `prompt_tokens_details`, ids) | < 2% | the part an analysis actually reads |

Three floats per output token at ~20 bytes each: 3.7M floats, ~70 MB. The same file with the three arrays and the duplicated text removed is 1.5 MB. Report size therefore scales with total output tokens, which makes it a function of how *fast* the system under test is - our faster arm produced files twice the size of the baseline arm from the same wall-clock window.

### Why it matters

- 25 cells across two sweeps produced 1.6 GB of per-request reports. Ten files exceed GitHub's 100 MB hard limit, so raw evidence cannot be published alongside the analysis without post-processing.
- Loading one file with `json.load` peaks at several hundred MB of RAM; a sweep-wide pandas analysis becomes memory-bound for no analytic gain.
- The mean ITL is already emitted as `computed_metrics.inter_token_latency`, and the summary/per-stage reports already carry ITL percentiles, so most consumers gain nothing from the raw deltas.

### Cause

`build_per_request_lifecycle_entry` in `inference_perf/reportgen/base.py` has five switches. `info: true` dumps the whole `RequestInfo` model (`model_dump()`), which includes `response_metrics.chunk_times`, `response_metrics.output_token_times` and both copies of the output text; the only key it pops is `response_chunks`. `computed_metrics: true` always emits `inter_token_latencies`. There is no configuration that keeps the scalar metrics without the arrays.

### Suggested fix

Add finer switches under `per_request_fields`, all defaulting to today's behaviour so existing consumers see no change:

```yaml
per_request_fields:
  token_times: true            # chunk_times + output_token_times
  inter_token_latencies: true  # the per-token delta list
  output_text: true            # output_text + output_message
```

Alternatively a single `per_request_detail: full | scalars` switch. Either way, a `scalars` profile should keep `start_time`, `end_time`, `error`, `info.request_metrics`, `info.response_metrics.output_tokens`, `info.response_metrics.server_usage`, `info.graph_event_id`, `info.labels`, `info.extra_info` and every scalar under `computed_metrics`. With that profile the file above would be ~1.5 MB.

Related: issue 2 asks for a session id in this same report; a scalar-only profile is where most users would want it.

---

## Not inference-perf bugs, recorded to avoid confusion

- **The extra "errors" in our reports** were our own `request_timeout: 600` firing on requests that the system under test intentionally held (its own backstop is 1800s). inference-perf reported them correctly.
- **Non-reproducible cache hit rates between identical runs** are inherent to closed-loop replay against a stateful, concurrent server, not a harness defect. A seed fixes what the generator sends, not how the server interleaves it; measured request volume was reproducible to 1% while hit rate varied 2.6x on short windows. An optional open-loop (fixed arrival schedule) replay mode would remove one variance source - and is technically feasible here because weka replay substitutes pre-reconstructed text rather than live responses - but it would not deliver determinism and would make overload behaviour unrealistic. Replication with reported error bars is the right answer.
- **One HTTP 500** came from a race inside ThunderAgent (the system under test), not from the harness; see `07-inference-perf-weka/UPSTREAM-ISSUES.md`.
