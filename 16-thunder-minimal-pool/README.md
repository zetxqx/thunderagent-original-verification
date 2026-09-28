# Step 16: the minimal thunder-agent on the 4-pod pool, against step 13

Question: does the minimal rewrite of the plugin (llm-d-router `thunder-agent-minimal` at `33dde5d2`, image `thunder-agent-min-33dde5d2`; step 15 checked it on one pod) reproduce the benchmarked port on the whole pool, where placement matters? The minimal plugin has one placement policy, origin-only (a paused session waits for its own pod; a new session goes to the pod with most room), so the reference is step 13's `epp-thunder-origin` arm (image `thunder-agent-v4`, `resumePlacement: origin-only`) at c=128, three cells. A second cell changes one parameter, the idle decay half-life, from upstream's 1 s to 10 s.

Fast check by design: one cell per arm, no same-day control.

## What runs

- Protocol: step 12's `run-pool.sh` exactly as step 13 ran its c=128 replicates: one EPP (the main release `program-aware-scheduling`) over the four vLLM pods, prefix-cache reset on every pod and a fresh EPP per cell, c=128 (32 sessions per pod), 30 min window (10 min warm-up), client timeout 1900 s, bench image `inference-perf:session-id-v1` (`sha256:f7381b01...`, the permit fix plus session ids, the same image as step 13 r2 and r3), bench pod on the non-spot default pool.
- Arms: `thunder-min` (`../12-llm-d-router-pool/thunder-min-plugins.yaml`, the six-key config of step 15: half-life 1 s, sweep 5 s, starvation 1800 s, TTL 3600 s) and `thunder-min-hl10` (`thunder-min-hl10-plugins.yaml`, identical except `idleDecayHalfLifeSeconds: 10`, the replay's idle-gap cap and about the prefix lifetime on a pod in step 13's wait-cost curve).
- The main release was at revision 71 (image `thunder-agent-v7`) before this step and was rolled back to it afterwards (revision 74, "Rollback to 71"); see `results/cluster-state-before.txt`.

Tooling changes, shared with step 12 (defaults unchanged): `run-pool.sh` reads the config log line under either JSON key (`msg` before, `body` in the newer base), checks the `thunder-min*` arms (flow control on, thunder-agent scorer, the arm's half-life in the live ConfigMap), and saves each pod's vLLM log and the EPP ConfigMap per cell; `prober.py` adds `epp-pods.csv` (per-pod working set and capacity), pool sums of the working set in `epp-metrics.csv`, and raw scrapes of the EPP and every vLLM pod every 10 s.

## Files

- `analyze.py <run> [step13 run]`: `analysis.md` with step 15's metric set plus pod balance and the session-level metrics of proposal Part 7, against step 13's llm-d default (2 cells), most-room (3) and origin-only (3) at c=128; `raw-metrics-<cell>.md` (every counter and histogram delta, vLLM summed over the pods); `timeseries.png`. On the step 13 cells it reproduces step 13's published numbers.
- `results/rep-20260927-195200-c128-t1900/`: the two cells (`epp-thunder-min-c128`, `epp-thunder-min-hl10-c128`), `driver.log`, `driver-hl10.log`. Not in the repo: `raw-epp-metrics.txt.gz` (27 to 48 MB per cell, gitignored; its deltas are in `raw-metrics-<cell>.md`) and, as for every earlier step, `per_request_lifecycle_metrics.json`.

## Results (2026-09-27)

Cells: `epp-thunder-min-c128` 19:53 to 20:37 PDT, `epp-thunder-min-hl10-c128` 20:39 to 21:25, both complete, no preemption, 0 request errors. Step 13 values are mean (min-max) over three cells.

| metric | step 13 v4 origin-only | thunder-min, half-life 1 s | thunder-min, half-life 10 s |
|---|---|---|---|
| output throughput (tok/s) | 1693 (1571-1807) | 1752 | 1817 |
| steady-state hit rate | 0.680 (0.629-0.722) | 0.691 | 0.733 |
| prefill tokens computed (M) | 76.1 (69.0-83.2) | 75.4 | 67.5 |
| TTFT p50 / p90 / p99 (s) | 1.0 / 11.4 / 123.5 | 0.9 / 10.4 / 149.4 | 0.6 / 8.2 / 129.0 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 1.53 | 1.50 | 1.63 |
| session SLO attainment, strict / lenient | 0.70 / 0.75 | 0.64 / 0.69 | 0.58 / 0.65 |
| sessions whose worst turn exceeded 60 s | 0.21 | 0.23 | 0.28 |
| vLLM waiting, mean steady | 0.6 | 1.2 | 1.4 |
| pauses / resumes | 1653 / 1524 | 495 / 422 | 391 / 317 |
| forced admissions | 0 (0-1) | 0 | 0 |
| pod balance: working set / capacity, per pod | - | 0.97-1.00 | 0.98-1.01 |

Readings:

1. **The minimal build reproduces the origin-only port on the pool.** With the same half-life (1 s), throughput, steady-state hit rate, prefill work, TTFT p50 and p90, goodput within SLO and the share of turns over the SLO all fall inside step 13's origin-only range or within 2 percent of its mean. No forced admissions, no errors, the four pods stay balanced (working set 97 to 100 percent of capacity on each), and nothing piles up inside vLLM (1.2 waiting on average across the pool).
2. **The same signature as on one pod (step 15).** Without `markedForPause` the sweep pauses only idle sessions, so pauses fall to a third (495 vs 1653) and the peak paused count from 129 to 73. On the pool this costs some fairness: strict session attainment is 0.64 against 0.69 to 0.72, TTFT p99 149 s against 102 to 137 s. The effect is smaller than on one pod, where TTFT p99 went from 410 to 712 s.
3. **Half-life 10 s helps efficiency and hurts the tail.** Compared with the 1 s cell: hit rate 0.733 vs 0.691, prefill work 10 percent lower, throughput 1817 vs 1752 (the highest of any c=128 cell so far), TTFT p50 and p90 lower, goodput 1.63 vs 1.50. But strict attainment drops again (0.58) and 28 percent of sessions have a worst turn over 60 s (23 percent at 1 s). A longer half-life keeps idle sessions on the books for longer, so fewer are admitted into room that is about to be reclaimed (fewer re-prefills), and those that wait, wait longer. The sim that recommended 10 s predicted the efficiency side; the tail cost is the part it did not model.
4. **Size of the differences.** Each step 16 arm is one cell. The half-life effect on throughput (3.7 percent) and hit rate (0.04) is smaller than step 13 origin-only's cell-to-cell spread (14 percent and 0.09), so it is a direction, not a result; that every efficiency metric moves the same way (hit rate, prefill, TTFT, TPOT, goodput) and the tail metrics move the other way makes the direction plausible. Two more cells per arm would settle it.

Caveats: step 13's pool of pods was different (spot churn) and ran nine days earlier; the step 13 working-set row covers only the first pod (its prober read one `pod_utilization` series), so the working-set rows are not comparable across the two steps.
