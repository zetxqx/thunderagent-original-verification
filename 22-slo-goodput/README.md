# Step 22: goodput under a TTFT SLO (analysis, no new runs)

Status: done on 2026-10-02 from the per-request reports of step 20 (phase A and B) and step 21.

## Question

Under overload every arm reaches about the same peak throughput, because it is limited by the GPU (steps 20 and 21). Production cares about something else: how much work a replica does **within a latency target**, and so how many replicas a load needs. How do the arms compare on that?

## Method

`goodput.py` reads every cell's `per_request_lifecycle_metrics.json` (66 cells) and scores the steady state (after the warm-up, before the window ends) against TTFT SLOs of 2 to 120 s:

- **goodput at X s:** output tokens per second generated in the steady state by turns with TTFT <= X. Tokens are counted by their timestamps (`output_token_times`).
- **turn share:** share of the turns started in the steady state that meet X. A turn with an error is a miss.
- **session share:** share of the sessions live in the steady state whose every steady turn meets X.
- **capacity:** the largest tested c per replica where the target holds at that point and at every smaller one.

Two notes on the numbers:

- **Throughput differs from step 20's.** "Throughput, steady state" here is lower than step 20's throughput, because step 20 counts the whole window, warm-up included, when prompts are still short.
- **Some turns are missing.** The report keeps a turn only if it ends within about 120 s after the window. A turn still waiting then is missing, so the turn shares and TTFT percentiles are slightly optimistic for arms with long waits. Goodput is not affected.

Run: `uv run --with matplotlib --with numpy python goodput.py` (results in `results/goodput.md`, figures in `figures/`; delete `results/goodput-data.json` to recompute).

## Result

**Goodput, TTFT <= 30 s (tok/s), phase B (400 GiB CPU tier), mean of 3 runs:**

| c | llm-d default | GPU tier | CPU tier |
|---|---|---|---|
| 32 | 465 | 495 | 472 |
| 64 | 0 | 552 | 1 |
| 128 | 0 | 533 | 0 |
| 192 | 0 | 420 | 0 |
| 256 | 0 | 348 | 0 |

**Capacity per replica (largest tested c):**

| target | llm-d default | GPU tier | CPU tier |
|---|---|---|---|
| p90 TTFT <= 30 s | 32 | 128 | 32 |
| 90% of turns <= 30 s | 32 | 128 | 32 |
| p99 TTFT <= 120 s | 64 | below 32 | 64 |

### Readings

1. **Goodput is where the gate wins.** With a 10 or 30 s SLO, the GPU tier gate keeps 530 to 550 tok/s of goodput up to c = 128. Both ungated arms (llm-d default and the CPU tier gate, which never holds anyone below c = 192) fall to 0 at c = 64: every session has a request queued in vLLM, so every turn waits 30 to 90 s (`figures/fig2-ttft-cdf.png`). For a 30 s p90 target, one gated replica carries at least 4x the sessions of an ungated one (128 against 32). The real ratio needs finer points between 32 and 64 and between 128 and 192.
2. **The cost is the tail.** The gate does not make waiting disappear; it gives it to fewer turns. The GPU tier's p99 TTFT is 300 to 1200 s at every point, against 38 to 583 s for llm-d default. No arm meets "p99 <= 30 s" at any tested point, and the gate does not meet "p99 <= 120 s" even at c = 32.
3. **Per session, about half are fully served.** At c = 64 and 128, 44 percent of sessions have every turn within 30 s with the gate, and 0 percent without it. Even at c = 32 only about 50 percent do in every arm, because a session with many turns usually has at least one long prefill.
4. **Offloading helps only the gated arm.** Offloading adds 60 to 110 tok/s of goodput to the gated arm (phase A against B), but the ungated arms stay at 0 from c = 64 with or without it.
5. **Step 21's arms match the GPU tier** within single-run noise (see `results/goodput.md`).

### What this means

- The gate is admission control. When load is above what fits, it serves the admitted sessions fast and makes the others wait at the door, instead of making everyone wait inside vLLM.
- With a TTFT SLO, this moves the point where a replica "breaks" from about 32 to about 128 sessions in this workload. In production that means fewer replicas for the same SLO, as long as the held sessions are handled. Ways to handle them: autoscale on held demand, reject them, or bound their wait (for example with the time slice from step 21).

## Possible follow-up runs

- **Find the knees:** llm-d default at c = 40, 48, 56, and the GPU tier at c = 144, 160, 176, to measure the capacity ratio instead of bounding it.
- **Open-loop arrivals:** session arrivals at a fixed rate, so held sessions show up as a growing queue, the signal an autoscaler would use.
