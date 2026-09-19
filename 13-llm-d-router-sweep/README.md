# Step 13: concurrency sweep, llm-d default vs the ThunderAgent port, on the 4-pod pool

Question: how does the port's gain over llm-d's default profile depend on load, and where is the crossover. Step 12 measured one point (c=338, 1.42x). This step draws the curve.

## Design

- Arms: `epp-baseline` (prefix-cache, queue and KV scorers) and `epp-thunder` (the port, step 12 config, pod-hopping resume left as is; see `../proposal/PROPOSAL.md` Part 3). Same EPP, same cache reset and restart per cell, same fixed load generator (`../12-llm-d-router-pool/results/inference-perf-image.txt`).
- Levels: c = 48, 96, 128, 192, 256, 338 active sessions on the pool, i.e. 12, 24, 32, 48, 64, 85 per pod. At about 50k prompt tokens per session, one pod's 2.24M-token KV is filled by the running requests alone somewhere between 32 and 48 sessions per pod.
- 30 minutes per cell (10 min warm-up, 20 min steady state), one cell per arm and level, arm order alternated per level. 12 cells, about 8 hours.
- Client timeout 1900 s, so the workload is not trimmed at any level.
- One change from step 12: the bench pod now runs on the non-spot `default-pool` (8 cores requested, 16 limit) instead of the spot H100 nodes. Step 08 put it on the H100 nodes for 24 cores under the v0.7.0 permit bug; the fixed generator used 2.3 cores median and 10 peak at c=338. A spot preemption therefore no longer takes the load generator down with it, and preempted cells are simply voided and rerun.

Pre-registered expectations:

- At 12 and 24 sessions per pod both arms are close to each other with high hit rates; thunder may be slightly slower there (flow-control round trip per turn, occasional sweep pauses) and if so that is a finding: the gate should engage only under pressure.
- The arms separate between 32 and 48 sessions per pod, where the running set alone fills the KV and baseline's waiting queue inside vLLM starts to grow.
- At 64 and 85 the gap approaches step 12's 1.42x on throughput and two orders of magnitude on hit rate.
- Baseline's requests waiting inside vLLM should rise monotonically with load; thunder's should stay near zero above the crossover, with the wait moving into the EPP queue.

## Files

- `run-sweep.sh [levels] [window_s]`: drives step 12's `run-pool.sh` once per level and arm pair, all cells into one run directory named `sweep-<timestamp>-t1900`, cells named `epp-<arm>-c<level>`.
- `analyze_sweep.py`: per-level tables (`sweep.md`) and the four-panel curve figure (`sweep.png`): throughput, steady-state hit rate, TTFT p50 and requests waiting inside vLLM against active sessions per pod.

## Results

Run `results/sweep-20260918-134248-t1900` (2026-09-18 13:42 to 23:35 PDT). All 12 cells completed, no preemption, 0 request errors in every cell. Full tables in `sweep.md`, curves in `sweep.png`.

| c | sessions/pod | throughput baseline / thunder (tok/s) | ratio | steady-state hit rate baseline / thunder | TTFT p50 baseline / thunder (s) | waiting inside vLLM baseline / thunder | thunder resumes that changed pod |
|---|---|---|---|---|---|---|---|
| 48 | 12 | 2014 / 1972 | 0.98x | 0.952 / 0.948 | 0.4 / 0.4 | 0 / 0 | 0 of 2 |
| 96 | 24 | 1541 / 1536 | 1.00x | 0.625 / 0.602 | 0.5 / 0.5 | 4 / 1 | 461 of 949 (49%) |
| 128 | 32 | 1151 / 1382 | 1.20x | 0.040 / 0.353 | 8.2 / 2.3 | 15 / 1 | 1079 of 1797 (60%) |
| 192 | 48 | 1065 / 1342 | 1.26x | 0.003 / 0.301 | 36.0 / 3.2 | 50 / 1 | 1808 of 2619 (69%) |
| 256 | 64 | 999 / 1438 | 1.44x | 0.002 / 0.266 | 65.8 / 3.4 | 93 / 1 | 2169 of 3157 (69%) |
| 338 | 84 | 1050 / 1538 | 1.46x | 0.002 / 0.249 | 101.5 / 3.5 | 152 / 1 | 2428 of 3440 (71%) |

Findings, against the pre-registered expectations:

1. **The crossover is between 24 and 32 sessions per pod**, earlier than the expected 32 to 48. At 24 per pod the arms tie on throughput, but baseline's TTFT p90 is already 1.7x thunder's (14.0 vs 8.1 s) and vLLM starts to queue. At 32 per pod baseline's steady-state hit rate collapses from 0.63 to 0.04 while thunder keeps 0.35.
2. **Below the crossover thunder costs about 2 percent** (c=48: 1972 vs 2014 tok/s, 19 pauses, 0 holds). This is the flow-control round trip and a few unnecessary pauses on a pool that never fills; as pre-registered, the gate should engage only under pressure.
3. **The gain grows with load to 1.44x at 64 and 1.46x at 84 sessions per pod**, matching step 12's replicated 1.42x (plus or minus 0.3 percent) at c=338. Thunder's throughput is flat to slightly rising from 32 per pod on (1382, 1342, 1438, 1538) while baseline keeps falling to about 1000 tok/s.
4. **TTFT p50 stays at 2 to 4 s for thunder at every level above the crossover; baseline's grows linearly with load to 101 s.** Baseline's wait sits inside vLLM (mean 4, 15, 50, 93, 152 requests waiting), thunder's inside the EPP (mean 1 waiting in vLLM at every level; 280 to 1716 holds per cell). Forced admissions are 0 up to 48 per pod, 2 at 64, 7 at 84.
5. **Pod hopping is the port's largest remaining loss and it grows with load.** The share of resumes that moved the program to a different pod is 49, 60, 69, 69, 71 percent from c=96 up (`rebinds_total` / `resumes_total`). This is why thunder's hit rate on the pool (0.25 to 0.35) sits below its single-pod value at the same per-pod pressure (0.55 in step 10 at 32 per pod) and why it does not beat baseline at c=96, where baseline still hits 0.63 and every move costs a full 60k-token prefill. `../proposal/PROPOSAL.md` Part 3 (origin-only resume) targets exactly this.

Why throughput falls with load in both arms (asked during the run): the pool is past its output-throughput peak at 12 sessions per pod already. Per-stream decode interval (ITL p50) doubles from 20 ms at 12 per pod to 38 ms at 24 and stays at 40 ms above, so the engines are memory-bandwidth-bound on attention over 60k to 84k-token contexts and a larger batch does not add decode throughput. On top of that, lost prefix hits turn into prefill work that steals steps from decoding; this shows as ITL mean rising far above ITL p50 (105 vs 40 ms for baseline at c=128, 90 vs 40 for thunder). Thunder's gain is in avoiding the second effect, not in raising the peak. The peak itself was not measured; c=16, 24, 32 would locate it.

Caveats:

- One cell per arm and level, so no error bars. The c=338 point reproduces step 12's three-replicate result, which had a spread of 0.3 percent on throughput.
- Absolute throughput is not comparable across levels: with 30-minute cells, low-concurrency sessions progress deeper, so the mean prompt is 84k tokens at c=48 and 61k at c=128. Within a level the arms' prompt means agree to within 1 percent, so the arm comparison is clean.
- The `epp-thunder-c256` cell was collected by hand. The driver's bench-pod name lookup returned empty on a transient API error, so its DONE poll spun forever while the cell ran normally inside the pod (bench reported completion, prober captured all metrics); artifacts were copied with the same commands the driver uses and the manifest carries a note. `../12-llm-d-router-pool/run-pool.sh` now retries the lookup until it gets a name. The stuck driver was killed and the last level (c=338, order thunder then baseline as planned) was relaunched into the same run directory at 21:46.
- A first launch at 11:30 was interrupted by the user during its first cell; that cell was voided (job deleted, directory removed) before this run.
- Cells took 42 to 53 minutes end to end for a 30-minute window; the whole sweep took just under 10 hours.
