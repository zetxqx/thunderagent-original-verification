# Step 31: minimal P/D (1 prefill + 1 decode) for Qwen3.5-397B-A17B-FP8 with CPU offload on both, 8x B200

Status: two smoke tests done (2026-10-21). The P/D path works end to end; decode reuses the KV it computes but not the KV it receives over NIXL (second smoke); no benchmark yet.

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

The pattern in every conversation: the turn after a remote-prefill turn finds nothing in D's prefix cache and prefills its whole prompt on D (165k tokens: TTFT 5.7 s; 192k: 10.1 s); from the next turn on, D hits the KV it computed itself. So **D reuses the KV it computes, not the KV it receives over NIXL**. Candidate causes, not yet separated: for this hybrid model a prefix hit also needs the GDN state at the matched block boundary (vLLM `mamba_cache_mode` `align`), which a NIXL transfer of the final state does not provide; or `bidirectional_kv_xfer` keeps received blocks for P to read back (TTL 480 s) outside D's prefix cache.

## Next steps

1. Separate the two candidate causes of the decode-side miss after each remote prefill: rerun with `bidirectional_kv_xfer` off (server restart), and read vLLM v0.31's NIXL scheduler for how received blocks enter D's prefix cache for hybrid (Mamba/GDN) groups.
2. Benchmark against step 26/30's aggregated TP=4 servers at c = 32, 48, 64 (same 8 GPUs: two aggregated servers against 1P1D), with `prefix-based-pd-decider`.
3. P/D-aware llm-d-thunder-agent-simplified: v1.0.0's plugin enters prefill pods in its ledger and their empty room admits new sessions (`saturation.go`, `fairness.go`); the fix skips `llm-d.ai/role=prefill` endpoints. The capacity then follows from step 1.

## Notes

- A throwaway curl pod in step 2 of the smoke script could not resolve the EPP Service name (DNS on that pod); `run-point.sh`'s own completion check through the EPP succeeded a minute later.
- With one endpoint per role, v1.0.0 still injects the utilization detector as a filter into both profiles; its fail-open fallback makes it a no-op here.
- The servers and the EPP are left up on `5qjv` for the follow-ups.
