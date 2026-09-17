# Lessons learned: verifying ThunderAgent on a live cluster

Running record of what bit us and what to always do. Written 2026-09-16 after steps 01-07. Read this before designing the next run.

## 1. Metrics you MUST record (and why)

The single biggest recurring failure is discovering, after a multi-hour run, that the one number needed to judge the result was never collected. Record all of these, every run, at 2s resolution.

### Pod-side, scraped DIRECTLY from the vLLM pod `/metrics` (not via any router)

| metric | why it is load-bearing |
|---|---|
| `vllm:kv_cache_usage_perc` | Saturation evidence, but see the correction below - it is the SECONDARY signal, not the primary one. Step 07's null result was interpretable partly because KV peaked at only 46-61%. |
| `vllm:prefix_cache_queries_total` / `hits_total` | Compute the **interval hit rate from counter deltas**, never from cumulative values: one pod had 1.15B cumulative queries from earlier experiments, which would have swamped a run's own signal. This is the arm-level cache metric. |
| `vllm:num_requests_running` / `num_requests_waiting` | Distinguishes "router held the request" from "engine queued it". Under admission control, work moves from the engine queue into the router; you need both to see the transfer. |
| `vllm:num_preemptions_total` | Tells you whether contention showed up as engine preemption or as cache eviction. In all runs so far it stayed 0, which is itself the finding: pressure manifested as eviction. |

### Router-side (ThunderAgent)

| metric | why |
|---|---|
| `/health` -> `paused_count`, `reasoning_count`, `acting_count`, `programs_count` | Aggregate proof that admission control engaged at all. |
| `/programs` per program: `state` and `status` | **The pause flag lives in `state` (active/paused), NOT in `status` (reasoning/acting).** A first attempt to extract per-program pause intervals found zero because it filtered on `status`. Record both. |
| router log | Only source of per-program *event* text: `Paused program <id> (tokens=N)`, forced-resume warnings. Save it per cell BEFORE any teardown (see lesson 4). |

### Per-request (from the load generator)

| metric | why |
|---|---|
| `usage.prompt_tokens_details.cached_tokens` / `prompt_tokens` | The only per-request cache evidence, and the only thing that supports paired analysis. **Requires vLLM `--enable-prompt-tokens-details`** - see lesson 3. |
| TTFT (`computed_metrics.time_to_first_token`) | Cache hits show up directly in prefill time; the fallback when cached_tokens is missing. |
| `graph_event_id` + prompt_tokens | The **pairing keys**. Without them, truncated arms cannot be compared at all (lesson 6). |

### Correction: the primary saturation signal is hit rate, not KV utilization

`vllm:kv_cache_usage_perc` counts only blocks held by **running** requests. Blocks left behind by completed requests drop to refcount 0 and sit in the evictable free pool, so they do NOT show up in this gauge. A pod can therefore show 50% KV utilization while its cache is doing all the work. Step 07 measured KV peak 46-61% together with a 0.905 hit rate: the correct reading is "half the pool holds live requests, the rest holds cached blocks that are being hit - no pressure".

So: **baseline prefix-cache hit rate is the primary pressure signal**; KV utilization, waiting-queue depth, and preemptions are corroborating. If the baseline hit rate is high, there is no recompute to save and no scheduling policy can help, whatever KV utilization says.

### Effective concurrency must be recorded, and it is not the configured number

Record `reasoning_count` from `/health` as a time series (programs with a request pending) and report its **time-weighted mean over the window**. Two separate things go wrong otherwise, both measured in step 07 (5-minute averages):

| configured | 0 min | 10 min | 20 min | 30 min | 40 min |
|---|---|---|---|---|---|
| c=8 | 5 | 6 | 6 | 6 | 3 |
| c=24 | 14 | 11 | 10 | 7 | 4 |

1. **Effective < configured from the start.** At c=24 only ~14 sessions ever had a request in flight, because replayed sessions are closed-loop: between turns they sit in think time / tool gaps. `concurrent_sessions: N` is a pool size, not N in-flight requests.
2. **It decays when the corpus runs out.** The c=24 cell had exactly 24 traces, so all sessions started at t=0 with no replacements; as sessions finished, effective concurrency fell to 4. The time-weighted average was ~8-9, not 24. The second half of that 45-minute cell measured almost nothing.

Sizing rule, derived from measured session durations (mean 793s at c=8, 1194s at c=24; longer under load):

```
corpus_size >= c x (1 + window / mean_session_duration)   ~= 3c for a 45-min window
```

Empirical check: at c=8 the run consumed 20 sessions in 45 min (2.5x the concurrency) and the 24-trace corpus was exhausted by minute 40. Never set the corpus equal to the target concurrency - reusing traces is NOT the workaround either, because two sessions replaying the same trace share identical hash_ids and fabricate cache hits that do not exist in reality.

Note on the pause metric semantics: a program can be "paused" while having no pending work. In step 07 the paused count rose only after sessions finished, i.e. the router was pausing already-idle programs. Always cross-check paused counts against whether those programs still had requests coming, or you will over-claim that admission control was "active".

## 2. Why the background driver got killed (and the fix that saved the night)

**What happened.** The full sweep was launched as one long-lived background shell (`caffeinate -dims ./run-weka-ab.sh`). It survived ~1h, got through all three `default` cells, and was killed by the harness partway into the `tr` cells. Local polling loops, per-cell result copying, and the lane teardown all died with it.

**Root cause.** Any single long-lived local process is a single point of failure: harness restarts, laptop sleep, network drops, and session boundaries all kill it. Wall-clock for this campaign (1-5h) is far longer than the reliable lifetime of a foreground/background command.

**What saved the run.** The design rule that survives process death: **results must outlive the driver, inside the cluster.** Each bench container does `... ; touch /results/DONE; sleep 28800` with `activeDeadlineSeconds: 43200`. So when the driver died, the Jobs kept running, finished their 45-minute stages, wrote DONE, and held the results in the pod. The next morning 4 of 6 cells were recovered intact with a plain `kubectl cp`. Nothing had to be rerun for that reason.

**Rules going forward.**
1. Never make the local process the owner of the results. Cluster-side grace period (`touch DONE; sleep 8h`) + generous `activeDeadlineSeconds` is mandatory.
2. Make the driver **restartable and idempotent**: a separate collect step that can run against an already-DONE pod, so recovery is "re-run collect", not "re-run benchmark".
3. Prefer many short orchestration steps over one long one when a human/agent is available to advance them.
4. `caffeinate -dims` prevents idle sleep but does NOT survive a lid close or a harness kill. It is a nice-to-have, not the protection.
5. Log per-cell state (manifest.json) as each cell finishes, so a partially completed sweep is self-describing.

## 3. Why `--enable-prompt-tokens-details` was missing

**What happened.** The weka A/B was designed around a per-request cache-hit ratio (`cached_tokens / prompt_tokens`), and the analysis script was written to pair on it. The smoke test revealed that vLLM's `usage` contained only `prompt_tokens / completion_tokens / total_tokens` - no `prompt_tokens_details`. The primary metric was unavailable for the whole sweep; the analysis fell back to pod-counter hit rate plus paired TTFT.

**Root cause.** In vLLM, `enable_prompt_tokens_details` defaults to **False** (`vllm/entrypoints/openai/cli_args.py:132` in 0.28.0). The existing `program-aware-vllm-decode` deployment predates this work and never set it. The requirement was inherited from a prior campaign's notes, where the flag happened to be enabled, so it was assumed rather than verified. inference-perf itself handles the field correctly (it records `total_cached_tokens` as None, explicitly distinct from 0, when the server omits it) - the gap was purely server-side configuration.

**Rules going forward.**
1. **Verify the primary metric is actually produced by THIS deployment before designing an experiment around it.** One curl of a real response body would have caught it in a minute.
2. Server-side capabilities are part of the experiment config; record them in the manifest (image + full arg list), not just the client config.
3. If enabling a flag requires restarting shared infrastructure, decide that BEFORE the long run, not after.
4. Keep a fallback metric with independent provenance (here: pod counters, which needed no server change).

## 4. Artifact collection: order matters

A `kubectl logs` grab for the tr-nodecay arm in step 06 raced the deployment teardown and the log was lost (the extracted statistics had already been recorded, so no conclusions were affected, but the raw evidence was gone). Since then: **collect router logs, prober logs, and reports into per-cell files BEFORE deleting any Job/Deployment**, and never write two cells' logs to the same filename.

## 5. Spot nodes will take a pod mid-run

The c16 lane's vLLM pod was preempted overnight; its `default` arm had completed but its `tr` arm never ran, and the pair could no longer be compared on identical hardware. Rules: record the target pod name and IP in every cell manifest; check the pod is the same one at collection time; if it changed, rerun the whole pair (a cross-pod pair violates the fairness design). Archive the orphaned data rather than deleting it (`default-c16-preempted-g8zsd`).

## 6. Comparing timeout-truncated arms: always pair

Aggregate metrics from arms truncated by a fixed time window are unreliable: the arms progress at different speeds, so the window captures different request populations. This produced phantom wins and losses in an earlier campaign. Because trace replay is deterministic, entries can be paired across arms on (`graph_event_id`, `prompt_tokens` within 1%) and judged as paired deltas. Report unpaired tails separately as window progress. Fix the decision rule (what counts as a win) BEFORE looking at the data.

## 7. Calibrate the pressure regime before spending hours

Both the synthetic step-04 run and the weka step-07 run produced null results for the same reason: **the pool was not saturated**, so admission control had nothing to do. Step 07 burned ~2h of cluster time to learn that 24 traces at c8/c24 leave KV at 46-61% and a baseline hit rate of 0.905.

Rule: run a **10-minute calibration cell first** and check exactly two numbers - peak KV utilization and baseline prefix-cache hit rate. If baseline hit rate is already >0.85 or KV peak is <0.8, the workload cannot demonstrate anything about admission control; change the regime (more sessions, more traces, or a smaller KV pool) before committing to the full sweep.

Corollary on sizing: the corpus caps concurrency. The 60MB weka slice yields 39 traces, 24 after filtering, so "c24" and "c48" would be the same experiment. Check corpus size against intended concurrency first, using the `>= 3c` rule above.

## 7b. Keep corpus filters minimal, and check what each rule actually costs

The first weka filter had two content rules: `turns <= 400` AND `max_input_tokens <= 245000`. Measured on the 39-trace sample, the token rule alone dropped 13 traces (33%) while the turns rule dropped 4 (10%).

The token rule was **unnecessary**: it existed to prevent context overflow, sized against a remembered "2-3% re-tokenization drift" from a different campaign (SGLang, different chat template). The measured drift here was **0.24%** (a trace recorded at <=245,000 counted 245,592 server-side), the dataset is already 256k-capped by construction, and the served window is 262,144. Zero 400s occurred. So a third of the corpus was thrown away for nothing - and since corpus size is the binding constraint on sustainable concurrency (lesson above), that waste directly weakened the experiment.

Rules:
1. Prefer ONE content rule with a concrete reason. Here: `turns <= 400`, justified by datagen cost (the graph for every trace is compiled up front; the dataset contains a 10,393-turn trace), keeping 90% of the corpus.
2. Quantify each rule's cost before adopting it - "how many traces does this drop?" is one line of code against the manifest.
3. Do not inherit thresholds from another environment's notes; measure the quantity (here, tokenization drift) in THIS deployment.
4. Reproducibility comes less from simple rules than from a **recorded decision per item**: the manifest stores the download sha256 plus turns / max_in / keep for every line, so anyone can audit or re-derive the corpus even if they disagree with the rule.

## 8. Upstream ThunderAgent gotchas found by running it

- The `thunderagent` CLI **silently ignores all its flags** (the router is constructed at package import with defaults, before `main()` applies the config). Launch via the embedding API instead (`02-deploy/launcher.py`).
- `GET /v1/models` 404s (proxies to `/models`).
- Capacity is only freed by an explicit `POST /programs/release`; there is no TTL. With realistic clients (which never signal completion), `--use-acting-token-decay` is REQUIRED - without it held programs serve the full 1800s forced-resume timeout and the system is 8x slower than a plain proxy.
- Program identity can come from the `X-Session-ID` header, which is what makes drop-in integration with inference-perf possible with zero code changes on either side.

## 9. Reporting discipline

- inference-perf per-request reports must set `per_request_fields` to drop `request` / `response` / `response_chunks`, or a run writes ~1MB per request (a past campaign silently accumulated 65GB).
- State null results plainly, with the saturation evidence that explains them. A null result with KV at 50% is a statement about the workload, not about the mechanism.
- Repeat before believing a gap: three trials of the step-06 A/B showed the baseline is deterministic (0.1% spread) while the tr arm varies ~9%, which turned a single-point "1.45x" claim into an honest "1.3-1.45x".
