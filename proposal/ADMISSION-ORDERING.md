# Admission and pause ordering: act on residency, do not reorder by proxies for it

Status: written 2026-09-21 against llm-d-router `f6ee4130` on branch `thunder-agent`, then **revised the same day after the age-only cell and the wait-cost curve, which falsify the first version's central proposal**. Sources: `../13-llm-d-router-sweep/README.md`, `RESULTS.md`, `SATURATION.md`, `results/sweep-20260918-134248-t1900/wait-cost.md`.

This sits alongside `PROPOSAL.md` rather than extending it. Part 1 asks how to stop large sessions starving. Part 3 asked which pod a resumed session lands on, and won. Part 8 asks how to decide hold-or-move from real residency. This document asks the question those three circle: **when capacity frees, which waiting session should get it?**

## Read this first: the original claim was tested and lost

The first version of this document argued that smallest-footprint tie-breaking is wrong because footprint is turn depth, so "smallest first" is "newest first", and that admission should instead prefer sessions with sunk work. The age-only cell tested the ordering half of that directly (`urgentWaitMs: 15000`, `urgentMove: false`, so pure reordering with no move) and it lost to plain origin-only:

| metric | origin-only (n=3) | age-only 15 s (n=1) |
|---|---|---|
| throughput (tok/s) | 1693 | 1461 |
| steady-state hit rate | 0.68 | 0.51 |
| share of turns with TTFT over 30 s | 3.7% | 18.3% |
| strict session attainment | 0.70 | 0.39 |
| turns completed | 2090 | 1714 |

Two mechanisms, both of which the first version missed:

1. **Oldest-first is largest-first, and large resumes are bad packing.** Pool occupancy was identical in both arms (68 running requests, KV 0.54), but each freed block of room resumed fewer sessions, so the queue lengthened for everyone. Every prompt-size quartile got slower, including the largest. Smallest-first is not a bug; it maximises resumes per freed block, and that has real value the first version did not account for.
2. **Waiting destroys the thing the ordering was trying to protect.** The wait-cost curve shows a paused session's prefix survives about 10 to 12 s on its pod at c=128 under LRU. Making warm sessions wait behind cold ones turns them cold too.

What survives is the choice of *variable*. Depth and wait time are bad proxies for residency; **idle age is a good one**, and the wait-cost table measures it directly:

| prefix idle age | origin-only: median cached fraction | share of turns |
|---|---|---|
| 0 to 2 s | 0.99 | 39% |
| 2 to 5 s | 0.98 | 22% |
| 5 to 10 s | 0.92 | 17% |
| 10 to 15 s | 0.17 | 9% |
| 15 s and more | 0.00 | 13% |

That is a cliff, not a gradient. It means residency is close to binary and knowable, which is Part 8's premise and why Part 8's first layer (`originWaitMaxMs` 8 s, ordering left smallest-first) is the variant that actually won: throughput 1504, strict attainment 0.78, the best measured. **Acting on residency beat reordering by it.**

## The claim, as it stands after those results

Ordering is a second-order lever here and a dangerous one, because any order that correlates with footprint also changes packing efficiency. The first-order lever is knowing whether a session's blocks are still on its pod and acting on that, which is Part 8. The rest of this document is kept because the framing still explains *why* Part 8 works, and because one ordering variant remains untested and is not refuted by the age-only cell: ordering by **recency of last response**, which unlike wait time positively predicts residency and does not systematically select the largest programs.

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

The intent is packing efficiency, and the age-only cell shows that intent is well founded: taking small candidates first resumes more sessions per freed block. The side effect, on this corpus, is to reinstate "newest first", because footprint and turn depth are the same variable:

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

## Upstream picked the depth ordering, and its evidence does not transfer

llm-d merged [PR #2116](https://github.com/llm-d/llm-d-router/pull/2116) on 2026-09-13, adding a `turn-priority` strategy to the `program-aware` fairness policy. It scores each waiting flow

```
score = turn_number + turnPriorityTimeWeight * head_wait_seconds
```

and dispatches the highest, resetting `turn_number` to one after `turnPriorityInactivitySeconds` (120 s default) of inactivity. The stated reasoning is this document's original one: a deeper session probably still has its prefix resident, and it is closer to completion. The strategy requires one fairness ID per session, which it gets from the same `agent-identity` headers the port uses; the PR notes that anonymous traffic shares one flow whose dispatched count is not a session depth, and belongs in a different band, which is Part 6's gap 2 stated upstream.

Its reported gains against FCFS are large. Read off the axes of the plots in the PR thread (the thread quotes no numbers in text, and the author's own annotations are more generous than the axes):

| at 128 concurrent sessions | FCFS | turn-priority (w=0.05) | ratio |
|---|---|---|---|
| sessions finished | ~4 | ~25 | ~6x |
| requests served | ~3,500 | ~7,900 | ~2.3x |
| request latency p50 (s) | ~340 | ~18 | ~19x |
| request latency p90 (s) | ~540 | ~120 | ~4.5x |
| output throughput (tok/s) | ~230 | ~590 | ~2.6x |
| total throughput (tok/s) | ~30,000 | ~104,000 | ~3.5x |

The experiment is well controlled in one respect worth copying: a second arm with `w=100` puts all weight on wait time, degenerating to FCFS, and it tracks the FCFS line everywhere. So the effect is the turn ordering, not the presence of the policy. At 16 sessions all three arms coincide, supporting the claim of no cost without contention.

**Why it is not evidence for this pool.** The setup differs on the four things that decide the outcome here:

| | PR #2116 | step 13 |
|---|---|---|
| replicas | 1 (TP=4, H200, 1M context) | 4 (TP=2, H100 80GB, 256k context) |
| CPU KV offload | 512 GiB | none |
| admission control | none; ordering only | fit gate, pause sweep, placement |
| baseline compared against | FCFS | llm-d default profile (prefix-cache, queue, KV scorers) |

The first two remove the failure modes the age-only cell hit. With one replica there is no placement and no per-pod fit, so ordering never interacts with packing and "largest first" costs nothing. With 512 GiB of CPU offload a lost GPU prefix is a reload, not a recompute, so making a warm session wait is far cheaper than it is here. And the baseline is weaker: their FCFS collapses to 30,000 tok/s total, where our default profile still does 91,172 at a harder concurrency.

Their KV plot is the most useful part for us. It splits GPU-internal from CPU-external hits, and shows FCFS at 128 sessions flat at zero on **both** tiers while turn-priority holds 75 to 95 percent GPU-internal. That is worth carrying into Part 5: a large CPU tier did not save a scheduler that lost the GPU tier, so offloading does not make admission control irrelevant.

**Transferring the ordering to a gated pool is the thing the age-only cell already argues against.** Depth correlates with footprint, so `turn-priority` is largest-first in effect, and that is precisely what cost age-only 14 percent of throughput and half its attainment. The 120 s inactivity reset is far beyond the measured 10 to 12 s residency horizon, so it would classify long-cold sessions as deep and warm. If anything transfers, it is the shape of the score, not its variables.

## What is still untested

One ordering variant survives the age-only result: **recency of last response**, not depth and not wait time. The wait-cost table shows idle age predicts cached fraction with a sharp cliff, and unlike depth it does not systematically select the largest programs, so it does not carry the packing penalty that sank age-only.

It is also, on the evidence, unlikely to be worth much on its own. Part 8 layer 2 reads residency from the KV index directly, and an exact signal beats a proxy for the same quantity. The honest framing is that recency ordering is the cheap approximation of Part 8 layer 2, worth one cell only if layer 2 is blocked.

If it is run: c=128 against the full 338-session corpus, both arms `resumePlacement: origin-only` with `originWaitMaxMs: 8000` (the current best), differing only in the tie-break, three replicates, session-id bench image so Part 7's metrics compute.

| arm | tie-break within a class |
|---|---|
| control | ascending footprint |
| `recency` | most recently active first; footprint still used in `fitPodLocked` |

Pre-registered, with the age-only cell as the warning:

- **Resumes per freed block must not fall.** Report turns completed next to throughput. Age-only failed here first (1714 vs 2090 turns at identical pool occupancy); if recency shows the same, the packing penalty applies to it too and the variable does not matter.
- **Steady-state hit rate rises above 0.53** (the wait-cap cell). No movement means recency adds nothing over acting on the 8 s cap.
- **Share of turns with TTFT over 30 s stays at or below 3.3 percent**, the level most-room and the wait cap both hold. Age-only went to 18.3 percent.
- **Strict attainment stays at or above 0.78.** That is the bar the wait cap set.

Pause ordering remains a separate arm: pausing the least recently active idle program instead of the smallest is the mirror-image change, it has the same packing risk, and it needs its own cell to attribute.
