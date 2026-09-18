# Step 10: the step 08 replicate protocol through the llm-d-router EPP

Question: does the ported `thunder-agent` plugin (step 09, upstream tr-decay semantics) reproduce upstream's effect on the same workload, the same pods, and the same load? Step 08 is the reference: Python router, c=128, one pod per lane, 45 minutes, three replicates: proxy 221 tok/s, tr-decay 469 tok/s, steady-state hit rate 0.008 vs 0.685.

## Design

Two arms per lane, sequential on the same pod, with a prefix-cache reset and a fresh EPP between them:

- `epp-thunder`: the plugin as deployed in step 09 (`thunder-plugins.yaml`).
- `epp-sticky`: the same plugin with the flow-control gate off (`sticky-plugins.yaml`): sticky placement and least-token spreading, no holds, no pauses. The EPP twin of step 08's proxy arm; it isolates admission control the way step 06 did.

Three lanes in parallel, one vLLM pod each on distinct nodes, arm order alternated across lanes (a: sticky then thunder; b: thunder then sticky; c: sticky then thunder). Lane = replicate. Load is step 08's inference-perf job unchanged except two things: the client `request_timeout` is 1900 s so the 1800 s forced admission is never counted as an error (the step 08 write-up asked for this), and the prober scrapes the lane's EPP instead of the Python router.

Pre-registered expectations: `epp-sticky` near 221 tok/s; `epp-thunder` near 469 tok/s with a steady-state hit rate near 0.68 and holds mostly under 12 s with a tail to minutes. If `epp-thunder` lands clearly between the two, the suspects in order are the ext_proc round trip per turn, event-driven admission versus upstream's 5 s tick, and the sticky-if-fits resume; each leaves a distinct signature in the prober series.

## How a lane is built

The EPP normally watches an InferencePool. To pin one EPP to one pod without touching the pool or the vLLM deployment, each lane runs the chart's standalone mode: `router.inferencePool.create: false` plus `matchLabels: {thunder-lane: X}`, which becomes `--endpoint-selector thunder-lane=X`. `deploy-lanes.sh` labels one running pod per node and applies the lane. Two chart problems had to be worked around, both recorded in the scripts:

- The envoy ConfigMap has a fixed name (`envoy`) that collides with the main release, and the Deployment mounts it by that hardcoded name even when `router.proxy.configMap.name` is set. Lanes are therefore rendered with `helm template` and the one volume reference is rewritten (`render-lane.sh`), then applied with kubectl. Lanes are not Helm releases; `teardown-lanes.sh` deletes the rendered manifests.
- Standalone mode creates only namespaced RBAC, but the metrics port authenticates readers through TokenReview, which needs cluster scope. `lane-rbac.yaml` binds the three lane service accounts to `system:auth-delegator`, as the main release has.

The envoy config is the chart's own preset with the ext_proc `message_timeout` raised from 1000 s to 2400 s: a held request sits inside that ext_proc exchange, so without this a hold longer than about 16 minutes would fail at envoy before the 1800 s backstop. The route timeout is already a day.

## Files

- `thunder-plugins.yaml`, `sticky-plugins.yaml`: the two arm configs.
- `lane-values-tmpl.yaml`, `render-lane.sh`, `lane-rbac.yaml`, `deploy-lanes.sh`, `teardown-lanes.sh`: lane plumbing.
- `config-tmpl.yaml`, `job-weka.yaml`, `filter_traces.py`, `prober.py`: the benchmark cell, from step 08 with the changes above. The bench pod runs as `thunderagent-metrics-reader` (step 09) so the prober can read the EPP metrics port.
- `run-replicates.sh [conc] [reps] [window_s] [arms]`: the driver. `128 1 600 thunder` is the calibration; defaults are the main run.
- `plot_timeseries.py`: per-lane time series (hit rate, KV, in flight, paused and queued) for both arms with the step 08 lane as reference.
- `analyze.py`: step 08's analyzer with the EPP series (holds, pauses, resumes, peak paused, forced admissions, mean queue wait) and a reference table against the step 08 Python arms. The step 08 "same sessions" comparison is not available: the EPP state dump lists no program ids.
- `results/`: `lanes.env` (lane to pod mapping), rendered lane manifests and values, `cal-*` and `rep-*` runs.

## Steps

1. `./deploy-lanes.sh thunder`
2. Calibration: `./run-replicates.sh 128 1 600 thunder`, then check holds, pauses, in-flight concurrency, and envoy errors before spending pod-hours.
3. Main run: `./run-replicates.sh` (c=128, 3 replicates, 45 min, both arms). About 1 h 40 min wall time.
4. `./teardown-lanes.sh` when done.

## Calibration (2026-09-17, `results/cal-20260917-171906-c128`)

One lane, `epp-thunder`, c=128, 10 minutes. Purpose: confirm the regime before spending pod-hours.

| signal | value | step 08 reference |
|---|---|---|
| output throughput | 445 tok/s (whole 10 min, all warm-up) | tr-decay 469 over 45 min |
| in-flight requests after 60 s | mean 34, peak 48 | ceiling about 48, set by the load generator |
| vLLM KV usage | mean 0.78, peak 1.00 | peaked 0.96 in step 05 |
| EPP holds / pauses / resumes | 217 / 363 / 325 | - |
| programs paused at once | mean 14, peak 38 | max 186 in step 05 at 4x on 4 pods |
| mean queue wait | 13.4 s | 67% of holds under 12 s in step 07 |
| forced admissions, rebinds, errors | 0 / 0 / 0 | - |

The mechanism is fully engaged through the EPP: the undecayed working set sat at 99 percent of capacity, idle programs were paused by the sweep, in-flight ones were marked and paused at the end of their turn, and their next turns were held until room opened. The lane EPP used about 0.5 core. The 10-minute steady-state hit rate row in `analysis.md` is not meaningful (the whole window is warm-up by step 08's definition). The `EXIT=137` in the bench log is the job's own kill after the last report is written, as documented in `job-weka.yaml`.

## Results (2026-09-17, two runs)

Run 1, client timeout 1900 s (`results/rep-20260917-173839-c128-t1900`): `epp-sticky` 227 tok/s, `epp-thunder` 351 tok/s (1.54x), steady-state hit rate 0.49. Run 2, step 08's 600 s client (`results/rep-20260917-221857-c128-t600`): 225 vs 405 tok/s (1.80x), hit rate 0.48, same session churn as step 08. Upstream's step 08 number, 2.12x, rests on two artifacts the port does not have: the 600 s client trimmed the workload in tr-decay's favor, and the Python router keeps client-abandoned requests on its books as REASONING programs forever (its REASONING count reaches 76 to 83 while vLLM runs 17 to 20), which throttles admission into a lighter, hotter engine in the last third of each run. Under equal load the two schedulers match on hit rate. Details, tables, time-series figures and the step 11 plan (a `utilThreshold` sweep) in `RESULTS.md`.
