# Step 20: CPU KV offloading (400 GiB) on single vLLM replicas: llm-d default, the lease gate, and the lease gate sized to the CPU tier

Status: run on 2026-09-30, all 24 cells complete; see "Result" at the end. Plan written 2026-09-29.

## Question

vLLM can keep KV cache that falls out of GPU memory in host (CPU) memory and load it back over PCIe instead of recomputing it. This attacks the same problem as thunder-agent: the agents' working set is bigger than GPU KV.

1. With a realistic CPU tier, how far does offloading alone take a replica with no admission control?
2. Does the lease gate still add value, and in which concurrency range?
3. Should the gate size admission to the GPU or to the CPU tier?
4. At which concurrency does the CPU tier itself start to thrash, and does the gate help again there?

Why single replicas:

- **It isolates admission control.** With one pod there is no placement. llm-d default, session affinity and the thunder-agent scorer all send every turn to the same pod, so the only difference between the arms is the gate. On the pool, llm-d default also moves sessions between pods, and a session loses its per-pod CPU tier when it moves, which mixes stickiness into the comparison.
- **Three replicas run the three arms at the same time.** This is step 10's lane setup: each vLLM pod has its own EPP, and all lanes replay the same workload at once.

Background: `../proposal/PROPOSAL.md` Part 5, `../13-llm-d-router-sweep/SATURATION.md` (why throughput stops rising), and PR #2116, where a 512 GiB CPU tier did not save an FCFS scheduler at 128 sessions (both tiers at zero hits, read off its plots).

## Versions

- **EPP:** llm-d-router `thunder-agent-lease-main`. Current head `7d548355` (upstream PR #3076) has the same plugin code as `44544c04`; only tests and the upstream base differ. So the step 19 image `thunder-agent-lease-44544c04` is reused for all three arms. No code change is needed (see "Sizing the gate to the CPU tier").
- **Load generator:** our inference-perf build, image `us-central1-docker.pkg.dev/bobzetian-gke-dev/bobinference/inference-perf@sha256:f7381b01...` (tag `session-id-v1`, `../12-llm-d-router-pool/results/inference-perf-image.txt`). It is commit `d2bfa20` on `zetxqx/inference-perf`: v0.7.0 plus two fixes.
  - The permit fix `d5a7c8c`: a session's queued events no longer hold worker permits while they wait, so `concurrent_sessions` is actually reached (`../INFERENCE-PERF-BUGS.md` issue 4).
  - `session_id` in the per-request report.
- **The permit bug is still in upstream.** It is in release v0.7.0 and in upstream main as of 2026-09-29 (`1acdc36`): `load_generator.py:297` still acquires the permit before reading an event and holds it while the event waits for its predecessor. Upstream PR #805 was closed without merging, and issue #648 is still open.
- **The lane driver defaults to the buggy image.** `../10-llm-d-router-replicates/run-replicates.sh` defaults to the official v0.7.0 image, so step 20 must pass `BENCH_IMAGE`. Step 15's single-pod cells ran on that buggy image; step 18's single-pod cells ran on `session-id-v1`.

## Arms

| arm | plugin file | what it is |
|---|---|---|
| `baseline` | `../12-llm-d-router-pool/baseline-plugins.yaml`, copied into the lane folder | llm-d default. On one pod it equals session affinity: no gate. |
| `thunder-lease-main` | `../10-llm-d-router-replicates/thunder-lease-main-plugins.yaml` | the lease gate, `idleLeaseSeconds` 30, as in steps 18 and 19. Capacity = GPU KV, scraped from vLLM (2,237,040 tokens). |
| `thunder-lease-main-tier` | new, `thunder-lease-main-tier-plugins.yaml` | the same gate and keys, with capacity = the CPU tier (about 8.74M tokens). Phase B only. |

## Sizing the gate to the CPU tier

**Today's code:** thunder-agent takes a pod's capacity from the block size and GPU block count in vLLM's `cache_config_info`. It uses the config key `capacityTokens` only when the endpoint does not report them (`accounting.go:121-126`, `endpointCapacity`). vLLM always reports them, so setting `capacityTokens` alone has no effect.

**Config-only way, no code change:**

- The EPP's `core-metrics-extractor` reads cache info through `cacheInfoSpec` (`datalayer/extractor/metrics/factories.go`).
- An empty spec is a supported value: `parseStringToSpec("")` returns a nil spec (`spec.go:54`, "allow empty string to represent the nil Spec"). The built-in sglang, trtllm-serve and triton configs already use it, and the extractor then skips cache info with no error.
- So the tier arm's EPP config declares `core-metrics-extractor` with the vLLM engine config restated, only `cacheInfoSpec: ""` changed, as in `test/perf/config/router-configs/endpoint-attribute-parity.yaml`. That test notes that declaring `vllm` replaces the whole built-in vLLM entry, so all five specs are carried over.
- The EPP then never learns the GPU block count, and thunder-agent uses `capacityTokens`.
- Nothing else in the lease arm's config reads block size: it has only `agent-identity`, `thunder-agent`, `max-score-picker` and `single-profile-handler`.

**Why the CPU tier size and not GPU plus CPU:** the connector copies every newly computed block to CPU each step (`_build_store_jobs` in vLLM's `offloading/scheduler.py`), not only blocks evicted from the GPU. So the CPU tier holds a copy of what the GPU holds, and the KV a pod can keep is about the CPU tier size.

**The value:** 400 GiB / 48 KiB per token = 8,738,133 tokens, set in `thunder-lease-main-tier-plugins.yaml`. The smoke test checks it two ways: it is within 1 percent of the tier size vLLM logs (`Created mmap file ... (N GB)`, converted to tokens), and the tier lane's `thunder_agent_endpoint_capacity_tokens` shows it.

**What each gate does:**

- The GPU-sized gate keeps the admitted sessions within GPU KV, about 40 to 50 sessions per pod, and holds the rest, whose KV sits in CPU.
- The tier-sized gate admits until the CPU tier is full, so it is idle at low c and engages only where the tier would thrash.

## The model server change

vLLM v0.28.0 ships the native `OffloadingConnector`. It is turned on by `--kv-offloading-size` (GiB, summed over the TP ranks; `vllm/config/vllm.py` `_post_init_kv_transfer_config`).

**The CPU buffer is a file in `/dev/shm`.** On CUDA the connector always uses a shared mmap file, `/dev/shm/vllm_offload_<engine_id>.mmap` (`v1/kv_offload/cpu/shared_offload_region.py:94`, used whenever `_uses_shared_region()` is true, `cpu/spec.py`). Before creating it, the connector checks the free space in `/dev/shm` (`check_shm_free_space`). It then prefaults the whole file (`MADV_POPULATE_WRITE`) and registers it as pinned memory (`cudaHostRegister`). So:

- the pod's `/dev/shm` volume (an in-memory `emptyDir`, `sizeLimit: 20Gi` today) must be at least the tier size;
- tmpfs pages count against the pod's memory limit.

| | now | phase A | phase B |
|---|---|---|---|
| replicas | 4 | 3, one per node | 3, one per node |
| vLLM args | as in `../model-server/deployment.yaml` | unchanged | plus `--kv-offloading-size=400` |
| memory request / limit | 96Gi / 128Gi | 96Gi / 128Gi | 450Gi / 450Gi |
| `/dev/shm` `sizeLimit` | 20Gi | 20Gi | 410Gi |
| pod anti-affinity | none | one replica per node | one replica per node |

**Why 400 GiB.** It is what each replica gets in a normal deployment on this hardware: an `a3-highgpu-4g` node has 4 H100s, so 2 replicas at TP=2, and 895 GiB allocatable. The result then carries over to the 4-replica pool. A larger tier (up to about 850 GiB on a node with one replica) would push the knee to c = 270 to 380 on one pod, where each session gets only 3 to 5 turns per window and the cell measures cold start and queueing more than reuse.

**Placement, from live values on 2026-09-29.** Each node has 895.4 GiB allocatable. With one 450Gi replica per node:

| node | other workloads | memory requested by others | fits 450Gi | lane |
|---|---|---|---|---|
| `trwg` | system pods only | about 1 GiB | yes | a |
| `91qy` | vllm-omni (64Gi, limit 128Gi), a dynamo worker | about 65 GiB | yes | b |
| `zhnf` | comfyui (200Gi), sglang (32Gi, limit 48Gi) | about 233 GiB | yes, 662 GiB free | c |

Pods on different nodes do not share host memory bandwidth, which carries the offload traffic. The neighbors on `91qy` and `zhnf` are a source of pod differences, which this step accepts (see "Cells").

**Memory budget per pod:** a 400 GiB tier, plus about 11 GiB of process and shm memory, plus reclaimable model page cache, with about 30 GiB of headroom, inside the 450Gi limit. Today a vLLM pod uses about 40 GiB, 30 GiB of which is page cache.

**Reach.** KV costs 48 KiB per token (48 layers x 2 for K and V x 4 KV heads x 128 dims x 1 byte in FP8):

- GPU KV: 2,237,040 tokens, about 102 GiB.
- The 400 GiB tier: 8.74M tokens, 3.9 times the GPU KV.

**Rollout risks:**

- `Recreate` restarts all pods.
- Going from 4 replicas to 3 frees 2 GPUs that another workload could take. None were pending on 2026-09-29; check again right before the change and restore promptly.
- Prefaulting 400 GiB takes time at startup.
- The container memlock limit is 8 MiB. `cudaHostRegister` normally does not count against it; the smoke test confirms it.

## Concurrency per replica

**Rule from step 13 (GPU only):** the hit rate collapses once the working set reaches about 0.75 to 0.87 times the KV that can hold it. At 0.45x the hit rate was 0.93, at 0.75x 0.73, at 0.87x 0.34, at 1.18x 0.04. The working set is about `c x mean prompt tokens`.

**Check without offloading:**

- 0.75 to 0.87 x 2.24M is 1.7M to 1.9M tokens.
- At 61k to 70k tokens per session, that is c = 24 to 32 on one pod.
- This matches step 13's collapse between 24 and 32 sessions per pod.

**With the 400 GiB tier:**

- 0.75 to 0.87 x 8.74M is 6.6M to 7.6M tokens.
- Tokens per session fall as c rises (step 13: 83k at 12 sessions per pod, 61k at 32, 49k at 84; about 45k expected above that).
- **So the CPU tier should start to thrash at about c = 130 to 175 per replica.**

c stays below the corpus size (338 traces), so no duplicated sessions are needed.

| c | expected working set / reach | role |
|---|---|---|
| 32 | about 0.2 | the GPU-only knee, with the tier holding everything; the step 18 single-pod load |
| 64 | about 0.4 | far past the GPU knee, well inside the tier |
| 128 | about 0.65 | just before the CPU knee |
| 192 | about 0.95 | at the CPU knee |
| 256 | about 1.2 | CPU tier thrashing |

These are estimates. Every cell measures the real working set against reach, from the per-request report and the vLLM counters.

## Cells: three arms in parallel, one round per point

Three lanes run at the same time, one arm each, one cell per arm and point. Which lane runs which arm rotates from point to point, so no arm always has the same pod.

Pod differences are not cancelled; this is chosen for speed. In step 10, the same arm on three different pods gave 221 to 236 tok/s (sticky) and 327 to 367 tok/s (thunder), about 3 to 6 percent apart. So an arm gap below about 6 percent at one point is read as no difference.

**Phase A, offload off** (the same three replicas, before offloading is turned on):

- No single-replica llm-d default cell exists on the fixed load generator at these loads: step 15 used the buggy image, and step 18 ran only the lease gate.
- Without offloading the tier arm makes no sense, so the third lane runs the lease gate a second time. Its gap to the other lease cell measures the pod difference directly, for free.
- Three points cover the range: 32 is the GPU-only knee, and 128 and 256 are deep past it. The GPU-only curve past the knee is expected to be flat, so 64 and 192 are left out. Adding them costs about 1.8 hours.

| c | window (warm-up) | lane a / lane b / lane c | time |
|---|---|---|---|
| 32 | 30 min (10) | baseline / lease / lease | about 46 min |
| 128 | 30 min (10) | lease / baseline / lease | about 46 min |
| 256 | 45 min (15) | lease / lease / baseline | about 61 min |

**Phase B, offload on (400 GiB):**

| c | window (warm-up) | lane a / lane b / lane c | time |
|---|---|---|---|
| 32 | 30 min (10) | baseline / lease / tier | about 46 min |
| 64 | 30 min (10) | tier / baseline / lease | about 46 min |
| 128 | 30 min (10) | lease / tier / baseline | about 46 min |
| 192 | 45 min (15) | baseline / lease / tier | about 61 min |
| 256 | 45 min (15) | tier / baseline / lease | about 61 min |

Time:

- Phase A: about 2.6 hours.
- Phase B: about 4.3 hours.
- Two rollouts, the smoke test and the restore: about 1 hour.
- Total: about 8 hours.

This answers:

- at c = 32, 128 and 256: offload effect for llm-d default and the lease gate (B against A), and the gate effect with and without offloading;
- at every B point: llm-d default against the GPU-sized gate against the tier-sized gate;
- along c in B: where the CPU tier starts to thrash;
- in A: the pod difference, from the two lease cells at each point.

Why the longer windows at c = 192 and 256: one replica finishes about 0.7 turns per second. At c = 256 all sessions start together, and their first turns alone are about 7M cold prompt tokens, about 5 minutes of prefill, so warm-up is 15 minutes and the window 45 minutes. The client timeout stays at 1900 s. At c = 256 a session gets a turn about every 6 minutes, well under it.

## Throughput will not tell thrashing apart from queueing

`../13-llm-d-router-sweep/SATURATION.md` shows two limits that offloading does not remove:

- **Decode is limited by memory bandwidth.** Output peaks at 12 to 16 sessions per pod (about 500 tok/s per pod) with the hit rate still 0.95. Every decode step reads each running request's whole KV.
- **GPU KV bounds the running batch.** A pod runs only about 32 to 37 requests of 60k to 70k tokens at once. With a large tier, extra requests wait in vLLM with their KV in CPU.

So output throughput will be roughly flat across c and TTFT will grow with c, whether or not the tier thrashes. Thrashing is judged by direct signals instead:

- the CPU hit rate falls;
- prefill tokens computed rise;
- store bytes grow faster than load bytes, because blocks are written and evicted before they are read back.

vLLM waiting growing on its own means queueing.

## Expectations (written before the run)

- **c = 32 and 64:** the tier holds everything.
  - llm-d default should come close to the gates on throughput and hit rate.
  - The tier-sized gate should be idle and look like llm-d default.
  - Any remaining gap between the GPU-sized gate and llm-d default comes from the gate's order: admitted sessions' turns first, instead of vLLM's FCFS. The TTFT distribution and session-level SLO may still differ.
- **c = 192 and 256:** the tier thrashes.
  - Both gates should gain over llm-d default, as the gate does without offloading.
  - The tier-sized gate should keep the CPU hit rate up while admitting more sessions than the GPU-sized gate.
- **A risk to watch for the GPU-sized gate:** on one pod it admits about 40 to 50 sessions and holds the rest. At high c, held sessions may reach the 1800 s forced admission. If forced admissions grow with c for the GPU-sized gate and not for the tier-sized gate, GPU sizing is too conservative when a CPU tier exists.

## Cache reset per cell: the GPU cache and the CPU tier

`RESET_EXTERNAL=1` in `run-replicates.sh` makes the per-cell reset clear both.

- It posts `/reset_prefix_cache?reset_external=true` to the lane's vLLM pod. Today the harness checks only the HTTP status, but in v0.28.0 the reset returns `{"success": false}` while blocks are held, for example by offload transfers still in flight.
- **Code path, checked in v0.28.0:**
  - The endpoint calls `Scheduler.reset_prefix_cache(reset_connector=True)` (`v1/core/sched/scheduler.py:2511`).
  - That resets the GPU prefix cache, then calls the offloading connector's `reset_cache()`, which calls `manager.reset_cache()`, "evicting all stored chunks" (`offloading/scheduler.py:1656`).
  - `success` is true only if both resets succeed.
- It retries every 10 s until `success` is true. If that does not happen within 5 minutes, the cell stops with FATAL and does not run.
- Every response is saved with its timestamp in the cell's `reset.jsonl`, one JSON object per line.
- The smoke test (check 5) proves on the live replicas that a reset with `reset_external=true` leaves no CPU hits.

## Metrics: GPU and CPU hits counted separately

The prober already saves each replica's full `/metrics` text every 10 s (`raw-vllm-<ip>.txt.gz`), so nothing new has to be scraped.

| metric | source |
|---|---|
| GPU hit rate | `vllm:prefix_cache_hits / queries` |
| CPU hit rate | `vllm:external_prefix_cache_hits / vllm:prefix_cache_queries` |
| total reuse | (GPU hits + CPU hits) / `vllm:prefix_cache_queries` |
| CPU store and load GB, load time | `vllm:kv_offload_store_bytes`, `load_bytes`, `load_time` |
| allocation failures | `vllm:kv_offload_allocation_failure` |
| working set / reach over time | per-request report: the latest prompt size of each live session, summed, divided by 8.74M |
| gate capacity | `thunder_agent_endpoint_capacity_tokens`: 2,237,040 for the lease arm, about 8.74M for the tier arm |
| prefill tok/s, vLLM waiting, TTFT p50 / p90 / p99, session-level SLO, holds, pauses, forced admissions | as in steps 13 to 19 |

In v0.28.0, `vllm:external_prefix_cache_queries` counts only the tokens the GPU missed (`v1/core/sched/scheduler.py`). That is why the CPU hit rate uses the GPU queries as its denominator.

Every cell reports the three hit rates (GPU, CPU, total), for the whole window and the steady state, and also as time series.

- The split comes only from the vLLM counters. v0.28.0 has no per-source prompt token metric.
- Each response's `cached_tokens` counts GPU and CPU hits together (smoke check 4 confirms this), so the per-request report gives total reuse only.
- "Prefill tokens computed" stays `prompt_tokens - cached_tokens`, which is recompute only, with or without offloading.
- Phase A cells report the same rows. The CPU rows must be 0 there, which checks that offloading is really off.

## Saved deployments and EPP configs

Every model-server state and every EPP config used in this step is kept as a file, so any cell can be traced to the exact deployment and config it ran on. Nothing is committed until you ask.

**vLLM manifests we apply**, in this folder. They were generated from `../model-server/deployment.yaml` and differ from it only in the fields listed in their headers; `offload.sh save-before` refuses to run if the live deployment no longer matches that base.

- `vllm-deploy-3rep-off.yaml`: phase A.
- `vllm-deploy-3rep-offload400.yaml`: phase B.

**EPP configs**, the three arm files in `../10-llm-d-router-replicates/`:

- `baseline-plugins.yaml`: step 12's llm-d default, with `apiVersion: llm-d.ai/v1` (the lease image no longer registers `inference.networking.x-k8s.io/v1alpha1`; plugins unchanged).
- `thunder-lease-main-plugins.yaml`: unchanged from step 18.
- `thunder-lease-main-tier-plugins.yaml`: new, described in "Sizing the gate to the CPU tier".

**Live vLLM state at each switch**, under `results/`:

- `vllm-deploy-before.yaml` and `.json`: the original deployment, from `kubectl get` before any change. `vllm-deploy-before-clean.json` is the same with runtime fields dropped; `restore` applies it.
- `vllm-deploy-live-<state>.yaml`: the deployment as the cluster holds it after each switch (`before`, `off`, `offload400`, `after-restore`).
- `vllm-pods-<state>.txt`: pod names, uids, nodes, IPs and restart counts.
- `vllm-cache-config-<state>.txt`: each pod's `vllm:cache_config_info` line.
- `vllm-startup-<state>-<pod>.log`: each pod's log right after the switch, with the connector name, the mmap file and its size.
- `vllm-deploy-after-restore.yaml`: the state after the restore, checked against `vllm-deploy-before.json`.
- `main-release-before.yaml`: the main EPP release manifest (`helm get manifest`), as in step 19. The lanes never touch it; the restore only checks it.

**Lanes**, under `results/`:

- `lanes.env`: lane to pod, IP and node, rewritten before every point.
- `lane-chart-commit.txt`: the commit of the standalone chart the lanes are rendered from.
- `smoke-test-output.txt` and `smoke-epp-lane-<lane>.log`: the smoke test and each lane EPP's log at that time.
- `vllm-memory.csv`: before and after every point, each lane pod's cgroup memory use and limit, its OOM kill count and its `/dev/shm` use. The 400 GiB tier is the main memory risk, so this is recorded even though the pods are expected to stay flat.

**Per cell**, in its directory:

- `plugins.yaml`: the arm file as used.
- `lane-manifest.yaml`, `lane-values.yaml`: the rendered lane EPP manifest and values that were applied.
- `epp-configmap.yaml`: the EPP ConfigMap read back from the cluster after the cell.
- `epp.log`, `vllm.log.gz`, `prober.log`, `reset.jsonl`, `config.yml` (inference-perf), `manifest.json` (images, vLLM pod, its uid, the vLLM container's restart count at start and end, the EPP's restart count at the end).
- `results/`: the prober's CSVs (vLLM every 2 s, EPP), the raw `/metrics` text of the vLLM pod and the EPP every 10 s (`raw-vllm-metrics.txt.gz`, `raw-epp-metrics.txt.gz`), and inference-perf's reports, including the per-request report with session ids.
- A cell is aborted and renamed `-PREEMPTED` if its vLLM pod is replaced or its vLLM container restarts (an OOM kill keeps the pod but empties every cache).

Each run directory also has `step20.json` (phase, c, window, warm-up, lane arms, nodes, images) and `driver.log`.

## How to run

Unattended, about 8 hours:

```
mkdir -p results && nohup caffeinate -i ./run-all.sh > results/driver.log 2>&1 &
```

`run-all.sh` runs, in order: `offload.sh save-before` (skipped when an original is already saved), `offload.sh on`, `smoke-test.sh` (which deploys the lanes), `run-cells.sh B`, `offload.sh off`, `lanes.sh deploy`, `run-cells.sh A`, then removes the lanes, restores the vLLM deployment, checks the main release and runs `analyze.py`.

Phase B runs first. The first launch (2026-09-30 00:34) ran phase A first; it was stopped about 12 minutes into A's c=32 point so that offloading runs first. Its partial cells are in `results/aborted/` and are not analyzed. The original deployment it saved at 00:34 is the one restored at the end.

- If any smoke check fails, phase B is skipped.
- The restore runs on every exit path, so a failure does not leave the model server at 3 replicas.
- `save-before` refuses to start if GPU pods are pending or the live deployment is not the manifests' base, and then changes nothing.

By hand, the same steps work one at a time. `run-cells.sh A 128` runs only one point, for example to redo a failed one.

## Smoke test, after offloading is on

`smoke-test.sh`, exit code = number of failed checks.

On each replica, offloading:

1. `vllm:cache_config_info` reports `kv_offloading_size` 400. The log names `OffloadingConnector`. The tier size in the log's `Created mmap file ... (N GB)` line, in tokens, is within 1 percent of the tier arm's `capacityTokens`. `/dev/shm` holds at least 380 GiB.
2. GPU KV is still 2,237,040 tokens (block size x GPU blocks).
3. No restart or OOM kill. `kv_offload_allocation_failure` is 0.

On each replica, the CPU tier works (`cpu-tier-probe.py`, run inside the pod):

4. Clear both tiers and send a fresh prompt of about 50k tokens; it is computed. Reset the GPU cache only and send it again. Expect `cached_tokens` and external hits of at least 90 percent of the prompt, and a response time at most half the first one. So the CPU tier serves the prefix, and "prefill tokens computed" still counts only recompute. Also expect `vllm:kv_offload_store_bytes` to grow on the first request and `vllm:kv_offload_load_bytes` on the second, which proves the offload counters the analyzer reads are exported under those names.
5. Reset with `?reset_external=true` and send it again. Expect `success: true`, `cached_tokens` below 5 percent and no external hits.

On the lanes, deployed as at phase B's first point (a baseline, b lease, c tier):

6. Lane a has no flow control and answers. Lanes b and c: build commit `44544c04`, flow control on, `idleLeaseSeconds: 30` in the live ConfigMap, and one endpoint at capacity 2,237,040 (lane b) or the tier value (lane c). Lane c's live ConfigMap has `cacheInfoSpec: ""` and the tier `capacityTokens`, and its EPP log shows its vLLM engine mapping registered.
7. Lanes b and c, step 19's accounting checks: two turns of one session and one turn of another are answered, 2 new sessions are tracked, none is running or paused afterwards, releases are new +2 and admitted +1, and there are no holds or pauses. No error or panic line in any lane EPP's log.

## Changes to the lane harness

All in `../10-llm-d-router-replicates/`, backward compatible: off by default, so earlier steps run unchanged.

- `run-replicates.sh`:
  - `RESET_EXTERNAL=1`: the reset described above.
  - `LANE_ARMS="a:<arm> b:<arm> c:<arm>"`: one cell per lane with the given arm, all lanes at the same time. Without it, every lane runs every arm in turn, as before.
  - `SKIP_ANALYSIS=1`: do not run step 10's analyzer at the end.
  - Every cell now keeps its own copy of the rendered lane manifest, the lane values and the arm file. Before, the lane files in `results/` were overwritten by the next cell.
  - Arm checks: `baseline` must run without flow control on the run's image; a `*-tier` arm must have `cacheInfoSpec: ""` and its `capacityTokens` in the live ConfigMap.
  - A vLLM container restart during a cell aborts it like a pod replacement. Before, only a new pod uid was caught. Restart counts go into `manifest.json`.
- `baseline-plugins.yaml` and `thunder-lease-main-tier-plugins.yaml` added.

## Files in this folder

- `vllm-deploy-3rep-off.yaml`, `vllm-deploy-3rep-offload400.yaml`: the two manifests.
- `lib.sh`: shared settings (lane nodes, images, the kubeconfig pinned to bobbm) and helpers.
- `offload.sh save-before | off | on | restore`: switches the deployment with `kubectl replace` and records each state.
- `lanes.sh label | deploy | teardown`: the three lane EPPs, pinned to their nodes.
- `smoke-test.sh`, `cpu-tier-probe.py`: checks 1 to 7.
- `run-cells.sh A|B [c ...]`: one phase's table through `run-replicates.sh`.
- `run-all.sh`: the whole step, unattended.
- `analyze.py`: `results/analysis.md` (one table per point, the three arms side by side, with the rows in "Metrics"), `results/summary.png` (curves against c, phase B solid and phase A dashed) and `results/timeseries-<phase>-c<c>.png` (GPU and CPU hit rates per minute).

## Checks done before the run (2026-09-30)

Nothing was deployed; these ran locally or read-only.

- **The three arm configs load under the production config path at `44544c04`** (the image's commit), in a temporary worktree with temporary tests, since removed. Step 12's llm-d default config failed there because of its old API group, hence the `llm-d.ai/v1` copy.
- **The tier config's extractor skips cache info:** against a mock vLLM `/metrics`, it leaves block size and GPU blocks at 0 while still reading queue, running and KV usage, with no extraction error. The default extractor, as a control, reads 139,815 blocks. thunder-agent then returns `capacityTokens` (8,738,133), and the scraped 2,237,040 when blocks are known.
- **The reset retry** was tested with a fake `kubectl`: it retries on `success: false` and on an HTTP error, succeeds on `success: true`, stops with FATAL after its deadline, and writes valid JSON lines.
- **`cpu-tier-probe.py`** was tested against a fake vLLM server, including a first reset answering `success: false`. The smoke test's pass conditions were evaluated on its output.
- **The live vLLM deployment matches `../model-server/deployment.yaml`**, the base of both manifests. **Both manifests pass a server-side dry run** (nothing persisted; the live deployment stayed at 4 replicas, generation 3).
- **All three lane EPP manifests render** with image `thunder-agent-lease-44544c04`.
- **vLLM exports every counter twice**, as `<name>_total` and as a `<name>_created` timestamp (22,967 such lines in step 18's scrapes). The analyzer and the probe read only the value series. The smoke test's allocation-failure check first summed both and would have failed on a timestamp of about 1.79e9; it was fixed and tested on step 18's scrapes (old pattern 1,790,134,939, fixed 0).
- **The offload metric names** were read from the v0.28.0 source (`offloading/metrics.py`): `vllm:kv_offload_store_bytes`, `load_bytes`, `store_time`, `load_time` and `allocation_failure` are counters with only the engine labels. `vllm:external_prefix_cache_hits` and `queries` already appear, at 0, on today's pods.
- **The memory snapshot and the restart-count lookup** were run read-only on a live vLLM pod: 43.9 GB used of a 128 GiB limit, 0 OOM kills, restart count 0.
- **`analyze.py` ran on step 18's single-pod lane cells.** Its GPU hit rates from the raw scrapes match step 18's published values: whole window exact, steady state within 0.003. Its working set from the per-request report, 2.23M tokens, matches the gate's ledger, 0.99 of capacity.

## Result (2026-09-30)

All 24 cells completed, 3 arms at 8 points. Phase B ran 01:08 to 05:04, phase A 05:08 to 07:23.

- **No failures:** no preemption, no vLLM or EPP restart, no OOM kill.
- **The deployment and the main release were restored at 07:27** and checked against the saved original.
- **One cell was recovered by hand:** phase A c=128 lane b. Its results copy failed 5 times with `unexpected EOF` on the 45 MB per-request report. It was re-copied from the bench pod, and every file matches the pod's md5 (`recover-cell.sh`, and the note in its `manifest.json`). The lane driver now copies file by file with md5 checks (`copy_results`).
- **Memory:** the peak was 445 GiB against the 450Gi limit (`results/vllm-memory.csv`; it includes reclaimable page cache). The margin was thin, so a later run should give the pod more headroom.

Full tables are in `results/analysis.md`, curves in `results/summary.png`, and hit-rate time series in `results/timeseries-*.png`.

**Output throughput (tok/s)**, one cell per arm; phase A's lease column is the mean of its two cells:

| c per replica | A: llm-d default | A: lease | B: llm-d default | B: lease, GPU capacity | B: lease, CPU-tier capacity |
|---|---|---|---|---|---|
| 32 | 359 | 516 (520, 511) | 567 | 570 | 560 |
| 64 | - | - | 545 | **637** | 585 |
| 128 | 284 | 498 (511, 485) | 562 | **631** | 568 |
| 192 | - | - | 361 | 560 | **576** |
| 256 | 286 | 367 (357, 376) | 286 | 527 | **535** |

**Total prefix reuse, steady state (GPU + CPU)**, and median TTFT:

| c | B: llm-d default | B: lease, GPU capacity | B: lease, CPU-tier capacity |
|---|---|---|---|
| 32 | 0.92, 5.1 s | 0.91, 0.5 s | 0.91, 5.1 s |
| 64 | 0.92, 45 s | 0.88, 0.6 s | 0.92, 44 s |
| 128 | 0.84, 103 s | 0.86, 1.3 s | 0.87, 106 s |
| 192 | **0.07**, 236 s | 0.76, 3.1 s | 0.81, 148 s |
| 256 | **0.00**, 415 s | 0.68, 9.5 s | 0.76, 167 s |

**Pod difference:** in phase A the two lease cells differ by 2 to 5 percent in throughput and 0.04 to 0.06 in hit rate, in line with step 10's 3 to 6 percent.

### Readings

1. **Offloading alone helps llm-d default a lot, until the CPU tier is full.**
   - Throughput goes from 359 to 567 tok/s at c=32 (1.58x) and from 284 to 562 at c=128 (1.98x).
   - Almost all of the reuse comes from the CPU tier: its hit rate is 0.84 to 0.92 while the GPU hit rate is near 0.
   - Between c=128 and 192 the tier thrashes. The CPU hit rate falls from 0.84 to 0.07, then 0.00. Throughput drops to 361, then 286, exactly the no-offload value.
   - The measured working set / tier at the collapse is 0.79 at c=128 and 1.07 at c=192. The plan predicted thrashing from about c = 130 to 175, at 0.75 to 0.87 of reach.
2. **Offloading also helps the gate.** The GPU-sized gate goes from 516 to 570 tok/s at c=32, 498 to 631 at c=128, and 367 to 527 at c=256. Its paused sessions come back from CPU: it loads 0.4 to 1.7 TB per cell.
3. **With offloading, the GPU-sized gate's throughput advantage over llm-d default depends on load.**
   - c=32: 1.01x.
   - c=64: 1.17x.
   - c=128: 1.12x.
   - c=192: 1.55x.
   - c=256: 1.84x.
   - This matches the expectation: small while the tier holds everything, large once it thrashes. The 12 to 17 percent at c=64 and 128 is above the pod noise. Even then, llm-d default has 30 to 90 requests waiting inside vLLM, because GPU KV fits only about 25 to 30 running requests.
4. **The CPU-tier-sized gate behaves as designed.**
   - At c=32 to 128 it is idle (its working set is 0.41 to 0.96 of capacity) and matches llm-d default.
   - At c=192 and 256 it holds the working set at the tier size, keeps total reuse at 0.81 and 0.76 where llm-d default falls to 0.07 and 0.00, and gets the best throughput (576 and 535).
   - Compared with the GPU-sized gate there, it has far fewer forced admissions (27 and 72 against 108 and 172) and a much shorter TTFT tail (p99 288 and 677 s against 1831 and 1851 s).
   - But every turn waits in vLLM's queue (about 100 waiting), so its median TTFT is 148 to 167 s.
5. **Latency is where the two gates differ most.**
   - The GPU-sized gate is the only arm with goodput within a 30 s TTFT SLO from c=64 on: 0.41 to 0.62 turns/s, against 0 for the other two. Its median TTFT stays at 0.5 to 9.5 s.
   - Its tail reaches the 1800 s forced admission from c=128 on (p99 1709 to 1851 s), the step 17 tail problem, made worse by load.
   - llm-d default and the tier-sized gate spread the wait over every turn instead: no session is fast, but none waits 30 minutes.

### Caveats

- One cell per arm and point, each arm on a different pod.
- Phase A has no c=64 or 192 points.
- Bench pods shared nodes with some vLLM pods.
- c=192 and 256 have 45-minute windows. At c=256 a session gets only a few turns in the window, so those points weigh early turns more.

## Replicates (2026-10-01)

Phase B ran twice more, on 2026-10-01 from 14:53 to 22:53 (`run-replicates-B.sh`, `REP=2` and `REP=3`).

- **Design:** each replicate moved every arm one lane over, so over the 3 runs every arm ran once on every pod at every concurrency.
- **Completeness:** all 30 new cells completed, with no preemption, no vLLM or EPP restart and no OOM kill. Peak memory was again 445 GiB. The model server and main release were restored and checked.
- **Files:** state and smoke-test files of this run carry the suffix `-replicates`.
- **Figures and tables:** `results/analysis.md` and the figures now give the mean (min-max) over the 3 cells of each arm and point. `figures/fig3-ttft` (median and p99 TTFT) was added.

**Output throughput (tok/s), mean (min-max) of 3 runs:**

| c | llm-d default | lease, GPU capacity | lease, CPU-tier capacity |
|---|---|---|---|
| 32 | 560 (551-567) | 578 (570-584) | 554 (546-560) |
| 64 | 565 (545-584) | 636 (627-643) | 566 (538-585) |
| 128 | 567 (561-578) | 635 (624-649) | 579 (568-585) |
| 192 | 366 (361-370) | 551 (535-560) | 569 (564-576) |
| 256 | 288 (286-292) | 516 (500-527) | 533 (530-535) |

The first run's readings hold. Most metrics vary by about 2 percent across runs, the TTFT p99 more.

- **c = 64 and 128:** the GPU-capacity gate's 12 to 13 percent gain over llm-d default is outside the pod noise. Its median TTFT stays at 0.6 to 1.1 s, against 44 to 104 s for the other two arms, which queue 30 to 87 requests inside vLLM.
- **c = 192 and 256:** the CPU-tier-capacity gate is about 3 percent ahead of the GPU-capacity gate, with non-overlapping ranges, and has fewer forced admissions (23 and 73 against 111 and 163). llm-d default falls to 366 and 288.
- **Tail:** from c = 128 the GPU-capacity gate's p99 TTFT reaches the 1800 s forced admission in every run.
