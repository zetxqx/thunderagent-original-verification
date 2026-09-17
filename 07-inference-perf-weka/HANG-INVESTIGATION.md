# Incident: inference-perf does not exit after a saturated, timeout-truncated stage

Date: 2026-09-16. Affected: calibration round 2 (`results/cal-20260916-103627/`), cells `cal-c64` and `cal-c128`. Unaffected: `cal-c192`.

**Bottom line: no measurement data was lost.** The benchmark ran to completion and wrote its reports; only the process exit hung, so the `DONE` marker the driver polls for never appeared. The fix is to stop making the driver depend on process exit.

## Symptom

Two of three cells stayed `Running` for 67+ minutes after a 10-minute stage. `kubectl exec ... test -f /results/DONE` kept failing, so the driver polled forever and never collected results or tore down the cell. The third cell finished and self-collected normally.

## Evidence

Container state of a stuck cell (`weka-bench-cal-c64-s6r7n`), ~31 min after its reports were written:

```
PID 1  /bin/sh -c inference-perf ... ; touch /results/DONE ; sleep 28800
PID 7  inference-perf --config_file /etc/config/config.yml      TIME 6:49
```

PID 7 alive but with only 6m49s of CPU over ~60 minutes of wall time, i.e. blocked, not spinning. The shell had not reached `touch /results/DONE`, which is why the marker was missing.

Timeline (UTC), from the cell's own log:

| event | cal-c64 (hung) | cal-c192 (clean) |
|---|---|---|
| replay schedule built | 17:38:12 | 17:38:23 |
| stage started | 17:38:13 | 17:38:24 |
| stage timeout, workers start cancelling | 17:50:13 | 17:50:25 |
| last report file written | 17:50:41 | 17:50:50 |
| process exited | **never** (killed at ~18:45) | shortly after 17:50:50 |

So everything up to and including report generation completed normally and at the same speed in both cells. The divergence is entirely after the last file was written.

The discriminating measurement - how many of the 24 worker processes logged that they finished cancelling their in-flight tasks at stage teardown:

| cell | workers that reported cancelling | tasks cancelled | never-dispatched requests | outcome |
|---|---|---|---|---|
| cal-c64 | **21 of 24** | 1858 | 3100 | hung |
| cal-c128 | **23 of 24** | 2164 | 7559 | hung |
| cal-c192 | **24 of 24** | 2299 | 15888 | exited cleanly |

Every cell that had a worker fail to report completion of its cancellation hung; the cell where all workers reported exited. Note the hung cells are the ones with *fewer* cancelled tasks, so this is not "too much work to clean up" - it is a small number of individual workers getting stuck.

## Root cause

Where the hang is NOT, established by reading v0.7.0 and by `ps` inside the stuck container:

- **Not report generation.** All report files were written; `validation.json`, the last one, landed at 17:50:41.
- **Not waiting on worker processes.** `ps` inside the hung container showed only the shell and one Python process: **all 24 workers were already gone**. Workers are also started as daemons (`load_generator.py:217`, `super().__init__(daemon=True)`), so interpreter exit would not join them anyway.
- **Not `LoadGenerator.stop()`.** It is explicitly bounded: `worker.join(timeout=1.0)`, then `terminate()`, then `join(timeout=0.0)` (`load_generator.py:1604-1609`). Worst case ~24s for 24 workers.

So a single Python process, having finished all its work and printed its summary table, could not exit. That points at a **non-daemon thread blocking interpreter shutdown**, and the most likely one is the `multiprocessing.Queue` feeder thread.

The mechanism: the parent feeds work to workers through `RequestQueue` (`load_generator.py:1347`). `mp.Queue.put()` buffers in the parent and a background feeder thread writes into the pipe. When the stage times out, the parent terminates the workers - so nobody drains that pipe - while requests are still queued (this run: 3100 never-dispatched requests for c64, 7559 for c128). If the pipe buffer is full, the feeder thread blocks in `write()`, and at exit Python joins that thread with no timeout. The remedy for exactly this case is `Queue.cancel_join_thread()`, and **the repository contains zero occurrences of it**.

This explains the worker-count correlation too: the cells where some workers were killed mid-cancel (c64: 21/24 reported, c128: 23/24) are the ones that left an undrained pipe, while c192 (24/24 reported) shut down cleanly.

Confidence: the negative findings (not reportgen, not worker join, no children alive) are established from evidence. The feeder-thread attribution is the leading hypothesis, not proven - the pods were deleted before a stack dump. To confirm: `py-spy dump --pid <parent>` on a future occurrence, which would name the blocked thread directly; it costs nothing to try next time.

Secondary hypothesis, worth keeping in mind: the connection teardown path through the ThunderAgent router (single-process Python proxy streaming ~65k-token responses) could be what wedges the workers in the first place. Two facts are consistent with a stuck close rather than stuck work: vLLM reported `num_requests_running=0` / `num_requests_waiting=0` while the client was hung, and the client's `request_timeout: 600` should have expired anything genuinely in flight long before 31 minutes. Testing one saturated cell directly against a vLLM pod, bypassing the router, would separate the two.

## Is an upstream fix needed?

Not to proceed - the container-side mitigations below are sufficient and need no patched image. But three items are genuinely upstream-worthy and worth filing:

1. **A benchmark process should always terminate (this bug).** After terminating workers, the parent should `cancel_join_thread()` and close its request queue(s), or hard-exit once reports are saved. `main.py` ends with `perfrunner.stop()` and then relies on a clean interpreter exit; a `Queue` that nobody will ever drain makes that exit unbounded. Impact: a CI or unattended sweep hangs indefinitely after producing correct results.
2. **Session-lifecycle reports silently disappear.** `stage_0_session_lifecycle_metrics.json` and `summary_session_lifecycle_metrics.json` were absent for both hung cells and present for the clean one, with no error logged. Either emit them with whatever data exists or fail loudly; silently varying the report set breaks downstream analysis that expects a fixed schema.
3. **Client-side concurrency ceiling (upstream #648, already open).** Concrete numbers from this campaign, useful as a data point: with `num_workers: 8` and an 8-core limit, effective concurrency saturated at 17-19 in-flight requests regardless of `concurrent_sessions` being 40, 64 or 96, leaving an H100 pod idle. Raising to 24 workers / 24-32 cores moved it to 41-48. On ~65k-token weka prompts that is roughly half a core per in-flight session, which is worth documenting so users size the load generator instead of mistaking a client limit for a server result.

## Why this appeared now

Earlier runs never hit it. Step 07 and calibration round 1 were unsaturated: requests completed quickly, so few were in flight when the window closed, and teardown was trivial. This only shows up once the regime is saturated - which is exactly the regime the real experiment needs, so it must be handled, not avoided.

## Data validity

Unaffected. For `cal-c64`: 431 successful requests, `per_request_lifecycle_metrics.json`, `stage_0_lifecycle_metrics.json`, `summary_lifecycle_metrics.json`, `validation.json` all written before the hang, plus the prober's three CSVs. The calibration verdict was computed from these.

Two caveats on the hung cells specifically:

1. **`stage_0_session_lifecycle_metrics.json` and `summary_session_lifecycle_metrics.json` are missing** (both present for cal-c192). Most likely the session-level aggregation depends on all workers reporting; it is the same root cause, not separate corruption. Session-level stats are unavailable for those two cells.
2. **The tail of their time series is meaningless.** The prober exits when it sees `DONE`, so with no `DONE` it kept sampling through the silent post-stage period. That is why `cal-c64` and `cal-c128` show effective-concurrency "sustain" of 0-2% while `cal-c192` shows 64% - an artifact of measuring an idle system, not a workload difference. Any sustain figure for those two cells should be discarded; peak and mid-window values remain valid.

## Fix

Stop tying result collection to process exit. Three changes, all on our side - no upstream patch and no custom image:

1. **Bound the run in the container.** Wrap the benchmark so it cannot outlive its own work:
   `timeout -s INT <stage_timeout + 900> inference-perf --config_file ...` followed unconditionally by `touch /results/DONE`. Reports are already on disk by then, so a kill costs nothing.
2. **Mark DONE on report completeness, not exit.** `validation.json` is the last file written; treating its presence as the completion signal makes the marker independent of the exit path entirely.
3. **Make the prober stop with the stage, not with the process**, so post-stage idle time never pollutes the time series - stop sampling once `DONE` exists *or* the configured stage window has elapsed.

With these, a hung exit degrades to a few wasted minutes at the end of a cell instead of blocking the whole sweep.

## Lesson for the long sweep

A 6-cell sweep is 6 chances to hit this. Before starting: apply the three fixes above, and keep the cluster-side grace period (`sleep 28800`, 12h job deadline) which already proved its value when the overnight driver was killed - see `../LESSONS.md` section 2.
