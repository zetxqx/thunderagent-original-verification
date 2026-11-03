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

## 2026-09-19/20: step 13 origin arm left the main release on thunder-agent-v4 with origin-only

Seven more per-cell upgrades (revisions 42 to 48) with `--set router.epp.image.tag=thunder-agent-v4`. The last cell was the `epp-thunder-origin-c192` rerun, so revision 48 runs image `thunder-agent-v4` with `thunder-origin-plugins.yaml` (`resumePlacement: origin-only`) and the 2400 s envoy `message_timeout`.

## 2026-09-20: step 13 replicates left the main release on thunder-agent-v4 with the most-room config

Nine more per-cell upgrades (revisions 49 to 57, including the voided and rerun c=128 replicate). The last cell was `epp-thunder-c128-r3`, so revision 57 runs image `thunder-agent-v4` with `thunder-plugins.yaml` (`resumePlacement` default, most-room) and the 2400 s envoy `message_timeout`.

## 2026-09-20 midday: two baseline cells for session-level metrics

Revisions 58 and 59 (`epp-baseline-c96-r2`, `epp-baseline-c128-r2`). The release now runs `thunder-agent-v4` with `baseline-plugins.yaml` and the 2400 s envoy `message_timeout`.

## 2026-09-20 evening: three 90-minute cells at c=128

Revisions 60 to 62 (`epp-thunder-origin-c128-w90`, `epp-baseline-c128-w90`, `epp-thunder-c128-w90`). The release now runs `thunder-agent-v4` with `thunder-plugins.yaml` (most-room) and the 2400 s envoy `message_timeout`.

## 2026-09-21: Option B cells (thunder-agent-v5)

Five per-cell upgrades for the u15 and u15-f25 arms. The last cell was `epp-thunder-origin-u15-c128-w90`, so the release now runs image `thunder-agent-v5` with `thunder-origin-u15-plugins.yaml` (`resumePlacement: origin-only`, `urgentWaitMs: 15000`) and the 2400 s envoy `message_timeout`. The planned u15-f25 90-minute cell was not run.

## 2026-09-21 midday: age-only (v6) and wait-cap (v7) cells

Revisions 68 and 69. The release now runs image `thunder-agent-v7` with `thunder-origin-w8-plugins.yaml` (`resumePlacement: origin-only`, `originWaitMaxMs: 8000`) and the 2400 s envoy `message_timeout`.

## 2026-09-21 afternoon: two more wait-cap cells

Revisions 70 and 71 (`epp-thunder-origin-w8-c128-r3`, `-r4`). The release still runs `thunder-agent-v7` with `thunder-origin-w8-plugins.yaml`.

## 2026-09-21 evening: lanes recreated for step 14

`10-llm-d-router-replicates/deploy-lanes.sh turnprio-005-ttl60` with `EPP_IMAGE_TAG=upstream-main-dc6538a1` recreated `thunder-lane-a/b/c` (pod labels, `lane-rbac.yaml`). They are still running after the step 14 cells; remove with `teardown-lanes.sh`.

## 2026-09-22: step 14 lanes removed

`teardown-lanes.sh` removed `thunder-lane-a/b/c` (deployments, services, configmaps, service accounts, roles), the `thunder-lane` pod labels and the `thunder-lane-auth-delegator` cluster role binding. Note: the first attempt ran against another cluster because the laptop's current kubectl context had changed; it deleted nothing there. The main release, the four vLLM pods and `thunderagent-original` are unchanged.

## 2026-10-10: registry read for cluster a4-pr (step 25)

**Change**: `roles/artifactregistry.reader` on repo `bobinference` (project `bobzetian-gke-dev`, us-central1) for `455207029971-compute@developer.gserviceaccount.com`, the default compute service account of project `supercomputer-testing`. Node pool `pool-1` of cluster `a4-pr` runs as this account, and the AgentX client Job runs there.

**Effect**: any VM in `supercomputer-testing` that uses the default compute account can pull images from `bobinference` (read only, this repo only).

**Revert**:

```
gcloud artifacts repositories remove-iam-policy-binding bobinference --location us-central1 --project bobzetian-gke-dev \
  --member="serviceAccount:455207029971-compute@developer.gserviceaccount.com" --role="roles/artifactregistry.reader"
```

Also on `a4-pr`: namespace `bobzetian-llmd` created; it holds the step 25 B200 vLLM Deployment, Service, ResourceClaimTemplate and PVC `agentx-data`.

## 2026-10-10 afternoon: thunder EPP on a4-pr (step 25)

In namespace `bobzetian-llmd` on `a4-pr`: Deployment, Service, ServiceAccount and two ConfigMaps `agentx-epp-a-epp*` (`25-glm52-tp8-offload/b200/lane-epp-a.yaml`, no RBAC objects), ServiceAccount `thunderagent-metrics-reader` (no roles). The vLLM Deployment `glm52-tp8` got `progressDeadlineSeconds: 3600`. Skill script changes: `run-point.sh` `MODE=direct` and `SERVER_ENV` (also in pool mode), `render-lane-epp.sh` `EXTRA_VALUES` and the `-produces` default image.

## 2026-10-28: step 26 part 2 (Qwen3.5 without CPU offload) on a4-pr

In namespace `bobzetian-llmd`: scaled to 0 (all idle, their steps done) step 41's `glm52-tp8-prefill` (`gw0s`), `glm52-dep8-decode` (`p3mf`), `pd-dep8-proxy`, EPP `agentx-epp-gt8d-epp`; step 32's `sglang-qwen35-a` (`13z6`), `sglang-qwen35-b` (was Pending), EPP `agentx-epp-sglang-epp`; and the KV delta compression test `vllm-delta-qwen35` (`13z6`). Their manifests before the change were saved locally (`26-qwen35-tp4-thunder/b200/results/nooff-saved-before/`, not committed: it holds the unpublished KV delta patch). Created Deployments and Services `qwen35-nooff-{a..f}` (`26-qwen35-tp4-thunder/b200/vllm-qwen35-nooff-*.yaml`; a, b on `13z6`, c, d on `gw0s`, e, f on `p3mf`) and the thunder lane EPPs `agentx-epp-n{b,d,f}-epp`.

**Revert**: `kubectl delete -f 26-qwen35-tp4-thunder/b200/vllm-qwen35-nooff-<x>.yaml` for each server and `kubectl delete -f` the lane EPP files, then scale the eight Deployments above back to their saved replica counts (1 each; `sglang-qwen35-b` was 1 but Pending).

2026-10-28 05:54 UTC: step 26 part 2 done; `qwen35-nooff-{a..f}` and `agentx-epp-n{b,d,f}-epp` scaled to 0 (objects kept). The eight Deployments scaled to 0 at the start (step 41 GLM, step 32 SGLang, `vllm-delta-qwen35`) are still at 0; restore them with the revert above when needed.

## 2026-10-28 23:28 UTC: step 26 part 2, thunder at 80% capacity (utilThreshold 0.8)

In namespace `bobzetian-llmd`: `qwen35-nooff-{a..e}` scaled back to 1 with new MAX_NUM_SEQS and nodes (`13z6`, `gw0s` and `p3mf` each had one GPU taken by another team, so they hold one server each: a on `13z6`, c on `gw0s`, e on `p3mf`; b and d moved to `d213`). New lane EPPs `agentx-epp-t{a..e}-epp` (`26-qwen35-tp4-thunder/b200/lane-epp-t*.yaml`, utilThreshold 0.8). `qwen35-nooff-f` stays at 0.

**Revert**: scale `qwen35-nooff-{a..e}` and `agentx-epp-t{a..e}-epp` to 0 (or `kubectl delete -f` their files).

23:49 UTC: b and d were evicted on `d213` (node low on ephemeral storage during the checkpoint download) and scaled back to 0; c=32 and c=24 run as second points on c (`gw0s`) and e (`p3mf`) instead. Lane EPPs used: `agentx-epp-t{a,c,e}-epp`.

2026-10-29 02:27 UTC: 80% arm done; `qwen35-nooff-{a,c,e}` and `agentx-epp-t{a,c,e}-epp` scaled to 0.

## 2026-10-29 07:19 UTC: step 26 part 2, knee points (c = 28, 36, 40, 44)

In namespace `bobzetian-llmd`: created Deployments and Services `qwen35-nooff-{g..r}` (`26-qwen35-tp4-thunder/b200/vllm-qwen35-nooff-{g..r}.yaml`, one TP=4 server each): g, h on `p3mf`; i on `13z6`; j on `gw0s`; k, l on `1g50`; m on `9r8s`; n on `dkvh`; o on `3v40`; p on `mzl3`; q on `q2b8`; r on `xfxp`. Thunder lane EPPs `agentx-epp-k{h,i,k,l,n,o,q,r}-epp` with lowered resource requests (250m / 1Gi per container; limits unchanged) and PVCs `agentx-data-k*`. `d213` skipped (1.2 TB free disk, at the eviction threshold).

**Revert**: scale `qwen35-nooff-{g..r}` and `agentx-epp-k*-epp` to 0 (or `kubectl delete -f` their files).

09:12 UTC: knee points done; `qwen35-nooff-{g..r}` and the eight `agentx-epp-k*-epp` scaled to 0.

## 2026-10-29 16:55 UTC: step 26 part 2, gate capacity sweep (utilThreshold 0.7 and 0.6)

In namespace `bobzetian-llmd`: created Deployments and Services `qwen35-nooff-u07c{24,28,32,36,40}` and `qwen35-nooff-u06c{24,28,32,36,40}` (`26-qwen35-tp4-thunder/b200/vllm-qwen35-nooff-u0*.yaml`): c=24 on `13z6`, c=28 on `gw0s`, c=32 on `p3mf`, c=36 on `1g50`, c=40 on `3v40`, two servers per node. Lane EPPs `agentx-epp-u0{7,6}c*-epp` (lowered requests, as for the knee points) and PVCs `agentx-data-u0*`.

**Revert**: scale `qwen35-nooff-u0*` and `agentx-epp-u0*-epp` to 0 (or `kubectl delete -f` their files).

18:39 UTC: sweep done; `qwen35-nooff-u0*` and `agentx-epp-u0*-epp` scaled to 0.

## 2026-11-02 18:43 UTC: step-time investigation (CPU offload copies vs engine step), experiments 1 to 3

Why the GLM-5.2 no-router step (25.6 ms at c=32) is slower than thunder's (18.7 ms): H2D contention microbenchmark, then py-spy and vLLM's torch profiler on step 25's server under no-router c=32. Namespace `bobzetian-llmd`, no Kueue (user's choice). Manifests are kept outside the repo (Jetski scratch `exp1/job.yaml`, `exp23/vllm-glm52-tp8-profile.yaml`).

- Created ResourceClaimTemplate `bobzetian-1gpu`, ConfigMap `h2d-contention-script` and Job `job-bobzetian-h2d-contention` (1 B200 on `t3gv`, `vllm/vllm-openai:v0.31.0`).
- Created Deployment `glm52-tp8` (it had been deleted; Service `glm52-tp8` and ResourceClaimTemplate `glm52-tp8-gpu` already existed) from `25-glm52-tp8-offload/b200/vllm.yaml` on `xfxp` (the only node with 8 free GPUs; `t3gv` and `qdcj` had GPUs claimed by other teams), with `MAX_NUM_SEQS=64`, `--profiler-config` (torch, `/profiles`, `max_iterations` 600), `SYS_PTRACE` and an emptyDir `/profiles`.

**Revert**: `kubectl -n bobzetian-llmd delete job job-bobzetian-h2d-contention; kubectl -n bobzetian-llmd delete cm h2d-contention-script; kubectl -n bobzetian-llmd delete resourceclaimtemplate bobzetian-1gpu; kubectl -n bobzetian-llmd scale deploy glm52-tp8 --replicas=0`.

2026-11-02 20:21 UTC: experiments done. `glm52-tp8` scaled to 0 (object kept, on `xfxp`); Jobs `job-bobzetian-h2d-contention`, `job-bobzetian-cpu-block` and ConfigMaps `h2d-contention-script`, `cpu-block-script` deleted. ResourceClaimTemplate `bobzetian-1gpu` kept (unused). One extra no-router c=32 point (`stepprof-direct`, 30 min, KV tiers reset first) ran on `glm52-tp8` and used PVC `agentx-data`.

## 2026-11-02 21:25 UTC: vLLM fix test (bounded CPU-offload load submission)

In namespace `bobzetian-llmd`: ConfigMap `offload-fix-patch` (branch diffs and a v0.31.0 `gpu_worker.py` backport); Job `job-bobzetian-offload-unittest` (1 B200, unit tests of the vLLM branch); Deployment `glm52-tp8` moved to `zxhd` (the `xfxp` node was taken by another team; `zxhd` had no HF cache, so the checkpoint downloads there) and patched at start-up with the backport (`VLLM_KV_OFFLOAD_MAX_LOAD_SUBMIT_DESCRIPTORS=8192`), for one no-router c=32 point (`stepfix-direct`).

**Revert**: `kubectl -n bobzetian-llmd scale deploy glm52-tp8 --replicas=0; kubectl -n bobzetian-llmd delete job job-bobzetian-offload-unittest; kubectl -n bobzetian-llmd delete cm offload-fix-patch`.

Also created in `bobzetian-llmd`: Jobs `job-bobzetian-offload-conn-{base,fix}` (1 B200 each, connector unit tests with and without the change; manifests in Jetski scratch `expfix/conn-*-job.yaml`). Client Job `agentx-c32-stepfix-direct` used PVC `agentx-data`.

2026-11-02 22:42 UTC: the cluster admins added the ValidatingAdmissionPolicy `require-queue` (go/cmcs-capacity-management#queues). Users can no longer create Pods, Jobs or Deployments in `bobzetian-llmd`; they must go to a queue namespace (`default`, `priority`, `automation`, `long-running`). The `stepfix-direct` results fetch Pod was denied, so its `aiperf_artifacts` stay on PVC `agentx-data` (only `bench-stdout.log` and `meta/` are local).

2026-11-02 22:55 UTC: `glm52-tp8` scaled to 0 (object kept, on `zxhd`). In namespace `default` (Kueue LocalQueue `default`, no queue label): ResourceClaimTemplate `bobzetian-1gpu`, ConfigMap `bobzetian-offload-fix-patch`, Job `job-bobzetian-offload-unittest2` (1 B200, re-run of the branch's unit test).

**Revert**: `kubectl -n bobzetian-llmd delete job job-bobzetian-offload-unittest job-bobzetian-offload-conn-base job-bobzetian-offload-conn-fix agentx-c32-stepfix-direct; kubectl -n bobzetian-llmd delete cm offload-fix-patch; kubectl -n default delete job job-bobzetian-offload-unittest2; kubectl -n default delete cm bobzetian-offload-fix-patch; kubectl -n default delete resourceclaimtemplate bobzetian-1gpu`.

2026-11-02 23:03 UTC: Job `job-bobzetian-offload-unittest2`, ConfigMap `bobzetian-offload-fix-patch` and ResourceClaimTemplate `bobzetian-1gpu` deleted from `default`. Still left in `bobzetian-llmd`: the Jobs and ConfigMap listed above (no Pods running, no GPUs held) and `glm52-tp8` at 0 replicas.

## 2026-11-02 23:54 UTC: vLLM fix sweep (no-router + fix vs thunder + fix at c = 24, 32, 48)

In namespace `long-running` (Kueue LocalQueue `default` -> ClusterQueue `gpu-longrun`, 480 min cap; user is in `cmcs-a4-longrun-users@twosync.google.com`):

- ServiceAccounts `thunderagent-metrics-reader`, `agentx-epp-b-epp` (`default` also patched with `imagePullSecrets: [artifact-registry-secret]`); Secret `artifact-registry-secret`; ConfigMap `bobzetian-offload-fix-patch`; ResourceClaimTemplate `glm52-tp8-gpu`; PVCs `agentx-data`, `agentx-data-b` (200 GiB `standard-rwo` each).
- Deployments and Services `glm52-tp8` (on `zxhd`, no-router + fix arm) and `glm52-tp8-b` (on `xfxp`, thunder-gpu-l10 + fix arm), both patched at start-up with `gpu_worker_v031_bounded.py` (`VLLM_KV_OFFLOAD_MAX_LOAD_SUBMIT_DESCRIPTORS=8192`, `MAX_NUM_SEQS=64`, no profiler).
- Deployment, Service and ConfigMaps `agentx-epp-b-{epp,envoy}` (`scratch/expfix/lane-epp-b-lr.yaml`, `thunder-gpu-l10-plugins.yaml`, pointing at `glm52-tp8-b` ClusterIP `10.0.40.172:8000`; `nodeAffinity` to `pool-1` removed because Kueue's `a4-dra` flavor injects `nodeSelector: cloud.google.com/gke-accelerator=nvidia-b200`).
- Driver `scratch/expfix/run_sweep.sh` running c = 24, 32, 48 (30 min each, `RESET=1`) on both arms in parallel (`CLIENT_NODE_LABEL=cloud.google.com/gke-accelerator`, `CLIENT_POOL=nvidia-b200`).

**Revert**: `kubectl -n long-running scale deploy glm52-tp8 glm52-tp8-b agentx-epp-b-epp --replicas=0` (or `kubectl -n long-running delete deploy glm52-tp8 glm52-tp8-b agentx-epp-b-epp svc/glm52-tp8 svc/glm52-tp8-b svc/agentx-epp-b-epp cm/bobzetian-offload-fix-patch cm/agentx-epp-b-epp cm/agentx-epp-b-envoy cm/agentic-bench-scripts sa/thunderagent-metrics-reader sa/agentx-epp-b-epp secret/artifact-registry-secret resourceclaimtemplate/glm52-tp8-gpu pvc/agentx-data pvc/agentx-data-b`).

2026-11-03 03:01 UTC: all 6 points (`fix-direct` and `fix-thunder` at c = 24, 32, 48) finished and their artifacts were fetched to Jetski scratch `expfix/results/{fix-direct,fix-thunder}/c{24,32,48}/`. In `long-running`: `glm52-tp8`, `glm52-tp8-b`, and `agentx-epp-b-epp` scaled to 0; all 6 client Jobs and both PVCs (`agentx-data`, `agentx-data-b`, which had been switched from `standard-rwo` to `a4-hyperdisk` because B200 nodes cannot attach `pd-balanced`) deleted. No GPUs or disks remain claimed in `long-running`.
