# Admission and pause ordering: serve the resident, not the small

Status: analysis, nothing implemented or run. Written 2026-09-21 against llm-d-router `f6ee4130` on branch `thunder-agent` (the `thunder-agent-v4` line plus the urgent tier), using the step 13 sweep and its origin-only arm (`../13-llm-d-router-sweep/README.md`, `RESULTS.md`, `SATURATION.md`).

This sits alongside `PROPOSAL.md` rather than extending it. Part 1 asks how to stop large sessions starving. Part 3 asked which pod a resumed session lands on, and has now been run and won. This document asks the question underneath both, which is still untested: **when capacity frees, which waiting session should get it?**

## The claim

Under saturation, admission should prefer the session whose KV is still resident, because its next turn is nearly free and finishing it releases capacity for good. The port instead breaks ties on smallest footprint, which on this corpus means the shallowest and newest session. The two orderings point in opposite directions.

## Little's law, and why "concentrate" beats "spread"

Resident KV equals arrival rate times residency time. Admitting a newcomer adds a working set that only grows; finishing a veteran releases one permanently. Under saturation the discipline should therefore narrow the set of sessions in flight.

Step 13 measured this directly. The pool completes a roughly fixed number of turns per window; concurrency only decides how thinly they are spread.

| baseline | sessions started | turns finished | turns per session | steady-state hit rate |
|---|---|---|---|---|
| c=48 | 81 | 3740 | 46.2 | 0.952 |
| c=128 | 142 | 3026 | 21.3 | 0.040 |
| c=338 | 338 | 3321 | 9.8 | 0.002 |

Concentrated on few sessions, the working set stays inside the 8.95M-token pool and the cache works. Spread across all of them it reaches 16.5M and every turn recomputes a context that used to be resident.

The port's class ordering already encodes the right instinct, `classReasoning < classPaused < classNew`, and the comment on `classPaused` gives the reason: "it is mid-trajectory with sunk work, and finishing it releases capacity permanently."

## The principle already won once, on the other axis

Origin-only resume (Part 3) is the same principle applied to placement rather than ordering. Instead of sending a resumed session to whichever pod has room now, it makes the session wait for the pod that still holds its prefix. Measured at three replicates per level:

| sessions/pod | metric | most-room (n=3) | origin-only (n=3) | ratio |
|---|---|---|---|---|
| 24 | throughput (tok/s) | 1531 | 1830 | 1.20x |
| 24 | steady-state hit rate | 0.590 | 0.824 | 1.40x |
| 32 | throughput (tok/s) | 1370 | 1693 | 1.24x |
| 32 | steady-state hit rate | 0.347 | 0.680 | 1.96x |

Waiting for the warm option beat taking the available one, by 14 to 25 percent on throughput at every level, with rebinds at zero. That is the placement-axis version of this document's claim, and it is now measured rather than argued.

The ordering axis has not been touched. Origin-only changed *where* a resume goes; nothing has changed *which* waiting program goes first.

## Three places the port hands priority back to the newcomer

### 1. Within a class, smallest footprint wins

The tie-break in `betterThan` (`fairness.go`), unchanged by v4 and by the urgent tier:

```go
if aClass != bClass { return aClass < bClass }
if aTokens != bTokens { return aTokens < bTokens }
return aWait > bWait
```

The intent is packing efficiency. On this corpus the effect is to reinstate "newest first", because footprint and turn depth are the same variable:

| turn index | requests | mean prompt tokens | mean output tokens |
|---|---|---|---|
| 0 to 1 | 5449 | 26,760 | 363 |
| 2 to 4 | 7562 | 47,276 | 684 |
| 5 to 9 | 10,515 | 57,355 | 730 |
| 10 to 19 | 11,656 | 67,557 | 773 |
| 20 and up | 8320 | 90,509 | 819 |

A 26k candidate is a session on its first turn with nothing resident. A 90k candidate is twenty turns deep with twenty turns of sunk prefill behind it. Smallest-first serves the first and defers the second.

### 2. Work conservation hands the freed slot to a newcomer

`Pick` skips any candidate that fits nowhere and takes the best of the rest. So when a 40k slot frees, a 90k PAUSED session cannot take it and a 26k NEW session can. Per decision that is right, capacity should not idle. Across decisions it trades a chance to finish an old working set for a new one that will grow.

### 3. The pause sweep also evicts smallest first

`pauseFromPodLocked` sorts idle candidates by ascending footprint. Pausing a small program frees little, so the sweep continues and ends up marking the in-flight large ones anyway: step 12's calibration log shows 195 sweeps that paused 0 or 1 program each and marked 70 to 116. The deeper issue is that the sweep has no notion of **who will come back soonest**, which is what actually sets the cost of a pause.

## What the ordering should key on

Resume priority should reflect the value of resuming: how cheap the next turn is, and how much finishing releases. Three signals, ordered by how well the port can see them today:

1. **Recency.** Median think time in the weka corpus is 0.31 s, p90 9.8 s, so a session that responded recently is likely to return immediately with its prefix still warm. The port already stores `lastResponseAt` and `lastActivity` on every program (`program_table.go`) and reads them only for idle decay and TTL eviction. Ordering by recency needs no new bookkeeping at all.
2. **Actual prefix residency.** Strictly better, because it is the thing recency estimates. The port cannot see it; llm-d's precise-prefix-cache-routing derives it from vLLM KV events and is the source if this is worth doing properly.
3. **Proximity to completion.** Completion releases capacity permanently, but remaining turns are not knowable from a replay and depth is a weak proxy. Least actionable of the three.

All three say the same thing: **priority should come from residency value; size belongs in the packing step only.**

## The fairness backstop already exists

Pure "oldest first" starves newcomers, and today's smallest-first supplies an accidental fairness that a residency order would remove. That objection is now largely answered by the code: commit `1e922b63` added `urgentWaitMs`, a fit-checked tier where a paused or new head that has waited past the threshold outranks every non-urgent candidate, is ordered oldest first, and is released from the origin-only restriction. It sits below `headWaitStarvationMs` and the config validates that ordering.

That is Part 1's queue aging in discrete form. It means a residency-based tie-break can be tried **without** shipping a new fairness mechanism first: the urgent tier is the floor, and the tie-break only decides who goes first among candidates that are not yet urgent.

The resulting decomposition separates three concerns the port currently collapses into one variable:

| concern | mechanism | status |
|---|---|---|
| who is worth resuming | residency value (recency now, prefix residency later) | **not implemented** |
| who has waited too long | `urgentWaitMs`, then `headWaitStarvationMs` | implemented, not yet swept |
| which pod, and does it fit | `fitPodLocked`, origin-only placement | implemented and measured |

## The expected cost, and its measured shape

Concentration improves aggregate work and hurts the unlucky tail. The origin-only session-level numbers already show that trade in its exact form:

| sessions/pod | metric | most-room | origin-only |
|---|---|---|---|
| 24 | goodput within SLO (turns/s) | 1.09 | 1.58 |
| 24 | session attainment, strict / lenient | 0.87 / 0.88 | 0.82 / 0.85 |
| 32 | goodput within SLO (turns/s) | 1.28 | 1.53 |
| 32 | session attainment, strict / lenient | 0.76 / 0.78 | 0.70 / 0.75 |

More work inside the SLO, a few points less strict attainment, because when a concentrating policy makes something wait it waits longer. A recency tie-break should be judged on the same axes, and Part 7's caveat applies: a strict all-turns criterion penalises the arm that completes more turns, so the per-turn violation share belongs next to it.

## What the runs so far cannot show

None of them tests newcomer-versus-veteran competition. At c=338 the corpus equals the concurrency: all 338 sessions arrive at t=0 and none arrive afterwards, so there are no newcomers to lose to. At lower levels the pool refills, but as a trickle (81 sessions started against a 48 pool).

A fair test needs sustained arrivals against a full pool: **c=128 against the full 338-session corpus**, which is the one level where the gate is fully engaged, forced admissions are near zero, and the corpus is 2.6x the concurrency so newcomers keep arriving. Both arms on `thunder-agent-v4` semantics with `resumePlacement: origin-only` (now the better default), differing only in the tie-break.

| arm | tie-break within a class |
|---|---|
| control | ascending footprint (today) |
| `recency` | most recently active first; footprint used only in `fitPodLocked` |

Three replicates each, 30-minute cells, reusing `run-origin-replicates.sh`'s alternation and the session-id bench image so Part 7's metrics are computable.

Pre-registered expectations:

- **Steady-state hit rate rises above origin-only's 0.68 at 32 per pod.** Resuming warm sessions first is the whole mechanism. No movement means recency is a poor proxy for residency and only signal 2 is worth pursuing.
- **Turns per session p50 rises; sessions started falls.** This is the Little's law prediction and the most direct test of the claim. Origin-only already moved p50 from 10 to 12 at this level; recency should move it further.
- **Throughput rises**, by the step 13 relation: requests completed equals prefill throughput divided by prefill per request, and warm resumes cut the denominator.
- **Urgent-tier promotions (`thunder_agent_urgent_promotions_total`) are the risk metric.** A large rise means the tie-break is starving newcomers and the urgent tier is carrying them; that is the mechanism working, but if it dominates, the tie-break is too aggressive.
- **Strict attainment falls a few points while goodput rises**, matching the origin-only shape. A fall without a goodput rise means the concentration bought nothing.

Pause ordering is a separate arm and must not be mixed in. Pausing the least recently active idle program instead of the smallest is the mirror-image change and needs its own cell to attribute.
