# Step 16: the minimal thunder-agent on the 4-pod pool, against step 13

Question: does the minimal rewrite of the plugin (llm-d-router `thunder-agent-minimal` at `33dde5d2`, image `thunder-agent-min-33dde5d2`; step 15 checked it on one pod) reproduce the benchmarked port on the whole pool, where placement matters? The minimal plugin has one placement policy, origin-only (a paused session waits for its own pod; a new session goes to the pod with most room), so the reference is step 13's `epp-thunder-origin` arm (image `thunder-agent-v4`, `resumePlacement: origin-only`) at c=128, three cells. A second cell changes one parameter, the idle decay half-life, from upstream's 1 s to 10 s.

First one cell per arm, then two replicates per arm (three cells each, like the reference); no same-day control of the v4 port.

## What runs

- Protocol: step 12's `run-pool.sh` exactly as step 13 ran its c=128 replicates: one EPP (the main release `program-aware-scheduling`) over the four vLLM pods, prefix-cache reset on every pod and a fresh EPP per cell, c=128 (32 sessions per pod), 30 min window (10 min warm-up), client timeout 1900 s, bench image `inference-perf:session-id-v1` (`sha256:f7381b01...`, the permit fix plus session ids, the same image as step 13 r2 and r3), bench pod on the non-spot default pool.
- Arms: `thunder-min` (`../12-llm-d-router-pool/thunder-min-plugins.yaml`, the six-key config of step 15: half-life 1 s, sweep 5 s, starvation 1800 s, TTL 3600 s) and `thunder-min-hl10` (`thunder-min-hl10-plugins.yaml`, identical except `idleDecayHalfLifeSeconds: 10`, the replay's idle-gap cap and about the prefix lifetime on a pod in step 13's wait-cost curve).
- The main release was at revision 71 (image `thunder-agent-v7`) before this step and was restored to it after each session (revisions 74 and 79 "Rollback to 71", 84 "Rollback to 79"). The overnight driver's `helm rollback 71` failed with `release has no 71 version`: Helm keeps the last 10 revisions and the night's upgrades had pruned 71. The release ran the minimal image, with no traffic but ours, from 03:33 until it was restored by hand at 05:35 from revision 79, whose manifest is identical to 71's. The drivers now use `restore-main-release.sh`, which matches on the saved manifest instead of a revision number; see `results/cluster-state-before.txt`.

Tooling changes, shared with step 12 (defaults unchanged): `run-pool.sh` reads the config log line under either JSON key (`msg` before, `body` in the newer base), checks the `thunder-min*` arms (flow control on, thunder-agent scorer, the arm's half-life in the live ConfigMap), and saves each pod's vLLM log and the EPP ConfigMap per cell; `prober.py` adds `epp-pods.csv` (per-pod working set and capacity), pool sums of the working set in `epp-metrics.csv`, and raw scrapes of the EPP and every vLLM pod every 10 s.

## Files

- `analyze.py <run> [step13 run]`: `analysis.md` with step 15's metric set plus pod balance and the session-level metrics of proposal Part 7, against step 13's llm-d default (2 cells), most-room (3) and origin-only (3) at c=128; `raw-metrics-<cell>.md` (every counter and histogram delta, vLLM summed over the pods); `timeseries.png`. On the step 13 cells it reproduces step 13's published numbers.
- `run-replicates.sh`: cells r2 and r3 of both arms in ABBA order, then the restore of the main release and the analysis.
- `run-overnight.sh`: three cells of `thunder-min-hl10-s1` (half-life 10 s, pause sweep 1 s) and one 90-minute `thunder-min` cell, unattended, with kubectl and helm pinned to the bobbm context through a temporary kubeconfig; run under `caffeinate -is`.
- `analyze_long.py <run> [step13 run]`: `long.md`, the 90-minute cell in 30-minute slices next to step 13's three 90-minute cells, with EPP state per slice.
- `restore-main-release.sh <saved manifest>`: rolls the main release back to the newest revision whose manifest equals the one saved before a run, and verifies it. `results/main-release-before.yaml` is the revision 71 manifest (image `thunder-agent-v7`).
- `results/rep-20260927-195200-c128-t1900/`: the six cells (three per arm) (`epp-thunder-min-c128[-r2|-r3]`, `epp-thunder-min-hl10-c128[-r2|-r3]`), `driver.log`, `driver-hl10.log`, `driver-replicates.log`. Not in the repo: `raw-epp-metrics.txt.gz` (27 to 48 MB per cell, gitignored; its deltas are in `raw-metrics-<cell>.md`) and, as for every earlier step, `per_request_lifecycle_metrics.json`.

## Results (2026-09-27 and 28, three cells per arm)

Cells, all complete, no preemption, 0 to 1 request errors each: `epp-thunder-min-c128` (19:53), `epp-thunder-min-hl10-c128` (20:39), then `run-replicates.sh` in ABBA order: `epp-thunder-min-c128-r2` (21:42), `epp-thunder-min-hl10-c128-r2` (22:28), `epp-thunder-min-hl10-c128-r3` (23:14), `epp-thunder-min-c128-r3` (23:59), main release rolled back to revision 71 at 00:43. Values are mean (min-max) over three cells; full table in `analysis.md`.

| metric | step 13 v4 origin-only | thunder-min, half-life 1 s | thunder-min, half-life 10 s |
|---|---|---|---|
| output throughput (tok/s) | 1693 (1571-1807) | 1770 (1752-1790) | 1846 (1817-1884) |
| steady-state hit rate | 0.680 (0.629-0.722) | 0.708 (0.688-0.744) | 0.746 (0.733-0.756) |
| prefill tokens computed (M) | 76.1 (69.0-83.2) | 74.1 (70.7-76.2) | 66.2 (64.1-67.5) |
| TTFT p50 / p90 (s) | 1.0 / 11.4 (10.4-12.5) | 0.8 / 10.1 (9.1-10.8) | 0.6 / 8.5 (8.2-8.7) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 1.53 (1.53-1.53) | 1.55 (1.50-1.60) | 1.62 (1.57-1.66) |
| session SLO attainment, strict | 0.70 (0.69-0.72) | 0.68 (0.64-0.72) | 0.55 (0.53-0.58) |
| session SLO attainment, lenient | 0.75 (0.73-0.76) | 0.72 (0.69-0.76) | 0.61 (0.59-0.65) |
| per-session worst TTFT, p90 (s) | 261 (219-302) | 256 (245-268) | 412 (319-459) |
| sessions whose worst turn exceeded 60 s | 0.21 | 0.22 (0.21-0.23) | 0.31 (0.28-0.33) |
| vLLM waiting, mean steady | 0.6 | 1.2 | 1.2 |
| pauses / resumes | 1653 / 1524 | 485 / 411 | 398 / 324 |
| forced admissions | 0 (0-1) | 0 (0-1) | 0 |
| working set / capacity per pod, steady, min-max over pods | - | 0.95-1.00 | 0.98-1.00 |

Readings:

1. **The minimal build reproduces the origin-only port on the pool.** At the same half-life (1 s) every main metric overlaps step 13's origin-only range: throughput, hit rate, prefill work, TTFT, goodput, session attainment (strict 0.68 vs 0.70; the 0.64 of the first cell alone was noise), worst-turn tail. No forced admissions beyond one, the four pods stay balanced, nothing piles up inside vLLM. What differs is the mechanism, as on one pod: without `markedForPause` the sweep pauses only idle sessions, so pauses fall to under a third (485 vs 1653) and the working set sits over capacity a larger share of the time, with no measurable cost on the pool.
2. **The idle decay half-life is a real trade-off between efficiency and fairness.** Going from 1 s to 10 s, the three cells of each arm do not overlap on either side: prefill work falls 11 percent (64.1-67.5 vs 70.7-76.2 M tokens), throughput rises 4 percent (1817-1884 vs 1752-1790 tok/s), TTFT p90 falls (8.2-8.7 vs 9.1-10.8 s); but strict session attainment falls from 0.68 to 0.55 (0.53-0.58 vs 0.64-0.72), the per-session worst TTFT p90 rises from 256 to 412 s, and the share of sessions with a turn over 60 s from 0.22 to 0.31. Hit rate and goodput improve too, with the ranges touching. A longer half-life keeps idle sessions on the books longer, so less room looks free: fewer sessions are admitted into room that is about to be reclaimed (fewer re-prefills), and the ones held wait longer.
3. **Which half-life to use depends on the objective.** For work done per GPU, 10 s is better and is the best c=128 result so far (1846 tok/s against origin-only's 1693 and llm-d default's 1154). For keeping each user's worst turn short, 1 s is better and matches the benchmarked port. The simulator's recommendation of a half-life at least as long as the tool call predicted the efficiency side only. The tail cost at 10 s is of the kind `markedForPause` or a bounded wait (proposal Part 8) would address; neither is in the minimal build.

Caveats: step 13's pods were different (spot churn) and ran nine days earlier; the step 13 working-set row covers only the first pod (its prober read one `pod_utilization` series), so working-set rows do not compare across the two steps; one load level (c=128).

## Pause sweep every 1 s (2026-09-28, three cells)

Arm `thunder-min-hl10-s1` (`../12-llm-d-router-pool/thunder-min-hl10-s1-plugins.yaml`): half-life 10 s and `pauseSweepSeconds: 1` instead of 5, the lever the design names first for a long-wait tail. Cells `epp-thunder-min-hl10-s1-c128` (01:18), `-r2` (02:02), `-r3` (02:48), all complete, no preemption, 0 to 1 errors.

| metric | half-life 1 s, sweep 5 s | half-life 10 s, sweep 5 s | half-life 10 s, sweep 1 s |
|---|---|---|---|
| output throughput (tok/s) | 1770 (1752-1790) | 1846 (1817-1884) | **1945 (1867-2019)** |
| steady-state hit rate | 0.708 (0.688-0.744) | 0.746 (0.733-0.756) | **0.795 (0.752-0.820)** |
| prefill tokens computed (M) | 74.1 (70.7-76.2) | 66.2 (64.1-67.5) | 60.7 (57.4-65.3) |
| TTFT p50 / p90 (s) | 0.8 / 10.1 | 0.6 / 8.5 | 0.5 / 7.0 (6.3-8.0) |
| goodput within SLO (turns/s) | 1.55 (1.50-1.60) | 1.62 (1.57-1.66) | **1.77 (1.64-1.94)** |
| session SLO attainment, strict | 0.68 (0.64-0.72) | 0.55 (0.53-0.58) | 0.64 (0.57-0.70) |
| per-session worst TTFT, p90 (s) | 256 (245-268) | 412 (319-459) | 275 (226-367) |
| sessions whose worst turn exceeded 60 s | 0.22 (0.21-0.23) | 0.31 (0.28-0.33) | 0.24 (0.20-0.31) |
| working set over capacity, share of samples | 0.20 | 0.25 | **0.04** |
| pauses / holds | 485 / 342 | 398 / 282 | 532 / 365 |
| vLLM waiting, mean steady | 1.2 | 1.2 | 0.7 |

Readings:

1. **A 1 s sweep keeps the pods under the line.** The undecayed working set is over capacity in 4 percent of samples, against 20 to 25 percent with the 5 s sweep: sessions idle during a short tool call can now be caught, which is what `markedForPause` did in v4 by other means.
2. **It is the best configuration measured at c=128 on every efficiency metric**: 1945 tok/s (the cells do not overlap with half-life 1 s; they touch half-life 10 s at 1867 vs 1884), hit rate 0.80, 18 percent less prefill than half-life 1 s, TTFT p90 7 s, goodput 1.77 turns/s. Against step 13's origin-only port: 1.15x throughput, 1.16x goodput.
3. **It recovers most of the tail that the 10 s half-life cost.** Strict attainment 0.64 against 0.55 (10 s, sweep 5 s) and 0.68 (1 s); worst-turn p90 275 s against 412 and 256 s. The first cell is the weak one (1867 tok/s, attainment 0.57, like the 5 s sweep arm); the two later cells are 1948 and 2019 tok/s with attainment 0.66 and 0.70, so the arm has the widest spread of the three and the tail recovery rests on two of three cells.
4. The sweep every second costs nothing measurable on the EPP: mean CPU 1.94 cores against 1.92 for both 5 s arms (v4 origin-only: 2.21). Pauses rise 34 percent over the 10 s arm (532 vs 398).

## 90-minute cell (2026-09-28)

Cell `epp-thunder-min-c128-w90` (03:35 to 05:32), `thunder-min` (half-life 1 s, sweep 5 s), complete, no preemption, against step 13's 90-minute cells (one each, same protocol). Slices of 30 minutes; slice 1 includes the warm-up, slice 2 has the deepest sessions (mean prompt 78k), in slice 3 a wave of finished sessions is replaced by new ones. Full tables in `long.md`.

| slice | throughput: step 13 origin-only / thunder-min (tok/s) | hit rate | TTFT p90 (s) | strict attainment | EPP sessions paused, mean | pauses in the slice |
|---|---|---|---|---|---|---|
| 1 | 1536 / 1436 (0.93x) | 0.688 / 0.645 | 11.2 / 12.6 | 0.67 / 0.54 | 31 / 28 | 1639 / 487 |
| 2 | 1167 / 1305 (1.12x) | 0.515 / 0.589 | 27.2 / 18.2 | 0.45 / 0.44 | 76 / 71 | 1486 / 429 |
| 3 | 1287 / 1329 (1.03x) | 0.501 / 0.503 | 21.1 / 20.6 | 0.49 / 0.43 | 155 / 149 | 2181 / 719 |

Readings:

1. **No drift over 90 minutes.** thunder-min tracks origin-only in every slice (0.93x, 1.12x, 1.03x on throughput; hit rate within 0.07); it is best relative to origin-only in the deepest slice. Nothing in the EPP series grows without bound: in-flight and idle counts stay flat.
2. **Finished sessions do not inflate the working set.** Sessions are released only by the 3600 s idle TTL (the replay never sends a final signal, so this was also true for v4). The paused count grows the same way in both builds (to 149 and 155 in slice 3): a finished session goes idle, the sweep pauses it, and paused sessions do not count toward occupancy. So the TTL-only release costs table entries, not admission room, at least within 90 minutes.
3. Strict attainment is lower than origin-only in slices 1 and 3 (0.54 vs 0.67, 0.43 vs 0.49). In the 30-minute replicates the same comparison overlapped (0.68 vs 0.70), so with one 90-minute cell per arm this is not separable from cell-to-cell spread.

