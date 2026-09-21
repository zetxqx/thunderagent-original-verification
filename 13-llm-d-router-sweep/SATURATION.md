# Why throughput falls as concurrency rises, and how to choose the saturation point

Written 2026-09-20 from the step 13 sweep (`results/sweep-20260918-134248-t1900`, 4 vLLM pods behind one EPP, Qwen3-Coder-30B-A3B FP8 at TP=2 on H100, weka agentic traces, 30-minute cells). Numbers are one cell per arm and level; the step README lists the caveats.

## The observation

Output throughput of the whole pool peaks at 12 to 16 active sessions per pod and then falls. It does not plateau.

| active sessions per pod | 4 | 8 | 12 | 16 | 24 | 32 | 48 | 64 | 84 |
|---|---|---|---|---|---|---|---|---|---|
| llm-d default, output tok/s | 1278 | 1782 | **2014** | 1956 | 1541 | 1151 | 1065 | 999 | 1050 |
| port (most-room), output tok/s | 1247 | 1775 | 1972 | 1974 | 1536 | 1382 | 1342 | 1438 | 1538 |
| port (origin-only), output tok/s | - | - | - | - | 1813 | 1571 | 1639 | 1633 | 1698 |
| per-stream decode interval, ITL p50 (ms) | 10 | 15 | 20 | 29 | 38 | 40 | | | |
| pool KV usage (mean) | 0.13 | 0.24 | 0.33 | 0.42 | 0.60 | 0.68 | 0.73 | 0.74 | 0.75 |
| steady-state prefix hit rate, llm-d default | 0.95 | 0.95 | 0.95 | 0.93 | 0.63 | 0.04 | 0.003 | 0.002 | 0.002 |
| requests waiting inside vLLM, llm-d default | 0 | 0 | 0 | 0 | 4 | 15 | 50 | 93 | 152 |
| mean prompt length (tokens) | 95k | 89k | 84k | 77k | 70k | 61k | | | |

(ITL and prompt length are from the inference-perf summary reports; they are the same for both arms at each level to within 1 percent, so one value is shown.)

## Why it falls instead of flattening

The load is closed-loop: each session has at most one request in flight, and it issues the next turn only after the previous one completes. For N active sessions, throughput = N / (mean turn latency) x (mean output tokens per turn). Doubling N raises throughput only if turn latency grows by less than 2x. Past 12 to 16 sessions per pod it grows faster than N, for three reasons that appear in order as load rises.

### 1. Decode is memory-bandwidth-bound on long contexts, so a larger batch does not add decode throughput

Every decode step reads the KV cache of every running request. With prompts of 60k to 95k tokens, that read dominates the step time, and it scales with the number of running requests times their context length. The measured ITL p50 rises 10, 15, 20, 29, 38 ms as sessions per pod go 4, 8, 12, 16, 24: roughly proportional to the running batch. When step time grows linearly with batch size, tokens per second per pod (batch / step time) stops growing. This is the opposite of the short-prompt chat regime, where decode is weight-bandwidth-bound and a larger batch is nearly free.

This sets the peak. At 12 to 16 sessions per pod the pool's KV is only 33 to 42 percent full and nothing waits inside vLLM, so the peak is not a capacity or queueing limit. It is where attention bandwidth becomes the binding constraint. Both schedulers peak at the same place and height (2014 vs 1972 tok/s at 12 per pod, within noise), because nothing a router does changes this term.

### 2. Past the peak, prefix-cache hits turn into prefill work

Above 16 sessions per pod the resident set of prefixes no longer fits: the llm-d default's steady-state hit rate goes 0.93, 0.63, 0.04 at 16, 24, 32. Each agentic turn resends the whole history, so a miss means recomputing tens of thousands of prompt tokens. Prefill steps produce no output tokens and, with chunked prefill, they take engine steps away from every stream that is decoding. This is visible as ITL mean rising far above ITL p50 (at 32 per pod: 105 vs 40 ms for the default, 90 vs 40 ms for the port): the median decode step is unchanged, the mean is inflated by long gaps where the engine was prefilling someone else's missed prefix.

This is the term that makes the curve fall rather than flatten, and it is the term the ThunderAgent gate removes. By pausing idle sessions so that the running set's prefixes stay resident, the port keeps the hit rate at 0.25 to 0.35 (most-room) or 0.42 to 0.63 (origin-only) where the default has 0.002, and its throughput curve past the peak is flat (1382 to 1698 tok/s) where the default's keeps falling (1151 to 999).

### 3. Then queueing inside the engine

From 24 sessions per pod the llm-d default accumulates requests in vLLM's waiting queue (4, 15, 50, 93, 152). Those requests hold no KV yet and simply wait; their TTFT grows linearly with load (p50 8, 36, 66, 101 s at 32, 48, 64, 84 per pod). The port keeps the engine queue at about 1 request at every level and holds the excess in the EPP instead, where it costs nothing in engine time.

### A confound to keep in mind

The workload mix shifts with concurrency. Sessions that finish are replaced by fresh traces, and at low concurrency sessions progress deep into long-prompt turns while at high concurrency they do not: the mean prompt is 95k tokens at 4 per pod and 61k at 32. Absolute throughput across levels is therefore not a fixed-workload comparison. Within a level the arms see the same mix (prompt means agree within 1 percent), so the arm comparison is clean.

## Three different "saturation points"

The word covers three distinct things on this curve. Naming which one is meant avoids most confusion about choosing concurrency.

| definition | where it is on this pool | what it is for |
|---|---|---|
| **Throughput peak**: adding sessions no longer raises total output | 12 to 16 sessions per pod, about 2000 tok/s, same for every scheduler | the most economical production operating point; sessions beyond it are pure loss in total output |
| **SLO capacity**: the largest load at which the user-facing SLO still holds | llm-d default 24 to 32 per pod, the port about 64 per pod at TTFT p90 <= 30 s; see the caveat below | the maximum safe production load and the autoscaling trigger |
| **Collapse point**: cache hit rate goes to zero and the engine queue grows without bound | llm-d default at 32 per pod; the port does not collapse in the measured range | the regime a scheduler benchmark must cover, because below it schedulers are indistinguishable |

Caveat on the SLO row: it is estimated from request-level TTFT percentiles, which hide sessions that were held for a long time (proposal Part 7). Under the port the misses are concentrated in sessions at the door (turns 0 to 9 wait, deeper turns are fast), so the session-level capacity may be lower than 64 per pod. Part 7's session SLO attainment is the metric to settle it.

## What the scheduler changes and what it cannot

- It cannot move the peak. The peak is set by bytes of KV per token, HBM bandwidth and prompt length. Below it the two arms are identical: ratios 0.98, 1.00, 0.98, 1.01 at 4 to 16 sessions per pod, with the gate essentially idle (0 to 53 pauses, 0 holds per cell).
- It changes the shape past the peak: flat instead of falling. That is the whole 1.2x to 1.6x gain, and it grows with overload because the default keeps losing hit rate while the port has already lost what it will lose.
- It changes where the wait happens: in the EPP, before the engine, instead of inside the engine where waiting requests compete for steps. The visible cost is that the wait falls on a minority of sessions rather than on all requests equally (again Part 7).

## Per-session progress, the number an operator feels

Because each session moves at pool throughput divided by session count, load translates directly into how many turns a session completes per unit time:

| sessions per pod | turns per session per 30 min, llm-d default | turns per session per 30 min, port (best arm) | time for a 60-turn session, port (best arm) |
|---|---|---|---|
| 4 | 137 | 134 | 13 min |
| 12 | 78 | 76 | 24 min |
| 24 | 37 | 43 | 42 min |
| 48 | 15 | 23 | 78 min |
| 84 | 9.8 | 15 | 2 h (3 h under the default) |

Sessions do finish at high load, just late. They fail to finish only when a client timeout or an SLO is shorter than that wait. Step 08's 600 s client timeout produced exactly that failure; at 1900 s no session in step 13 was lost (0 errors in 22 of 24 cells, 2 corpus-related 400s in the other two), and forced admissions at 1800 s stayed at 0 to 10 per cell.

## How to choose

For a scheduler experiment:

- Use sessions per pod as the axis, not total concurrency, so results transfer across pool sizes.
- Cover the peak (to show the scheduler is free there), the collapse point of the baseline, and 2 to 3x beyond it. Step 13's 4 to 84 per pod does this; going higher only stretches the per-session wait linearly and adds no information.
- Keep the client timeout above the forced-admission backstop (1800 s here). A shorter timeout measures workload trimming, not scheduling.
- Report capacity at SLO with session-level metrics (Part 7), not a throughput ratio at one arbitrary load.

For a production operating point:

- Nobody chooses concurrency; users do. The operator chooses how many sessions a pod actually runs, which is what the port's `utilThreshold` and pause sweep implement. Run at or just below the throughput peak for efficiency, and up to the SLO capacity when demand requires it.
- Treat a growing paused set, holds, or any forced admissions as the scale-out signal: they mean demand is past the SLO capacity of the current pool.

To locate the peak on a new model, GPU or prompt distribution:

- Sweep sessions per pod on a geometric grid (4, 8, 12, 16, 24, 32), 30 minutes each, any scheduler.
- Watch two curves: output throughput, and ITL p50 against sessions per pod. The peak is where throughput stops rising, and it coincides with ITL starting to grow linearly with the batch. The KV-usage fraction at that point tells you how far below capacity the bandwidth limit sits (here about 0.4).
- Longer prompts move the peak left; more HBM bandwidth per token of KV (smaller KV per token, more GPUs per replica) moves it right.

## Related

- `README.md` in this directory: the full step 13 tables, the origin-only arm and the caveats.
- `../proposal/PROPOSAL.md` Part 7: the session-level metrics that should replace request-level TTFT for the SLO capacity claim.
- `../proposal/PROPOSAL.md` Part 5: CPU KV offloading, which attacks term 2 (prefill from misses) from the engine side and could change how much of the port's gain remains.
