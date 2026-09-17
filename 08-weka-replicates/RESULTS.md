# Replicated weka A/B: how stable is the ThunderAgent result?

`results/rep-20260917-031427-c128` - same configuration run three times (c=128, 45 min per cell, one replicate per lane on its own vLLM pod, default then tr-decay sequentially on the same pod with a cache reset between). All 6 cells completed, no preemptions.

This step exists because step 07 produced single runs, and two nominally identical 10-minute calibration cells had disagreed by 2.6x on hit rate.

## Headline: the result is highly reproducible

Mean over 3 replicates, with the min-max range:

| metric | default | tr-decay | ratio |
|---|---|---|---|
| throughput (output tok/s) | 221 (210-242) | **469 (464-476)** | **2.12x** |
| requests completed | 1059 (1033-1108) | 1994 (1978-2011) | 1.88x |
| hit rate, **steady state** (after 10 min) | 0.008 (0.007-0.009) | **0.685 (0.661-0.698)** | **85x** |
| hit rate, whole window | 0.057 (0.037-0.077) | 0.615 (0.603-0.622) | 10.8x |
| hit rate, first 10 min (warm-up) | 0.197 (0.124-0.258) | 0.188 (0.117-0.310) | **0.96x (no difference)** |
| TTFT p50 (s) | 52.7 (45.9-58.0) | **3.0 (2.9-3.2)** | 17x faster |
| TTFT p90 (s) | 92.5 (70.2-104.5) | 18.0 (17.4-19.1) | 5x faster |
| requests getting zero cache hit | 88% | 36% | - |
| client timeouts | 17 (15-20) | 47 (45-50) | 2.7x - but see the error section: these are 600s client-patience cutoffs, not failures |

**tr-decay's throughput spread is +-1.3%** (464-476) across three independent replicates on three different pods. The default arm is looser (+-7%) but still tight. So the earlier worry that single runs are untrustworthy was wrong *for 45-minute windows* - see the next section for where the instability actually lives.

Cross-check against step 07, which ran the same c=128 configuration on a different day: tr 468 tok/s (here 464-476), default 218 tok/s (here 210-242). Independent reproduction.

## Where the variance lives: the warm-up, not the steady state

| phase | default | tr-decay |
|---|---|---|
| first 10 min (cold pool filling) | 0.197 (0.124-0.258) | 0.188 (0.117-0.310) |
| after 10 min | 0.008 (0.007-0.009) | 0.685 (0.661-0.698) |

Two things fall out of this split:

1. **During warm-up the two arms are indistinguishable** (0.197 vs 0.188). Admission control does nothing until the pool is full, which is exactly right - there is nothing to protect while there is spare capacity. Every bit of ThunderAgent's benefit is earned after the capacity cliff.
2. **All the run-to-run noise is in the warm-up** (ranges of 0.124-0.258 and 0.117-0.310, i.e. +-30%), while steady state varies by a few percent. That explains the earlier 0.249-vs-0.097 disagreement: those were 10-minute cells, so they measured mostly warm-up, i.e. mostly noise. Short windows do not shrink the experiment, they replace it with its transient.

Reporting the whole-window number alone understates the effect by more than an order of magnitude: 0.057 vs 0.008 for the default arm.

## The honest per-session number: 1.3x, not 2.1x

`step_count` is now recorded per program, so the arms can be compared on **only the sessions both of them started** - removing the confound that the faster arm pulls more traces out of the corpus (tr touched 109 sessions, default 68).

| replicate | shared sessions | turns: default | turns: tr-decay | ratio |
|---|---|---|---|---|
| r1 | 54 | 853 | 1068 | 1.25x |
| r2 | 54 | 927 | 1041 | 1.12x |
| r3 | 46 | 777 | 1196 | 1.54x |

So for a given session, ThunderAgent advances it about **1.3x faster** (1.12-1.54x). The 2.12x system-level throughput is real but is a different quantity: it counts all work, and part of tr's advantage is that it gets to *more sessions* rather than pushing shared ones proportionally further.

Both numbers are true and should be quoted together. "2x the throughput" is the cluster operator's view; "1.3x faster progress" is an individual agent's view.

## The ~50-request ceiling is the load generator, not the router

Measured this time instead of guessed (`cpu-usage.csv`, `kubectl top` every 30s):

| component | median CPU | peak |
|---|---|---|
| ThunderAgent router | 0.06-0.11 cores | 0.23 cores |
| vLLM pod | 2.3-2.8 cores | 3.1 cores |
| bench pod (load generator) | 1.27 cores | 8.0 cores |

The single-process Python router is nowhere near saturated, so **it is not the bottleneck** - the earlier hypothesis is disproved. The load generator dispatched all 128 sessions at t=0 (confirmed in its log) but only **46 of them sent a first request within the first 5 minutes**; the rest trickled in over the whole run. With 24 worker processes available and only ~1.3 cores used, that points to a serialized dispatch/prompt-construction path in the client (consistent with upstream #648), not to a resource limit we set.

Consequence: the offered concurrency label is fiction. We never measured this system at a true c=128. It affects both arms identically, so the comparison stands, but no claim should be made about behaviour at a specific concurrency.

## The extra "errors" are client timeouts, not failures (`errors.png`)

Diagnosed after the run. Across all three replicates: 140 of 6122 tr requests (2.3%) versus 52 of 3228 default requests (1.6%). Every one of them is a `TimeoutError` whose request duration is **exactly 600-601s** - the `request_timeout: 600` I set in the client config. Only a single request in 9350 was an actual server failure (see below).

The two arms time out for different reasons, and the counts line up with the mechanism:

| | timeouts | where the request was waiting | router holds over 600s |
|---|---|---|---|
| default | 52 | vLLM engine queue | 0 (it never holds) |
| tr-decay | 140 | router admission queue | **161** |

161 admission holds exceeded 600s and 140 requests timed out - near one-to-one. Meanwhile the successful requests tell the opposite story: **median end-to-end 27s under tr versus 100s under default**.

That is the same concentration-of-pain effect measured in step 07, now visible as timeouts: ThunderAgent makes the large majority of requests ~4x faster by making a small minority wait much longer. Under a pure proxy everybody waits moderately; under admission control most wait briefly and a few wait past any fixed patience limit.

**Partly my configuration error.** I set the client's patience to 600s while ThunderAgent's own forced-admission backstop is **1800s** - the client gives up three times sooner than the system is designed to make it wait. With `request_timeout: 1800` most of those 140 would have completed slowly instead of failing. So the honest statement is not "tr has 2.7x the error rate" but "under a 10-minute client patience limit, 2.3% of tr requests exceed it versus 1.6% for the proxy" - a real tail property, described without the word "error" doing unearned work. Next run should align the client timeout with the system under test.

### One genuine upstream bug (1 occurrence in 9350 requests)

A race between the background scheduler and the request path, seen once in `tr-decay-r1`:

```
INFO  Paused program wekatrace132_... from http://10.100.3.12:8000
INFO  Scheduler paused ACTING program wekatrace132_...
ERROR Program wekatrace132_... has no valid backend
      httpcore.RemoteProtocolError: Server disconnected without sending a response
      -> HTTP 500
```

The scheduler pauses a program and clears its `backend_url` while a request for that program is already in flight through `update_program_before_request`; the request then reaches the "resolve backend" step and finds `None` (`router.py`, `logger.error("Program %s has no valid backend")`). Too rare to affect any result here, but it is a real synchronisation gap worth reporting upstream.

## Caveats
- Single configuration (c=128) and one workload; the earlier concurrency sweep is superseded but not replaced.
- Still no comparison against a simple concurrency cap, so this measures "admission control vs none", not "ThunderAgent's algorithm vs a trivial limiter".
- `--use-acting-token-decay` is required and is off by default upstream; without it the same setup is 8x *slower* than a plain proxy (step 06).

## Files

- `analysis.md` - the tables above, generated by `analyze.py`
- `replicates.png` - one point per replicate for throughput, steady-state hit rate and TTFT, so the spread is visible rather than averaged away
- `errors.png` - why tr logs more "errors": timeout share, successful-request duration (tr 4x faster), and the hold-duration distribution that causes the timeouts
- per cell: `results/report/` (per-request metrics, no raw text), `results/vllm-metrics.csv`, `results/router-health.csv`, `results/programs-timeline.csv` (now with `step_count`), `cpu-usage.csv`, `router.log`, `config.yml`, `manifest.json`
