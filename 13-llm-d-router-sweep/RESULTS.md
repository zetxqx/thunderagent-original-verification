# Step 13 results: why throughput falls as concurrency rises

Run `results/sweep-20260918-134248-t1900`: two arms (`epp-baseline`, `epp-thunder`) at six concurrency levels (48, 96, 128, 192, 256, 338 active sessions on the 4-pod pool), one 30-minute cell each, 10-minute warm-up, client timeout 1900 s, prefix caches reset and the EPP restarted before every cell. Twelve cells, no preemptions, no errors. Auto-generated tables in `results/sweep-20260918-134248-t1900/sweep.md`, figure in `sweep.png`.

A one-page version of the whole step in the standard benchmarking-report format (sweep, origin-only resume, replicates, variants, long window, wait-cost curve; ITL, requests per second and TTFT p99 added) is `BENCHMARK-REPORT.md`.

The measured curve is non-monotonic and, read naively, says the system gets slower the more work you give it:

| output throughput (tok/s) | c=48 | c=96 | c=128 | c=192 | c=256 | c=338 |
|---|---|---|---|---|---|---|
| baseline | 2014 | 1541 | 1151 | 1065 | 999 | 1050 |
| thunder | 1972 | 1536 | 1382 | 1342 | 1438 | 1538 |

That reading is wrong. This document takes the curve apart.

A `c=16` level is being appended to the same run directory as of 2026-09-19; it extends the low end and does not change anything below. If anything it sharpens section 1's last point, since 4 sessions per pod is further still from saturation.

## Headline

**The pool is doing 6.6x more token work at c=338 than at c=48. The throughput metric counts only output tokens, and almost all of the extra work is re-prefilling prefixes that used to be cache hits.**

| baseline | output tok/s | prefill tok/s | total tok/s | vs c=48 |
|---|---|---|---|---|
| c=48 | 2014 | 11,787 | 13,801 | 1.0x |
| c=96 | 1541 | 38,157 | 39,698 | 2.9x |
| c=128 | 1151 | 68,157 | 69,308 | 5.0x |
| c=192 | 1065 | 86,055 | 87,119 | 6.3x |
| c=256 | 999 | 86,313 | 87,313 | 6.3x |
| c=338 | 1050 | 90,122 | 91,172 | 6.6x |

`prefill tok/s` is `(prompt_tokens - cached_tokens) / 1800`, i.e. the prompt tokens the engine actually had to compute. Two separate effects push the output number down, one physical and one an artefact of the experiment design. Both are quantified below.

## 1. The saturation point is where the working set crosses the KV pool

The pool holds 8.95M tokens (4 pods x 2,237,040). A session's working set is its context, so the aggregate working set is roughly `c x mean prompt tokens`. The cliff lands exactly where that crosses capacity.

Hit rate below is prompt-weighted over the whole window (`cached_tokens / prompt_tokens`), which is the quantity that determines prefill work. `sweep.md` reports a steady-state hit rate from vLLM's interval counters instead; the two agree on the shape. The working-set column is the baseline arm's; thunder's is 0 to 6 percent smaller at the same level because its request mix runs slightly shallower prompts.

| c | working set | vs KV capacity | baseline hit | thunder hit | baseline queued in vLLM | baseline TTFT p50 |
|---|---|---|---|---|---|---|
| 48 | 4.0M | 0.45x | 0.932 | 0.930 | 0 | 0.4 s |
| 96 | 6.7M | 0.75x | 0.725 | 0.706 | 4 | 0.5 s |
| 128 | 7.8M | 0.87x | 0.336 | 0.479 | 15 | 8.2 s |
| 192 | 10.6M | 1.18x | 0.043 | 0.309 | 50 | 36.0 s |
| 256 | 13.3M | 1.48x | 0.002 | 0.257 | 93 | 65.8 s |
| 338 | 16.5M | 1.85x | 0.002 | 0.236 | 152 | 101.5 s |

Three things follow.

- **c=128 is the knee.** The working set reaches 0.87x capacity and the baseline hit rate collapses from 0.725 to 0.336. Above it the pool is oversubscribed and something must be evicted on every turn.
- **Total token throughput plateaus at 87k to 94k tok/s from c=192 on.** That is this hardware's ceiling on this workload. Adding concurrency past that point adds queueing, not work.
- **c=48 is not a capacity measurement.** KV sits at 0.33, the engine queue is empty, preemptions are zero. It is demand-limited by the traces' own think time. Using it as the baseline overstates the "decline".

Preemption is not the mechanism: the whole 30-minute window sees 0 to 23 preemptions per cell in the baseline arm and 0 to 6 in the thunder arm.

## 2. Half the apparent drop is the request population, not the system

Output throughput is `requests completed x output tokens per request / 1800`. Both factors move, and the second moves more.

| baseline | requests | output tokens per request | median turn index |
|---|---|---|---|
| c=48 | 3740 | 969 | 18 |
| c=128 | 3026 | 685 | 9 |
| c=338 | 3321 | 569 | 4 |

From c=48 to c=338 the request count falls to 0.89x while output per request falls to 0.59x. Multiplied, 0.52x, which is the whole drop from 2014 to 1050.

The output length per request falls because the measured requests are drawn from shallower parts of the traces, and in this corpus a deep turn is a longer turn:

| turn index within a session | requests | mean output tokens | mean prompt tokens |
|---|---|---|---|
| 0 to 1 | 5449 | 363 | 26,760 |
| 2 to 4 | 7562 | 684 | 47,276 |
| 5 to 9 | 10,515 | 730 | 57,355 |
| 10 to 19 | 11,656 | 773 | 67,557 |
| 20 and up | 8320 | 819 | 90,509 |

### Why the turn depth shifts

Not because of corpus refill. It is division. The pool finishes a roughly fixed number of turns in 30 minutes, and concurrency decides how many sessions share them.

| baseline | sessions started | turns finished | turns per session |
|---|---|---|---|
| c=48 | 81 | 3740 | 46.2 |
| c=128 | 142 | 3026 | 21.3 |
| c=192 | 193 | 2933 | 15.2 |
| c=338 | 338 | 3321 | 9.8 |

At c=48 the 48-slot pool churns through 81 sessions and each reaches turn 46. At c=338 all 338 start at once and each reaches turn 10. Corpus refill does happen below c=256, but it works against depth rather than for it: more sessions started means the same finished turns are spread thinner.

This is a property of the experiment, not of the schedulers, and it affects both arms identically. It does mean the levels are not measuring the same workload, so the curve should not be read as a pure capacity curve.

## 3. What the scheduler actually controls

Above saturation the binding resource is prefill work, and the relation is exact:

```
requests completed = prefill throughput x 1800 / prefill tokens per request
```

| c=338 | prefill per request | prefill tok/s | requests completed | output tok/s |
|---|---|---|---|---|
| baseline | 48,846 | 90,122 | 3321 | 1050 |
| thunder | 35,310 | 92,786 | 4730 | 1538 |

Both arms saturate the same hardware at the same total token rate. Thunder wins by making each request cheaper: a 0.236 hit rate against 0.002 cuts prefill per request by 28 percent, which buys 42 percent more requests. That is the entire mechanism of the 1.46x, and it is the only lever a scheduler has once the pool is saturated.

It also explains the U shape of the thunder curve. Thunder dips to 1342 at c=192 and recovers to 1538 at c=338 because its hit rate stops falling (0.309 to 0.236) while the extra offered load fills the pipeline more completely.

## 4. Can a better algorithm push turns deeper?

Not materially, at a fixed concurrency. Turns per session is total turns divided by sessions, and the numerator is capped by the hardware. To give all 338 sessions the 46 turns they reach at c=48 would take 15,548 finished turns in 30 minutes, 3.3x what thunder achieves. No admission policy creates that capacity.

What is still on the table is the prefill cost per request. Thunder holds a 0.236 hit rate at c=338, and Part 3 of `../proposal/PROPOSAL.md` identifies where most of the rest leaks: about 70 percent of resumes move the session to a different pod and pay a full re-prefill. If origin-only resume lifted the hit rate to 0.5, prefill per request would fall from 35.3k to about 23.1k and the same prefill budget would finish roughly 7200 requests, about 1.5x more than now.

That estimate is optimistic because decode also consumes time and the relation above ignores it, but the direction and the order of magnitude are supported by the measurements here. It is the strongest argument for running Part 3 next.

## 5. What to change in the harness

- **Report prefill tok/s alongside output tok/s.** One extra row makes the curve self-explanatory instead of looking like a system that slows down under load.
- **Report the working set against KV capacity.** It locates the knee without the reader having to derive it.
- **Fix the population confound before drawing capacity conclusions.** Replay is deterministic, so requests can be paired across cells on `graph_event_id` and only the requests present at every level compared. Alternatively size the corpus well above the highest concurrency so every level reaches a comparable depth.
- **Do not quote ratios against c=48.** That cell is demand-limited, not capacity-limited.

## Summary

| question | answer |
|---|---|
| Does throughput really fall? | No. Total token work rises 6.6x. Output tokens fall because prefill crowds out decode. |
| Are we saturated? | Yes, from c=128, where the working set reaches 0.87x the KV pool. Total throughput plateaus at 87k to 94k tok/s. |
| Is the shallow turn depth an algorithm failure? | No. It is total turns divided by session count, and the numerator is hardware-capped. |
| Does the algorithm matter? | Yes, entirely through prefill cost per request. Thunder cuts it 28 percent and gets 42 percent more requests. |
| How much headroom is left? | Raising the hit rate from 0.236 to 0.5 would be worth roughly 1.5x. Proposal Part 3 targets exactly that. |
