# The model server: what every step ran against

The serving side is the constant of this whole repo. Every number in steps 04 to 13 was produced against the deployment described here, and only the routing layer in front of it changed. This folder exists so a reader does not have to reconstruct that from four different step folders.

Collected from the live cluster on 2026-09-18 with `collect.sh`. Nothing here is from memory; the section "How to re-check" gives the command behind each value.

## Summary

| | |
|---|---|
| model | `Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8` |
| serving engine | `vllm/vllm-openai:v0.28.0`, the official image, unmodified |
| live manifest | `deployment.yaml` in this folder |
| parallelism | tensor parallel 2, pipeline 1, data 1 |
| replicas | 4 pods, so 8 H100 GPUs in total |
| hardware | GKE `a3-highgpu-4g` spot nodes, 4x NVIDIA H100 80GB each, `us-central1-a` |
| chunked prefill | enabled (vLLM default in v0.28.0, not set on the command line) |
| batch limits | `max_num_batched_tokens` 8192, `max_num_seqs` 1024 (both v0.28.0 defaults, see the caveat below) |
| KV pool per pod | 2,237,040 tokens (139,815 blocks x 16), FP8 KV, prefix caching on |

## Hardware

| | |
|---|---|
| node pool | `bobbm-spoth100`, **spot** (so pods can be preempted mid-run) |
| machine type | `a3-highgpu-4g` |
| GPU | `nvidia-h100-80gb`, 4 per node |
| node CPU / memory | 104 vCPU, 965 GiB |
| zone | `us-central1-a` |
| kubelet | `v1.35.3-gke.1389002`, GPU driver channel `latest` |

Each vLLM pod takes 2 GPUs (TP=2), so the 4 replicas occupy 8 of the pool's GPUs. They are not spread one per node. Pod placement as of 2026-09-18, all four running continuously since 2026-09-16T15:01:04Z:

| pod | node suffix | pod IP |
|---|---|---|
| `program-aware-vllm-decode-9c9b54cb6-f9qsh` | `...-thfk` | 10.100.3.12 |
| `program-aware-vllm-decode-9c9b54cb6-gkzmr` | `...-6j7g` | 10.100.15.21 |
| `program-aware-vllm-decode-9c9b54cb6-kccxc` | `...-6j7g` | 10.100.15.20 |
| `program-aware-vllm-decode-9c9b54cb6-mngw2` | `...-pskw` | 10.100.2.6 |

Two pods share node `...-6j7g`. That matters for any experiment that puts a comparison pair on those two, because they share the node's CPU and network; step 10 avoided it deliberately.

Container resources per pod: requests 8 CPU / 96 GiB / 2 GPU, limits 16 CPU / 128 GiB / 2 GPU.

## Model

`Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8`, a mixture-of-experts coder model, served as published with no local modification.

| | |
|---|---|
| architecture | `qwen3_moe`, 48 layers, hidden size 2048 |
| attention | 32 query heads, 4 key/value heads (grouped-query) |
| routing | top 8 experts per token |
| context | 262,144 positions, served at the full `--max-model-len=262144` |
| vocabulary | 151,936 |
| weights | FP8 `e4m3`, block-wise 128x128, dynamic activation scaling |
| compute dtype | bfloat16 |

The 4 key/value heads are why a 2.2M-token KV pool is possible on two H100s at this context length.

## How it is launched

Deployment `program-aware-vllm-decode` in namespace `llm-d-program-aware-scheduling`, strategy `Recreate`, 4 replicas. Command `vllm serve` with exactly these arguments:

```
Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8
--host=0.0.0.0
--port=8000
--tensor-parallel-size=2
--max-model-len=262144
--kv-cache-dtype=fp8_e4m3
--gpu-memory-utilization=0.88
--compilation-config={"pass_config":{"fuse_allreduce_rms":false}}
--enable-prompt-tokens-details
```

Environment:

| variable | value | effect |
|---|---|---|
| `VLLM_USE_DEEP_GEMM` | `0` | DeepGEMM MoE kernels **off** |
| `VLLM_ALLREDUCE_USE_SYMM_MEM` | `0` | symmetric-memory allreduce **off** |
| `VLLM_SERVER_DEV_MODE` | `1` | enables `/server_info`, which is how the table below was read |
| `HF_TOKEN` | from secret `llm-d-hf-token` | model download |

The two optimisation flags are explicitly disabled, so the throughput numbers in this repo are from the conservative kernel path rather than the fastest one vLLM can do on this hardware.

Nothing about batching or chunked prefill is set on the command line, so those are v0.28.0 defaults.

## The deployment manifest

`deployment.yaml` is the live spec, exported 2026-09-18 and verified with `kubectl diff` to be byte-identical to what is running. Runtime-only fields are stripped so it re-applies cleanly. It needs a secret `llm-d-hf-token` with key `HF_TOKEN`; no secret value is in this repo.

Five things in it that shape how the experiments behave:

- **`strategy: Recreate`.** Any change takes all four replicas down at once. There is no rolling update and no overlap.
- **The Hugging Face cache is an `emptyDir`.** Every pod restart re-downloads the weights, which is why a rollout is expensive and why prefix caches are always cold afterwards.
- **`/dev/shm` is a 20 GiB memory-backed `emptyDir`.** Required for TP=2; NCCL fails on the 64 MiB default.
- **`startupProbe` allows 120 failures at 30 s.** A replica has up to an hour to load before Kubernetes gives up, which matches the download-plus-compile cost above.
- **`nodeSelector: cloud.google.com/gke-accelerator=nvidia-h100-80gb`.** Nothing pins the pods to distinct nodes, which is why two of them currently share one.

## Resolved engine configuration

Read from the running engine (`/server_info` and `vllm:cache_config_info`), so these are what the server actually used, not what the flags asked for:

| | value |
|---|---|
| `enable_chunked_prefill` | **True** |
| `enable_prefix_caching` | **True** |
| `tensor_parallel_size` | 2 |
| `max_seq_len` | 262,144 |
| `dtype` | `torch.bfloat16` |
| `quantization` | `fp8` |
| `kv_cache_dtype` | `fp8_e4m3` |
| `gpu_memory_utilization` | 0.88 |
| `block_size` | 16 |
| `num_gpu_blocks` | 139,815 |
| `kv_cache_size_tokens` | **2,237,040** |
| `kv_cache_max_concurrency` | 8.53 |
| cudagraph mode | `FULL_AND_PIECEWISE`, capture sizes up to 512 |
| compilation | inductor, `fuse_allreduce_rms` disabled by the explicit flag |

`kv_cache_size_tokens` is the number the ThunderAgent port is configured with as `capacityTokens` in every step from 09 on, and `kv_cache_max_concurrency` of 8.53 is the same fact stated the other way: a pod holds only about eight full-length 262k conversations, which is why the weka workload saturates it so easily.

### Caveat on the two batch numbers

`max_num_batched_tokens` and `max_num_seqs` are **not** exposed by `/server_info` or by any metric in v0.28.0. The values quoted above, 8192 and 1024, come from re-running vLLM's own argument resolution inside the pod with the same flags and the same `OPENAI_API_SERVER` usage context:

```python
EngineArgs(model=..., tensor_parallel_size=2, max_model_len=262144,
           kv_cache_dtype='fp8_e4m3', gpu_memory_utilization=0.88
           ).create_engine_config(UsageContext.OPENAI_API_SERVER).scheduler_config
```

That is a faithful reproduction rather than a direct read, so treat it as one step weaker than the rest of the table. The same call also gives `long_prefill_token_threshold` 0, `policy` `fcfs` and `async_scheduling` True. Neither batch limit was ever the binding constraint in our runs: the highest `vllm:num_requests_running` we measured on any pod was 61, against a `max_num_seqs` of 1024. The KV pool binds first, every time.

## Change history

The serving side is nearly, but not exactly, constant. Three deployment revisions exist:

| revision | created | what |
|---|---|---|
| 1 | 2026-09-10T08:05:05Z | initial |
| 2 | 2026-09-10T08:07:38Z | |
| 3 | 2026-09-16T15:01:04Z | **current**: added `--enable-prompt-tokens-details` |

Revision 3 is the only change made during this verification work, and it is recorded in `../08-cluster-changes.md`. It makes vLLM report `prompt_tokens_details.cached_tokens` in the OpenAI `usage` object, which is what every per-request cache-hit number in this repo is computed from. It changes reporting only, not scheduling, batching or capacity.

Every step from 07 onward ran on revision 3, and the four pods have not restarted since it rolled out. Steps 04 to 06 ran on revision 2, identical apart from that flag.

The nodes are spot, so a preemption can replace a pod at any time. Step 12's driver detects this by comparing pod UIDs and voids the affected cell rather than reporting it.

## How to re-check

Two scripts:

| script | what it does |
|---|---|
| `collect.sh` | prints every value in this document from the live cluster; read-only |
| `export-deployment.sh` | regenerates `deployment.yaml` from the live cluster and checks it against `kubectl diff` |

`./collect.sh` prints every value in this document from the live cluster. Run it before trusting any of these numbers against a cluster that has since been rebuilt.

To confirm `deployment.yaml` still matches what is deployed:

```
kubectl diff -f deployment.yaml     # silent and exit 0 means identical
```

To recreate the model server elsewhere:

```
kubectl create secret generic llm-d-hf-token --from-literal=HF_TOKEN=<your token> -n <namespace>
kubectl apply -f deployment.yaml
```
