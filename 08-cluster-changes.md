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

## 2026-09-17: EPP upgraded to the rewritten thunder-agent plugin (step 09)

**Change**: Helm release `program-aware-scheduling` upgraded from revision 10 to 11: EPP image `llm-d-router-endpoint-picker:thunder-agent-v2` -> `thunder-agent-v3` (built from the working tree recorded in `09-llm-d-router-smoke/image-source.md`) and plugin config replaced by `09-llm-d-router-smoke/thunder-plugins.yaml` (upstream tr-decay defaults, no utilization filter, request TTL 0). The chart used is `llm-d-router/config/charts/llm-d-router-standalone` from that checkout, so the rendered envoy config map is that chart's default rather than the newer one revision 10 carried; the EPP and envoy came up and served traffic.

**Why**: verify the port on the live cluster (step 09) before running the step 08 protocol through it.

**Revert**: `helm rollback program-aware-scheduling 10 -n llm-d-program-aware-scheduling` (revision 10 is intact; image `thunder-agent-v2` still exists in the registry).

**Also created**: ServiceAccount `thunderagent-metrics-reader` (namespace `llm-d-program-aware-scheduling`), ClusterRole and ClusterRoleBinding of the same name, granting GET on `/metrics` and `/debug/plugins/state` for the EPP's kube-rbac-protected metrics port. Revert: `kubectl delete -f 09-llm-d-router-smoke/metrics-reader-rbac.yaml`.

## 2026-09-17: three lane EPPs for step 10

**Change**: pods `program-aware-vllm-decode-9c9b54cb6-{f9qsh,gkzmr,mngw2}` labeled `thunder-lane=a|b|c`; three EPP deployments `thunder-lane-{a,b,c}-epp` (each with its envoy sidecar, service, service account, namespaced role, config maps `thunder-lane-X-epp` and `thunder-lane-X-envoy`) applied from rendered manifests under `10-llm-d-router-replicates/results/`; ClusterRoleBinding `thunder-lane-auth-delegator` binding the three lane service accounts to `system:auth-delegator`. Each lane EPP watches only its labeled pod (standalone mode, `--endpoint-selector`). Nothing else changed: the InferencePool, the main EPP release (revision 11) and the vLLM deployment are untouched.

**Why**: one EPP per pod reproduces step 08's one-router-per-pod lanes for the step 10 replicates.

**Revert**: `10-llm-d-router-replicates/teardown-lanes.sh` (deletes the three manifests, the pod labels and the ClusterRoleBinding). Status: the three lane EPPs, the pod labels and the ClusterRoleBinding were removed on 2026-09-18 with `teardown-lanes.sh` after step 12.

## 2026-09-18: main EPP release switched per arm for step 12

**Change**: Helm release `program-aware-scheduling` is upgraded by `12-llm-d-router-pool/run-pool.sh` before every cell (revisions 12 and up): values `12-llm-d-router-pool/main-values.yaml` (the step 09 user values plus the envoy ext_proc `message_timeout` raised to 2400 s) and the arm's plugin config (`baseline-`, `affinity-` or `thunder-plugins.yaml`), followed by a rollout restart. Image stays `thunder-agent-v3`. Prefix caches of all four pods are reset before each cell.

**Revert**: `helm upgrade program-aware-scheduling <chart> -n llm-d-program-aware-scheduling -f 09-llm-d-router-smoke/results/values-rev10-user-supplied.yaml --set router.epp.image.tag=thunder-agent-v3 --set-file router.epp.pluginsCustomConfig.thunder-plugins\.yaml=09-llm-d-router-smoke/thunder-plugins.yaml` restores the step 09 state (revision 11), or `helm rollback program-aware-scheduling 11`. **Done 2026-09-18 after step 12** (see the revision recorded in `12-llm-d-router-pool/results/revert-output.txt`).

## 2026-09-18: unrelated stacks removed to free CPU for the load generator

**Change** (at the user's request, not part of the verification): Helm releases `bench` (namespace `llm-d-bench`, EPP plus `bench-vllm` deployment, 3 pods on the L4 pool) and `text-to-video` (namespace `llm-d-diffusion-t2v`, EPP plus a scaled-to-zero decode deployment) were uninstalled and their model-server deployments deleted. The two namespaces themselves were left in place (empty apart from config maps and secrets); deleting them was not permitted from this session. This frees 14 cores on `default-pool-40bcbd6e-02b4` and three L4 GPUs.

**Revert**: not applicable; these were separate experiments.

## Resources created and already removed

- `thunderagent-ab*` routers and `weka-bench-*` / `thunderagent-*-bench` Jobs: created and deleted per run by the drivers; none left running.
- ConfigMaps still present (small, reusable): `thunderagent-launcher`, `thunderagent-bench-script`, `weka-bench-scripts`, `weka-bench-config-*`.

## Resources intentionally left running

- `thunderagent-original` deployment + `thunderagent-router` service (step 02): the reference router, idle.
- `thunderagent-vllm-backends` headless service (step 02).
- The pre-existing `program-aware-scheduling-epp` (llm-d EPP) was never touched.

## 2026-09-18 evening: step 13 sweep left the main release on the baseline config

`12-llm-d-router-pool/run-pool.sh` upgraded `program-aware-scheduling` once per cell (revisions 24 to 35). The last cell was `epp-baseline-c338`, so revision 35 carries `baseline-plugins.yaml` and the 2400 s envoy `message_timeout`. Revert to the step 09 thunder state with `09-llm-d-router-smoke/deploy.sh` if single-EPP thunder work resumes.

## 2026-09-19: step 13 extension (c = 16, 32, 64) left the main release on the thunder config

Six more per-cell upgrades (revisions 36 to 41). The last cell was `epp-thunder-c64`, so revision 41 carries `thunder-plugins.yaml` with the 2400 s envoy `message_timeout` (step 09's state differs only in the 1000 s timeout).
