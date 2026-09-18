# Step 09: smoke test of the llm-d-router port of ThunderAgent

Goal: put the rewritten `thunder-agent` EPP plugin (upstream tr-decay semantics, see `../../llm-d-thunderagent-how-it-works.md`) on the live cluster and verify, with simple checks, that the running binary is the new build, that it loaded the faithful config, and that its accounting and stickiness behave on real vLLM pods. No load, no holds: those come in a later step.

## What runs

- Same namespace and the same 4 vLLM pods as steps 01 to 08 (`llm-d-program-aware-scheduling`).
- The EPP is the Helm release `program-aware-scheduling` (chart `llm-d-router/config/charts/llm-d-router-standalone`). Before this step it ran image tag `thunder-agent-v2` with a scaled-down smoke config of the old plugin design (revision 10).
- Traffic enters through the EPP pod's envoy sidecar (service port 80), which calls the EPP over ext_proc and forwards to the picked vLLM pod.

## Files

- `image-source.md`: the exact llm-d-router working tree the image was built from (HEAD plus an uncommitted diff, identified by its sha256).
- `thunder-plugins.yaml`: the plugin config, identical to `llm-d-router/deploy/config/thunderagent-config.yaml` except the capacity fallback is the real per-pod value from step 03.
- `deploy.sh`: builds the chart dependency and upgrades the release in place with the new image tag and this config, passing the previous revision's user-supplied values as a file (saved under `results/`). Not `--reuse-values`: in Helm 3 that flag also swaps in the old chart's default values, and this release was last deployed from a newer chart whose envoy template needs helpers this checkout's chart does not define. The first attempt failed that way; `results/deploy-output.txt` has the working run.
- `metrics-reader-rbac.yaml`: a read-only service account for the EPP metrics port, which enforces kube-rbac on `/metrics` and `/debug/plugins/state`. The EPP's own service account is not allowed to read them.
- `smoke-test.sh`: the checks below. Exit code is the number of failed checks.
- `results/`: recorded output.

## Steps

1. Build the image with Cloud Build from the modified working tree: `~/.claude/skills/cloud-build-epp/build-epp.sh thunder-agent-v3` (run inside `llm-d-router`). The tag is new, so the old image stays available for rollback.
2. `./deploy.sh` (revert with `helm rollback program-aware-scheduling 10 -n llm-d-program-aware-scheduling`).
3. `kubectl apply -f metrics-reader-rbac.yaml` (once)
4. `./smoke-test.sh | tee results/smoke-test-output.txt` (rerunnable: unique session ids per run, counter checks are deltas)

## What the smoke test checks

| # | check | why it proves the version or behavior |
|---|---|---|
| 1 | the build info metric is present | the EPP is up and serving metrics |
| 2 | `thunder_agent_pauses_total` and `resumes_total` exist, `sheds_total` does not | these metric names exist only in the new build; the strict config decoder would also have refused `pauseSweepSeconds` on the old build |
| 3 | all 4 pods report `pod_capacity_tokens{source="real"}` = 2,237,040 | capacity comes from scraped `cache_config_info`, not the fallback |
| 4 | state dump reachable with 0 programs | the debug endpoint and the plugin's dump work |
| 5 | two turns for session `smoke-a`, one for `smoke-b`, all answered | end-to-end path through envoy, EPP, vLLM |
| 6 | 2 programs, committed tokens > 0, no in-flight left, none paused, at most 2 pods carry tokens | accounting closes per turn; paused count is a new field |
| 7 | `releases_total{class="new"}` = 2, `{class="reasoning"}` = 1, `rebinds_total` = 0, no holds or pauses | first turns were admitted as new, the follow-up bypassed as reasoning, the session stayed on its pod, and nothing was held at real capacity |
| 8 | a turn with `x-session-final: true` drops the program count to 1 and increments `session_final_releases_total` | release path |

## Results (2026-09-17)

Image `thunder-agent-v3` built by Cloud Build from the working tree in `image-source.md` (HEAD `513f0727` plus the uncommitted port, diff sha256 `81439931ca1e82a8`), amd64, binary layer different from `thunder-agent-v2`. Helm release upgraded to revision 11. All 20 checks pass; raw output in `results/smoke-test-output.txt`.

| # | check | result |
|---|---|---|
| 1 | build info | `inference_extension_info{commit="513f0727..."}` present |
| 2 | version | `thunder_agent_pauses_total` and `resumes_total` exported, `sheds_total` gone; the startup log shows the config parsed with `pauseSweepSeconds: 5`, `kvUsageCorrection: false`, `defaultRequestTTL: 0s` |
| 3 | capacity | all 4 pods `source="real"`, 2,237,040 tokens each (matches step 03) |
| 4 | state dump | reachable with the token; fields `pausedPrograms`, `pausesTotal`, `resumesTotal`, per-pod `tokens` and `decayed` present |
| 5 | traffic | two turns of session A and one of session B answered through envoy, EPP, vLLM |
| 6 | accounting | program count +2, committed tokens > 0, in-flight back to 0, nothing paused, every bound pod carries tokens |
| 7 | classes and stickiness | `releases_total` deltas: new +2, reasoning +1; `rebinds_total` +0; holds 0; pauses 0 |
| 8 | release | final turn drops the program count by 1 and advances `session_final_releases_total` by 1 |

Two observations worth keeping:

- The bytes-per-token estimator settled around 7 on these tiny chat bodies, against the 4.0 seed and upstream's 5 chars per token. JSON framing dominates short requests; it will converge lower on real 60k-token histories.
- The first run against a fresh pod also passed all behavior checks; the failures in the very first attempt were the metrics port rejecting unauthenticated reads (401, then 403 with the EPP's own token), not the plugin.

Not tested here, by design: holds, pauses and resumes under load. At real capacity nothing is held. That is step 10: the step 08 replicate protocol through the EPP, which also needs the gateway route timeout raised since `defaultRequestTTL` is 0 and holds can last up to 1800 s.

## Cluster state after this step

- Helm release `program-aware-scheduling` at revision 11: image `thunder-agent-v3`, config `thunder-plugins.yaml` from this directory. Revert: `helm rollback program-aware-scheduling 10 -n llm-d-program-aware-scheduling`.
- ServiceAccount, ClusterRole and ClusterRoleBinding `thunderagent-metrics-reader`. Revert: `kubectl delete -f metrics-reader-rbac.yaml`.
- The vLLM pods and the original Python router are untouched.
