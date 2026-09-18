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

(filled in after the run)
