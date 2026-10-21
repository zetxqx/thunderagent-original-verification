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

### Counter and per-turn comparison (Smokes 1–4)

We also ran **Smoke 4** (`b200/results/qwen35-1p1d-always-bi-false-smoke/c4/`) with `always-disagg-pd-decider` and `bidirectional_kv_xfer: false` to isolate the effect of `bidirectional_kv_xfer` from the choice of PD decider:

| | always-disagg, `bi=true` (smoke 1) | prefix-based, `bi=true` (smoke 2) | prefix-based, `bi=false` (smoke 3) | always-disagg, `bi=false` (smoke 4) |
|---|---|---|---|---|
| requests on P / D | 51 / 48 | 19 / 56 | 25 / 76 | 56 / 56 |
| client requests completed (43 warmup + profiling) | 47 (43 + 4) | 55 (43 + 12) | 75 (43 + 32) | 55 (43 + 12) |
| D peak / end `vllm:kv_cache_usage_perc` | **99.2% / 99.2%** | 31.7% / 31.6% | **4.2% / 0.0%** | **3.3% / 0.0%** |
| client TTFT median (all requests) | 1,569 ms | 1,443 ms | **715 ms** | 1,222 ms |
| client TTFT median (12 matched profiling turns) | — (stalled at 4) | 1,068 ms | 1,060 ms | **851 ms** |
| client TTFT max (12 matched profiling turns) | — | 1,920 ms | 4,253 ms | **1,205 ms** |
| P local prefix-cache hits | 2.86M of 4.10M (70%) | 0.44M of 1.09M (40%) | 0.49M of 1.19M (41%) | 3.35M of 4.61M (73%) |
| D local prefix-cache hits | 0 | 2.58M of 4.61M (56%) | 2.92M of 5.12M (57%) | 0 |
| D tokens over NIXL | 4.02M (100%) | 1.09M (24%) | 1.19M (23%) | 4.61M (100%) |
| NIXL transfers / bytes | 192 / 142.8 GB | 84 / 40.0 GB | 100 / 44.6 GB | 224 / 164.0 GB |

Per-turn breakdown in Smoke 3 (`profile_export.jsonl`, 75 requests across 14 conversations):

| turn class | turns | prompt tokens | cached | TTFT median |
|---|---|---|---|---|
| first turn of a conversation (P) | 14 | 0.80M | 0.02M | 2.20 s |
| later turn, new tokens >= 4096 (P) | 16 | 0.96M | 0.47M (P's cache) | 0.98 s |
| later turn on D, cache hit | 38 | 2.66M | 2.45M | 0.62 s |
| **later turn on D right after a P turn, cache 0** | **7** | **0.69M** | **0** | **1.95 s** |

Turn-by-turn comparison on the 12 identical profiling turns (`03e110ac6921c2fe*`) across Smoke 2, Smoke 3, and Smoke 4:

| Session / Turn | ISL | OSL | Route under `prefix-based` | S2 (`prefix, bi=T`) | S3 (`prefix, bi=F`) | S4 (`always, bi=F`) |
|---|---:|---:|---|---:|---:|---:|
| `2a9654314a2beb` turn=2 | 77,870 | 5,306 | P (`>4096` new) | 1,163.9 ms | 1,180.1 ms | **1,062.3 ms** |
| `2a9654314a2beb` turn=3 | 79,412 | 801 | **D after P (miss 79k!)** | 1,920.2 ms | 1,945.0 ms | **762.3 ms** |
| `2a9654314a2beb` turn=4 | 86,199 | 4,033 | P (`>4096` new) | **786.8 ms** | 821.0 ms | 824.0 ms |
| `2a9654314a2beb` turn=5 | 103,350 | 9,543 | P (`>4096` new) | 1,236.6 ms | 4,252.6 ms | **1,204.6 ms** |
| `t_001_d7c3d5d2` turn=1 | 27,605 | 384 | P (first turn) | **247.5 ms** | 271.0 ms | 352.9 ms |
| `t_001_d7c3d5d2` turn=2 | 61,195 | 931 | P (`>4096` new) | 1,245.5 ms | 1,231.3 ms | **1,194.7 ms** |
| `t_001_d7c3d5d2` turn=3 | 62,805 | 346 | **D after P (miss 63k!)** | 1,158.5 ms | 1,271.6 ms | **722.7 ms** |
| `t_001_d7c3d5d2` turn=4 | 64,606 | 190 | D after D (local hit) | **483.4 ms** | 519.3 ms | 724.4 ms |
| `t_001_d7c3d5d2` turn=5 | 64,872 | 5,685 | D after D (local hit) | **352.6 ms** | 374.8 ms | 590.2 ms |
| `t_002_e411ff6e` turn=1 | 48,642 | 4,917 | P (first turn) | 883.3 ms | 971.3 ms | **878.3 ms** |
| `t_003_157ce302` turn=1 | 53,759 | 249 | P (first turn) | 1,036.3 ms | **983.0 ms** | 996.4 ms |
| `t_003_157ce302` turn=2 | 78,394 | 3,846 | P (`>4096` new) | **1,100.1 ms** | 1,136.6 ms | 1,106.9 ms |
| **Median TTFT (12 matched)** | | | | 1,068.2 ms | 1,059.8 ms | **851.1 ms** |
| **Mean TTFT (12 matched)** | | | | 967.9 ms | 1,246.5 ms | **868.3 ms** |
| **Max TTFT (12 matched)** | | | | 1,920.2 ms | 4,252.6 ms | **1,204.6 ms** |

### Verified root causes in vLLM v0.31.0

1. **Why Smoke 1 (`always-disagg`, `bi=true`) stalled at 4 profiling requests (`D KV usage = 99.2%`), and why `bidirectional_kv_xfer: false` fixes it:**
   - With `bidirectional_kv_xfer: true`, `NixlPullScheduler._handle_completed_request` (`nixl/pull_scheduler.py:231-268`) registers every finished request on D into `_reqs_to_send` for `decoder_kv_blocks_ttl = 480s`, pinning its KV blocks on D so they cannot be evicted.
   - Under `always-disagg` (Smoke 1), D pulled a fresh full-prompt copy on every turn (4.02M tokens across 48 requests), filling D's GPU KV pool to **99.2%** by `t=39.8s` (`vllm:num_requests_waiting = 3`).
   - With `bidirectional_kv_xfer: false`, D frees blocks immediately on completion: peak D KV usage drops to **4.2%** (`prefix-based`, Smoke 3) and **3.3%** (`always-disagg`, Smoke 4), with **0.0%** pinned at the end of the run.
2. **Why `mamba_cache_mode="align"` cannot populate D's Mamba prefix cache from a NIXL transfer (hurting `prefix-based-pd-decider`):**
   - **On P (`vllm/distributed/kv_transfer/kv_connector/v1/nixl/base_scheduler.py:290-300`):** In `align` mode (`_ssm_state_slots_are_positional = False`), `get_exchange_clipped_blocks` clips the Mamba group to `blocks[-1:]` — only the single running Mamba state at `N - _prefill_backoff()` in the unaligned tail block is sent to D; block-aligned Mamba checkpoints materialized during P's chunked prefill are not transferred.
   - **On D (`vllm/v1/core/single_type_kv_cache_manager.py:298-365`, `1989-1994`):** When allocating slots for `num_external_computed_tokens` received over NIXL, `MambaManager.get_num_skipped_tokens` returns `num_computed_tokens - 1`. `add_local_computed_blocks` pads all full prefix blocks `0 .. K-1` in `MambaManager.req_to_blocks` with `_null_block` and sets `num_cached_block = K`, allocating only 1 real Mamba block at index `K` for the tail state.
   - **When NIXL recv finishes on D (`vllm/v1/core/sched/scheduler.py:3085`):** `cache_blocks` caches all `K` full blocks in `FullAttentionManager`, but caches **0 blocks** in `MambaManager` (`num_cached_blocks >= num_full_blocks` and blocks `0 .. K-1` are `_null_block`).
   - **On the next turn on D (`vllm/v1/core/kv_cache_coordinator.py:1131-1200`):** `HybridKVCacheCoordinator.find_longest_cache_hit` intersects hits across `FullAttention` and `Mamba`. Because `MambaManager` has 0 cached blocks for that prefix on D, the combined hit is reduced to `0`, forcing D to recompute the entire prompt locally on the Decode GPUs (e.g., `2a9654314a2beb turn=3`: **1,945 ms** vs **762 ms** under `always-disagg`; `t_001_d7c3d5d2 turn=3`: **1,272 ms** vs **723 ms** under `always-disagg`).
3. **Why `always-disagg` transfers 100% of FullAttention blocks on every turn instead of reusing D's local FullAttention cache (`MultiConnector` bug):**
   - `NixlBaseConnector` sets `supports_divergent_local_hybrid_hits = True` (`nixl/connector.py:81-82`). When D uses `NixlConnector` alone, `scheduler._get_local_prefix_cache_hit()` (`scheduler.py:533`) calls `kv_cache_manager.get_computed_blocks_for_connector()` (`kv_cache_manager.py:322-369`), which returns D's local `FullAttention` prefix hit even when D's `Mamba` hit is `0`. D then reuses its local FullAttention prefix blocks and only pulls the new suffix FullAttention blocks + 1 Mamba state block over NIXL.
   - However, because our deployment wraps `NixlConnector` + `OffloadingConnector` inside `MultiConnector`, `MultiConnector.supports_divergent_local_hybrid_hits` (`vllm/distributed/kv_transfer/kv_connector/v1/multi_connector.py:214-218`) evaluates `all(c.supports_divergent_local_hybrid_hits for c in self._connectors)`. Since `OffloadingConnector` inherits `False` from `KVConnectorBase_V1`, `all([True, False])` evaluates to `False`, disabling `get_computed_blocks_for_connector()` on D and forcing D to report `0` local hits and pull all FullAttention blocks over NIXL on every turn (~220 ms extra NIXL transfer on turns 4 and 5 of `t_001_d7c3d5d2`).

## Next steps

1. Benchmark against step 26/30's aggregated TP=4 servers at c = 32, 48, 64 (same 8 GPUs: two aggregated servers against 1P1D), with `prefix-based-pd-decider` and `bidirectional_kv_xfer: false`.
2. P/D-aware llm-d-thunder-agent-simplified: v1.0.0's plugin enters prefill pods in its ledger and their empty room admits new sessions (`saturation.go`, `fairness.go`); the fix skips `llm-d.ai/role=prefill` endpoints.

## Notes

- A throwaway curl pod in step 2 of the smoke script could not resolve the EPP Service name (DNS on that pod); `run-point.sh`'s own completion check through the EPP succeeded a minute later.
- With one endpoint per role, v1.0.0 still injects the utilization detector as a filter into both profiles; its fail-open fallback makes it a no-op here.
- The servers and the EPP are left up on `5qjv` for the follow-ups.
