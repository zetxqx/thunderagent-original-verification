# ThunderAgent scheduling: three proposals

**Part 1** - why large sessions starve at admission, and four ways to bound the wait.
**Part 2** - whether the 5-second scheduler interval is costing throughput, and why shortening it should come with signal smoothing.
**Part 3** - why resumed sessions change pods on a multi-pod pool, and an origin-only resume policy for the llm-d port.

None has been run.

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


---

# Part 3: origin-only resume on a multi-pod pool

Status: proposal, nothing implemented or run yet. Written 2026-09-18 from the step 12 measurements (`../12-llm-d-router-pool/RESULTS.md`), against llm-d-router commit `ae371354` (the port) and upstream ThunderAgent commit `7ddc861`.

## The problem, measured

Step 12 ran the port on the whole 4-pod pool at c=338. It beat llm-d's default profile 1.42x on throughput, but its steady-state prefix-cache hit rate was 0.25, half of the 0.49 the same plugin reached on a single pod at comparable per-pod pressure (step 10). The EPP counters say why:

| per 45-minute cell, mean of 3 replicates | value |
|---|---|
| resumes (paused programs whose next turn was admitted) | 4470 |
| resumes that changed pod (`thunder_agent_rebinds_total`) | about 3100, i.e. 70 percent |
| pauses | 4720 |
| requests with zero cache hit | 0.67 (single pod: 0.38) |

Every move is a full re-prefill of a 50k-token history on a pod that has never seen it, plus the eviction of someone else's prefix to make room. The pool calibration showed the same ratio (1025 of 1448) before the main run, so it is a property of the mechanism, not of one cell.

## Root cause in the code

The port's gate (`llm-d-router/pkg/epp/framework/plugins/thunderagent/fairness.go`, `fitPodLocked`) admits a paused program onto its origin pod if that pod's decayed room covers the program, otherwise onto the pod with the most room. It is tempting to read the 70 percent as load imbalance, with the origin pod full and a neighbour half empty. The calibration log says otherwise: every pod is full, and the move is a matching failure rather than a placement preference.

From the calibration cell (`epp.log`, 195 `thunderagent.pause_sweep` records, and the EPP program counters between minutes 2 and 9):

| | value |
|---|---|
| working set just after a sweep, median | 2,222,110 |
| pod ceiling (`capacityTokens` x `utilThreshold`) | 2,237,040 |
| standing room per pod | about 14,900 |
| what one resume needs (median prompt + buffer) | 40,690 |
| unpaused programs with a request in flight | 202 of 203 (idle: 1) |

The chain behind those numbers:

1. **The sweep pins every pod at its ceiling.** `pauseFromPodLocked` pauses programs until the undecayed working set falls back under the ceiling, so in steady state it sits just below it. Standing room is about 15k tokens, well under the 40k a median resume needs.
2. **Decay never fires, so there is no admission room to find.** Room is `ceiling - usedDecayed`, and `decayedFootprint` discounts only programs with no request in flight. Under this load essentially every unpaused program is in flight, so the decayed view equals the undecayed one and room collapses to `ceiling - working set`.
3. **Room appears one slot at a time, on one pod.** When a marked program finishes its turn it is paused and leaves `podLoads`, freeing its full footprint, roughly 40k, on that pod and no other.
4. **A global queue competes for that slot.** `Pick` iterates every queue, skips the candidates that fit nowhere, and takes the best of the remainder by class then footprint. The winner is the smallest paused program in the pool, and its origin has nothing to do with which pod just freed the slot.

A resume therefore keeps its pod only when the pod that happened to free a slot is its own.

Upstream does the same thing by design: `_greedy_resume` (`ThunderAgent/scheduler/router.py`) places each resumed program on the backend with the highest remaining capacity (best-fit-decreasing) and `_resume_program` accepts whatever target it is given; the origin backend is only a fallback when no target is supplied. The single-pod lanes of steps 08 to 10 could not expose this because there was nowhere else to go.

The paper's headline mechanism, keeping a session's prefix resident until its next turn, is therefore undone by its own placement step as soon as there is more than one backend.

### Why one in four

The chain predicts a stay rate near `1/N` on `N` pods, and the calibration cell matches:

| | value |
|---|---|
| resumes | 1448 |
| stayed on the origin pod | 423 (29.2 percent) |
| `1/N` for N = 4 | 25 percent |

The four point excess is the first-refusal rule in `fitPodLocked`, which keeps the origin on the occasions when it also happens to fit. The prediction is falsifiable and unwelcome: the larger the pool, the smaller the share of resumes that keep their prefix, with an eight-pod pool keeping roughly one in eight.

## What this rules out

Two knobs that look like they should help cannot, and both fail for the same reason: they act on the sweep, not on the placement rule.

- **Lowering `utilThreshold` to leave standing headroom.** The sweep drives the working set to just under whatever the ceiling is, so standing room stays near zero at any threshold. A lower one only pauses more programs sooner.
- **Tuning `actingHalfLifeSeconds`.** Decay applies only to programs with no request in flight, and under load there is about one of those in the whole pool. The half-life has nothing to act on.

## Options

### Option A: origin-only (the proposal)

A paused program waits for its origin pod. It is admitted only when the origin pod has room for it. Two exceptions: the origin pod has left the pool (then place by room, as today), and the forced-admission backstop has fired (then place by room, as today). New programs' first turns are unchanged and still go to the pod with the most room. Cost: a paused program may wait longer, and pods can diverge in load. Benefit: the prefix stays where it is, which is the whole point of pausing rather than dropping.

Implementation in the port: a config field `resumePlacement` with values `most-room` (today's behaviour, default, faithful to upstream's BFD) and `origin-only`; in `fitPodLocked`, when the policy is `origin-only` and the preferred pod is present in the fit view, return "no fit" instead of falling through to the most-room pod. About twenty lines plus tests. No change to the sweep, the decay, the priorities or the backstop.

No matching logic is needed on top of that. `Pick` already skips candidates that fit nowhere and takes the best of the remainder, so restricting the fit test to the origin pod turns each freed slot into a contest among that pod's own paused programs, which is exactly the behaviour we want.

On the added wait, the arithmetic is kinder than it first looks. Today a program waits for any of `N` pods to free a slot while competing against the whole queue. Under A it waits for one pod while competing against that pod's share of the queue. Supply and demand both fall by `N`, so the mean wait should be roughly unchanged; what rises is its variance, and the real risk is a pod whose own arrival rate and own completion rate drift apart. That is what the pod-balance metric below is for.

### Option B: origin with a bounded wait

Like A, but after a program has waited `T` seconds for its origin pod it may take the most-room pod. `T` on the order of the tail we can tolerate (30 to 60 s). Trades some cache residency for a bounded added delay; adds one parameter and one more interaction with Part 1's starvation.

### Option C: move only when the origin is clearly the worse choice

Allow the move only when the most-room pod has room exceeding the origin's by a margin (for example a full program's worth), i.e. hysteresis on the placement decision. Keeps some load balancing; harder to reason about and to test than A.

Recommendation: A first. It is the smallest change, it isolates one variable, and the two exceptions already cover the failure cases. B and C are refinements to try only if A shows either pod-load divergence or a visibly longer tail.

## Interaction with Part 1

Waiting for one pod instead of any pod lengthens some holds. Part 1's starvation (large sessions losing to a stream of smaller ones, held until the 1800 s backstop) can therefore get worse under A, and the 55 forced admissions per cell measured in step 12 are the number to watch. If forced admissions rise, the queue-aging remedy from Part 1 is the companion change, not a reason to abandon A.

## What I would test first

One more pool arm under the step 12 protocol (`../12-llm-d-router-pool/run-pool.sh`, c=338, 45 minutes, three replicates, image rebuilt as `thunder-agent-v4`):

| arm | `resumePlacement` | status |
|---|---|---|
| epp-thunder | most-room | measured: 1447 tok/s, hit rate 0.248, 3100 rebinds, 55 forced admissions per cell |
| epp-thunder-origin | origin-only | to run |

Pre-registered expectations:

- **Rebinds** fall from about 3100 to near zero (only vanished-pod and forced-admission cases remain).
- **Steady-state hit rate** rises from 0.25 toward the single-pod 0.49; zero-hit share falls from 0.67 toward 0.4.
- **Throughput** rises above 1447 tok/s. If it does not while the hit rate does rise, the extra wait for the origin pod is costing more than the saved prefill, and Option B is the next arm.
- **Forced admissions** per cell are the risk metric: the same 55 or fewer is a pass; a clear rise means Part 1 must come along.
- **Pod balance**: per-pod in-flight and KV should stay within a few percent of each other; a persistent skew means origin-only needs Option C's escape hatch.

About three hours of pool time. The result also settles a question step 12 could not: how much of the port's gap to its single-pod hit rate is placement, and how much is the higher per-pod pressure of the pool run.
