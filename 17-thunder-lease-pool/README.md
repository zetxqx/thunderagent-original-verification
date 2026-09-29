# Step 17: the lease thunder-agent on the 4-pod pool, against step 16

Question: does the lease rewrite of the minimal plugin behave correctly on the pool, and how does it compare with the minimal build step 16 measured? The lease build (llm-d-router branch `thunder-agent-lease-main`, one commit `20e3b1ee` on upstream `8a2f37d3`) replaces the minimal build's two working-set views (idle decay for admission, undecayed for a periodic pause sweep) with one view and on-demand pausing inside the gate:

- one working set per pod: every unpaused session at its full footprint;
- no pause sweep: when the picked paused or new head does not fit, idle sessions give up their room, longest idle first, and are paused; for a paused or new head only sessions idle for at least `idleLeaseSeconds`, for an admitted turn that pushes its pod over the ceiling any idle session; sessions with a turn queued are never paused;
- every picked head's room is reserved until its request reaches the pod;
- three config keys: `idleLeaseSeconds`, `utilThreshold`, `headWaitStarvationMs`; capacity is scraped only (no fallback key), the idle TTL is derived (`max(1 h, 2 x starvation)`).

No same-day control: by the user's choice, the reference is step 16's three arms (three cells each, same protocol, 2026-09-27 and 28), and step 16's best arm (half-life 10 s, sweep 1 s) is the ratio reference.

## What runs

- Build: image `llm-d-router-endpoint-picker:thunder-agent-lease-20e3b1ee` (`sha256:c71cdd393ab9...`, `results/epp-image.txt`), built with Cloud Build from the commit above; the commit is pinned by the annotated tag `thunder-agent-lease-20e3b1ee` on `zetxqx/llm-d-router`.
- Protocol: step 16's exactly, through step 12's `run-pool.sh`: one EPP (the main release `program-aware-scheduling`) over the four vLLM pods, prefix-cache reset on every pod and a fresh EPP per cell, c=128 (32 sessions per pod), 30 min window (10 min warm-up), client timeout 1900 s, bench image `inference-perf:session-id-v1`, bench pod on the non-spot default pool.
- Arms (`../12-llm-d-router-pool/thunder-lease*-plugins.yaml`, identical to step 16's config except the plugin keys):

| arm | `idleLeaseSeconds` | why |
|---|---|---|
| `thunder-lease` | 30 (the default) | the shipped config. The replay caps tool-call gaps at 10 s (`trace_idle_gap_cap_seconds`), so admission should almost never reclaim a live session; pauses should come from the growth rule |
| `thunder-lease5` | 5 | half the gap cap: admission reclaims sessions in longer tool calls |

- Round 1: one cell per arm; replicates after review (two more cells per arm, ABBA order: lease 30 s, lease 5 s, lease 5 s, lease 30 s).
- The main release was saved before this step (`results/main-release-before.yaml`, revision 84, image `thunder-agent-v7`, identical to step 16's saved state) and is restored with `../16-thunder-minimal-pool/restore-main-release.sh`.

Tooling changes, shared with earlier steps (defaults and earlier results unchanged): `run-pool.sh` checks `thunder-lease*` arms (the arm's `idleLeaseSeconds` must be in the live ConfigMap); `prober.py` reads a working-set series with no `view` label as the undecayed view; step 15's `analyze.py` tolerates a missing decayed view.

## Pass criteria (written before the run)

Correctness, every lease cell:

1. The gate engages: `pauses_total > 0` and holds (paused + new) `> 0`.
2. The ledger closes: EPP running sessions track vLLM running requests.
3. Nothing piles up in the engine: vLLM waiting, mean steady, near step 16's 1.2.
4. The EPP log has no error or panic lines.
5. Forced admissions and request errors at step 16's level (0 to 1 per cell).
6. The per-pod working set stays at or below capacity most of the time (steady mean per pod at most about 1.0).

Performance is compared with step 16, not judged pass/fail: throughput, steady-state hit rate, prefill tokens, TTFT p50/p90, goodput within the 30 s SLO, strict session attainment, per-session worst TTFT p90, pauses and holds.

Predictions: lease 30 s behaves like upstream with decay off plus the growth rule, so hit rate at or above step 16's best arm, with a longer wait tail for held sessions; lease 5 s sits closer to the decayed builds.

## Files

- `smoke-test.sh [image-tag]`: deploys the `thunder-lease` arm on the main release and runs 18 checks (build, metric set, scraped capacity on all four pods, session tracking, class accounting, EPP log).
- `run-cells.sh <arm:cell-tag> ...`: the cells in order through `run-pool.sh`, then the restore and the analysis, with kubectl and helm pinned to the bobbm context.
- `analyze.py <run> [step16 run]`: `analysis.md` (step 16's metric set) against step 16's three arms, `raw-metrics-<cell>.md`, `timeseries.png`.

## Steps

1. `~/.claude/skills/cloud-build-epp/build-epp.sh thunder-agent-lease-20e3b1ee` in the llm-d-router `thunder-agent-lease-main` checkout.
2. `./smoke-test.sh | tee results/smoke-test-output.txt`
3. `nohup caffeinate -is ./run-cells.sh thunder-lease:c128 thunder-lease5:c128 > results/driver.log 2>&1 &`
   Replicates: `AB_ID=rep-20260928-115246-c128-t1900 nohup caffeinate -is ./run-cells.sh thunder-lease:c128-r2 thunder-lease5:c128-r2 thunder-lease5:c128-r3 thunder-lease:c128-r3 > results/driver-replicates.log 2>&1 &`
4. `uv run --with matplotlib --with numpy python analyze.py results/<run>` (the driver runs it too).

## Smoke test (2026-09-28)

All 18 checks pass (`results/smoke-test-output.txt`): `llm_d_epp_info` reports commit `20e3b1ee`; the live ConfigMap has `idleLeaseSeconds: 30`; `resumes_total` and the `view` and `source` labels are gone; all four pods report their scraped capacity (2,237,040 tokens); three turns answered; two sessions tracked, none running or paused after the turns; releases new +2 and reasoning +1; no holds or pauses on an idle pool; the EPP log has no error lines. The first run passed the log check without reading a log (the EPP pod lookup by label returned nothing); the script now finds the pod by name, fails if the log is empty, and was rerun in full.

## Results, round 1 (2026-09-28, one cell per arm)

Run `results/rep-20260928-115246-c128-t1900`: `epp-thunder-lease-c128` (11:52 to 12:37 PDT) and `epp-thunder-lease5-c128` (12:37 to 13:24), both complete, not preempted, 338 corpus traces, on the same four pods as step 16. The main release was restored to revision 84's manifest at 13:25 (revision 89, "Rollback to 84"). Full table in `analysis.md`, counter deltas in `raw-metrics-<cell>.md`, series in `timeseries.png`. Step 16 values are mean (min-max) over three cells.

| metric | step 16, half-life 10 s, sweep 1 s | step 17, lease 30 s | step 17, lease 5 s |
|---|---|---|---|
| output throughput (tok/s) | 1945 (1867-2019) | 1871 | 1863 |
| steady-state hit rate | 0.795 (0.752-0.820) | 0.778 | 0.766 |
| prefill tokens computed (M) | 60.7 (57.4-65.3) | 62.0 | 63.3 |
| TTFT p50 / p90 / p99 (s) | 0.5 / 7.0 / 140.6 | 0.5 / 8.5 / 227.4 | 0.6 / 8.6 / 163.8 |
| goodput within SLO, TTFT <= 30 s (turns/s) | 1.77 (1.64-1.94) | 1.60 | 1.69 |
| session SLO attainment, strict | 0.64 (0.57-0.70) | 0.61 | 0.60 |
| per-session worst TTFT, p90 (s) | 275 (226-367) | **435** | **386** |
| sessions whose worst turn exceeded 60 s | 0.24 (0.20-0.31) | 0.23 | 0.30 |
| vLLM waiting, mean steady | 0.7 | 1.2 | 0.9 |
| EPP running sessions / vLLM running requests, mean steady | 71 / 70 | 69 / 68 | 72 / 70 |
| working set / capacity per pod, steady, min-max over pods | 0.95-0.98 | 0.96-0.99 | 0.98-0.99 |
| share of samples with working set over capacity | 0.04 (0.01-0.07) | 0.17 | 0.06 |
| pauses / holds (paused + new) | 532 / 365 | 308 / 227 | 475 / 362 |
| releases of paused sessions | 449 | 242 | 396 |
| forced admissions / request errors | 0 / 0 | 0 / 0 | 0 / 0 |

`resumes_total` is gone in the lease build; `releases_total{class="paused"}` carries the same count.

Against the correctness criteria, both cells pass all six: the gate engages (308 and 475 pauses, 227 and 362 holds); the ledger closes (EPP running sessions within 2 of vLLM's running requests); vLLM waiting stays at 0.9 to 1.2; both EPP logs have no error or warning lines (13,035 and 13,360 lines); no forced admissions and no request errors; the working set stays at or below capacity on every pod (steady means 0.96 to 0.99).

Readings (one cell per arm; superseded by the three-cell results below, which revise readings 2 and 4):

1. **The lease build works and lands in step 16's efficiency range.** Throughput, hit rate and prefill work of both arms sit inside or at the edge of the best step 16 arm's range (0.96x throughput, 0.98x and 0.96x hit rate), between step 16's half-life 10 s arms. One view and on-demand pausing replace the two views and the sweep without losing work per GPU.
2. **The wait tail is longer, as predicted for lease 30 s.** Per-session worst TTFT p90 is 435 s and 386 s against 275 s (226-367), TTFT p99 227 s and 164 s against 141 s; strict session attainment 0.61 and 0.60 is inside the reference range. The tail sits where step 16's half-life 10 s arm without the fast sweep was (412 s).
3. **The lease sets how much admission reclaims, as designed.** With lease 30 s, above the replay's 10 s gap cap, admission reclaims almost nothing but finished sessions: pauses fall to 308 and the working set is over capacity in 17 percent of samples, where it waits for a reasoning turn's growth rule to pause someone. With lease 5 s, admission reclaims sessions in longer tool calls: 475 pauses, over capacity in 6 percent of samples, close to the reference's 4 percent, and a shorter tail than lease 30 s, at a slightly lower hit rate.
4. **Prediction check.** Lease 30 s did not reach the reference hit rate (0.778, inside its range but below its mean); its longer tail did appear. Lease 5 s sits closer to the decayed builds, as predicted.

Caveats: one cell per arm against three cells from the day before, no same-day control (by choice); the throughput and hit-rate differences are inside or just below step 16's cell-to-cell spread (lease 5 s throughput 1863 against a 1867 minimum); only the tail rows are clearly outside it. Replicates would settle whether the tail difference is real.

## Results, three cells per arm (2026-09-28)

Replicates in the same run directory, ABBA order: `epp-thunder-lease-c128-r2` (13:32), `epp-thunder-lease5-c128-r2` (14:18), `epp-thunder-lease5-c128-r3` (15:04), `epp-thunder-lease-c128-r3` (15:50), driver log `results/driver-replicates.log`. All six cells complete, not preempted, 338 corpus traces, every artifact intact, no error or warning line in any EPP log (13,035 to 13,628 lines). The main release was restored to revision 84's manifest at 16:36 (revision 89 again, found by manifest). Values are mean (min-max) over three cells; full table in `analysis.md`.

| metric | step 16, half-life 10 s, sweep 1 s | step 17, lease 30 s | step 17, lease 5 s |
|---|---|---|---|
| output throughput (tok/s) | 1945 (1867-2019) | 1931 (1871-2018) | 1859 (1839-1874) |
| steady-state hit rate | 0.795 (0.752-0.820) | **0.819 (0.778-0.849)** | 0.749 (0.724-0.766) |
| prefill tokens computed (M) | 60.7 (57.4-65.3) | **56.0 (51.3-62.0)** | 65.3 (63.3-69.3) |
| TTFT p50 / p90 (s) | 0.5 / 7.0 (6.3-8.0) | 0.5 / 7.3 (6.5-8.5) | 0.6 / 8.6 (8.4-8.9) |
| TTFT p99 (s) | 141 (119-173) | **242 (220-279)** | 139 (122-164) |
| goodput within SLO, TTFT <= 30 s (turns/s) | 1.77 (1.64-1.94) | 1.72 (1.60-1.79) | 1.62 (1.54-1.69) |
| session SLO attainment, strict | 0.64 (0.57-0.70) | 0.67 (0.61-0.70) | 0.61 (0.59-0.63) |
| share of turns over the SLO | 0.032 (0.027-0.042) | 0.028 (0.025-0.034) | 0.038 (0.034-0.042) |
| per-session worst TTFT, p90 (s) | 275 (226-367) | 353 (291-435) | 359 (298-394) |
| sessions whose worst turn exceeded 60 s | 0.24 (0.20-0.31) | 0.22 (0.19-0.23) | 0.27 (0.24-0.30) |
| vLLM waiting, mean steady | 0.7 (0.6-1.0) | 0.9 (0.7-1.2) | 1.1 (0.9-1.2) |
| vLLM preemptions | 7 (5-8) | 7 (6-8) | 14 (10-20) |
| EPP running sessions / vLLM running requests, mean steady | 71 / 70 | 67 / 65 | 72 / 71 |
| working set / capacity per pod, steady, min-max over pods | 0.95-0.98 | 0.96-1.00 | 0.97-0.99 |
| pauses / holds (paused + new) | 532 / 365 | 316 / 231 | 464 / 349 |
| forced admissions / request errors, per cell | 0-0 / 0-1 | 0-1 / 0-0 | 0-2 / 0-1 |

Per cell (throughput, hit rate, TTFT p99, worst-turn p90, forced admissions): lease 30 s 1871 / 0.778 / 227 / 435 / 0, 1903 / 0.830 / 279 / 335 / 1, 2018 / 0.849 / 220 / 291 / 0; lease 5 s 1863 / 0.766 / 164 / 386 / 0, 1874 / 0.724 / 130 / 394 / 0, 1839 / 0.757 / 122 / 298 / 2.

Against the correctness criteria: criteria 1 to 4 and 6 hold in all six cells. Criterion 5 holds in five: `epp-thunder-lease5-c128-r3` had 2 forced admissions, above step 16's 0 to 1. The three request errors (one each in `lease5-r2`, `lease5-r3`; none in the lease 30 s cells) are envoy 503s ("upstream connect error ... connection termination"), the same type step 16 saw in three of its nine cells, but on requests open for 633 s and 1301 s rather than failing at once, so they were held in the gate when the connection was reset.

Readings:

1. **Lease 30 s is at least as efficient as the best minimal arm.** Throughput 0.99x and goodput 0.97x, inside the reference range; hit rate 0.819 is the highest of any c=128 arm so far and prefill work 56.0 M tokens the lowest (0.92x, below the reference range). One view and on-demand pausing, with the default lease, lose nothing in work per GPU against two views and a 1 s sweep.
2. **Its cost is the turn-latency tail, and it is narrower than round 1 suggested.** TTFT p99 is 242 s against 141 s with no overlap between the three-cell ranges; the per-session worst TTFT p90 (353 s against 275 s) and the share of sessions with a turn over 60 s (0.22 against 0.24) overlap the reference, and strict session attainment is at the reference (0.67 against 0.64). Round 1's lease 30 s cell was its weakest cell on every efficiency row. Mechanism, as in round 1: above the replay's 10 s gap cap, admission reclaims almost only finished sessions, so the working set is over capacity in 16 percent of samples (reference 4 percent) and a held session waits for a reasoning turn's growth rule to pause someone on its pod.
3. **Lease 5 s trades work for the p99, and is the worse default here.** Reclaiming sessions in longer tool calls brings TTFT p99 back to the reference (139 s) but costs their prefixes: hit rate 0.749 and prefill 65.3 M, below the reference range, twice the vLLM preemptions, lower goodput and attainment, and the only cell with 2 forced admissions. It sits where step 16's half-life 10 s arm was on efficiency.
4. **Prediction check.** Lease 30 s: hit rate at or above the reference, met (0.819 against 0.795, inside the range); longer wait tail, met for TTFT p99 only. Lease 5 s closer to the decayed builds, met.

Caveats: no same-day control (by choice), though step 16 ran on the same four pods the day before; lease 30 s cells spread widely (1871 to 2018 tok/s, hit rate 0.778 to 0.849), wider than the reference arm's; one load level (c=128) and one workload, whose 10 s gap cap puts every live tool call inside a 30 s lease.

## Where the TTFT tail comes from (2026-09-28, analysis of the cells above, no new runs)

Question: lease 30 s's clearest cost is TTFT p99 (242 s against 141 s for step 16's best arm). Which requests make up that tail, and why do they wait? `tail_analysis.py` matches every client request to its EPP log entry (100 percent matched in all nine cells; the client and EPP clocks differ by a constant offset) and splits TTFT into the hold in the gate (EPP arrival to dispatch) and everything after (scheduling, vLLM queue, prefill). A request is classed new if it is its session's first in the run, paused if it was held more than 1 s (admitted sessions' turns dispatch at once), admitted otherwise. Full table in `tail.md`; three cells per arm, lease 30 s and 5 s against step 16's half-life 10 s, sweep 1 s.

| | minimal, 10 s, sweep 1 s | lease 30 s | lease 5 s |
|---|---|---|---|
| tail (TTFT at or above the cell's p99) that is a paused session | 1.00 | 1.00 | 1.00 |
| hold share of a tail request's TTFT, median | 0.99 | 0.99 | 0.98 |
| tail: engine time (TTFT minus hold), median (s) | 5.0 | 3.9 | 5.6 |
| paused requests per cell | 353 | 220 | 341 |
| paused requests: hold p50 / p90 (s) | 13 / 248 | 26 / 671 | 15 / 199 |
| paused requests held over 60 s | 0.19 | 0.37 | 0.21 |
| paused, prompt above the median: hold p90 (s) | 359 | 589 | 405 |
| paused, prompt at or below the median: hold p90 (s) | 40 | 147 | 57 |
| steady pauses, three cells | 1193 | 693 | 1071 |
| releases of paused sessions in a 2 s interval that also has a pause | 0.90 | 0.81 | 0.91 |
| admission rate, paused + new (per s) / EPP queue, mean | 0.264 / 27.0 | 0.152 / 32.4 | 0.239 / 24.8 |
| Little's law mean wait / measured mean hold of paused requests (s) | 102 / 72 | 213 / 123 | 104 / 74 |
| holds over 60 s released 28-32 s after some session's last response (random times) | 0.06 (0.10) | 0.08 (0.11) | 0.06 (0.10) |

Findings:

1. **The p99 tail is entirely paused sessions waiting in the gate.** In every arm, every tail request is a paused session's next turn, and 98 to 99 percent of its TTFT is the hold before dispatch; once dispatched it takes about 4 to 6 s (the median tail request re-prefills about 75 to 90 k tokens with no cache hit). New sessions, admitted turns and vLLM are not in the tail.
2. **A paused session gets in by swapping with one that is paused.** 81 to 91 percent of releases of paused sessions fall in a 2 s interval that also has a pause, in all three builds: room on a pod appears when an idle session is paused (the sweep in the minimal build; on-demand reclaim in the lease build), and a waiting session takes it.
3. **Lease 30 s swaps half as often, so each paused session waits about twice as long.** On this replay (tool-call gaps capped at 10 s) no live session is ever idle 30 s, so admission almost never reclaims one; pauses come from the growth rule and number 693 against 1071 to 1193. The admission rate falls to 0.15 per s against 0.24 to 0.26 with a longer queue (32 against 25 to 27), so Little's law gives twice the mean wait (213 against 102 to 104 s); the measured mean hold agrees in ratio (123 against 72 to 74 s; Little's law runs higher because requests still held at stage end count in the queue but not in the client report). Fewer sessions are paused (220 against about 350 per cell), which is where the hit rate gain comes from, but those that are wait longer: 37 percent over 60 s against about 20.
4. **Large sessions wait longest in every build.** Within the paused class the gate releases the smallest first, so a paused session above the median prompt size waits a p90 of 359 to 589 s against 40 to 147 s below it. The tail's median prompt (73 to 90 k) is above the paused median (60 to 68 k).
5. **Rejected: waiting for a finished session.** Under a 30 s lease a finished session's room becomes reclaimable 30 s after its last response, so if paused sessions were waiting for sessions to end, long holds would be released 28 to 32 s after one. They are not: 8 percent against 11 percent at random times.

What this means for the design: the lease sets how fast the gate rotates held sessions through the pods, and so trades the hit rate (fewer rotations, fewer re-prefills) against the wait tail (fewer rotations, longer waits), with smallest-first ordering concentrating the wait on large sessions. Levers that follow from this, untested: a lease just above typical tool-call gaps (about 10 s here) to rotate a little more; or an age term in the paused-class order so a large session is not overtaken indefinitely (step 13's age-only and urgent tiers were tried on the v4 port and failed, so this needs care).

Limits: class is inferred from the client side (the plugin's reclaim events are debug-level and not in the EPP log); the pod a request went to is not recorded per request, so the swap is shown at pool level in 2 s intervals, not per pod.
