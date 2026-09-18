# Original ThunderAgent router setup (paper verification)

Goal: run the original (upstream Python) ThunderAgent router from the paper (arXiv 2602.13692, commit `7ddc861` of `ThunderAgent/`) against the real vLLM backends in the `llm-d-program-aware-scheduling` namespace, so the paper's program-aware scheduling behavior can be verified on a live cluster.

This folder records every step. Files are numbered in the order they were used.

## Environment baseline (2026-09-15)

- Cluster: GKE `bobbm` (`gke_bobzetian-gke-dev_us-central1_bobbm`)
- Namespace: `llm-d-program-aware-scheduling`
- Backends: Deployment `program-aware-vllm-decode`, 4 replicas of `vllm/vllm-openai:v0.28.0`, model `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8`, TP=2 on H100 (spot), serving port 8000
- Full serving-side reference (engine flags, resolved batch and chunked-prefill settings, KV pool, hardware, change history): `model-server/README.md`, re-collectable with `model-server/collect.sh`
- Already present (untouched by this setup): the llm-d EPP with the Go `thunder-agent` plugin (`program-aware-scheduling-epp`)
- Upstream ThunderAgent source: `../ThunderAgent` at git commit `7ddc861`, clean working tree

The original router is a Python FastAPI proxy. Clients send OpenAI chat completions to it with a `program_id` in the body (or `X-Session-ID` header); it tracks per-program token state, schedules admission against each backend's KV capacity (fetched from vLLM `/metrics` at startup: `vllm:cache_config_info` block_size x num_gpu_blocks), and proxies to a sticky vLLM backend.

## Steps

### 1. Build the container image (Cloud Build)

The upstream repo has no Dockerfile. `01-image/Dockerfile` packages it with `pip install .` (deps: fastapi, httpx, uvicorn). The host here is an arm64 Mac without Docker, so the image is built for amd64 with Google Cloud Build via `01-image/build.sh`, which:

1. Stages the upstream source plus the Dockerfile into a temp dir (the upstream checkout is not modified).
2. Runs `gcloud builds submit` in project `bobzetian-gke-dev`.
3. Pushes `us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/thunderagent-original:7ddc861`.

Run: `./01-image/build.sh`

### 2. Deploy to the cluster

Manifests in `02-deploy/`, applied with `kubectl apply -f 02-deploy/`:

- `backends-headless.yaml`: headless Service `thunderagent-vllm-backends` selecting the existing vLLM pods on port 8000. Used only for DNS discovery of pod IPs.
- `launcher.py`: startup script, mounted as ConfigMap `thunderagent-launcher`. Needed because of an upstream bug: the `thunderagent` CLI silently ignores all its flags (the router is created at package import time with the default config, before `main()` sets the CLI config). The first deployment attempt proved it: the pod logged `Started router with 1 backend(s): ['http://localhost:8000']` despite a correct `--backends` flag. The launcher uses upstream's documented embedding API (`Config` + `MultiBackendRouter` + `register_routes`) so the config actually takes effect. No upstream source is modified.
- `thunderagent.yaml`: Deployment (1 replica, CPU node) + Service `thunderagent-router` on port 8300.

Apply order:

```
cd 02-deploy
kubectl create configmap thunderagent-launcher --from-file=launcher.py -n llm-d-program-aware-scheduling
kubectl apply -f backends-headless.yaml -f thunderagent.yaml
```

ThunderAgent takes a static `--backends` list at startup. The pod's entrypoint resolves the headless service DNS, waits until all 4 backend IPs are visible, then execs:

```
python /launcher/launcher.py --router tr --backend-type vllm --backends http://<ip1>:8000,... --port 8300 --metrics --profile
```

Flags match the paper's "tr" (ThunderAgent router) mode with defaults: scheduler interval 5s, acting-token-weight 1.0, decay off. `--metrics` enables the 5s background metrics poll (needed for the shared_tokens prefix discount), `--profile` enables per-program timing needed for verification.

Limitation (accepted for a verification setup): backend IPs are resolved once at startup. If a spot vLLM pod is replaced, restart the router: `kubectl rollout restart deploy/thunderagent-original -n llm-d-program-aware-scheduling`.

### 3. Smoke test

`03-verify/smoke-test.sh` port-forwards to the router service and checks, in order:

1. `GET /health` - router mode is `tr`, scheduling enabled, 4 backends
2. `GET /v1/models` - proxying to vLLM works
3. Two chat completions for the same `program_id` (multi-turn), one for a second program
4. `GET /programs` - both programs tracked with token counts and step counts, sticky backend recorded
5. `GET /metrics` - per-backend KV capacity (cache_config) fetched, kv usage and prefix-cache hit rate visible
6. `POST /programs/release` - explicit release works

Run: `./03-verify/smoke-test.sh` (results recorded in `03-verify/smoke-test-results.md`)

### 4. Benchmark with metrics time series

`04-benchmark/benchmark.py` drives N concurrent agentic sessions (one `program_id` each, unique large preamble, growing multi-turn context) through the router, while a prober thread records 2s-interval time series of per-backend prefix-cache hit rate (computed from counter deltas), KV cache utilization, queue depth, and the router's program-state counts (REASONING/ACTING/paused). It then validates the run: all requests OK, sticky routing per program, aggregate hit rate above threshold, KV cache touched, programs tracked and released. Exit code is non-zero if any check fails.

Run: `./04-benchmark/run-benchmark.sh` (pass-through flags, e.g. `--sessions 24 --turns 8`). Results of the recorded run: `04-benchmark/results.md`, all checks PASS, aggregate prefix-cache hit rate 0.799 with sticky placement confirmed on all 12 sessions.

### 5. Saturation test (admission control / pause+resume)

`05-saturation/` runs the same benchmark script as an in-cluster Job at 2.2x KV over-subscription (320 sessions x ~61k tokens against 8.95M tokens total capacity) to verify the paper's pause/resume admission control. The benchmark script gained per-session release (required: capacity only frees on release), start ramp, pause profiling, and an `--expect-pauses` check for this.

Run: `./05-saturation/run-saturation.sh`. Recorded run: all 6 checks PASS - max 186 programs paused concurrently, 318/320 programs held at admission, KV peaked at 96%, everything resumed and completed. Details: `05-saturation/results.md`.

### 6. Single-node A/B: tr vs default (the paper's headline claim)

`06-single-node-ab/` compares the original router's `tr` mode against `default` (pure proxy) on ONE vLLM pod, so admission control is isolated from placement. Workload scaled to one node: 80 sessions x ~61k tokens = 2.2x over-subscription. Arms run sequentially against the same pod with a prefix-cache reset between them (`run-ab.sh` orchestrates: reset -> deploy `thunderagent-ab` router in the arm's mode -> in-cluster job -> collect; `compare.py` renders the comparison).

Recorded results (two runs): with per-session release, tr is 1.5x faster end-to-end (457s -> 305s, hit rate 0.000 -> 0.362). The main run then removed ALL release calls (realistic: clients never signal completion) across three arms: `default` 457.5s, `tr + acting decay` **315.3s (1.45x faster, no release needed)**, `tr without decay` **3677.7s (8x slower - held sessions serve full 1800s forced-resume timeouts because capacity accounting never frees)**. Conclusion: the paper's mechanism survives uncooperative clients only with `--use-acting-token-decay` enabled (off by default upstream). Details: `06-single-node-ab/results.md`.

### 7. Weka trace replay A/B (done)

`07-inference-perf-weka/` replays REAL Claude Code sessions (weka dataset, official inference-perf v0.7.0, digest-pinned) through the router: `default` vs `tr-decay` at c=96/128/192, 45 min per cell, three lanes in parallel on three pods, paired per-request analysis.

**Result: tr-decay delivers 2.0-2.4x the output-token throughput and lifts the prefix-cache hit rate from 0.04-0.10 to 0.54-0.69**, with TTFT p50 an order of magnitude lower. The paired per-request analysis was later found unsound (`graph_event_id` is not unique per session) and is retracted in `07-inference-perf-weka/RESULTS.md`; every arm-level result stands. Design and version pins: `PLAN.md`; incident write-ups: `HANG-INVESTIGATION.md`, `UPSTREAM-ISSUES.md`.

### 8. Replicated A/B (done) - error bars, warm-up split, per-session fairness

`08-weka-replicates/` runs ONE configuration (c=128) three times instead of sweeping concurrency, because the sweep turned out to measure a single operating point while changing which traces were sampled.

**Result: 2.12x throughput, reproducible to +-1.3%** across three independent replicates, and **85x steady-state hit rate** (0.008 -> 0.685); TTFT p50 52.7s -> 3.0s. Three things the single-run sweep could not show:

- the arms are **indistinguishable during warm-up** (hit rate 0.197 vs 0.188) and all run-to-run noise lives there - which is why the earlier 10-minute cells disagreed by 2.6x;
- restricted to the sessions **both** arms touched, per-session progress is **1.3x**, not 2.1x (the rest of the system-level gain comes from reaching more sessions);
- the ~50-request in-flight ceiling is the **load generator**, not the single-process router (measured: router 0.06-0.11 cores).

Open item, resolved in step 10: the extra errors were 600 s client timeouts on the longest-held sessions, and each one also dropped that session's remaining turns from the workload (about 2300 per tr cell), so the 2.12x is measured on a client-trimmed workload; see the addendum in `08-weka-replicates/RESULTS.md`.

### 9. llm-d-router port on the cluster: smoke test (done)

`09-llm-d-router-smoke/` puts the rewritten `thunder-agent` EPP plugin (upstream tr-decay semantics: 1 s acting decay, 5 s pause sweep, paused-before-new admission, 1800 s forced admission) on the same 4 pods and checks the plumbing with simple traffic: the running build, the new config parsed, real scraped capacity on all pods, program accounting per turn, class ordering, stickiness, and session-final release. **All 20 checks pass.** No load and no holds yet; that is the next step. Details: `09-llm-d-router-smoke/README.md`.

### 10. llm-d-router port: the step 08 protocol through the EPP (done)

`10-llm-d-router-replicates/` runs step 08's replicate protocol through per-lane EPPs, `epp-sticky` (scorer only) vs `epp-thunder` (the port), twice: with a 1900 s client and with step 08's 600 s client. **The EPP path is free (sticky equals the Python proxy). The port delivers 1.54x with a patient client and 1.80x with step 08's client, with the same TTFT and the same loaded-phase hit rate as upstream.** Upstream's 2.12x stands as measured but stacks two artifacts the port does not have: the 600 s client trimmed about 2300 turns per cell in tr-decay's favor, and the Python router leaves client-abandoned requests as phantom REASONING programs (76 to 83 on its books against 17 to 20 running), throttling admission into a lighter, hotter engine late in each run. Time series per lane in both run folders. Details and step 11 in `10-llm-d-router-replicates/RESULTS.md`.

### 12. llm-d-router: three EPP policies on the whole 4-pod pool (done)

`12-llm-d-router-pool/` compares, through one EPP over the four pods, llm-d's default profile (prefix-cache, queue and KV scorers), plain session affinity, and the ThunderAgent port, at c=338 (the whole corpus) for 45 minutes, three replicates each, with the load generator fixed first (inference-perf v0.7.0 lets only about half of the sessions start; see `INFERENCE-PERF-BUGS.md` issue 4). **The two llm-d policies are indistinguishable (1020 tok/s, hit rate 0.002, TTFT p50 123 s). The port gives 1.42x throughput, a 0.25 steady-state hit rate and a 3.7 s median TTFT.** Admission control is the entire effect; placement alone does nothing under oversubscription. The port loses half its single-pod hit rate to pod hopping on resume (70 percent of resumes move), identified before the run; an origin-only resume policy is the next step. Details: `12-llm-d-router-pool/RESULTS.md`.

## Proposals (not part of the numbered steps)

`proposal/PROPOSAL.md` - three ThunderAgent scheduling proposals, none run yet. Kept outside the numbered sequence.

**Part 1, admission-wait starvation**: why a minority of sessions wait up to 30 minutes for admission. Measured cause: `_greedy_resume` orders the waiting pool by token count **ascending** with no aging, so large sessions lose every round to a refreshed supply of smaller newcomers. **71% of sessions above 80k tokens were held past 600s; 0% of sessions below 40k tokens were**, with holds pinned at upstream's hard-coded 1800s forced-admission backstop. Four remedies compared (lower the timeout / age the queue / head-of-line reservation / shed with Retry-After), with a one-cell experiment and pre-registered expectations.

**Part 2, the 5s scheduler interval**: 67% of admission holds last under 12s and pile up on the polling period, and the engine sits idle 9.3% of the time under tr (5.6% under the proxy) with a non-empty waiting queue - so shortening the interval should recover throughput. But the capacity decision reads a single instantaneous sample (`latest_metrics`, never an average), and one sample misjudges free capacity by +-87k tokens - more than a median session - so faster polling multiplies noise-driven decisions rather than averaging them. Proposal: shorten the interval AND smooth the signal, with a three-arm experiment to separate the two.

**Part 3, origin-only resume on a multi-pod pool**: in step 12, 70% of the port's resumes (about 3100 of 4470 per cell) moved the session to another pod, because on equally loaded pods the origin pod rarely has room at the instant a paused session's turn arrives while the pod with the most room always does; upstream's best-fit-decreasing placement behaves the same way. Each move is a full re-prefill, and the pool hit rate ended at half the single-pod value. Proposal: a `resumePlacement` switch, default unchanged, `origin-only` making paused sessions wait for their own pod unless it vanished or the forced-admission backstop fired; new sessions still go to the pod with most room. One more pool arm with pre-registered expectations (rebinds near zero, hit rate toward 0.49, forced admissions as the risk metric).

## Data note: per-request reports are not in this repo

Every inference-perf cell in `07-inference-perf-weka/results/` and `08-weka-replicates/results/` is published complete except one file: `report/per_request_lifecycle_metrics.json` (50-123 MB each, 1.6 GB total, over GitHub's file limit; the size comes from per-token timing arrays that the v0.7.0 field filter cannot drop - see `INFERENCE-PERF-BUGS.md` issue 5). Every number in the write-ups is also derivable from the files that are here: the summary and per-stage lifecycle reports, `vllm-metrics.csv`, `programs-timeline.csv`, `router-health.csv`, and the committed `analysis.md` per run. Only re-running `analyze.py`, `pair.py` and `verdict.py` from scratch needs the raw per-request files; ask and we will share them.

## Start here

- `LESSONS.md` - what bit us and the rules that came out of it: which metrics must always be recorded, why the overnight driver died (and the cluster-side grace period that saved the results), why `--enable-prompt-tokens-details` was missing, and how to calibrate the pressure regime before spending hours.
- `08-cluster-changes.md` - every change made to shared cluster state, with revert instructions.
- `INFERENCE-PERF-BUGS.md` - the five inference-perf v0.7.0 bugs this campaign hit, written to be filed upstream as-is.

## Result summary

Setup succeeded on 2026-09-15. The original router is live in `tr` mode with all 4 vLLM backends, real per-backend KV capacity (2,237,040 tokens each), working program tracking, sticky routing, load-balanced placement, profiling, and release. Details and the two upstream bugs found along the way (broken CLI flag handling, broken `/v1/models` proxy path) are in `03-verify/smoke-test-results.md`; raw output in `03-verify/smoke-test-output.txt`.

Access from a laptop:

```
kubectl port-forward svc/thunderagent-router -n llm-d-program-aware-scheduling 18300:8300
curl http://localhost:18300/health
```

Send requests exactly like the paper describes: OpenAI chat completions with `"program_id": "<session>"` in the body (or an `X-Session-ID` header).

## How to tear down

```
kubectl delete -f 02-deploy/
```

The vLLM backends and the llm-d EPP are untouched.

## What this setup enables next

With the router live you can replay an agentic workload (e.g. the weka trace via inference-perf, sending `program_id` per session) through:

- `thunderagent-router:8300` (original paper router, tr mode)
- the same router restarted with `--router default` (pure proxy baseline)
- the existing llm-d gateway (Go port)

and compare prefix-cache hit rate, prefill tokens, and latency, which is the paper's headline claim (1.5-3.6x throughput from program-aware scheduling).
