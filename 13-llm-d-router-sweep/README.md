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

- `SATURATION.md`: why throughput falls with concurrency on this workload, the three meanings of "saturation point" (throughput peak, SLO capacity, collapse), and how to choose concurrency for experiments and for production.

- `run-sweep.sh [levels] [window_s]`: drives step 12's `run-pool.sh` once per level and arm pair, all cells into one run directory named `sweep-<timestamp>-t1900`, cells named `epp-<arm>-c<level>`.
- `analyze_sweep.py`: per-level tables (`sweep.md`, one column per arm present plus thunder/baseline and origin/thunder ratios, including rebinds, origin waits and sessions replaced) and the four-panel curve figure (`sweep.png`, log x axis): throughput, steady-state hit rate, TTFT p50 and requests waiting inside vLLM against active sessions per pod.
- `analyze_long.py [run_dir] [slice_seconds] [cell_suffix]`: the 90-minute cells sliced into 30-minute windows (`long.md`, `long.png`).
- `run-origin-replicates.sh`: replicates 2 and 3 of most-room and origin-only at c=96 and c=128 (v4 image, session-id bench image); `analyze_replicates.py` writes `replicates.md` and `replicates.png` with cell-level means and min-max plus the Part 7 session-level metrics for cells whose report carries session ids.
- `run-origin.sh [levels]`: the `epp-thunder-origin` arm (`EPP_IMAGE_TAG=thunder-agent-v4`, `../12-llm-d-router-pool/thunder-origin-plugins.yaml`) appended to an existing run given by `AB_ID`, with the v4 control cell at c=192.

## Results

Run `results/sweep-20260918-134248-t1900`: six levels on 2026-09-18 (13:42 to 23:35 PDT), three lower levels c = 16, 32, 64 appended on 2026-09-19 (10:24 to 15:15) to locate the throughput peak, then the `epp-thunder-origin` arm at c = 96 to 338 plus a v4 control cell (2026-09-19 15:37 to 2026-09-20 00:05), then two more replicates per arm at c = 96 and 128 (2026-09-20 01:00 to 08:35) one llm-d default cell per level with the session-id bench image (09:39 to 11:15), and three 90-minute cells at c=128 (15:25 to 21:34). 37 valid cells, no preemption; every cell of the first two arms had 0 request errors, two origin cells had 2 each (`400 - Context Window`). Full tables in `sweep.md` (including a `sessions completed and replaced` row), curves in `sweep.png` (log-scale x axis).

The table below compares the two arms at each level. For the other question this sweep answers, why throughput falls as concurrency rises within an arm, see `RESULTS.md`: the short version is that the pool does 6.6x more token work at c=338 than at c=48 and the metric counts only the decode half.

| c | sessions/pod | throughput baseline / thunder (tok/s) | ratio | steady-state hit rate baseline / thunder | TTFT p50 baseline / thunder (s) | waiting inside vLLM baseline / thunder | thunder resumes that changed pod |
|---|---|---|---|---|---|---|---|
| 16 | 4 | 1278 / 1247 | 0.98x | 0.947 / 0.945 | 0.5 / 0.4 | 0 / 0 | 0 of 0 |
| 32 | 8 | 1782 / 1775 | 1.00x | 0.953 / 0.952 | 0.5 / 0.4 | 0 / 0 | 0 of 1 |
| 48 | 12 | 2014 / 1972 | 0.98x | 0.952 / 0.948 | 0.4 / 0.4 | 0 / 0 | 0 of 2 |
| 64 | 16 | 1956 / 1974 | 1.01x | 0.930 / 0.926 | 0.4 / 0.4 | 0 / 0 | 1 of 26 |
| 96 | 24 | 1541 / 1536 | 1.00x | 0.625 / 0.602 | 0.5 / 0.5 | 4 / 1 | 461 of 949 (49%) |
| 128 | 32 | 1151 / 1382 | 1.20x | 0.040 / 0.353 | 8.2 / 2.3 | 15 / 1 | 1079 of 1797 (60%) |
| 192 | 48 | 1065 / 1342 | 1.26x | 0.003 / 0.301 | 36.0 / 3.2 | 50 / 1 | 1808 of 2619 (69%) |
| 256 | 64 | 999 / 1438 | 1.44x | 0.002 / 0.266 | 65.8 / 3.4 | 93 / 1 | 2169 of 3157 (69%) |
| 338 | 84 | 1050 / 1538 | 1.46x | 0.002 / 0.249 | 101.5 / 3.5 | 152 / 1 | 2428 of 3440 (71%) |

Findings, against the pre-registered expectations:

1. **The crossover is between 24 and 32 sessions per pod**, earlier than the expected 32 to 48. At 24 per pod the arms tie on throughput, but baseline's TTFT p90 is already 1.7x thunder's (14.0 vs 8.1 s) and vLLM starts to queue. At 32 per pod baseline's steady-state hit rate collapses from 0.63 to 0.04 while thunder keeps 0.35.
2. **Below the crossover the port is free.** Ratios at 4, 8, 12 and 16 sessions per pod are 0.98, 1.00, 0.98 and 1.01: within the plus or minus 2 percent cell-to-cell noise, in both directions. The gate stays idle there (0 to 53 pauses, 0 holds, at most 1 rebind per cell), so the flow-control round trip per turn has no measurable cost. The earlier reading of the single c=48 pair as a 2 percent penalty did not survive the extra levels.
3. **The gain grows with load to 1.44x at 64 and 1.46x at 84 sessions per pod**, matching step 12's replicated 1.42x (plus or minus 0.3 percent) at c=338. Thunder's throughput is flat to slightly rising from 32 per pod on (1382, 1342, 1438, 1538) while baseline keeps falling to about 1000 tok/s.
4. **TTFT p50 stays at 2 to 4 s for thunder at every level above the crossover; baseline's grows linearly with load to 101 s.** Baseline's wait sits inside vLLM (mean 4, 15, 50, 93, 152 requests waiting), thunder's inside the EPP (mean 1 waiting in vLLM at every level; 280 to 1716 holds per cell). Forced admissions are 0 up to 48 per pod, 2 at 64, 7 at 84.
5. **Pod hopping is the port's largest remaining loss and it grows with load.** The share of resumes that moved the program to a different pod is 49, 60, 69, 69, 71 percent from c=96 up (`rebinds_total` / `resumes_total`). This is why thunder's hit rate on the pool (0.25 to 0.35) sits below its single-pod value at the same per-pod pressure (0.55 in step 10 at 32 per pod) and why it does not beat baseline at c=96, where baseline still hits 0.63 and every move costs a full 60k-token prefill. `../proposal/PROPOSAL.md` Part 3 (origin-only resume) targets exactly this.

**Where the pool's throughput peak is (the c = 16, 32, 64 extension).** Output throughput rises from 1278 tok/s at 4 sessions per pod to 1782 at 8, peaks at 2014 at 12, holds at 1956 to 1974 at 16, then falls: 1541 at 24, 1151 at 32 (baseline). So the closed-loop peak of this pool on the weka replay is at 12 to 16 sessions per pod, and the two arms are identical up to that point. Per-stream decode interval (ITL p50) grows steadily with load, 10, 15, 20, 29, 38 ms at 4, 8, 12, 16, 24 per pod, while the pool's KV is only 13 to 42 percent full up to 16 per pod and nothing waits inside vLLM. The engines are therefore not queue-bound but bandwidth-bound on attention over 78k to 95k-token contexts well before the KV fills; adding sessions beyond 12 per pod only slows every stream. The crossover where ThunderAgent starts to pay off (24 to 32 per pod) sits about 2x past the peak, i.e. in the overload regime the paper targets.

**Origin-only resume (the third arm, 2026-09-19 15:37 to 2026-09-20 00:05).** Proposal Part 3 implemented as `resumePlacement: origin-only` in the port (llm-d-router commit `8ee881c2`, image `thunder-agent-v4`, config `../12-llm-d-router-pool/thunder-origin-plugins.yaml`), run at the five levels where the port pauses and resumes programs (below 24 sessions per pod there are almost no resumes, so the policy cannot differ). Driver `run-origin.sh`. One same-day control cell, `epp-thunder-c192-v4ctl` (v4 image, default `most-room`), reproduced yesterday's `epp-thunder-c192` within noise: 1374 vs 1342 tok/s, hit rate 0.320 vs 0.301, rebinds 1742 vs 1808. The first `epp-thunder-origin-c192` attempt was voided (its bench pod's corpus download was truncated at 31 of 640 MB, leaving 10 of 338 traces; directory kept as `-VOID-truncated-corpus`, `run-pool.sh` now voids such cells automatically) and rerun.

| sessions/pod | throughput most-room -> origin-only (tok/s) | origin / most-room | origin / baseline | steady-state hit rate most-room -> origin | TTFT p50 (s) | TTFT p90 (s) | rebinds most-room -> origin | origin waits | holds most-room -> origin | forced admissions |
|---|---|---|---|---|---|---|---|---|---|---|
| 24 | 1536 -> 1813 | 1.18x | 1.18x | 0.602 -> 0.816 | 0.5 -> 0.5 | 8.1 -> 5.7 | 461 -> 0 | 552 | 280 -> 437 | 0 -> 0 |
| 32 | 1382 -> 1571 | 1.14x | 1.37x | 0.353 -> 0.629 | 2.3 -> 1.3 | 9.9 -> 12.5 | 1079 -> 0 | 1231 | 698 -> 1079 | 0 -> 0 |
| 48 | 1342 -> 1639 | 1.22x | 1.54x | 0.301 -> 0.525 | 3.2 -> 3.0 | 12.0 -> 17.2 | 1808 -> 0 | 1912 | 1062 -> 1798 | 0 -> 2 |
| 64 | 1438 -> 1633 | 1.14x | 1.63x | 0.266 -> 0.456 | 3.4 -> 4.0 | 27.1 -> 29.2 | 2169 -> 0 | 2587 | 1434 -> 2337 | 2 -> 2 |
| 84 | 1538 -> 1698 | 1.10x | 1.62x | 0.249 -> 0.422 | 3.5 -> 4.4 | 75.2 -> 73.0 | 2428 -> 0 | 2972 | 1716 -> 2785 | 7 -> 10 |

Against Part 3's pre-registered expectations:

- **Rebinds fall to zero at every level** (predicted: near zero). The only moves left would be vanished-pod and forced-admission cases, and none occurred as rebinds.
- **Hit rate rises toward the single-pod value** (predicted: toward 0.45 to 0.49 at c=338): 0.42 at 84 sessions per pod, 0.53 at 48, 0.82 at 24. The remaining gap to 0.95 is the pause and resume churn itself, not placement.
- **Throughput rises above most-room at every level** (predicted: above 1447 at c=338): 1.10x to 1.22x over most-room, which lifts the port's gain over llm-d's default to 1.18x at 24 sessions per pod (where most-room only tied), 1.37x at 32, 1.54x at 48, 1.63x at 64 and 1.62x at 84. Requests completed rose 8 to 14 percent, so the gain is not a workload artifact; origin-only also completed more sessions per cell (21 to 30 vs 14 to 25), i.e. it absorbed more cold starts and the ratios are, again, conservative.
- **The cost is visible and bounded.** Origin waits (resumes delayed while another pod had room) are 552 to 2972 per cell and total holds are 55 to 69 percent higher than most-room. This shows up as TTFT p50 0.5 to 0.9 s higher at 64 and 84 sessions per pod (4.0 and 4.4 s vs 3.4 and 3.5 s), TTFT p90 higher at 32 and 48, and forced admissions rising from 7 to 10 at 84 per pod. At 24 and 32 per pod TTFT is better under origin-only because the avoided prefills outweigh the extra wait. Pod balance stayed within a few percent (pool KV 0.50 to 0.59 vs 0.56 to 0.62), so Option C's escape hatch was not needed.
- **Recommendation**: `origin-only` is the better default for a multi-pod pool on this workload; Part 3's Option B (a bounded origin wait before moving) is the knob to try if the p90 TTFT cost at 32 to 48 sessions per pod matters. The two 4xx errors in the origin cells at 48 and 64 per pod are `400 - Context Window` from the trace corpus, unrelated to the policy.

**Replicates of origin-only vs most-room (2026-09-20 01:00 to 08:35).** Two more cells per arm at c=96 and c=128 (driver `run-origin-replicates.sh`, both arms on thunder-agent-v4, bench image `session-id-v1`, arm and level alternated), so each arm has three cells per level with the sweep cell as replicate 1. Analysis `analyze_replicates.py`, tables `replicates.md`, figure `replicates.png`. One cell (`epp-thunder-c128-r3`) was voided by the corpus guard added the day before (its download returned 0 traces) and rerun. Cells: mean (min-max); ratio: origin-only / most-room of the means with the range of the per-replicate paired ratios in brackets.

| sessions/pod | metric | most-room (n=3) | origin-only (n=3) | origin / most-room |
|---|---|---|---|---|
| 24 (c=96) | throughput (tok/s) | 1531 (1500-1556) | 1830 (1804-1872) | 1.20x [1.18-1.20] |
| 24 | steady-state hit rate | 0.590 (0.547-0.621) | 0.824 (0.816-0.831) | 1.40x [1.34-1.51] |
| 24 | TTFT p50 / p90 (s) | 0.5 / 8.0 | 0.5 / 5.9 | 0.98x / 0.74x |
| 24 | holds / rebinds / origin waits | 275 / 454 / 0 | 439 / 0 / 544 | |
| 32 (c=128) | throughput (tok/s) | 1370 (1362-1382) | 1693 (1571-1807) | 1.24x [1.14-1.32] |
| 32 | steady-state hit rate | 0.347 (0.341-0.353) | 0.680 (0.629-0.722) | 1.96x [1.78-2.08] |
| 32 | TTFT p50 / p90 (s) | 2.4 / 10.1 | 1.0 / 11.4 | 0.41x / 1.13x |
| 32 | holds / rebinds / origin waits | 711 / 1091 / 0 | 971 / 0 / 1105 | |

Cell-to-cell spread is small: most-room throughput varies by under 4 percent across its three cells at either level, origin-only by 4 percent at c=96 and 14 percent at c=128. The paired ratios never fall below 1.14x, so the origin-only throughput gain of 15 to 25 percent at 24 to 32 sessions per pod is established; rebinds are 0 in every origin-only cell; errors 0 to 1 per cell; forced admissions 0 except one cell with 1.

**Session-level metrics (proposal Part 7)**, from the cells whose per-request report carries session ids: replicates 2 and 3 of most-room and origin-only, and one llm-d default cell per level added on 2026-09-20 (`epp-baseline-c96-r2`, `epp-baseline-c128-r2`; their cell-level numbers agree with the sweep cells: 1597 and 1156 tok/s, hit rate 0.686 and 0.073). SLO = TTFT <= 30 s, after the 10-minute warm-up. Population = sessions with a request open or issued after warm-up ended; a session whose trace finished during warm-up is not counted (an earlier draft of this table counted every session seen in the cell, which inflated the zero-progress share and depressed attainment for all arms; corrected 2026-09-20 evening).

| sessions/pod | metric | llm-d default (n=1) | most-room (n=2) | origin-only (n=2) |
|---|---|---|---|---|
| 24 (c=96) | goodput within SLO (turns/s) | 1.22 | 1.09 (1.05-1.14) | 1.58 (1.54-1.62) |
| 24 | session SLO attainment, strict / lenient | 0.58 / 0.69 | 0.87 / 0.88 | 0.82 / 0.85 |
| 24 | turns per session after warm-up, p10 / p50 / p90 | 2 / 13 / 29 | 2 / 11 / 25 | 1 / 15 / 34 |
| 24 | sessions with zero turns after warm-up | 0.00 | 0.01 | 0.03 |
| 32 (c=128) | goodput within SLO (turns/s) | 0.57 | 1.28 (1.27-1.29) | 1.53 (1.53-1.53) |
| 32 | session SLO attainment, strict / lenient | 0.08 / 0.08 | 0.76 / 0.78 | 0.70 / 0.75 |
| 32 | turns per session after warm-up, p10 / p50 / p90 | 3 / 8 / 16 | 2 / 10 / 22 | 1 / 12 / 28 |
| 32 | sessions with zero turns after warm-up | 0.01 | 0.04 | 0.02 |

Three readings:

- **The llm-d default fails the session SLO long before its throughput does.** At 24 sessions per pod it matches most-room on throughput (0.98x), beats it on hit rate (0.66 vs 0.59) and on goodput within SLO (1.22 vs 1.09 turns/s), yet only 58 percent of its sessions meet the strict SLO against 87 percent under most-room: its misses are spread thinly over many sessions (TTFT p90 12.8 s vs 8.0 s), so the request percentiles look acceptable and the session view does not. At 32 per pod it collapses to 8 percent attainment while the port keeps 70 to 78 percent. This is the capacity-at-SLO statement Part 7 asked for: at a 30 s TTFT SLO and 75 percent strict session attainment, the default supports fewer than 24 sessions per pod and the port about 32.
- **Origin-only trades a little attainment for a lot of goodput.** It does more work inside the SLO (goodput 1.19x to 1.44x) and moves the typical session faster (p50 and p90 progress up 10 to 36 percent), while strict attainment is 5 to 6 points lower than most-room (0.82 vs 0.87, 0.70 vs 0.76) and lenient 3 points lower. Zero-progress sessions are rare under both (1 to 4 percent); the earlier reading that origin-only doubled them was the population artifact. The remaining attainment gap is sessions whose origin pod stays full for a while: they wait where most-room would have moved them.
- **Why most-room scores higher on session attainment although the two arms violate the SLO on the same share of turns.** Turns with TTFT over 30 s are 2.0 vs 1.8 percent of turns at 24 per pod and 3.3 vs 3.7 percent at 32 (most-room vs origin-only, per cell), i.e. the same. Two things separate the session numbers: origin-only sessions complete 30 to 40 percent more turns in the window (18 vs 13.5 at 24 per pod, 14.7 vs 12.2 at 32), so a strict all-turns criterion gives them more chances to fail, and when origin-only does wait it waits longer, because a hold for the origin pod lasts until that pod frees room while a most-room move costs one prefill of a few seconds (per-session maximum TTFT p90: 42 to 81 s vs 32 to 34 s at 24 per pod, 219 to 302 s vs 167 s at 32; sessions whose worst turn exceeded 60 s: 21 vs 14 percent at 32 per pod). About half of the failing sessions in either arm failed on a single turn. The strict metric therefore carries a bias against the arm that makes more progress; the lenient variant (95 percent of turns) removes part of it, and a per-turn violation share or attainment over a fixed number of turns should be reported next to it (added to proposal Part 7).
- **Which arm is "better" depends on the objective.** For total useful work and typical latency, origin-only; for the fraction of users kept inside the SLO, most-room by a few points; the default is worst on both once past 24 sessions per pod. Part 3's Option B (a bounded origin wait) is the natural knob to close the remaining gap; the 90-minute cells below say when it matters most.

**Long window (2026-09-20 15:25 to 21:34): c=128 for 90 minutes, one cell per arm, sliced into 30-minute windows.** Question: does the gain change as sessions deepen. Analysis `analyze_long.py`, tables `long.md`, figure `long.png`. Slice 1 includes the 10-minute warm-up (empty caches); slice 2 is where sessions are deepest (mean prompt 76k to 79k tokens); in slice 3 a wave of sessions finished their traces and fresh ones replaced them (active sessions 242 to 254 vs about 150 in slices 1 and 2; mean prompt back to 62k), so slice 3 is a mix of deep and new sessions, not a deeper regime. The corpus was not exhausted (302 sessions seen at most). Session attainment per slice is over the sessions active in that slice.

| slice (min) | metric | llm-d default | most-room | origin-only | most-room / default | origin / most-room |
|---|---|---|---|---|---|---|
| 1 (0-30) | throughput (tok/s) | 981 | 1238 | 1536 | 1.26x | 1.24x |
| 2 (30-60) | throughput (tok/s) | 761 | 1101 | 1167 | 1.45x | 1.06x |
| 3 (60-90) | throughput (tok/s) | 972 | 1164 | 1287 | 1.20x | 1.11x |
| 1 | prefix-cache hit rate | 0.33 | 0.48 | 0.69 | | |
| 2 | prefix-cache hit rate | 0.002 | 0.33 | 0.52 | | |
| 3 | prefix-cache hit rate | 0.12 | 0.33 | 0.50 | | |
| 1 | TTFT p50 / p90 (s) | 5.8 / 32 | 2.2 / 8.9 | 1.1 / 11.2 | | |
| 2 | TTFT p50 / p90 (s) | 41.2 / 67 | 4.6 / 13.8 | 5.6 / 27.2 | | |
| 3 | TTFT p50 / p90 (s) | 18.2 / 53 | 3.6 / 12.9 | 3.7 / 21.1 | | |
| 1 | session SLO attainment, strict | 0.16 | 0.87 | 0.67 | | 0.78x |
| 2 | session SLO attainment, strict | 0.01 | 0.70 | 0.45 | | 0.64x |
| 3 | session SLO attainment, strict | 0.06 | 0.67 | 0.49 | | 0.73x |
| 1 | goodput within SLO (turns/s) | 1.40 | 1.93 | 2.15 | 1.38x | 1.12x |
| 2 | goodput within SLO (turns/s) | 0.12 | 1.03 | 1.06 | 8.7x | 1.02x |
| 3 | goodput within SLO (turns/s) | 0.98 | 1.54 | 1.64 | 1.57x | 1.07x |
| 1 | mean prompt tokens | 60k | 60k | 63k | | |
| 2 | mean prompt tokens | 79k | 76k | 79k | | |
| 3 | mean prompt tokens | 63k | 62k | 64k | | |

Findings:

- **The port's gain over the llm-d default grows as sessions deepen.** most-room / default on throughput goes 1.26x, 1.45x, 1.20x across the slices, peaking in the deepest slice, where the default's hit rate is 0.002 and its TTFT p50 is 41 s (goodput within SLO 0.12 turns/s: essentially nothing the default did in that half hour met a 30 s TTFT). The port keeps hit rate 0.33 and TTFT p50 4.6 s there. In slice 3 the replacement wave (fresh short sessions) gives the default cache hits again and the gap narrows to 1.20x. So the 30-minute cells, whose steady state corresponds to the end of slice 1, understate the port's advantage in the deep regime.
- **Origin-only's extra gain over most-room shrinks as sessions deepen, and its attainment penalty grows.** origin / most-room on throughput goes 1.24x, 1.06x, 1.11x; its strict attainment is 0.78x, 0.64x, 0.73x of most-room's; TTFT p90 in the deepest slice is 27 s vs 14 s. With 80k-token sessions the origin pod is full more often and for longer, so waiting for it costs more and saves less. This is the regime where Part 3's Option B (a bounded origin wait, then move) should help most, and it is where the decision between origin-only and most-room actually depends on the objective: origin-only still completes more work (1.06x to 1.11x, hit rate 0.52 vs 0.33), most-room keeps 20 to 25 points more sessions inside the SLO.
- **Throughput falls from slice 1 to slice 2 for every arm** (default 981 to 761, most-room 1238 to 1101, origin-only 1536 to 1167), tracking the mean prompt rising from 60k to 79k tokens, then recovers in slice 3 as fresh sessions arrive. This is the same mechanism as the cross-level fall in `SATURATION.md` (attention bandwidth on long contexts) seen within one cell over time. Any fixed-window measurement of this workload is therefore also a measurement of how deep its sessions got.
- One cell per arm, so the slice-to-slice ratios carry the plus or minus 2 to 4 percent cell noise measured in the replicates; the direction of the two trends (port vs default up, origin vs most-room down with depth) is larger than that, the exact magnitudes are not.

Why throughput falls with load in both arms (asked during the run): the pool is past its output-throughput peak at 12 sessions per pod already. Per-stream decode interval (ITL p50) doubles from 20 ms at 12 per pod to 38 ms at 24 and stays at 40 ms above, so the engines are memory-bandwidth-bound on attention over 60k to 84k-token contexts and a larger batch does not add decode throughput. On top of that, lost prefix hits turn into prefill work that steals steps from decoding; this shows as ITL mean rising far above ITL p50 (105 vs 40 ms for baseline at c=128, 90 vs 40 for thunder). Thunder's gain is in avoiding the second effect, not in raising the peak. The peak itself was not measured; c=16, 24, 32 would locate it.

Caveats:

- Sessions that finish their trace are replaced by fresh traces, so the concurrency stays at c but the mix changes: at 4 to 16 sessions per pod, 20 to 33 sessions completed per 30-minute cell (median about 9 minutes each), at 24 per pod 23, at 32 per pod 14 (baseline) and 25 (thunder), and above that 0 to 17. Low-concurrency cells therefore include cold starts and early short-prompt turns; high-concurrency cells are almost all deep long-prompt turns. Within a level the faster arm finishes more sessions and absorbs more cold starts (17 vs 1 at 48 per pod), so the reported ratios are slightly conservative.
- At c=338 the corpus is exhausted: the filtered corpus has exactly 338 traces, so a session that finishes is not replaced (338 sessions dispatched in every c=338 cell, vs 81 at c=48 and 126 at c=96 where replacements happen). Concurrency therefore decays during a c=338 cell by the number of completed sessions: 0 for the default, 14 for most-room, 21 for origin-only, i.e. up to 6 percent, and more for the faster arm, which again makes the ratios conservative. Levels up to c=256 are unaffected (256 + 24 completions < 338). Replicates should be run at c <= 256.
- One cell per arm and level, so no error bars. The c=338 point reproduces step 12's three-replicate result, which had a spread of 0.3 percent on throughput.
- Absolute throughput is not comparable across levels: with 30-minute cells, low-concurrency sessions progress deeper, so the mean prompt is 84k tokens at c=48 and 61k at c=128. Within a level the arms' prompt means agree to within 1 percent, so the arm comparison is clean.
- The `epp-thunder-c256` cell was collected by hand. The driver's bench-pod name lookup returned empty on a transient API error, so its DONE poll spun forever while the cell ran normally inside the pod (bench reported completion, prober captured all metrics); artifacts were copied with the same commands the driver uses and the manifest carries a note. `../12-llm-d-router-pool/run-pool.sh` now retries the lookup until it gets a name. The stuck driver was killed and the last level (c=338, order thunder then baseline as planned) was relaunched into the same run directory at 21:46.
- A first launch at 11:30 was interrupted by the user during its first cell; that cell was voided (job deleted, directory removed) before this run.
- Cells took 42 to 53 minutes end to end for a 30-minute window; the first six levels took just under 10 hours, the three appended levels just under 5. The extension used `run-sweep.sh "16 32 64"` with `AB_ID` preset to the existing run id (arm order alternated per level as before: baseline first at 16 and 64, thunder first at 32).
