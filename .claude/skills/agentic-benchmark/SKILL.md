---
name: agentic-benchmark
description: Benchmark agentic (multi-turn, tool-calling) LLM inference on the bobbm GKE cluster with the AgentX harness (aiperf --scenario agentx, weka Claude Code traces) - plan a sweep, deploy vLLM and EPP arms (llm-d default, thunder-agent gate), run points, collect vLLM and EPP metrics, analyze, draw report figures, and write the step report. Use when starting a new numbered step in this repo, running or comparing router or server configurations under an agentic workload, or analyzing AgentX/aiperf results.
---

# Agentic inference benchmark

The workflow and shared scripts for every new benchmark step in this repo. Steps 01 to 22 used inference-perf; from step 23 on the standard client is AgentX (`aiperf --scenario agentx`), the same client and rules as SemiAnalysis InferenceX, so results are comparable with theirs.

Open the reference you need, not all of them:

| Need | Read |
|---|---|
| What to collect, what each `summary.csv` column means, validity rules | [references/metrics.md](references/metrics.md) |
| vLLM flags, EPP arms and timeouts, aiperf settings, concurrency grid | [references/deployment.md](references/deployment.md) |
| Which figures, made with which skill | [references/figures.md](references/figures.md) |
| Report structure and template | [references/report.md](references/report.md) |

## Files

| Path | Role |
|---|---|
| `scripts/run-point.sh` | one concurrency point: fresh server, aiperf Job, EPP scrape sidecar (pool mode), metadata, copy back |
| `scripts/run-sweep.sh` | points in order, then `analyze.py` |
| `scripts/run-lanes.sh` | points in parallel, one vLLM pod (lane) each, from a shared queue; then `analyze.py` |
| `scripts/render-lane-epp.sh` | renders a per-lane EPP release (EPP + envoy that see only that lane's pod) for an arm's plugin file |
| `scripts/vllm-offload.py` | clean copy of the live vLLM deployment, or its CPU KV offloading variant (`--kv-offloading-size`, memory, `/dev/shm`, one replica per node) for `kubectl replace` |
| `scripts/analyze.py` | `summary.csv`, `summary.md` with validity checks; calls `point_figures.py` |
| `scripts/point_figures.py` | per-point figures, the sweep Pareto and the concurrency view, into the report folder (style rules: references/figures.md) |
| `scripts/make_figures.py` | across-arm figures fig1 to fig5 and `ratios.md` |
| `scripts/figstyle.py` | the `scientific-figure-making` style for every figure, PNG only |
| `scripts/epp_scrape.py` | EPP metrics scraper (runs in the Job) |
| `scripts/lib.sh` | cluster constants, `pin_kube`, `vllm_get` |
| `manifests/` | PVC, lane Service, metrics-reader RBAC, EPP arm plugin configs, per-lane EPP values and RBAC (`lane-epp-*.yaml`) |

Scripts live only here. A step folder holds its README, its own config (arm files, values) and `results/` (every figure lives in a `results/.../report/` folder), and calls these scripts with `RESULTS=<step>/results`. Fix or extend a script here, not by copying it into a step. Steps 20 to 23 still hold their own copies; leave them as the record of what those steps ran.

## Workflow

1. **Create the step folder** `NN-<short-name>/` and start its `README.md` from the template in references/report.md: question, setup, arms, grid, SLO, and the expectations written before any run.
2. **Check the cluster is free and as recorded.** Pin the context (the scripts do; for manual kubectl use `--context gke_bobzetian-gke-dev_us-central1_bobbm`). Compare the live vLLM deployment with `model-server/deployment.yaml` (`kubectl diff`). Check no GPU pods are pending and nobody else uses the namespace: pool mode restarts every vLLM pod and the EPP.
3. **Put the arm in place** (references/deployment.md section 3). Save `helm get manifest` before touching the main release. Record every shared-state change in `08-cluster-changes.md`.
4. **Smoke point** after any script, image or config change:
   `RESULTS=$PWD/results MODE=pool RESTART=0 DURATION=120 EXTRA_ARGS="--unsafe-override --num-dataset-entries 8 --warmup-requests-per-lane 1" ../.claude/skills/agentic-benchmark/scripts/run-point.sh 4 smoke1`
   Then check: `summary.md` has numbers, `epp/raw-epp-metrics.txt.gz` exists (pool), `epp-*.log` has no gate warnings ("setups that defeat the gate"), a response carries cached tokens.
5. **Calibration point** (`DURATION=900`) of the baseline at the concurrency that should carry the conclusion: hit rate below 85% or KV peak above 80%, else raise the load.
6. **Sweep**, one label per arm, replicates as `<arm>-r1`, `<arm>-r2`, ...:
   `RESULTS=$PWD/results MODE=pool nohup caffeinate -i ../.claude/skills/agentic-benchmark/scripts/run-sweep.sh thunder-r1 8 16 32 64 128 > results/thunder-r1.log 2>&1 &`
   Alternate arms between replicates so time-of-day effects do not line up with one arm.
   Lane mode can run one point per vLLM pod in parallel (`LANE=a|b|c|d`, references/deployment.md section 3).
7. **Analyze all arms together**: `uv run <skill>/scripts/analyze.py --ttft-slo 60 --skip-minutes 5 --out results/compare/report results/*/c*`. `summary.csv` holds whole-window (AgentX) and steady-state (`ss_*`) columns; the sweep figures use the steady state (references/metrics.md section 2). Read every point's validity line; fix or exclude before going on.
8. **Across-arm figures**: `uv run <skill>/scripts/make_figures.py --out results/compare/report --baseline baseline --name baseline="llm-d default" --name thunder="thunder gate (PR3)" results/compare/report/summary.csv` (steady state by default; `--window whole` for InferenceX-comparable numbers). Open every png.
9. **Write the report** in the step README (references/report.md), then add the step to the repo `README.md` "Steps" list. Restore any shared state you changed.

## Gotchas that cost hours before

- **kube context switches under you** (also mid-run). Every script pins `bobbm` through `$RESULTS/bobbm.kubeconfig`; never run a bare `kubectl` against the shared release.
- **Spot nodes.** A preempted or restarted vLLM or EPP pod empties caches or the gate ledger. `run-point.sh` compares pod uids and restart counts; such a point is invalid, rerun it.
- **Timeouts trim the workload.** A client or proxy timeout shorter than the gate's backstop makes the run measure abandoned turns, not scheduling. Same timeouts in every arm.
- **`--reuse-values` breaks the EPP release**, and Helm keeps only 10 revisions: restore by saved manifest (`16-thunder-minimal-pool/restore-main-release.sh`).
- **The EPP metrics port needs a token** (kube-rbac): the Job runs as `thunderagent-metrics-reader`; apply `manifests/metrics-reader-rbac.yaml` once.
- **Counters are cumulative across runs.** Always use deltas inside the profiling window (the scripts do).
- **aiperf's server-metrics CSV and JSON include the warmup** in their counter totals (CSV prompt tokens = profiling delta + warmup ISL). `analyze.py` reads only the parquet, which covers the profiling window.
- **Requests cancelled at the end of the grace period** appear in no export file, only in `logs/aiperf.log` (`Phase profiling ... cancelled=N`); `analyze.py` reads it from there.
- **The first 5 minutes of profiling run at low load**: lanes wait out recorded first-request gaps until the 300 s per-tree idle cap fires (harness behavior; 25% of a 20 min run, 8% of 60 min).
- **The cluster autoscaler evicts vLLM pods mid-run.** On 2026-10-09 GKE scaled down a spot H100 node that held one lane pod (`deleting pod for node scale down`); the point failed the 10% error threshold. Annotate every vLLM pod used by a run with `cluster-autoscaler.kubernetes.io/safe-to-evict=false` (`run-point.sh` annotates every target pod). Moving lane pods around can also make the autoscaler add a node in another zone.
- **Lane claims: an unclaimed pod is fresh.** Lanes never remove their label, so a pod without one has served no point. The first version of the claim excluded pods that existed before the lane's own delete; with four lanes restarting within seconds, two lanes took each other's replacements and two waited 45 min for a pod that never came (step 24 phase 2). Fixed in `run-point.sh`.
- **Lane envoy and vLLM keep-alive.** vLLM closes idle connections after 5 s; envoy reusing one returns 503 "reset before headers: connection termination", and AgentX aborts on one failed root warmup request. `manifests/lane-epp-values.yaml` sets the upstream `idle_timeout` to 4 s. Gate holds make connections idle longer, so only router arms hit it.
- **Analysis memory.** `analyze.py` on a c=192 point needed about 5 GB and stalled the laptop when memory was short; it blocks `run-lanes.sh` before the next wave. Analyses can be rerun later.
- **Never edit a script while a run uses it.** bash reads a running script from the file as it goes; an edit makes the running copy execute shifted bytes (it broke a lane on 2026-10-09). Finish or stop the runs first.
- **Closed loop**: a faster arm completes more requests and sees a slightly different request mix. Report `completed`.
- **aiperf `worker_id` is not a lane**; a lane is `root_correlation_id`.
- **Results are lost if not copied before teardown.** The PVC keeps every point; `run-point.sh` copies it back at the end, also after a failed job.

## Legacy: inference-perf (steps 07 to 22)

Use only to rerun or extend an old step. Harness: `20-cpu-offload-pool/` (lanes, `run-cells.sh`, `analyze.py`) on `10-llm-d-router-replicates/` plumbing. Always pass `BENCH_IMAGE` with the session-id build (`12-llm-d-router-pool/results/inference-perf-image.txt`): the official v0.7.0 starts only half of the sessions (`INFERENCE-PERF-BUGS.md` issue 4). The `inference-perf` skill covers the tool itself.
