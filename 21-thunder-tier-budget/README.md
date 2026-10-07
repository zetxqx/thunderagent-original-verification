# Step 21: the lease gate with an offload tier budget (plan)

Status: one run on 2026-10-02 (00:28 to 03:55); see "Result" at the end. Plan written 2026-10-02.

## Question

Step 20 (CPU KV offloading, 400 GiB, single replicas, 3 runs) found two gates, each good at one thing:

- **GPU tier** (lease gate sized to GPU KV): low median TTFT (0.5 to 7 s) and the best throughput at c = 64 and 128 (1.12 to 1.13x llm-d default). But from c = 128 its p99 TTFT reaches the 1800 s forced admission, and at c = 192 and 256 its CPU hit rate is only 0.27 to 0.28.
- **CPU tier** (the same gate sized to the CPU tier): the best reuse and throughput at c = 192 and 256 (0.77 to 0.81 reuse). But it never holds anyone below that, so vLLM queues 30 to 110 requests and the median TTFT is 44 to 162 s.

The GPU tier loses reuse at high load because a paused session stops counting anywhere. New sessions keep being admitted until the paused sessions lose their copy in the CPU tier, so they recompute when they return.

llm-d-router commit `a13a87ed` (branch `thunder-agent-lease-tier`, on `thunder-agent-lease-main`) adds `offloadCapacityTokens`:

- **GPU room:** admission stays sized to GPU KV, as in the GPU tier arm.
- **Tier budget:** each endpoint also has a tier budget that counts every bound session, paused ones included.
- **New sessions:** a new session needs tier room as well as GPU room. The room is made by unbinding paused sessions, longest idle first.
- **Paused sessions:** a paused session's next turn needs only GPU room, and its KV should come back from the CPU tier.

The questions:

1. Does the tier budget keep the GPU tier's low median TTFT while bringing reuse and throughput at high c up to the CPU tier's?
2. How much of the GPU tier's tail comes from the 30 s lease? With a CPU tier a pause is cheap, so a shorter lease (5 s) may rotate sessions faster.

## Arms

A 2 x 2 design: tier budget off or on, lease 30 s or 5 s. Off with 30 s is step 20's GPU tier arm (3 runs). Its code path is unchanged when `offloadCapacityTokens` is 0, so the three other cells run here as the three lanes.

| arm (plugin file in `../10-llm-d-router-replicates/`) | `offloadCapacityTokens` | `idleLeaseSeconds` |
|---|---|---|
| step 20 `thunder-lease-main` (reference, not rerun) | 0 | 30 |
| `thunder-lease-budget30` | 8,738,133 | 30 |
| `thunder-lease-budget5` | 8,738,133 | 5 |
| `thunder-lease-main5` | 0 | 5 |

- All three arms use the scraped GPU capacity, so the step 20 `cacheInfoSpec: ""` setup is not needed.
- The names avoid the suffix `-tier`, which the lane driver reserves for step 20's CPU tier arm.
- Other keys are as in step 20: `utilThreshold` 1.0, `headWaitStarvationMs` 1,800,000, `evictionTtlSeconds` 3600.

## Setup

The same as step 20 phase B:

- 3 single vLLM replicas with the 400 GiB CPU tier, one per node (`../20-cpu-offload-pool/vllm-deploy-3rep-offload400.yaml`), with one lane EPP each.
- inference-perf `session-id-v1`, client timeout 1900 s.
- Cache reset with `reset_external=true` and a `success` check before every cell.
- **New EPP image:** `thunder-agent-lease-tier-a13a87ed`, built from `a13a87ed` with Cloud Build. It is pinned by an annotated tag of the same name on `zetxqx/llm-d-router` once the branch is pushed.

## Cells

Concurrency 64, 128, 192 and 256 per replica. At c = 32 the gates barely act (step 20: 1.03x), so it is left out.

- **Replicates:** 3, rotating lanes as in step 20 (`REP=1..3`), so each arm runs once on each pod at each point.
- **Windows:** 30 min at c = 64 and 128, 45 min at c = 192 and 256.
- **Time:** about 3.3 hours per replicate, about 10 hours for three, plus about 15 minutes for the rollout, smoke test and restore.
- **One replicate first?** Running 1 replicate first (about 3.5 hours) and deciding on more after looking at it is an option.

## Expectations (written before the run)

**`budget30` against step 20's GPU tier (same lease):**

- c = 64 and 128: about the same as the GPU tier. The tier budget is not reached yet (working set / tier 0.4 to 0.5).
- c = 192 and 256:
  - fewer new sessions admitted;
  - paused sessions return from the CPU tier, so the CPU hit rate rises well above 0.28;
  - total reuse and throughput approach or pass the CPU tier's (569 and 533 tok/s);
  - the median TTFT stays low;
  - holds of new sessions may rise, and forced admissions may rise with them.

**Lease 5 s against 30 s:**

- more pauses, resumes and CPU loads;
- shorter holds;
- a lower p99 TTFT and fewer forced admissions.

**Risk:** a short lease may pause sessions that come back within seconds, which could cost GPU hits and throughput, mostly without the tier budget (`main5`).

## Measurements

The same as step 20 (`../20-cpu-offload-pool/analyze.py`, `make_figures.py`), reused by pointing them at this step's results. Two additions:

- `thunder_agent_endpoint_resident_tokens` against the tier budget, as a time series;
- `thunder_agent_tier_drops_total`, the paused sessions unbound to make tier room.

## Files to write

- The three plugin files in `../10-llm-d-router-replicates/`.
- `run-all.sh`, built from step 20's `run-replicates-B.sh`:
  - check the original state;
  - offloading on, smoke test;
  - `REP=1..3 run-cells.sh` with this step's arm table;
  - restore, analysis.
  It reuses step 20's `lib.sh`, `offload.sh`, `lanes.sh` and `smoke-test.sh` with this step's `results/`.
- A smoke check that the budget arms export `endpoint_resident_tokens` and `tier_drops_total` and report the GPU capacity (2,237,040).

## Order

1. Push branch `thunder-agent-lease-tier` to `zetxqx/llm-d-router` (needs your approval), tag `thunder-agent-lease-tier-a13a87ed`, and build the image.
2. Write the files above, then dry-run the arm configs through the production config loader (as in step 20's checks).
3. Run, then analyze.

## Result (2026-10-02, one run)

The run went from 00:28 to 03:55.

- **Build:** image `thunder-agent-lease-tier-a13a87ed`, built from the local commit `a13a87ed` (branch `thunder-agent-lease-tier`, not pushed at the time of the run).
- **Smoke test:** all 82 checks passed (`results/smoke-test-output.txt`).
- **Completeness:** all 12 cells completed, with no preemption and no vLLM restart. The model server and main release were restored and checked.
- **Comparison:** step 20's numbers are the mean of 3 runs; step 21 is one run per arm.

**Output throughput (tok/s):**

| c | step 20 GPU tier | step 20 CPU tier | budget30 | budget5 | main5 |
|---|---|---|---|---|---|
| 64 | 636 | 566 | 612 | 593 | 633 |
| 128 | 635 | 579 | 608 | 650 | 632 |
| 192 | 551 | 569 | 546 | 544 | 554 |
| 256 | 516 | 533 | 504 | 507 | 535 |

**At c = 256:**

| | step 20 GPU tier | budget30 | budget5 | main5 |
|---|---|---|---|---|
| total reuse, steady | 0.69 | 0.73 | 0.70 | 0.71 |
| median TTFT | 7.3 s | 5.9 s | 3.9 s | 6.3 s |
| p99 TTFT | 1852 s | 1847 s | 1848 s | 1840 s |
| forced admissions | 163 | 170 | 154 | 148 |

### Readings

1. **The tier budget did not change the results.** The three new arms are within single-run pod noise (3 to 6 percent) of the step 20 GPU tier arm at every point. Their median TTFT is as low and vLLM barely queues. At c = 192, budget30's CPU hit rate rose to 0.37 (GPU tier 0.27), but total reuse and throughput did not follow.
2. **The 5 s lease did not cut the tail.** It lowered the p99 at c = 128 once (1183 s against about 1650 s). From c = 192 every arm's p99 sits at the 1800 s forced admission.
3. **Why: the starvation backstop bypasses both budgets.** The budget arms' resident footprint (`thunder_agent_endpoint_resident_tokens`) reached 13 to 16M tokens at c = 192 and 256, against a tier budget of 8.74M, even though the gate dropped 76 to 153 paused sessions to make tier room. Two paths bypass the budgets: forced admissions (104 to 170 per 45-minute cell at those points), and the growth of admitted sessions, whose turns always dispatch. At c = 64 and 128 the budget was not reached (no drops). At c = 192 budget5 never dropped anyone, because with a 5 s lease a paused session's next turn is queued almost at once, and queued sessions are not dropped.

### Conclusion

In overload, all gates reach 500 to 550 tok/s: the limit set by GPU bandwidth and GPU KV. The step 20 CPU tier arm, the best case for tier control, is only about 3 percent above the GPU tier arm at c = 256. An admission rule decides who waits, not how much work gets done.

Two replicates more of this design are not planned. Directions with more promise:

- **A time slice:** when sessions are held, pause an admitted session between turns after a quantum, so held sessions get in; this bounds the wait instead of leaving it to the 1800 s backstop.
- **Held demand as an autoscaling signal.**

### Figures

`make_figures.py` writes `figures/` (PNG and PDF). It compares the three arms with step 20's GPU tier and CPU tier arms (mean of 3 runs, min-max lines).

- `fig1-throughput`: output throughput.
- `fig2-reuse`: total prefix reuse and the CPU tier hit rate.
- `fig3-wait`: median TTFT, p99 TTFT and forced admissions.
- `fig4-tier-budget`: at c = 192 and 256, the budget arms' resident footprint against the 8.74M tier budget, and forced admissions over time. Forced admissions start at 30 minutes (the 1800 s backstop), and the footprint passes the budget before that. The drop at about 48 minutes is after the bench ends.
