# Step 31: minimal P/D (1 prefill + 1 decode) for Qwen3.5-397B-A17B-FP8 with CPU offload on both, 8x B200

Status: three smoke tests done (2026-10-21). The P/D path works end to end; root cause of the decode-side prefix-cache miss on the turn immediately following a remote prefill is verified in vLLM v0.31 source and confirmed by Smoke 3 (`--mamba-cache-mode all` + `bidirectional_kv_xfer: false`).

## Question

Can Qwen3.5-397B-A17B-FP8 (hybrid Gated DeltaNet + attention) run prefill/decode disaggregated on cluster a4-pr with the stock vLLM v0.31.0 image and llm-d-router v1.0.0, KV moving over the node's RDMA NICs, and a CPU KV tier on both servers? This is the base for P/D benchmarks and for a P/D-aware llm-d-thunder-agent-simplified (see Next steps).

## Setup

| | |
|---|---|
| Node | `5qjv` (`a4-highgpu-8g`, 8 B200, 8 RDMA NICs), freed by scaling step 27's `glm52-dep8-a` to 0; its local SSD caches the checkpoint |
| Prefill | `qwen35-pd-prefill`: vLLM v0.31.0, TP=4, GPUs 4-7 + their 4 NICs, `MAX_NUM_SEQS` 64, KV pool 4,843,063 tokens |
| Decode | `qwen35-pd-decode`: same flags, GPUs 0-3 + their 4 NICs, `MAX_NUM_SEQS` 128, KV pool 4,739,337 tokens; llm-d disagg sidecar `ghcr.io/llm-d/llm-d-router-disagg-sidecar:v1.0.0` on 8000, vLLM on 8200 |
| GPU and NIC claim | [`b200/gpu-nic-claim.yaml`](b200/gpu-nic-claim.yaml): two groups of 2 GPUs + 2 RDMA NICs (DeviceClass `mrdma.google.com`), each on one PCIe root (an A4 root holds 2 GPUs and 2 NICs). DRA placed them rail-aligned on the first try |
| Model flags | step 26's, identical on P and D so the NIXL KV layouts match: FP8 KV, MTP 3, `--max-num-batched-tokens 16384`, `--gpu-memory-utilization 0.8`, prefix caching; plus `VLLM_SSM_CONV_STATE_LAYOUT=DS` and `VLLM_PREFIX_CACHE_RETENTION_INTERVAL=0` from llm-d's Mamba-hybrid P/D guide (nemotron-3-ultra) |
| KV connectors | `MultiConnector` = `NixlConnector` (P `kv_producer`, D `kv_consumer`, `bidirectional_kv_xfer`) + `OffloadingConnector` (387 GiB per server, `lazy_offload`), [`b200/vllm-qwen35-pd.yaml`](b200/vllm-qwen35-pd.yaml). `--kv-offloading-size` is not used: in v0.31 it overwrites `kv_connector` with `OffloadingConnector` and would silently drop NIXL (`config/vllm.py`) |
| RDMA | `IPC_LOCK`; `UCX_TLS=^cuda_ipc` (the two pods see different GPUs); NIXL backend UCX |
| Router | llm-d-router v1.0.0 EPP `agentx-epp-pd`, file discovery with an `llm-d.ai/role` label per endpoint, `disagg-profile-handler` with `always-disagg-pd-decider` (every request takes the remote-prefill path), `prefill-filter` / `decode-filter` profiles: [`b200/pd-plugins.yaml`](b200/pd-plugins.yaml), [`b200/epp-values-pd.yaml`](b200/epp-values-pd.yaml) |
| Smoke | [`b200/run-smoke.sh`](b200/run-smoke.sh): one request, then AgentX c=4 for 120 s (`run-point.sh` MODE=pool, both servers' KV tiers emptied before), dataset `semianalysis_cc_traces_weka_062126_256k` |

## Results

- **Start-up:** 12 minutes for both servers (weights from local SSD in 1.5 to 3 minutes, then CUDA graphs and the CPU tier). Both logged `MultiConnector`, a NIXL agent with the UCX backend, and on D "Bidirectional KV transfer is enabled ... KV blocks on D are released after a TTL of 480 seconds".
- **One request:** sidecar -> prefill `POST /v1/chat/completions 200` -> decode "NIXL compatibility check passed" -> decode `200`.
- **AgentX c=4:** job succeeded, pods unchanged, `verify-point.sh` all ok, 0 error lines in either vLLM log.

| Counter (warmup + 120 s profiling) | Prefill | Decode |
|---|---|---|
| requests served | 51 | 48 |
| prompt tokens | 4.18M | 4.02M |
| local prefix-cache hits | 3.01M (72%) | **0** |
| tokens from the KV connectors (`external_prefix_cache_hits`) | 0 | 4.02M (100%) |
| NIXL transfers / bytes / failed | | 192 / 142.8 GB / 0 |
| NIXL transfer time | | 5.19 s total, 27 ms mean, all under 100 ms; about 27.5 GB/s effective over the 4 ranks |
| CPU tier stores | 34.6 GB | 26.4 GB |

Every decode request took its whole prompt (85k tokens on average, about 744 MB at 35.6 KB per token) from the prefill pod over NIXL, as `always-disagg-pd-decider` asks. The prefill pod reused 72% of its prompt tokens from its own prefix cache (the sessions' history), so P/D does not recompute history on P.

## Open question before benchmarking

**The decode pod had 0 local prefix-cache hits.** In multi-turn sessions, turn N on D could reuse turn N-1's KV, which D received over NIXL and extended while decoding; instead every turn transferred the full prompt again. Either vLLM v0.31 does not insert NIXL-received blocks into D's prefix cache for this hybrid model (Mamba state checkpoints in `align` mode), or bidirectional transfer holds them only for P to read back. This matters for two reasons:

1. `prefix-based-pd-decider` (prefill locally on D when D holds the prefix) relies on the EPP's estimate of D's cache; if D really holds nothing, every "local" turn on D becomes a full recompute.
2. A P/D thunder gate counts session KV as resident on D. If D never reuses it, the resident set worth protecting is on P, not D, and the capacity question changes.

The next smoke runs `prefix-based-pd-decider` and checks D's local hit counter; the vLLM source (`nixl/base_scheduler.py`, D-side `get_num_new_matched_tokens` and block caching) says which case it is.

## Second smoke: prefix-based-pd-decider (2026-10-21 04:55)

Same pair, EPP switched to [`b200/pd-plugins-prefix.yaml`](b200/pd-plugins-prefix.yaml): `prefix-based-pd-decider` with `nonCachedTokens: 4096`, `approx-prefix-cache-producer` matching the whole prompt (the default 131072-token cap is below this workload's longest prompts). Runner [`b200/run-smoke-prefix.sh`](b200/run-smoke-prefix.sh); counters are deltas over the point. `verify-point.sh` all ok.

| | always-disagg (smoke 1) | prefix-based (smoke 2) |
|---|---|---|
| requests on P / D | 51 / 48 | 19 / 56 |
| D local prefix-cache hits | 0 | 2.58M of 4.61M (56%) |
| D tokens over NIXL | 4.02M (100%) | 1.09M (24%) |
| NIXL bytes | 142.8 GB | 40.0 GB |

Per turn, from the client records (the decode sidecar reports D's own cached tokens for turns that stay on D):

| turn class | turns | prompt tokens | cached | TTFT median |
|---|---|---|---|---|
| first turn of a conversation (P) | 12 | 0.76M | 0 | 2.18 s |
| later turn, new tokens >= 4096 (P) | 11 | 0.79M | 0.37M (P's cache) | 1.24 s |
| later turn on D, cache hit | 26 | 2.38M | 2.22M | 0.81 s |
| **later turn on D right after a P turn, cache 0** | **6** | **0.68M** | **0** | **2.75 s** |

The pattern in every conversation: the turn after a remote-prefill turn finds nothing in D's prefix cache and prefills its whole prompt on D (165k tokens: TTFT 5.7 s; 192k: 10.1 s); from the next turn on, D hits the KV it computed itself. So **D reuses the KV it computes, not the KV it receives over NIXL**.

## Third smoke: `--mamba-cache-mode all` + `bidirectional_kv_xfer: false` (2026-10-21 06:30)

Both `qwen35-pd-prefill` and `qwen35-pd-decode` were updated with `--mamba-cache-mode all` and `"bidirectional_kv_xfer": false` ([`b200/vllm-qwen35-pd.yaml`](b200/vllm-qwen35-pd.yaml)) and tested with `LABEL=qwen35-1p1d-mamba-all-smoke` ([`b200/run-smoke-prefix.sh`](b200/run-smoke-prefix.sh)).

### Startup verification: why `--mamba-cache-mode all` falls back to `align`

At startup, vLLM v0.31 logs two warnings on both P and D (`vllm/model_executor/models/config.py:648-657`):

```text
WARNING [cache.py:345] Mamba cache mode 'all' is deprecated and will be removed in an upcoming release.
WARNING [config.py:654] Hybrid or mamba-based model detected without support for prefix caching with Mamba cache 'all' mode: falling back to 'align' mode.
```

In vLLM v0.31.0, `SupportsMambaPrefixCaching` (`all` mode) is only implemented for Mamba1/Mamba2 (`mamba_attn.py`), not for Qwen3.5's Gated DeltaNet (`gdn_attn.py` / `Qwen3_5MoeMTP`). Consequently, `vllm:cache_config_info` reports `mamba_cache_mode="align"` even when `--mamba-cache-mode all` is passed.

### Counter and per-turn comparison

| | always-disagg (smoke 1) | prefix-based, `bi=true` (smoke 2) | prefix-based, `bi=false` (smoke 3) |
|---|---|---|---|
| requests on P / D | 51 / 48 | 19 / 56 | 25 / 76 |
| client requests completed (120 s) | 47 | 55 | **75 (+36%)** |
| client TTFT median | 2,135 ms | 1,564 ms | **715 ms** |
| D local prefix-cache hits | 0 | 2.58M of 4.61M (56%) | 2.92M of 5.12M (57%) |
| D tokens over NIXL | 4.02M (100%) | 1.09M (24%) | 1.19M (23%) |
| NIXL transfers / bytes | 192 / 142.8 GB | 84 / 40.0 GB | 100 / 44.6 GB |

Per-turn breakdown in Smoke 3 (`profile_export.jsonl`, 75 requests across 14 conversations):

| turn class | turns | prompt tokens | cached | TTFT median |
|---|---|---|---|---|
| first turn of a conversation (P) | 14 | 0.80M | 0.02M | 2.20 s |
| later turn, new tokens >= 4096 (P) | 16 | 0.96M | 0.47M (P's cache) | 0.98 s |
| later turn on D, cache hit | 38 | 2.66M | 2.45M | 0.62 s |
| **later turn on D right after a P turn, cache 0** | **7** | **0.69M** | **0** | **1.95 s** |

### Verified root cause in vLLM v0.31.0

1. **`bidirectional_kv_xfer` is not the cause of the miss, and disabling it improves throughput/TTFT:** With `bidirectional_kv_xfer: false`, D no longer pins finished requests' blocks for `decoder_kv_blocks_ttl = 480s` (`nixl/pull_scheduler.py:231-268`). Throughput at `c=4` rose from 55 to 75 requests (+36%) and median TTFT dropped from 1,564 ms to 715 ms, while the 7 D-turns immediately following a P-turn still got `cached = 0` (except subagent turns sharing a system-prompt prefix already locally prefilled on D).
2. **Why `mamba_cache_mode="align"` cannot populate D's Mamba prefix cache from a NIXL transfer:**
   - **On P (`vllm/distributed/kv_transfer/kv_connector/v1/nixl/base_scheduler.py:290-300`):** In `align` mode (`_ssm_state_slots_are_positional = False`), `get_exchange_clipped_blocks` clips the Mamba group to `blocks[-1:]` — only the single running Mamba state at `N - _prefill_backoff()` in the unaligned tail block is sent to D; block-aligned Mamba checkpoints materialized during P's chunked prefill are not transferred.
   - **On D (`vllm/v1/core/single_type_kv_cache_manager.py:298-365`, `1989-1994`):** When allocating slots for `num_external_computed_tokens` received over NIXL, `MambaManager.get_num_skipped_tokens` returns `num_computed_tokens - 1`. `add_local_computed_blocks` pads all full prefix blocks `0 .. K-1` in `MambaManager.req_to_blocks` with `_null_block` and sets `num_cached_block = K`, allocating only 1 real Mamba block at index `K` for the tail state.
   - **When NIXL recv finishes on D (`vllm/v1/core/sched/scheduler.py:3085`):** `cache_blocks` caches all `K` full blocks in `FullAttentionManager`, but caches **0 blocks** in `MambaManager` (`num_cached_blocks >= num_full_blocks` and blocks `0 .. K-1` are `_null_block`).
   - **On the next turn on D (`vllm/v1/core/kv_cache_coordinator.py:1131-1200`):** `HybridKVCacheCoordinator.find_longest_cache_hit` intersects hits across `FullAttention` and `Mamba`. Because `MambaManager` has 0 cached blocks for that prefix on D, the combined hit is reduced to `0`, forcing D to run one local chunked prefill (which materializes and caches the block-aligned Mamba state on D so all subsequent D-turns hit).

## Next steps

1. Benchmark against step 26/30's aggregated TP=4 servers at c = 32, 48, 64 (same 8 GPUs: two aggregated servers against 1P1D), with `prefix-based-pd-decider` and `bidirectional_kv_xfer: false`.
2. P/D-aware llm-d-thunder-agent-simplified: v1.0.0's plugin enters prefill pods in its ledger and their empty room admits new sessions (`saturation.go`, `fairness.go`); the fix skips `llm-d.ai/role=prefill` endpoints.

## Notes

- A throwaway curl pod in step 2 of the smoke script could not resolve the EPP Service name (DNS on that pod); `run-point.sh`'s own completion check through the EPP succeeded a minute later.
- With one endpoint per role, v1.0.0 still injects the utilization detector as a filter into both profiles; its fail-open fallback makes it a no-op here.
- The servers and the EPP are left up on `5qjv` for the follow-ups.
