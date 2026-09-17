# Cluster changes made during this verification work

Log of every change to shared cluster state, so it can be audited or reverted.

## 2026-09-16: enabled per-request cache metrics on vLLM

**Change**: added `--enable-prompt-tokens-details` to the `program-aware-vllm-decode` deployment in `llm-d-program-aware-scheduling`.

```
kubectl patch deploy program-aware-vllm-decode -n llm-d-program-aware-scheduling --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--enable-prompt-tokens-details"}]'
```

**Why**: vLLM defaults this to False (`vllm/entrypoints/openai/cli_args.py:132`, v0.28.0), so `usage` carried no `prompt_tokens_details` and the weka A/B (step 07) could not compute a per-request cache-hit ratio - its intended primary metric. See `LESSONS.md` section 3.

**Effect**: rolled all 4 replicas (strategy `Recreate`; deployment revision 2 -> 3). Prefix caches were cold afterwards. No other workload runs against this deployment (`llm-d-bench` is a separate stack).

**Verified** on `program-aware-vllm-decode-9c9b54cb6-f9qsh` with two identical-prefix requests:

```
1st: prompt_tokens 1210, prompt_tokens_details {cached_tokens: 0,    created_cache_tokens: 1200}
2nd: prompt_tokens 1210, prompt_tokens_details {cached_tokens: 1200, created_cache_tokens: 0}
```

**Backup / revert**: pre-change deployment YAML saved at `/tmp/vllm-deploy-backup-20260916-080101.yaml` (note: `/tmp`, so copy it somewhere durable if the revert matters). To revert:

```
kubectl patch deploy program-aware-vllm-decode -n llm-d-program-aware-scheduling --type=json \
  -p '[{"op":"remove","path":"/spec/template/spec/containers/0/args/8"}]'   # index of the flag
```
or `kubectl rollout undo deploy/program-aware-vllm-decode -n llm-d-program-aware-scheduling`.

**Post-change pod topology** (relevant for lane assignment; spot nodes so expect churn):

| pod | node | IP |
|---|---|---|
| program-aware-vllm-decode-9c9b54cb6-f9qsh | ...-thfk | 10.100.3.12 |
| program-aware-vllm-decode-9c9b54cb6-gkzmr | ...-6j7g | 10.100.15.21 |
| program-aware-vllm-decode-9c9b54cb6-kccxc | ...-6j7g | 10.100.15.20 |
| program-aware-vllm-decode-9c9b54cb6-mngw2 | ...-pskw | 10.100.2.6 |

Only 3 distinct nodes now (two pods share ...-6j7g), so a 3-lane parallel sweep still works, but the two pods on 6j7g share a node's CPU/network - avoid putting a comparison pair across those two.

## Resources created and already removed

- `thunderagent-ab*` routers and `weka-bench-*` / `thunderagent-*-bench` Jobs: created and deleted per run by the drivers; none left running.
- ConfigMaps still present (small, reusable): `thunderagent-launcher`, `thunderagent-bench-script`, `weka-bench-scripts`, `weka-bench-config-*`.

## Resources intentionally left running

- `thunderagent-original` deployment + `thunderagent-router` service (step 02): the reference router, idle.
- `thunderagent-vllm-backends` headless service (step 02).
- The pre-existing `program-aware-scheduling-epp` (llm-d EPP) was never touched.
