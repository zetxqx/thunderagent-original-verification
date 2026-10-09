# Deployment: server, router and client flags

Everything here is what steps 07 to 23 ran. Re-check live values with `model-server/collect.sh` before trusting them against a rebuilt cluster. Every point records the live config in `meta/`, so the report can cite the files instead of this page.

## 1. Cluster and namespace

| | |
|---|---|
| Cluster | GKE `bobbm`, context `gke_bobzetian-gke-dev_us-central1_bobbm`. The scripts pin it through a private kubeconfig; never rely on the laptop's current context |
| Namespace | `llm-d-program-aware-scheduling` |
| vLLM | Deployment `program-aware-vllm-decode`, labels `llm-d.ai/guide=program-aware-scheduling,llm-d.ai/role=decode`, container `modelserver`, port 8000 |
| Main EPP | Deployment `program-aware-scheduling-epp`, Helm release `program-aware-scheduling`, gateway URL `http://program-aware-scheduling-epp:80`, metrics port 9090 (kube-rbac) |
| GPU nodes | pool `bobbm-spoth100`, `a3-highgpu-4g` **spot** (4x H100 80GB, 104 vCPU, 965 GiB), `us-central1-a`. A preemption mid-run invalidates the point |
| Client nodes | `default-pool` (non-spot CPU) |

One-time objects (all in `manifests/`): `pvc.yaml` (PVC `agentx-data`, 200Gi: HF cache, dataset mmap cache, results; `run-point.sh` creates `agentx-data-<lane>` for other lanes), `metrics-reader-rbac.yaml` (ServiceAccount `thunderagent-metrics-reader`, needed by the EPP scrape). Record any change to shared cluster state in the repo's `08-cluster-changes.md`.

## 2. vLLM model server

`vllm/vllm-openai:v0.28.0`, unmodified. Model `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8`. Live manifest: `model-server/deployment.yaml`; details and history: `model-server/README.md`.

```
vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8
  --host=0.0.0.0 --port=8000
  --tensor-parallel-size=2
  --max-model-len=262144
  --kv-cache-dtype=fp8_e4m3
  --gpu-memory-utilization=0.88
  --compilation-config={"pass_config":{"fuse_allreduce_rms":false}}
  --enable-prompt-tokens-details      # required: cached-token counts per response
```

| Env | Value | Effect |
|---|---|---|
| `VLLM_USE_DEEP_GEMM` | `0` | DeepGEMM MoE kernels off |
| `VLLM_ALLREDUCE_USE_SYMM_MEM` | `0` | symmetric-memory allreduce off |
| `VLLM_SERVER_DEV_MODE` | `1` | enables `/server_info` and `/reset_prefix_cache` |
| `HF_TOKEN` | secret `llm-d-hf-token` | model download |

Resolved engine config (what the server really used): chunked prefill on, prefix caching on, `block_size` 16, 139,815 GPU blocks = **2,237,040 KV tokens per pod**, `max_num_batched_tokens` 8192, `max_num_seqs` 1024, cudagraph `FULL_AND_PIECEWISE`. KV costs 48 KiB per token (FP8). The KV pool binds long before `max_num_seqs`.

Pod shape: requests 8 CPU / 96Gi / 2 GPU, limits 16 CPU / 128Gi / 2 GPU, `/dev/shm` 20Gi, HF cache `emptyDir` (a restart re-downloads weights), `strategy: Recreate` (any change restarts every replica).

### CPU KV offload variant (step 20)

Add `--kv-offloading-size=400` (GiB, summed over TP ranks; vLLM's native `OffloadingConnector`). The CPU tier is a file in `/dev/shm`, so also: memory request and limit 450Gi, `/dev/shm` `sizeLimit` 410Gi, one replica per node (anti-affinity). Tier reach: 8.74M tokens, 3.9x the GPU KV. Reset both tiers before a cell with `POST /reset_prefix_cache?reset_external=true`. Manifests: `20-cpu-offload-pool/vllm-deploy-3rep-offload400.yaml`; switch and restore with `20-cpu-offload-pool/offload.sh`.

## 3. Router (EPP) arms

Plugin configs in `manifests/epp/`:

| Arm | File | What it is |
|---|---|---|
| llm-d default | `baseline-plugins.yaml` | prefix-cache (3), queue (2), KV utilization (2) scorers. No sessions, no admission control |
| thunder gate (PR3) | `thunder-pr3-plugins.yaml` | `agent-identity` (session from `x-session-id`) + `thunder-agent` in three slots: scheduling profile (session affinity), saturation detector, fairness policy (the gate) |
| no router | none | `MODE=lane`: client talks to one vLLM pod directly |

Lanes in parallel (`MODE=lane`): set `LANE=a|b|c|d` to run one point per vLLM pod at the same time. Each lane has its own Service `agentx-lane-<lane>` and PVC (`agentx-data` for `a`, `agentx-data-<lane>` otherwise; the PVCs are RWO, so lanes cannot share one). Before a point the lane deletes its pod and claims a fresh replacement with a resource-version guarded label, so lanes restarting together never share a pod; a lane's first pod must be Ready (a pod still starting is another lane's replacement). Lanes share nodes and neighbors: each point records them in `meta/`. Example: `for p in a:12 b:20 c:24 d:32; do LANE=${p%:*} RESULTS=$PWD/results DURATION=1200 nohup caffeinate -i <skill>/scripts/run-point.sh ${p#*:} <label> > results/<label>-${p%:*}.log 2>&1 & done`.

EPP image for PR3: `us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/llm-d-router-endpoint-picker:thunder-agent-pr3-a025437b` (digest `sha256:14f97db8...`). Build other images with the `cloud-build-epp` skill.

`thunder-agent` parameters:

| Field | Our value | PR3 default | Note |
|---|---|---|---|
| `capacityTokens` | 2237040 | 4194304 | fallback when `cache_config_info` is not scraped; set it to the real pool size |
| `utilThreshold` | 1.0 | 1.0 | fit ceiling as a fraction of capacity |
| `idleLeaseSeconds` | 30 | 30 | about a typical tool-call duration. AgentX caps idle gaps at 10 s (system) and 300 s (per tree) |
| `headWaitStarvationMs` | 1800000 | 30000 | forced-admission backstop. Must be below every timeout on the path |
| `evictionTtlSeconds` | 3600 | 3600 | must exceed the backstop |

Timeouts on the request path must be ordered: gate backstop < flow-control `defaultRequestTTL` (0 = no eviction) < envoy ext_proc `message_timeout` (raised to 2400 s in `10-llm-d-router-replicates/lane-values-tmpl.yaml`) < client timeout. aiperf does not send `x-session-final`, so the gate frees a session only by idle lease and eviction TTL.

### How to put an arm in front of the pods

- **Lane EPP per pod (parallel lanes with a router arm)**: apply `manifests/lane-epp-rbac.yaml` once, then for each lane `scripts/render-lane-epp.sh <lane> manifests/epp/<arm>-plugins.yaml [epp-image-tag] | kubectl apply -f -`. Each release (`agentx-epp-<lane>-epp`, chart from the image's branch, requests 1 CPU for the EPP and 1 for envoy) watches only the pod labeled `agentx-lane=<lane>`. Run points with `LANE=<lane> LANE_EPP=1` (or `LANE_EPP=1 run-lanes.sh <label> <conc>...`): before each point the lane takes a fresh vLLM pod and restarts its EPP (fresh gate ledger), sends `X-Session-ID`, and scrapes the EPP metrics. Step 24 is the first user.
- Client CPU: each lane's PVC is zonal and each zone has one `default-pool` node, so two lanes can share a client node; with lane EPPs on the same nodes use `CLIENT_CPU=4`.

- Legacy (steps 10 to 21, inference-perf): `10-llm-d-router-replicates/render-lane.sh <lane> <arm>` and `20-cpu-offload-pool/lanes.sh`. Use the lane EPP bullet above for new steps; its pool-mode variant (`MODE=pool` with a lane `DECODE_SELECTOR`) restarts the whole vLLM deployment and so cannot run lanes in parallel.
- Main release: `helm upgrade` with `-f <(helm get values ...)` plus `--set-file` for the plugin config. Never `--reuse-values`. Save `helm get manifest` first and restore with `16-thunder-minimal-pool/restore-main-release.sh <saved>`; Helm keeps only 10 revisions, so never roll back by number.
- `MODE=pool RESTART=1` restarts the whole vLLM deployment and the EPP. That restarts every lane: do not run it while another lane or another person's experiment uses the namespace.

## 4. Client: aiperf with the AgentX scenario

Image `us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/agentx-harness:agentx-v1.0.6` (digest `sha256:918909fe...`), built unmodified from `SemiAnalysisAI/agentx-harness` release `agentx-v1.0.6` (commit `89b21867872a`, local checkout `../aiperf`). Rebuild instructions: `23-aiperf-thunder-pr3/README.zh.md` section 3.1. Do not use the official aiperf v0.13.0: it lacks the AgentX rules.

Dataset `semianalysis_cc_traces_weka_062126_256k` (393 traces, the 256k variant because `--max-model-len=262144`). Datasets of different dates are not comparable.

`--scenario agentx` sets (do not override for a submission-valid point):

| Setting | Value | Effect |
|---|---|---|
| timing mode | `agentic_replay` | N lanes, each replays a session tree (main agent + subagents); closed loop |
| `--streaming`, `ignore_eos:true` | on | TTFT and ITL per token; output length fixed by the trace |
| `--cache-bust first_turn_prefix` | on | a unique marker per replay, so reused traces do not hit each other's cache |
| `--system-idle-gap-cap-seconds` | 10 | when the whole system is idle, jump timers ahead by at most 10 s |
| `--trace-idle-gap-cap-seconds` | 300 | compress idle gaps over 5 min per tree |
| `--benchmark-duration` | 3600 | 1 h profiling (min 900 s) |
| `--warmup-requests-per-lane` | 10 | warm by request count, plus each lane's primer context; not counted |
| `--warmup-grace-period` | 1800 | wait up to 30 min for deep primers |
| `--failed-request-threshold` | 0.10 | stop early past 10% failures (the job fails; that is a result) |
| `--random-seed` | 42 | same traces and start offsets in every arm |
| `--slice-duration`, `--stats-interval` | 1.0, 30 | per-second timeslices, live stats in the log |
| `--use-server-token-count` | on | ISL and OSL from server `usage` |
| `--benchmark-grace-period` | 30 (default) | requests unfinished 30 s after the window are cancelled (`cancelled` column) |
| env `AIPERF_HTTP_TCP_USER_TIMEOUT` | 900000 | a connection is dead only after 15 min without ack |

Added by `run-point.sh` (collection only, requests unchanged):

| Setting | Why |
|---|---|
| `--server-metrics <each vLLM pod>/metrics` | the gateway's `/metrics` hits a random pod; scrape pods directly |
| `--server-metrics-formats json csv parquet` | parquet = full time series for the figures |
| `AIPERF_SERVER_METRICS_COLLECTION_INTERVAL=1.0` | AgentX analyzes per second |
| `AIPERF_HTTP_X_SESSION_ID_FROM_CORRELATION_ID=true` (pool) | sends `X-Session-ID` per session (main agent and each subagent), which `agent-identity` reads |
| `HF_HOME=/data/hf`, `AIPERF_DATASET_MMAP_CACHE_DIR=/data/mmap` | caches on the PVC, shared by all points |
| EPP scrape sidecar (pool) | `scripts/epp_scrape.py`, every 10 s, as `thunderagent-metrics-reader` |
| `aiperf analyze swim-lane --html` | per-point session Gantt chart |

Client Job: `default-pool`, 8 CPU, 32Gi, `activeDeadlineSeconds` 21600, runs as uid 1000.

## 5. Concurrency grid

- One fresh server per point (AgentX rule: "restart the server for every CONC value... do not flush caches or reuse a live server").
- Start with powers of two, 8 to 256 on the 4-pod pool (8.9M KV tokens; a session often holds over 100k tokens, so the working set passes the pool at a few dozen sessions). Add points around the knee.
- One point is about 1.5 to 2 h (restart, primer warmup, 60 min, collection). Plan sweeps overnight with `nohup caffeinate -i`.
- Run a 10-minute calibration point first (`DURATION=900`), and a smoke point (`EXTRA_ARGS="--unsafe-override --num-dataset-entries 8 --warmup-requests-per-lane 1" DURATION=120`) after any script or config change.
