# Handoff: ThunderAgent verification and the llm-d-router port

Written 2026-09-18 so a fresh session can continue without replaying the history. Everything below is derivable from the numbered step folders, but this is the short path. Dates are absolute. Everything through step 13 is committed and pushed to the public GitHub repo (`zetxqx/thunderagent-original-verification`); raw per-request reports are git-ignored (see the README data note).

## Where things are

| what | where |
|---|---|
| this verification repo | `~/projects/llmdthunder/thunderagent-original-setup/` (steps `01-` to `13-`, `proposal/`, `INFERENCE-PERF-BUGS.md`, `LESSONS.md`, `08-cluster-changes.md`) |
| the llm-d-router port | `~/projects/llmdthunder/llm-d-router/`, branch `thunder-agent`, commit `ae371354` pushed to `zetxqx/llm-d-router`; plugin at `pkg/epp/framework/plugins/thunderagent/`; explainer `~/projects/llmdthunder/llm-d-thunderagent-how-it-works.md` |
| upstream Python ThunderAgent | `~/projects/llmdthunder/ThunderAgent/` at commit `7ddc861`, untouched |
| inference-perf with the permit fix | `~/projects/llmdthunder/inference-perf/`, branch `fix-session-replay-permits`, commit `d5a7c8c`, pushed to `zetxqx/inference-perf` |
| cluster | GKE `bobbm`, context `gke_bobzetian-gke-dev_us-central1_bobbm`, namespace `llm-d-program-aware-scheduling`, 4 vLLM pods `program-aware-vllm-decode-*` (spot H100, TP=2, `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8`, 2,237,040 KV tokens each) |
| images | EPP `us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/llm-d-router-endpoint-picker:thunder-agent-v3` (= commit `ae371354`) and `:thunder-agent-v4` (= commit `8ee881c2`, adds `resumePlacement`; identical under the default); load generator `.../inference-perf@sha256:63f2fbcf...` (permit fix), also in `12-llm-d-router-pool/results/inference-perf-image.txt` |

## Cluster state right now

- Helm release `program-aware-scheduling` (the main EPP, 1 replica, envoy sidecar, service port 80 -> envoy 8081, metrics 9090): revision 48, after the step 13 origin arm (2026-09-20 00:05): image **`thunder-agent-v4`**, **thunder-origin** plugin config (`12-llm-d-router-pool/thunder-origin-plugins.yaml`, `resumePlacement: origin-only`) and envoy `message_timeout` 2400 s, left by the last cell `epp-thunder-origin-c192`; revision 22 was the step 09 state (thunder config, 1000 s). Whatever arm ran last leaves its config on the release. `12-llm-d-router-pool/run-pool.sh` upgrades it per cell with `main-values.yaml` (2400 s timeout) and reverts are documented in `08-cluster-changes.md`.
- The three step 10 lane EPPs, their pod labels and the `thunder-lane-auth-delegator` binding were removed on 2026-09-18 (`10-llm-d-router-replicates/teardown-lanes.sh`); `deploy-lanes.sh` recreates them if single-pod work resumes.
- ServiceAccount `thunderagent-metrics-reader` (namespace) with a ClusterRole on `/metrics` and `/debug/plugins/state`: the EPP metrics port enforces kube-rbac; use `kubectl create token thunderagent-metrics-reader -n <ns>` as a bearer. The EPP's own service account gets 403.
- The original Python router `thunderagent-original` (step 02) is still deployed and idle.
- Unrelated stacks `bench` (llm-d-bench) and `text-to-video` (llm-d-diffusion-t2v) were uninstalled on 2026-09-18 to free default-pool CPU; their empty namespaces remain.
- vLLM deployment carries `--enable-prompt-tokens-details` (step 07 change).

## What was established, in order

1. **Steps 01 to 08 (Python router, one pod per lane, c=128, 45 min, 3 replicates).** tr-decay 469 tok/s vs proxy 221 (2.12x), steady-state hit rate 0.685 vs 0.008. Two corrections found later (both written as addenda in `08-weka-replicates/RESULTS.md`): the 600 s client timeout killed tr's longest-held sessions and dropped about 2300 of their turns per cell, trimming the workload in tr's favor; and the router leaves client-abandoned requests as phantom REASONING programs forever (`vllm_request_processor.py:205-210`), which throttled admission into a lighter, hotter engine in the last third of each run (router REASONING count 76 to 83 vs 17 to 20 running). Also `INFERENCE-PERF-BUGS.md` issues 1 to 5.
2. **Port rewritten (llm-d-router commit `ae371354`)** to upstream tr-decay semantics: undecayed working set drives a 5 s pause sweep, decayed view (1 s half-life) drives admission, paused programs re-enter ahead of new ones, sticky-if-fits resume, 1800 s forced admission, `kvUsageCorrection` off (dead code upstream). 78 unit tests, 10 flow-control integration tests and sims. Details in the plugin README and `llm-d-thunderagent-how-it-works.md`.
3. **Step 09 (smoke, live cluster).** 20 checks pass: version, real capacity on all pods, accounting, stickiness, release.
4. **Step 10 (single-pod lanes through the EPP, 3 replicates).** `epp-sticky` reproduces the Python proxy (227 vs 221 tok/s). `epp-thunder`: 351 tok/s (1.54x) with a 1900 s client, 405 (1.80x) with step 08's 600 s client; under equal load its hit rate matches upstream (0.55 vs 0.57). The residual gap to 2.12x is the two step 08 artifacts above, not a scheduling difference.
5. **inference-perf v0.7.0 permit bug (found 2026-09-18).** An event parked on predecessors kept its `worker_max_concurrency` permit, so only about half of the dispatched sessions ever started (51 to 109 of 128 to 183) in every run of steps 07 to 10, both routers alike. Fixed in `d5a7c8c`; every run from step 12 on uses the fixed image. Older runs should quote active sessions, not c. Verified by md5 of the file inside the image and by 128 of 128 / 338 of 338 sessions issuing requests.
6. **Step 12 (whole 4-pod pool, one EPP, c=338, 45 min, 3 replicates, 1900 s client).** llm-d default profile and plain session affinity are indistinguishable: 1020 tok/s, hit rate 0.002, TTFT p50 123 s, about 190 requests waiting inside vLLM. The port: 1447 tok/s (1.42x, plus or minus 0.3 percent), hit rate 0.248, TTFT p50 3.7 s, engine queue near zero with about 370 requests held in the EPP, 55 forced admissions and 25 client timeouts per cell. About 70 percent of resumes moved pods (3100 of 4470 per cell), which halves the hit rate versus a single pod; recorded as `proposal/PROPOSAL.md` Part 3 (origin-only resume). Figures: `pool.png`, `timeseries.png`, `waiting.png` in the run directory.
7. **Step 13 (concurrency sweep, three arms, 9 levels from 4 to 84 sessions per pod, 30 min per cell, one cell each; the origin arm at the five levels from 24 up).** Pool throughput peaks at 12 to 16 sessions per pod (about 2000 tok/s) with both arms equal (0.98x to 1.01x) up to there; tie at 24, 1.20x at 32, 1.26x at 48, 1.44x at 64, 1.46x at 84. Thunder TTFT p50 stays 2 to 4 s above the crossover; baseline's grows to 101 s with 152 requests waiting inside vLLM. Resumes that changed pod: 49 to 71 percent. With `resumePlacement: origin-only` (thunder-agent-v4): rebinds 0, hit rate 0.82 / 0.63 / 0.53 / 0.46 / 0.42 at 24 / 32 / 48 / 64 / 84 per pod, throughput 1.18 / 1.14 / 1.22 / 1.14 / 1.10x over most-room, TTFT p50 within 1 s of most-room. Details and caveats in `13-llm-d-router-sweep/README.md`.

## Decisions taken (and by whom)

- Resume placement: `most-room` stays the plugin default (faithful to upstream); `origin-only` was implemented 2026-09-19 as a config knob and measured better on the pool (step 13). Making it the default is an open decision.
- `kvUsageCorrection` default off because upstream never activates it (corrected my own earlier claim).
- Preempted cells are voided and rerun, no partial-result machinery (user, 2026-09-18).
- Step 11 (utilThreshold sweep, or rerunning upstream at 1900 s) deferred; step 13 is the two-arm concurrency sweep.

## How to run things

- Lane smoke: `09-llm-d-router-smoke/smoke-test.sh` (needs the metrics-reader token; rerunnable).
- Single-pod lanes: `10-llm-d-router-replicates/run-replicates.sh [c] [reps] [window] [arms] [client_timeout]`; `BENCH_IMAGE=...` selects the load generator image.
- Pool: `12-llm-d-router-pool/run-pool.sh [c] [reps] [window] [arms] [client_timeout]`; env `AB_ID` and `REP_START` append make-up cells to an existing run, `CELL_TAG` renames cells, `OUT_BASE` redirects output, `SKIP_ANALYSIS` skips the analyzer. Helm and rollout steps are retried. Analysis: `analyze.py`, `plot_timeseries.py`, `plot_waiting.py`.
- Sweep (step 13, not yet run): `13-llm-d-router-sweep/run-sweep.sh [levels] [window_s]`, defaults `48 96 128 192 256 338` and 1800 s; `analyze_sweep.py` draws the curves.
- Images: `~/.claude/skills/cloud-build-epp/build-epp.sh <tag>` from the llm-d-router checkout; `12-llm-d-router-pool/build-inference-perf.sh <tag>` from the inference-perf checkout.
- Analyzers need matplotlib: `uv run --quiet --with matplotlib --with numpy python <script> <run_dir>`.

## Traps that cost time (do not rediscover)

- `helm upgrade --reuse-values` on the main release fails to render: it swaps in an older/newer chart's defaults whose envoy template needs a helper this checkout lacks. Always pass values as a file (`09-llm-d-router-smoke/results/values-rev10-user-supplied.yaml` or `12-llm-d-router-pool/main-values.yaml`).
- The chart names the envoy ConfigMap `envoy` and the Deployment mounts it by that hardcoded name; side-by-side releases in one namespace need `helm template` plus the volume-name rewrite in `10-llm-d-router-replicates/render-lane.sh`.
- Standalone-mode EPPs get only namespaced RBAC; the metrics port then cannot TokenReview. `10-llm-d-router-replicates/lane-rbac.yaml` binds them to `system:auth-delegator`.
- The envoy access log in this chart is truncated to method and time; status codes are not logged. Judge failures from inference-perf errors and the EPP log.
- A held request sits inside the ext_proc exchange; with the 1800 s forced admission, envoy's `message_timeout` must exceed 1800 s (2400 s in the lane and pool values).
- Every arm of a comparison must use the same client `request_timeout`, above 1800 s unless the point is to reproduce step 08; report skipped turns and sessions ended per arm.
- Background commands launched through the tool are capped at 10 minutes; long drivers must be started with `nohup ... &` in a subshell (macOS has no `setsid`).
- Pool cells take about 55 to 58 minutes end to end for a 45-minute window (4000+ requests of reports).
- The generator starts all sessions at t=0 and starts a new trace whenever one ends. Under heavy load sessions rarely finish (0 to 25 of 128 to 338 slots in 30 min), but under light load they do: at c=48 about two thirds of the slots turned over in 30 min (30 to 33 completed sessions, median 9 min). Low-concurrency cells therefore mix in trace turnover (cold starts, early short-prompt turns); see the `sessions completed and replaced` row in the step 13 tables. The faster arm finishes more sessions and pulls in more cold traces, which makes the reported gains slightly conservative.

## Open items, in the order they were agreed

1. Step 13 sweep: DONE, including the c = 16, 32, 64 extension (2026-09-19) and the `epp-thunder-origin` arm at c = 96 to 338 (2026-09-19/20). Origin-only resume beats most-room by 1.10x to 1.22x at every level with rebinds 0 and hit rate 0.42 to 0.82; gain over llm-d default becomes 1.18x to 1.63x. Cost: holds up 55 to 69 percent, TTFT p50 up 0.5 to 0.9 s at 64 and 84 sessions per pod, forced admissions 7 to 10 at 84. Details in the step README. The origin arm and its code are not yet committed in this repo (llm-d-router commit `8ee881c2` is pushed).
2. Commit and push this repo (steps 09 to 13, the step 08 addenda, the docs); the user asks for commits explicitly.
3. Proposal Part 3 (origin-only resume): DONE (knob, v4 image, five-level arm). Possible follow-up: Option B (bounded origin wait) if the TTFT p90 cost at 32 to 48 sessions per pod matters; decide whether `origin-only` becomes the shipped default.
4. Proposals Part 1 (queue aging) and Part 2 (interval plus smoothing) remain unrun; Part 2's premise was weakened by step 10 (continuous admission cost hit rate under upstream's phantom regime; see step 10 RESULTS).
5. File the five inference-perf issues and the ThunderAgent phantom-REASONING issue upstream (write-ups are ready to paste).
