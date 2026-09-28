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

- Round 1: one cell per arm; replicates only after review.
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

Readings:

1. **The lease build works and lands in step 16's efficiency range.** Throughput, hit rate and prefill work of both arms sit inside or at the edge of the best step 16 arm's range (0.96x throughput, 0.98x and 0.96x hit rate), between step 16's half-life 10 s arms. One view and on-demand pausing replace the two views and the sweep without losing work per GPU.
2. **The wait tail is longer, as predicted for lease 30 s.** Per-session worst TTFT p90 is 435 s and 386 s against 275 s (226-367), TTFT p99 227 s and 164 s against 141 s; strict session attainment 0.61 and 0.60 is inside the reference range. The tail sits where step 16's half-life 10 s arm without the fast sweep was (412 s).
3. **The lease sets how much admission reclaims, as designed.** With lease 30 s, above the replay's 10 s gap cap, admission reclaims almost nothing but finished sessions: pauses fall to 308 and the working set is over capacity in 17 percent of samples, where it waits for a reasoning turn's growth rule to pause someone. With lease 5 s, admission reclaims sessions in longer tool calls: 475 pauses, over capacity in 6 percent of samples, close to the reference's 4 percent, and a shorter tail than lease 30 s, at a slightly lower hit rate.
4. **Prediction check.** Lease 30 s did not reach the reference hit rate (0.778, inside its range but below its mean); its longer tail did appear. Lease 5 s sits closer to the decayed builds, as predicted.

Caveats: one cell per arm against three cells from the day before, no same-day control (by choice); the throughput and hit-rate differences are inside or just below step 16's cell-to-cell spread (lease 5 s throughput 1863 against a 1867 minimum); only the tail rows are clearly outside it. Replicates would settle whether the tail difference is real.
