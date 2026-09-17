# Upstream issues for kubernetes-sigs/inference-perf

Found while replaying the weka agentic trace corpus against a saturated vLLM pod, 2026-09-16. Version: **v0.7.0**, official image `quay.io/inference-perf/inference-perf@sha256:d247e6ad725dc5bb56df71d115abc8ca455bba9f0ccd4110e14bbb56504250ec`. Full evidence: `HANG-INVESTIGATION.md`.

> **Superseded for inference-perf**: the canonical, updated list is `../INFERENCE-PERF-BUGS.md`,
> which adds the missing-session-identifier issue and corrects the cause analysis in issue 3.
> This file is kept for the ThunderAgent issue at the end and for the original evidence.

Status: not yet filed. Each section below is written so it can be pasted into an issue as-is.

---

## Issue 1: benchmark process never exits after a timeout-truncated stage (hangs indefinitely after reports are written)

**Severity**: high for unattended/CI use - the run produces correct results and then blocks forever.

### What happens

A `trace_session_replay` stage with `timeout` set ends while thousands of requests are still in flight. All reports are written correctly and the summary table is printed, then the process never exits. Observed 31+ minutes after the last report file, with the process blocked (6m49s CPU over ~60 min wall).

Because the process does not exit, any wrapper that keys off exit (`cmd && touch DONE`, a CI step, a Job completion) hangs too.

### Reproduction

- v0.7.0, official image, single vLLM 0.28 backend (Qwen3-Coder-30B-A3B-FP8, TP2, H100)
- `load.type: trace_session_replay`, one stage with `concurrent_sessions: 64`, `timeout: 600`, `num_workers: 24`, `request_timeout: 600`
- `data.type: weka_trace_replay` over 338 local traces (~65k-token prompts), so the pod is saturated and many requests are in flight when the timeout fires
- 2 of 3 otherwise identical cells (c=64, c=128) hung; the third (c=192) exited normally, so it is a race

### Evidence

Log tail of a hung run (all timestamps UTC):

```
17:50:13  [Worker 19] cancelling 96 tasks still running at stage teardown
17:50:14  Stage 0: dropped 3100 request(s) that were never dispatched to the model server
17:50:40  Report saved to: /results/report/summary_lifecycle_metrics.json
17:50:41  Report saved to: /results/report/validation.json     <- last output, ever
          (process still alive at 18:22, killed at ~18:45)
```

Inside the container while hung - note there are **no worker processes left**, only the parent:

```
PID 1  /bin/sh -c inference-perf ... ; touch /results/DONE ; sleep 28800
PID 7  inference-perf --config_file /etc/config/config.yml      TIME 6:49
```

Correlation across the three cells - the two that hung are the ones where some workers did not finish their teardown:

| cell | workers reporting "cancelling N tasks" | tasks cancelled | never-dispatched | exited? |
|---|---|---|---|---|
| c=64 | 21 of 24 | 1858 | 3100 | no |
| c=128 | 23 of 24 | 2164 | 7559 | no |
| c=192 | 24 of 24 | 2299 | 15888 | yes |

### Analysis

Ruled out by evidence: report generation (all files written), waiting on children (none alive; workers are `daemon=True`, `load_generator.py:217`), and `LoadGenerator.stop()` (bounded: `join(timeout=1.0)` -> `terminate()` -> `join(timeout=0.0)`, `load_generator.py:1604-1609`).

That leaves a non-daemon thread blocking interpreter shutdown. Most likely the `multiprocessing.Queue` feeder thread of `RequestQueue` (`load_generator.py:1347`): the parent is the producer, workers are terminated at stage teardown while requests are still queued, so nothing drains the pipe; once the pipe buffer is full the feeder thread blocks in `write()`, and interpreter exit joins that thread without a timeout.

Supporting detail: `cancel_join_thread` - the standard remedy for exactly this situation - does not appear anywhere in the repository (0 occurrences at v0.7.0).

Not independently confirmed with a stack dump (the pods were deleted before one could be taken). A `py-spy dump` on the parent during a future occurrence would settle it.

### Suggested fix

In the shutdown path, after terminating workers:

```python
request_queue.cancel_join_thread()   # do not let a full pipe block interpreter exit
request_queue.close()
```

and/or make `main.py` exit explicitly once reports are saved (e.g. `os._exit(0)` after `perfrunner.stop()`), so a stuck background thread can never turn a successful run into a hang.

### Workaround used here

Bound the process externally and decouple completion from exit:

```sh
timeout -s INT $((STAGE_TIMEOUT + 900)) inference-perf --config_file /etc/config/config.yml
touch /results/DONE      # unconditional: reports are already on disk
```

---

## Issue 2: session-lifecycle reports silently missing on truncated runs

**Severity**: medium - breaks downstream analysis that expects a fixed report set, with no error to notice.

Same three cells as above, same config apart from `concurrent_sessions`:

| cell | report files produced |
|---|---|
| c=192 (clean exit) | config.yaml, inference-perf.partial.stage_0.yaml, per_request_lifecycle_metrics.json, stage_0_lifecycle_metrics.json, **stage_0_session_lifecycle_metrics.json**, summary_lifecycle_metrics.json, **summary_session_lifecycle_metrics.json**, validation.json |
| c=64, c=128 (hung) | same **minus both session files** |

No warning or error was logged about the missing reports; `validation.json` reported `0 error(s), 2 warning(s)` (both about token mismatches, unrelated). A consumer that opens `stage_0_session_lifecycle_metrics.json` just gets a `FileNotFoundError` with nothing in the log explaining why.

Expected: either emit the session reports with whatever data was collected (a truncated run still has session-level facts worth reporting), or log an explicit error stating they were skipped and why.

Probably the same root cause as Issue 1 - session aggregation appears to need all workers to have reported - so fixing Issue 1 may fix this. It is listed separately because the *silence* is a distinct problem: even if generation legitimately cannot proceed, that should be visible.

---

## Issue 3: load generator is the concurrency bottleneck on large prompts (data point for #648)

**Severity**: low as a bug, high as a documentation gap - it is easy to mistake a client-side limit for a server-side result.

Upstream #648 (client CPU-bound, request construction per event) is already known and open. Concrete measurements from this campaign, on ~65k-token weka prompts (median prompt 65-69k tokens, p90 ~140k):

| `num_workers` | container CPU (request/limit) | `concurrent_sessions` configured | effective in-flight requests observed | server state |
|---|---|---|---|---|
| 8 | 4 / 8 | 40 | 16 peak | KV 0.69, idle |
| 8 | 4 / 8 | 64 | 18 peak | KV 0.73, idle |
| 8 | 4 / 8 | 96 | 17 peak | KV 0.72, idle |
| 24 | 24 / 32 | 64 | 41 peak | KV 1.00, saturated |
| 24 | 24 / 32 | 128 | 45 peak | KV 1.00, saturated |
| 24 | 24 / 32 | 192 | 48 peak | KV 1.00, saturated |

Two things worth upstream attention:

1. **`concurrent_sessions` is silently not achieved.** With 8 workers, configuring 40, 64 or 96 all produced the same ~17 in-flight requests. Nothing in the output says the configured concurrency was never reached; a user reading only the report would conclude the *server* saturated at 17 concurrent requests. A warning when sustained in-flight concurrency stays far below `concurrent_sessions` would prevent this class of mistake.
2. **Rule of thumb worth documenting**: on ~65k-token prompts this needed roughly half a CPU core per in-flight session, and `num_workers` must be raised alongside cores (it defaults to `cpu_count()`, which inside a container reports the *node's* core count, not the cgroup limit - so the default can oversubscribe badly).

The `cpu_count()` default is arguably its own small bug: in a container with `limits.cpu: 8` on a 103-core node, the default spawns 103 worker processes.

---

# Upstream issue for ThunderAgent-org/ThunderAgent (commit 7ddc861)

## Race between the pause scheduler and the request path yields HTTP 500

**Frequency**: 1 occurrence in 9350 requests (measured across 6 cells in `08-weka-replicates`), so low impact but a genuine synchronisation gap.

The background scheduler pauses a program and clears its `backend_url` while a request for that same program is already partway through `update_program_before_request`. The request then reaches the "resolve backend" step, finds `None`, and the connection is dropped:

```
INFO  Paused program wekatrace132_... from http://10.100.3.12:8000
INFO  Scheduler paused ACTING program wekatrace132_...
ERROR Program wekatrace132_... has no valid backend
      httpcore.RemoteProtocolError: Server disconnected without sending a response
      -> HTTP 500 Internal Server Error
```

The error is raised at the `logger.error("Program %s has no valid backend")` branch in `scheduler/router.py` (step 3 of `update_program_before_request`). Suggested fix: hold the program lock across the pause, or have the request path re-resolve/await admission instead of failing when it finds no backend.

Reproduction: saturate a single backend (KV over-subscribed ~2x) with `--router tr --use-acting-token-decay` and drive ~50 concurrent multi-turn sessions for 45 minutes; the scheduler then pauses programs frequently enough to hit the window.
