# Step 15: the minimal thunder-agent on one pod, against step 10

Question: does the minimal rewrite of the plugin (llm-d-router `thunder-agent-minimal`, design in `../../thunder-agent-minimal-design.zh.md`) behave like the benchmarked port on a single pod? One pod removes placement from the question: with one pod, origin-only and most-room are the same policy, so what is left is the admission gate itself (fit check, pause sweep, reservation, class order, starvation backstop) and the ledger.

This is a fast check by design: one lane, one cell, no same-day control. The reference is step 10's run `../10-llm-d-router-replicates/results/rep-20260917-173839-c128-t1900` (three lanes, `epp-thunder` on image `thunder-agent-v3`, plus `epp-sticky`), measured at the same protocol.

## What runs

- Build: llm-d-router branch `thunder-agent-minimal` at `33dde5d2` (three commits on upstream `038495c2`: ledger, scorer, admission gate), image `llm-d-router-endpoint-picker:thunder-agent-min-33dde5d2` (`sha256:c71cd081c947...`), built with Cloud Build. `33dde5d2` includes the fix for new-session reservations being dropped by the idle TTL check (found in review before this step, amended into the gate commit).
- Config: `../10-llm-d-router-replicates/thunder-min-plugins.yaml`, the step 10 `thunder` arm in the six keys the minimal plugin accepts: real capacity fallback 2,237,040, `utilThreshold` 1.0, `idleDecayHalfLifeSeconds` 1 (was `actingHalfLifeSeconds`), `pauseSweepSeconds` 5, `headWaitStarvationMs` 1800000, `evictionTtlSeconds` 3600. The old config does not load on this build: the strict decoder rejects the removed keys.
- Lane: step 10 lane `a` (standalone chart, one EPP pinned to one vLLM pod by label), rendered from the current `llm-d-router` chart. That chart differs from the one step 10 rendered in three places that do not touch the plugin: gRPC health service names, a 5 s preStop sleep, and config apiVersion `llm-d.ai/v1`.
- Load: step 10's cell unchanged: inference-perf v0.7.0 (digest-pinned, with the parked-permit bug, so the numbers compare with step 10 and 14 only, not with steps 12 and 13), weka replay, c=128, 45 min, client timeout 1900 s, base seed 20260915, prefix-cache reset and a fresh EPP before the cell.

Behavior differences from v3 that are intended by the design, and what they should do here:

| difference | expected effect on one pod |
|---|---|
| no 100-token buffer per session | about 3k tokens of 2.24M at 30 sessions: none |
| no `markedForPause` (running sessions are not marked; the sweep pauses only idle ones) | the working set can stay over the line longer; vLLM waiting may rise a little |
| no streaming growth update of in-flight tokens | in-flight is underestimated during long outputs; weka outputs are short: small |
| origin-only resume | none on one pod |
| no `x-session-final` | none: the weka replay never sent it (step 07 `PLAN.md`) |

Pass criteria, written before the run: throughput, steady-state hit rate and TTFT p50 inside or near step 10's v3 min-max range (327-367 tok/s, 0.482-0.502, 3.6-4.6 s); vLLM waiting near 0 in steady state; forced admissions and errors of the same order as v3 (8-11 and 5-6).

## Metrics recorded

Everything step 10 recorded (inference-perf reports, prober series at 2 s, EPP log, `kubectl top`), plus:

- `raw-vllm-metrics.txt.gz`, `raw-epp-metrics.txt.gz`: the full text of both scrapes every 10 s, so any metric can be recovered afterwards. `analyze.py` turns them into `raw-metrics-<cell>.md`: the delta of every counter and histogram over the run. Not in the repo: `raw-epp-metrics.txt.gz` (27 to 48 MB per cell, gitignored; its deltas are in `raw-metrics-<cell>.md`) and, as for every earlier step, `per_request_lifecycle_metrics.json`.
- `epp-metrics.csv` columns `working_set_undecayed`, `working_set_decayed`, `capacity_tokens` (the minimal build replaced `pod_utilization` with absolute working-set gauges).
- per cell: `vllm.log.gz` (vLLM log for the cell window) and `epp-configmap.yaml`.

## Files

- `deploy-lane.sh [image-tag]`: labels one vLLM pod `thunder-lane=a` and applies the lane with the `thunder-min` arm. All lane files go to `results/`, so step 10's recorded lane files stay untouched.
- `smoke-test.sh`: step 09's checks adapted to the minimal build and one lane (metrics only; the minimal plugin has no state dump). 20 checks.
- `analyze.py <run> [step10 run]`: `analysis.md` (every shared metric, step 10 sticky and v3 as mean (min-max), thunder-min / v3 and whether it lies inside the v3 range), `raw-metrics-<cell>.md`, `timeseries.png`.
- Shared with step 10 (changed for this step, defaults unchanged): `run-replicates.sh` (`RESULTS_DIR`, the `thunder-min` arm check, vLLM log and ConfigMap per cell), `render-lane.sh` (`RESULTS_DIR`, accepts the newer chart's quoted config map name), `prober.py` (raw snapshots, working-set columns).

## Steps

1. `~/.claude/skills/cloud-build-epp/build-epp.sh thunder-agent-min-33dde5d2` in the llm-d-router `thunder-agent-minimal` checkout.
2. `./deploy-lane.sh`
3. `./smoke-test.sh | tee results/smoke-test-output.txt`
4. `RESULTS_DIR="$PWD/results" EPP_IMAGE_TAG=thunder-agent-min-33dde5d2 ../10-llm-d-router-replicates/run-replicates.sh 128 1 2700 thunder-min 1900`
5. `uv run --with matplotlib --with numpy python analyze.py results/<run>`
6. Tear down: `kubectl delete -f results/lane-a-manifest.yaml` and `kubectl label pod <pod in results/lanes.env> thunder-lane- -n llm-d-program-aware-scheduling`.

## Smoke test (2026-09-27)

All 20 checks pass (`results/smoke-test-output.txt`): `llm_d_epp_info` reports commit `33dde5d2`; the minimal metric set is exported and the removed metrics are gone; the lane pod reports real capacity 2,237,040; three turns answered; two sessions tracked, none running or paused after the turns, working set above 0; releases new +2 and reasoning +1; no holds or pauses at real capacity. The first run failed only the build-info check, because the metric was renamed from `inference_extension_info` to `llm_d_epp_info` upstream; the check now accepts both.

## Results (2026-09-27, `results/rep-20260927-173546-c128-t1900`)

One cell, `epp-thunder-min-r1`, on pod `program-aware-vllm-decode-9c9b54cb6-dk9ld`, 17:37 to 18:28 PDT, not preempted, reports complete. Full table (about 30 metrics) in `analysis.md`, every raw counter and histogram delta in `raw-metrics-epp-thunder-min-r1.md`, series in `timeseries.png`. Step 10 values are mean (min-max) over its three lanes.

| metric | step 10 sticky | step 10 thunder v3 | step 15 thunder-min |
|---|---|---|---|
| output throughput (tok/s) | 227 (221-236) | 351 (327-367) | **397** |
| steady-state hit rate | 0.003 | 0.489 (0.482-0.502) | **0.573** |
| prefill tokens computed (M) | 53.6 | 41.5 (40.9-42.8) | 38.5 |
| TTFT p50 / p90 (s) | 49.4 / 113.5 | 4.0 / 22.0 | 2.2 / 15.0 |
| TTFT p99 (s) | 146.6 | 409.7 (352.9-462.7) | **712.4** |
| turns with TTFT over 300 s / over 1200 s | - | 17-24 / 4-6 | **32 / 10** |
| vLLM waiting, mean steady | 20.4 | 0.3 | 0.5 |
| vLLM KV usage, mean steady | 0.92 | 0.89 | 0.90 |
| EPP pauses / resumes | 0 / 0 | 971 / 921 | **345 / 311** |
| EPP holds (paused + new) | 0 | 648 | 265 |
| undecayed working set over capacity, share of samples | - | 0.24 | **0.65** |
| forced admissions / request errors | 0 / 0 | 10 / 6 | 7 / 1 |

Against the pass criteria: the gate works and the ledger closes. vLLM waiting stays at 0.5 (sticky: 20), KV at 0.90, the EPP log has no errors or warnings, the EPP's running-session count follows vLLM's running count (28 vs 28), forced admissions and errors are at or below v3. Throughput, hit rate and TTFT p50 are outside the v3 range, but on the better side.

The difference is the intended removal of `markedForPause`, and it has a clear signature. v3 marked running sessions on an over-full pod and paused them at the end of their turn; the minimal build pauses only sessions that are idle when the sweep runs (every 5 s), so a session whose tool call is shorter than the gap to the next sweep is never paused. Pauses fall from 971 to 345, fewer sessions lose their prefix, the hit rate rises from 0.49 to 0.57 and prefill work falls 7 percent. The cost is that the undecayed working set sits over capacity in 65 percent of samples instead of 24 percent, so the paused and new sessions that do wait, wait longer: TTFT p99 712 s vs 410 s, and 10 turns waited over 20 minutes vs 4 to 6. The engine does not thrash in exchange (waiting 0.5, preemptions 6 vs 1).

Caveats: one cell against three from ten days earlier, no same-day control; a different vLLM pod and a newer chart than step 10; the load generator has the parked-permit bug (same as step 10). The throughput gain of 13 percent is outside v3's 12 percent spread, and the hit rate gap is four times v3's spread, so the direction is likely real, but its size needs replicates. The long-wait tail is the metric to watch if the minimal build is benchmarked again; `markedForPause` or a shorter `pauseSweepSeconds` are the design's documented levers for it (design section 8).
