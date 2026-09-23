Title: [Agentic] Session level admission control: add a ThunderAgent plugin

Labels: needs-triage

**What would you like to be added**:

A `thunder-agent` plugin: session level admission control for agentic workloads, a port of ThunderAgent (arXiv 2602.13692) into the EPP. No change to vLLM. The client only sends a session id header.

How it works:

- Track each session's KV footprint in tokens and the pod it is bound to.
- A pod is saturated when the footprints of all its sessions, running and idle, exceed its KV capacity.
- When saturated, pause idle sessions. Hold their next turn, and new sessions, in the router until a pod has room. Paused sessions go first.
- Turns of admitted sessions always pass through.

It uses existing extension points: `agent-identity` for the session id, `PreRequest` and `ResponseBody` hooks for the session state, the flow control `saturationDetector` and `fairnessPolicy` for the gate, and a `Scorer` to keep a session on its pod. The session state is the same idea as the `session-state-producer` in #2524.

**Why is this needed**:

Agentic sessions send about 100 prompt tokens per output token, and each turn repeats the previous prompt. When a pod is over-subscribed, vLLM evicts idle sessions' KV blocks, and every turn becomes a full prefill. Keeping a session on one pod does not help; the cache is gone before the next turn.

Measured with the original Python ThunderAgent router on one vLLM pod (Qwen3-Coder-30B-A3B-FP8, vLLM v0.28.0, 2x H100, 338 real Claude Code sessions replayed, 45 minutes, three runs per arm):

| one pod | passthrough | ThunderAgent |
|---|---|---|
| output tok/s | 221 | 469 (2.1x) |
| steady state prefix cache hit rate | 0.008 | 0.685 |
| TTFT p50 | 52.7 s | 3.0 s |
| requests with zero cache hit | 88% | 36% |

The cost is a longer tail: a few sessions wait minutes before they are admitted. That is the first thing to tune once the plugin is in.

Filed: https://github.com/llm-d/llm-d-router/issues/2964 (2026-09-22)
