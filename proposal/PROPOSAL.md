# ThunderAgent scheduling: two proposals

**Part 1** - why large sessions starve at admission, and four ways to bound the wait.
**Part 2** - whether the 5-second scheduler interval is costing throughput, and why shortening it should come with signal smoothing.

Neither has been run.

---

# Part 1: bounding admission wait (large-session starvation)

Status: proposal, nothing implemented or run yet. Written 2026-09-17 against upstream ThunderAgent commit `7ddc861`.

## The problem, measured

In the replicated weka A/B (`../08-weka-replicates`), ThunderAgent's admission control delivered 2.12x throughput and an 85x steady-state cache hit rate - but a minority of sessions waited absurdly long to be admitted. Per-session longest hold, across 3 replicates at c=128:

| session size (peak tracked context) | median longest hold | p90 |
|---|---|---|
| smallest 25% (median 60k tokens) | 271s | 1332s |
| 25-50% (median 80k tokens) | 398s | 1011s |
| 50-75% (median 87k tokens) | 965s | 1800s |
| **largest 25% (median 103k tokens)** | **1470s** | 1802s |

**71% of sessions above 80k tokens were held longer than 600s. Zero sessions below 40k tokens were.** This is not bad luck; it is a systematic bias against large sessions, and it is the direct cause of the 140 client timeouts recorded in that run.

It also happens to be backwards from what the system is trying to achieve: a 103k-token session is the *most* expensive one to recompute, so it is the one whose cache residency is worth the most - and it is the one the scheduler serves last.

## Root cause in the code

Two functions, both ordering purely by size with no notion of how long anyone has waited:

- `_get_paused_programs_sorted(ascending=True)` (`scheduler/router.py:578-591`) sorts the waiting pool by `total_tokens` ascending.
- `_greedy_resume` (`router.py:807+`) then does Best-Fit-Decreasing packing over that list, in priority groups REASONING > NEW > ACTING, **"within each group, sorted by token count ascending"**.
- `_pause_until_safe` (`router.py:773+`) evicts "smallest first" as well.

So each 5-second scheduler tick admits whichever waiting programs are smallest and happen to fit. A large program competes against a continuously refreshed supply of smaller newcomers and loses every round. This is shortest-job-first with no aging - a textbook starvation generator.

The only protection is `_wait_for_resume(program_id, state, timeout: float = 1800.0)` (`router.py:934`), a hard 30-minute forced admission. That is a binary backstop, not a gradient: a session is either served promptly or waits half an hour. The measured distribution shows exactly that shape - median hold 6-8s, maximum 1804-1880s pinned to the timeout.

Note also that 1800s is a *function default*, not a CLI flag, so an operator cannot tune it without patching.

## Four options

Ordered by implementation cost. They are complementary, not exclusive; 2 and 4 are the ones I would actually ship.

### Option 1: lower the forced-admission timeout (smallest change, blunt)

Change `_wait_for_resume`'s 1800s default to something like 60-120s, and expose it as a CLI flag.

- **Pro**: one line, immediately bounds the tail, easy to validate.
- **Con**: forced admission is by definition admitting something that does not fit, so it reintroduces exactly the over-subscription the scheduler exists to prevent. Set it too low and the mechanism degenerates toward the pure proxy.
- **Expected cost**: low here. The median hold is 6-8s, so capacity usually frees quickly; a 120s bound would only affect the starved tail, which is a small fraction of admissions.
- **Good as**: an experiment to quantify the throughput/tail trade-off curve, and as an operator safety valve.

### Option 2: age the queue (the real fix)

Replace the pure size ordering with a priority that grows as a program waits. For example, order by effective size

```
effective_tokens = total_tokens / (1 + waited_seconds / AGING_TIME_CONSTANT)
```

with `AGING_TIME_CONSTANT` on the order of 30-60s. A 103k-token program that has waited two minutes then competes as if it were ~34k, so it reaches the head of the queue on its own instead of being rescued by a 30-minute backstop.

- **Pro**: keeps the packing efficiency of smallest-first in the common case (nothing has waited long, so ordering is unchanged), while making starvation impossible in the limit. Standard OS scheduling practice for exactly this failure.
- **Con**: one more constant to tune; admitting a large program occupies capacity that could have held several small ones, so instantaneous admitted-count drops when an aged program is let in.
- **Where**: `_get_paused_programs_sorted`'s sort key, plus a `paused_since` timestamp on the program state.

### Option 3: head-of-line reservation

When capacity frees, reserve it for the longest-waiting program even if that program does not fit yet, instead of letting newcomers consume it. Accumulate until the head fits, then admit it.

- **Pro**: guarantees the queue drains in bounded time without any tuning constant; strictly fair.
- **Con**: deliberately idles capacity while accumulating, so utilisation dips; needs care to avoid convoy effects behind one enormous session.
- **Good as**: a complement to aging (aging decides *who* is next, reservation guarantees they actually get in).

### Option 4: stop holding the connection - shed with a retry hint

Independent of the queue discipline: today a held request keeps an HTTP connection open for up to 30 minutes. Instead, after a bounded wait (say 30s), return `503` with `Retry-After` and let the agent back off and retry.

- **Pro**: removes the pathology at the protocol level rather than the scheduling level. Clients stop burning sockets and timeouts; waiting becomes explicit, observable back pressure that upper layers (autoscaling, routing, the agent framework itself) can react to. It also makes the benchmark's "errors" disappear as a category - they become retries.
- **Con**: only works with clients that retry; a naive client sees a failure. Needs the retry budget to be bounded so a starved session does not spin.
- **Note**: this is what the measured data argues for most strongly. A 600s hold is indistinguishable from a hang to the caller, and our own client gave up at exactly that point 140 times.

## What I would test first

Option 1, because it is measurable in one cell and its result informs the others.

`_wait_for_resume`'s timeout cannot be configured upstream, but it can be monkey-patched from our `launcher.py` without touching upstream source - the same technique already used there to work around the CLI-ignores-its-flags bug. Run one tr-decay cell at c=128, 45 minutes, identical to the existing replicates, with the timeout at 120s, and compare directly against the three tr replicates already measured.

Fixed expectations before running, so the result cannot be rationalised afterwards:

- **Tail**: maximum hold should drop from ~1800s to ~120s, and requests exceeding the 600s client timeout should fall from ~47 per cell to near zero.
- **Throughput**: expected to fall somewhat, because forced admissions over-subscribe the pool. If it stays above roughly 400 tok/s (default is 221), the trade is clearly worth it.
- **Steady-state hit rate**: expected to drop from ~0.685. If it collapses toward the proxy's 0.008, the timeout is doing real damage and 120s is too aggressive.

A second cell at 300s would give three points (120s / 300s / 1800s) and sketch the trade-off curve, for ~50 minutes more.

Separately, and cheaply: raise the benchmark's own `request_timeout` from 600s to 1800s so that the client's patience matches the system under test. That was a configuration error on my side - the client gave up three times sooner than the system was designed to make it wait, which inflated the apparent error rate.

## Upstream report

Independent of what we run, two items are worth filing against ThunderAgent:

1. **Size-ordered admission starves large sessions.** Include the table above: 71% of >80k-token sessions held past 600s versus 0% of <40k-token sessions, with holds pinned at the 1800s backstop. Suggest aging (option 2).
2. **The forced-admission timeout is a function default, not a flag.** An operator running latency-sensitive traffic cannot bound admission wait at all without patching the source.

---

# Part 2: the 5-second scheduler interval

Separate question, same file because the remedies interact: the admission scheduler runs on a fixed `--scheduler-interval` (default 5.0s). Does shortening it help?

## What the interval controls

`_scheduled_check()` runs every interval and does three things in order: fetch fresh metrics from each backend, `_greedy_resume()` (admit waiting programs), then check `remaining_capacity() < 0` and `_pause_until_safe()` (evict).

Admission of a program that is *already queued* therefore only happens on a tick. A request arriving when capacity is free is admitted immediately, but once queued it waits for the next scheduler pass.

## Evidence that the interval, not scarcity, dominates the median wait

Hold durations across the three tr replicates (2565 intervals, prober sampling every 2s):

| duration | share |
|---|---|
| 0-4s | 17.6% |
| **4-6s** | **22.3%** (mode, sitting on the tick) |
| 6-8s | 13.2% |
| 8-12s | 13.4% |
| 12-60s | 22.8% |
| >300s | 4.2% |

p25 = 4s, p50 = 6s, and **67% of holds are under 12s, i.e. one or two ticks**. If those programs were genuinely waiting for capacity, the distribution would not pile up on the polling period. The median wait is largely queueing for the next scheduler pass.

## Evidence that this costs throughput

The engine goes idle under tr more often than under the pure proxy, while dozens of programs sit in the admission queue:

| | mean running requests | time with <10 running | **time with 0 running** |
|---|---|---|---|
| default | 30.6 | 6.2% | 5.6% |
| tr-decay | 27.7 | 13.2% | **9.3%** |

9.3% of the run with an idle GPU and a non-empty waiting queue is a direct, recoverable loss. This is the strongest argument for shortening the interval.

## Why *lengthening* the interval is the wrong direction

Overhead is not the constraint: the router consumed 0.06-0.11 cores median at 5s with one backend. Going to 10s would roughly double the median hold (6s -> ~11s) and lengthen the idle windows, buying nothing measurable.

## The subtlety: faster polling does not reduce per-decision noise in this code

A reasonable objection is that sampling 5x more often should *reduce* noise, since more samples average out. That is true of an estimator that averages. **This code never averages.** `metrics_history` retains 12 samples but is only read by `to_dict()` for display; the capacity decision uses a single instantaneous sample:

```python
# vllm_metrics.py, calculate_shared_tokens
vllm_actual_used = int(self.latest_metrics.kv_cache_usage_perc * capacity)
```

So a 1s interval produces 5x as many decisions, each carrying exactly the same per-sample noise as before.

How noisy is one sample, measured on our runs (2s sampling, tr arm):

| statistic of `kv_cache_usage_perc` | value |
|---|---|
| mean | 0.788 |
| std of a single sample vs a 30s rolling mean | 0.039 |
| p90 absolute deviation | 0.062 |
| max absolute deviation | 0.188 |
| **share of time a single sample is >5 points off the 30s mean** | **17.7%** |

On a 2.24M-token pool, a 0.039 standard deviation is about **+-87k tokens - larger than an entire median session's context (65k)**. Any single sample can misjudge remaining capacity by roughly one whole session.

Whether acting on that more often is harmful depends on whether the actions are self-correcting. Here they are **not symmetric**: a spurious pause triggered by a noise spike evicts that program's KV blocks, and resuming it on the next tick does not bring them back - it pays a full 60-100k token re-prefill. We have seen this failure mode before, in the step-06 synthetic work: mis-sized accounting produced 53 shed/readmit ping-pongs with zero benefit.

## Proposal: shorten the interval *and* smooth the signal

- **Change A (config only)**: `--scheduler-interval 1`. It is a real CLI flag, unlike the 1800s forced-admission timeout, so no patching is needed.
- **Change B (one line, needs a patch)**: make `calculate_shared_tokens` use the mean of the last N samples instead of `latest_metrics`. The history is already collected. With 1s sampling and a 5-sample mean, decision noise drops by roughly 1/sqrt(5) *and* worst-case reaction latency falls to a fifth of the 5s value - the "more samples, less noise" intuition, which only materialises once something actually averages.

Related detail worth fixing at the same time: `METRICS_HISTORY_SIZE = 12` is defined in *samples*, not seconds. At a 5s interval it spans 60s of history; at 1s it spans 12s. If smoothing is added, the window should be specified in time.

## Experiment to run (not yet run)

Three arms, each one 45-minute tr cell at c=128, directly comparable to the three existing replicates:

| arm | configuration | question |
|---|---|---|
| baseline | interval 5s | already measured (3 replicates) |
| A | interval 1s, no smoothing | net effect of faster reaction alone |
| B | interval 1s + 5-sample mean | does smoothing recover what noise costs? |

Arm B needs a monkey-patch of `calculate_shared_tokens` from our `launcher.py`, the same technique already used there for the CLI-ignores-its-flags bug; upstream source stays untouched. Roughly 100 minutes for both arms.

Pre-registered expectations:

- **Median hold** should fall from 6s to about 2s in both A and B, and the 4-6s mode should disappear.
- **Idle GPU time** should fall from 9.3%. If it does not, the idleness is caused by something else - most likely the load generator supplying only a third of the configured concurrency (see `../INFERENCE-PERF-BUGS.md` issue 4) - and no scheduler tuning will fix it.
- **Throughput** should rise above the 469 tok/s baseline if the idle time is genuinely admission-limited.
- **Churn check**: total hold count should not balloon. If A produces far more holds than the 2565 baseline without a throughput gain, that is the noise-driven ping-pong, and B should then beat A.
- **The tail is out of scope here.** The >300s holds are caused by the size-ordered queue with no aging (Part 1) and will not move with the interval.

If B clearly beats A, "smooth the capacity signal" becomes an upstream recommendation in its own right, and a more valuable one than a parameter change.
