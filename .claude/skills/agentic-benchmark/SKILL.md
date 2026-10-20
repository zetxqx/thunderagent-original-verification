---
name: agentic-benchmark
description: Benchmark multi-turn, tool-calling (agentic) LLM inference against a Kubernetes vLLM deployment, with or without a router (llm-d EPP) in front, using the AgentX harness (aiperf --scenario agentx). Plan the sweep, run concurrency points, validate them, analyze, draw the report figures and write the step report. Use when starting a new numbered benchmark step in this repo, comparing server or router configurations under an agentic workload, or analyzing aiperf/AgentX results.
---

# Agentic inference benchmark

The workflow and shared scripts for every new benchmark step in this repo. Steps 01 to 22 used inference-perf; from step 23 on the standard client is AgentX (`aiperf --scenario agentx`), the same client and rules as SemiAnalysis InferenceX, so results are comparable with theirs. The scripts target one cluster at a time through a profile (`profiles/<name>.env`, default `bobbm`): cluster, namespace, deployment, container, images and dataset come from there, and any value can be overridden from the environment.

The scripts live in the repo at `.claude/skills/agentic-benchmark/`; a copy installed elsewhere (for discovery) needs `REPO_ROOT=<repo checkout>` so `model-server/collect.sh` and the step folders resolve. Prerequisites on the machine that runs the scripts: `kubectl` with a context for the target cluster, `helm` (lane EPPs), `uv` (Python scripts declare their own dependencies), `gcloud` only for Cloud Logging. Runs take hours: start them with `nohup ... &` and keep the machine awake (macOS: `caffeinate -i`).

Open the reference you need, not all of them:

| Need | Read |
|---|---|
| What to collect, what each `summary.csv` column means, validity rules | [references/metrics.md](references/metrics.md) |
| vLLM flags, EPP arms and timeouts, aiperf settings, concurrency grid | [references/deployment.md](references/deployment.md) |
| Which figures, made with which skill | [references/figures.md](references/figures.md) |
| Report structure and template | [references/report.md](references/report.md) |
| What went wrong before, with dates, and the rule each failure left | [references/incidents.md](references/incidents.md) |

## Files

| Path | Role |
|---|---|
| `scripts/run-point.sh` | one concurrency point: fresh server, aiperf Job, EPP scrape sidecar (pool mode), metadata, copy back |
| `scripts/run-sweep.sh` | points in order, then `analyze.py` |
| `scripts/run-lanes.sh` | points in parallel, one vLLM pod (lane) each, from a shared queue; then `analyze.py` |
| `scripts/verify-point.sh` | the smoke checklist on one or more point folders (bash + python3 only) |
| `scripts/render-lane-epp.sh` | renders a per-lane EPP release (EPP + envoy that see only that lane's pod) for an arm's plugin file |
| `scripts/vllm-offload.py` | clean copy of the live vLLM deployment, or its CPU KV offloading variant (`--kv-offloading-size`, memory, `/dev/shm`, one replica per node) for `kubectl replace` |
| `scripts/analyze.py` | `summary.csv`, `summary.md` with validity checks; calls `point_figures.py` |
| `scripts/router_metrics.py` | EPP scrape parser, `gate_*` and `epp_*` columns and checks (`GATE_METRIC_PREFIX` for another gate plugin) |
| `scripts/point_figures.py` | per-point figures, the sweep Pareto and the concurrency view, into the report folder (style rules: references/figures.md) |
| `scripts/make_figures.py` | across-arm figures fig1 to fig5 and `ratios.md` |
| `scripts/export_bundle.py` | one JSON bundle per step for the interactive dashboard (repo `dashboard/`, format in `dashboard/SCHEMA.md`) |
| `scripts/figstyle.py` | the `scientific-figure-making` style for every figure, PNG only |
| `scripts/epp_scrape.py` | EPP metrics scraper (runs in the Job) |
| `scripts/lib.sh` | loads the profile, `pin_kube`, `vllm_get`, `selector_yaml` |
| `profiles/<name>.env` | cluster, namespace, deployment, selector, container, images and dataset of one target (`PROFILE=<name>`, default `bobbm`); every value can still be overridden from the environment |
| `manifests/` | PVC, lane Service, metrics-reader RBAC, EPP arm plugin configs, per-lane EPP values and RBAC (`lane-epp-*.yaml`) |
| `tests/` | pytest for `analyze.py`, `router_metrics.py` and `verify-point.sh` on a synthetic point; run with `tests/run.sh` (uv) after changing a parser or a check |

Scripts live only here. A step folder holds its README, its own config (arm files, values) and `results/` (every figure lives in a `results/.../report/` folder), and calls these scripts with `RESULTS=<step>/results`. Fix or extend a script here, not by copying it into a step. Steps 20 to 23 still hold their own copies; leave them as the record of what those steps ran.

## Workflow

1. **Create the step folder** `NN-<short-name>/` and start its `README.md` from the template in references/report.md: question, setup, arms, grid, SLO, and the expectations written before any run.
2. **Check the cluster is free and as recorded.** Pin the context (the scripts do; for manual kubectl pass `--context <the profile's CTX>`). Compare the live vLLM deployment with `model-server/deployment.yaml` (`kubectl diff`). Check no GPU pods are pending and nobody else uses the namespace: pool mode restarts every vLLM pod and the EPP.
3. **Put the arm in place** (references/deployment.md section 3). Save `helm get manifest` before touching the main release. Record every shared-state change in `08-cluster-changes.md`.
4. **Smoke point** after any script, image or config change:
   `RESULTS=$PWD/results MODE=pool RESTART=0 DURATION=120 EXTRA_ARGS="--unsafe-override --num-dataset-entries 8 --warmup-requests-per-lane 1" ../.claude/skills/agentic-benchmark/scripts/run-point.sh 4 smoke1`
   Then `scripts/verify-point.sh results/smoke1/c4`: job succeeded and pods unchanged, completed profiling requests, the server-metrics parquet, a response carrying cached tokens, and in pool or lane-EPP mode the EPP scrape and no gate warning ("setups that defeat the gate") in `epp-*.log`. Then read `summary.md`.
5. **Calibration point** (`DURATION=900`) of the baseline at the concurrency that should carry the conclusion: hit rate below 85% or KV peak above 80%, else raise the load.
6. **Sweep**, one label per arm, replicates as `<arm>-r1`, `<arm>-r2`, ...:
   `RESULTS=$PWD/results MODE=pool nohup ../.claude/skills/agentic-benchmark/scripts/run-sweep.sh thunder-r1 8 16 32 64 128 > results/thunder-r1.log 2>&1 &`
   Alternate arms between replicates so time-of-day effects do not line up with one arm.
   Lane mode can run one point per vLLM pod in parallel (`LANE=a|b|c|d`, references/deployment.md section 3).
7. **Analyze all arms together**: `uv run <skill>/scripts/analyze.py --ttft-slo 60 --skip-minutes 5 --out results/compare/report results/*/c*`. `summary.csv` holds whole-window (AgentX) and steady-state (`ss_*`) columns; the sweep figures use the steady state (references/metrics.md section 2). Read every point's validity line; fix or exclude before going on.
8. **Across-arm figures**: `uv run <skill>/scripts/make_figures.py --out results/compare/report --baseline baseline --name baseline="llm-d default" --name thunder="thunder gate (PR3)" results/compare/report/summary.csv` (steady state by default; `--window whole` for InferenceX-comparable numbers). Open every png. Then export the step for the dashboard: `uv run <skill>/scripts/export_bundle.py --out ../dashboard/data/<step>.json --title "..." --baseline baseline --name baseline="..." --kv-bytes-per-token 49152 results/*/c*` (same `--name` values; one point at a time, about 1 MB per 20 points; `--kv-bytes-per-token` gives offload points their CPU tier size, 49152 for Qwen3-Coder-30B-A3B with FP8 KV).
9. **Write the report** in the step README (references/report.md), then add the step to the repo `README.md` "Steps" list. Restore any shared state you changed.

## Gotchas

Rules that cost hours before. The stories behind the dated ones are in [references/incidents.md](references/incidents.md).

**Method**

- **Timeouts trim the workload.** A client or proxy timeout shorter than the gate's backstop makes the run measure abandoned turns, not scheduling. Same timeouts in every arm.
- **Counters are cumulative across runs.** Always use deltas inside the profiling window (the scripts do).
- **Closed loop**: a faster arm completes more requests and sees a slightly different request mix. Report `completed`.
- **Results are lost if not copied before teardown.** The PVC keeps every point; `run-point.sh` copies it back at the end, also after a failed job.
- **Never edit a script while a run uses it.** bash reads a running script from the file as it goes; an edit makes the running copy execute shifted bytes. Finish or stop the runs first.

**Kubernetes and the cluster**

- **kube context switches under you** (also mid-run). Every script pins the profile's context through `$RESULTS/<profile>.kubeconfig`; never run a bare `kubectl` against the shared release.
- **A replaced or restarted pod invalidates the point** (spot preemption, node scale-down, a crash): caches and the gate ledger are empty. `run-point.sh` compares pod uids and restart counts; rerun such a point.
- **The cluster autoscaler evicts pods mid-run.** `run-point.sh` annotates every target pod `cluster-autoscaler.kubernetes.io/safe-to-evict=false`. Moving lane pods around can also make the autoscaler add a node in another zone.
- **A bad GPU node kills points** ("CUDA error: an illegal memory access", always on the same node). The pod's logs go with it: read the crash in Cloud Logging (`gcloud logging read 'resource.labels.pod_name="<pod>"'`), then cordon the node. With CPU offload the crashed container cannot restart (the old offload file still fills `/dev/shm`).
- **A leftover Job blocks a rerun** ("job ... already exists; pick another run label"). Delete the failed point's Job before rerunning it, and when you stop a point by hand, kill its `run-point.sh` and delete its Job, or aiperf keeps running.
- **API server throttling.** `kubectl apply` of a lane EPP can fail with "ENHANCE_YOUR_CALM" and leave half the objects missing; retry the apply.
- **Credential outages** ("print credential failed", for minutes on GKE): `run-point.sh` waits up to 30 min for the API; if a point still ends early, its data is on the PVC and can be fetched afterwards.
- **Analysis memory.** `analyze.py` on a c=192 point needs a few GB; it blocks `run-lanes.sh` before the next wave. Analyses can be rerun later.

**aiperf and the AgentX scenario**

- **aiperf's server-metrics CSV and JSON include the warmup** in their counter totals. `analyze.py` reads only the parquet, which covers the profiling window.
- **Requests cancelled at the end of the grace period** appear in no export file, only in `logs/aiperf.log` (`Phase profiling ... cancelled=N`, with thousands separators); `analyze.py` reads it from there.
- **The first 5 minutes of profiling run at low load**: lanes wait out recorded first-request gaps until the 300 s per-tree idle cap fires (harness behavior; 25% of a 20 min run, 8% of 60 min). The `ss_*` columns and the sweep figures start after minute 5.
- **One failed root warmup request aborts an AgentX run.** vLLM closes idle connections after 5 s; aiohttp (direct mode) or envoy (lane EPP) can reuse one it just closed and get a reset or a 503. `lane-epp-values.yaml` sets envoy's upstream `idle_timeout` to 4 s; in direct mode rerun the point.
- **aiperf `worker_id` is not a lane**; a lane is `root_correlation_id`.

**Router (EPP) and the gate**

- **`--reuse-values` breaks the EPP release**, and Helm keeps only 10 revisions: save `helm get manifest` first and restore by saved manifest (`16-thunder-minimal-pool/restore-main-release.sh`), never by revision number.
- **The EPP metrics port needs a token** (kube-rbac): the Job runs as the profile's `METRICS_READER_SA`; apply `manifests/metrics-reader-rbac.yaml` once.
- **EPP per-flow series appear mid-window** (the queue-duration histogram has one series per session): their base is 0, not their first value in the window. The histogram's top finite bucket is 60 s, so a router-wait quantile above 60 s is unknown; `analyze.py` leaves it empty and reports `epp_queue_wait_over_top_bucket_pct`.
- **Lane claims: an unclaimed pod is fresh.** Lanes never remove their label, so a pod without one has served no point; lanes restarting together each take one.

## Legacy: inference-perf (steps 07 to 22)

Use only to rerun or extend an old step. Harness: `20-cpu-offload-pool/` (lanes, `run-cells.sh`, `analyze.py`) on `10-llm-d-router-replicates/` plumbing. Always pass `BENCH_IMAGE` with the session-id build (`12-llm-d-router-pool/results/inference-perf-image.txt`): the official v0.7.0 starts only half of the sessions (`INFERENCE-PERF-BUGS.md` issue 4). The `inference-perf` skill covers the tool itself.
