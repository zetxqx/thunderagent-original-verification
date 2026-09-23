Title: feat(epp): add thunder agent, session level admission control for agentic workloads

Branch: `thunder-agent-pr1`, one commit, `513f0727` cherry-picked onto `upstream/main` (now `6bc20ec5`). The only change during the rebase: the sample config's `apiVersion` moved from `inference.networking.x-k8s.io/v1alpha1` to `llm-d.ai/v1`, because upstream graduated the EPP config API in #2923. Verified on current main: `go build ./...`, plugin and runner unit tests, and the flow control simulation tests pass. The later commits on `thunder-agent` (upstream alignment, origin-only resume, urgent tier, wait cap) go in follow-up PRs.

---

**What type of PR is this?**

/kind feature

**What this PR does / why we need it**:

Adds the `thunder-agent` plugin: session level admission control for agentic workloads, based on ThunderAgent (arXiv 2602.13692). No change to vLLM. The client only sends a session id header.

The problem: an agent session repeats its whole prompt on every turn, so it is cheap only while its KV blocks stay on the pod. When a pod is over-subscribed, vLLM evicts idle sessions' blocks and every turn becomes a full prefill. Keeping a session on one pod does not help, because the cache is gone before the next turn.

What the plugin does:

- Tracks each session's KV footprint in tokens (from `usage.total_tokens`, or an estimate while a turn is in flight) and the pod it is bound to.
- Treats a pod as full when the footprints of all its sessions, running and idle, reach its KV capacity. Capacity is scraped from the engine's `cache_config_info`, with a configured fallback.
- Holds a new session's first turn in the router until a pod has room for it. Smallest first, with a starvation guard so a large session cannot wait forever.
- Turns of admitted sessions always pass through. Their completion is what frees room.
- Releases a session on the `x-session-final` header, or after an idle TTL.

Where it plugs in (one named plugin instance in all slots, so accounting and decisions cannot drift apart):

| slot | interface | role |
|---|---|---|
| scheduling profile | `Scorer` | keep a session on its bound pod; least token load for a new one |
| `flowControl.saturationDetector` | `SaturationDetector` | keeps the per pod fit view; always reports not saturated, because the controller's own gate would also block admitted sessions |
| `defaultPriorityBand.fairnessPolicyRef` | `FairnessPolicy` | the admission gate |
| request lifecycle | `PreRequest`, `ResponseBodyProcessor` | token accounting, pod binding, release |

Files: the plugin under `pkg/epp/framework/plugins/thunderagent/` with unit tests and a README, plugin registration in `cmd/epp/runner`, an example pipeline in `deploy/config/thunderagent-config.yaml`, and flow control integration and simulation tests. Metrics are `thunder_agent_*`, all Alpha. Session ids never appear in metrics, logs or dumps.

Motivation, measured with the original Python ThunderAgent router on one vLLM pod (Qwen3-Coder-30B-A3B-FP8, vLLM v0.28.0, 2x H100, 338 real Claude Code sessions replayed, 45 minutes, three runs per arm):

| one pod | passthrough | thunder agent |
|---|---|---|
| output tok/s | 221 | 469 (2.1x) |
| steady state prefix cache hit rate | 0.008 | 0.685 |
| TTFT p50 | 52.7 s | 3.0 s |

This first PR is the plugin skeleton and the gate. Follow-up PRs align the defaults and the pause sweep with upstream ThunderAgent and add the resume placement knobs. The plugin is off unless referenced from a config, so there is no change for existing deployments.

**Which issue(s) this PR fixes**:

Part of #2964

**Release note**:
```release-note
Add the `thunder-agent` EPP plugin (Alpha): session level admission control for agentic workloads. Off unless referenced from the plugin config.
```

Opened as draft: https://github.com/llm-d/llm-d-router/pull/2968 (2026-09-22)
