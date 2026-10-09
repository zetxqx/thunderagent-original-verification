# Step 23: the PR3 thunder-agent gate, benchmarked with aiperf

Status (2026-10-09): EPP image built; aiperf harness written and smoke-tested (workload decided, see below). Next: the single-replica plain vLLM baseline (`MODE=lane`), then the PR3 arms.

## Question

Re-measure the thunder-agent per-pod admission gate as it stands in PR3 ([llm-d/llm-d-router#3076](https://github.com/llm-d/llm-d-router/pull/3076)), this time with [aiperf](https://github.com/ai-dynamo/aiperf) as the load generator instead of inference-perf.

## EPP image

| | |
|---|---|
| Image | `us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/llm-d-router-endpoint-picker:thunder-agent-pr3-a025437b` |
| Digest | `sha256:14f97db8c3758a4596d0eb61607d192ff943786212be16ba25ccbbbdba1dff0e` |
| Source | llm-d-router `a025437b` (PR #3076 head, branch `thunder-agent-lease-main` on `origin`, local `thunder-agent-pr3-rebased`), stacked on PR1 #2968 and PR2 #3052 |
| Built | 2026-10-09 01:16 UTC, Cloud Build `d6bbffdc-46a2-42ef-a745-6e5b3b933b68`, linux/amd64 |
| Plugin type | `thunder-agent` |

## Changes since the image of steps 18 to 21

Steps 18 to 21 ran `thunder-agent-lease-*` images. PR3 differs in ways that affect a run or its analysis:

- `llm_d_epp_thunder_agent_holds_total` is renamed to `llm_d_epp_thunder_agent_delayed_dispatches_total` (`bddb05ac`). Analysis code that reads `holds_total` must read the new name.
- The starvation backstop now defaults below the request TTL (`4ac4c751`). The earlier runs used 1800 s with a 1900 s client timeout; check the effective value in the plugin config before choosing the client timeout.
- The gate logs setups that defeat it (`6926dfcb`). Check `epp.log` for these warnings after the smoke test.
- The gate sizes a session with its turns in flight (`775b3ec1`), and admitted turns reclaim only past the idle lease (`78caca14`).

## Harness: the exact AgentX client

The load generator is the SemiAnalysis AgentX harness, not upstream aiperf: `SemiAnalysisAI/agentx-harness` release `agentx-v1.0.6` (commit `89b21867872a`, the commit InferenceX pins), run with `--scenario agentx` on the `semianalysis_cc_traces_weka_062126_256k` corpus, one fresh server per concurrency point. Upstream aiperf v0.13.0 lacks the AgentX rules, and the aiperf K8s operator does not apply `scenario:` in-cluster, so each point is a plain K8s Job.

| | |
|---|---|
| Image | `us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/agentx-harness:agentx-v1.0.6` |
| Digest | `sha256:918909fef9175f7476a53633727a8a3a6aae9828670a59dccb284109729e0a5a` |
| Build | Cloud Build `dad86584-03d5-4de3-861b-a56aa9608490`, the fork's own `Dockerfile`, target `runtime` (distroless: bash and the aiperf venv only, no `tar`) |

Two modes in `run-point.sh`:

- `MODE=lane` (default): one vLLM pod labeled `agentx-lane=a`, reached directly through Service `agentx-lane` (no envoy, no EPP, no `X-Session-ID`). The lane pod is deleted and its replacement labeled before every point.
- `MODE=pool`: all 4 vLLM pods through `program-aware-scheduling-epp:80`; the vLLM deployment and the EPP are restarted before every point; `X-Session-ID` is sent for the EPP's `agent-identity` plugin. aiperf never sends `x-session-final`, so the thunder plugin releases ended sessions only through `evictionTtlSeconds`.

Every point records pod identity at start and end (a new uid or restart marks it invalid), scrapes each vLLM pod's `/metrics` directly every second into parquet, and keeps the per-request JSONL. `analyze.py` reports the InferenceX columns (per-GPU throughput, P50 to P95 interactivity, TTFT, E2E, E2E normalized interactivity, Pareto curves) and the [../BENCHMARK-METRICS.md](../BENCHMARK-METRICS.md) columns (hit rates by source, working set against KV pool, B and T with the step-time fit, waiting by reason, engine queue and prefill time, session worst-turn TTFT, goodput at a TTFT SLO, validity checks).

Full guide (Chinese): [README.zh.md](README.zh.md).

## Files

- `run-point.sh <conc> [label]`: one point as a K8s Job, results to `results/<label>/c<N>/`. Sources `../20-cpu-offload-pool/lib.sh` (`pin_kube`, `vllm_get`, `vllm_pod_on`) with this step's results folder, and runs `../model-server/collect.sh` per point.
- `run-sweep.sh <label> <conc>...`: points in sequence, then `analyze.py`.
- `analyze.py <point dirs>`: `summary.md`, `summary.csv`, and all figures in `results/<label>/report/`: `pareto` (Pareto curves), `concurrency` (throughput, TTFT and interactivity against concurrency), plus per point `timeline`, `cache`, `prefill` (TTFT split into queue wait and prefill; prefill work against time per output token), `latency`, `isl-osl`.
- `make_figures.py`: the figure code, in the publication style of steps 20 to 22 (the earlier steps' figures redrawn from aiperf data). Engine-step bins with more prefill per step than `max_num_batched_tokens` (8192) are dropped as metrics-lag artifacts.
- `lane-svc.yaml`, `pvc.yaml` (`agentx-data`: HF cache, reconstructed-dataset cache, artifacts).
- `results/smoke1/c4`: 2-minute smoke test through the gateway, 13 requests, 0 errors.
- `results/smoke-lane/c4`: 2-minute lane smoke test with a pod restart.
- `results/lane-20m/c16` (run alone as `try-lane-c16-20m`, then moved into `lane-20m`): first valid point, lane, c=16, 20 min: 524 requests, 0 errors, 5 cancelled at the end; 19.4k total and 167 output tok/s/GPU; P90 interactivity 18.8 tok/s/user, P90 TTFT 2.07 s; hit 91.9% vs 94.9% theoretical; working set 0.70x KV pool mean, 1.12x peak; B 8.1, T 21.9 ms (report with the other lane points in `results/lane-20m/report/`). The first 5 minutes run at 2 to 5 requests: lanes wait out recorded first-request gaps until the 300 s per-tree idle cap fires (harness behavior; 8% of a 1-hour run).

## Open decisions

- ~~Workload~~: decided, the AgentX harness above.
- Arms and topology: llm-d default vs the PR3 gate; single replica or the 4-pod pool; CPU offload on or off.
- Concurrency grid, window, warm-up, client timeout, and replicates.

Metrics to collect: [../BENCHMARK-METRICS.md](../BENCHMARK-METRICS.md).
