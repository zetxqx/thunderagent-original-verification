# Step 24: thunder-agent PR3 gate vs no router, one vLLM replica per lane, AgentX workload

Status: runs done (2026-10-09), all 20 points valid; results and takeaways not written yet. Four-arm report and figures: [results/compare-all/report/](results/compare-all/report/). Offload-thunder c=128, 64, 32 were rerun after fixes (failed first runs in `results/offload-thunder-60m-invalid/`); offload-thunder c=32 and offload-baseline c=192 were fetched from the PVC after kubectl lost its GKE credentials at 20:06 UTC (both jobs had completed; offload-baseline c=192 has no end-of-run pod check or vLLM log, see its `meta/finish.json`).

## Takeaways

To be written after the runs.

## Question

Step 23's 20-minute lane runs showed one vLLM replica falling off a cliff between c=20 and c=24: GPU prefix hit rate dropped from 89% to 51%, output throughput halved and P90 TTFT rose from 2.8 s to 35 s, because the sessions' contexts no longer fit the 2.24M-token KV pool and prefixes were evicted before reuse. The thunder-agent gate (PR3, [llm-d/llm-d-router#3076](https://github.com/llm-d/llm-d-router/pull/3076)) is built for exactly this: hold sessions at the router so the admitted working set fits the pod. Does it keep throughput and TTFT past the cliff, and what does it cost below it?

## Setup

| | |
|---|---|
| Model server | vLLM v0.28.0, Qwen3-Coder-30B-A3B-Instruct-FP8, TP=2, one pod per lane (2 H100), KV 2,237,040 tokens per pod, CPU offload off |
| Server flags | as in the skill's references/deployment.md section 2; live copy in `results/<label>/c<N>/meta/vllm-deployment.yaml` |
| Router arms | **thunder-60m**: a lane EPP per pod (`agentx-epp-<lane>-epp`, standalone chart from the PR3 branch, watching only that lane's pod), image `llm-d-router-endpoint-picker:thunder-agent-pr3-a025437b-produces` (`sha256:e038ea5a9eda...`): PR3 `a025437b` plus a `Produces()` declaration for the `inflight-estimate` request attribute ([thunder-produces.patch](thunder-produces.patch), 6 lines). `a025437b` alone fails every request: since upstream #2580 the data layer drops an undeclared write and the director fails the request (`plugin "thunder/thunder-agent" wrote undeclared request attribute "inflight-estimate/thunder-agent"; add it to Produces()`, seen in the first smoke test). The patch is not in any PR branch yet; it belongs in the PR1 commit, plugins `../.claude/skills/agentic-benchmark/manifests/epp/thunder-pr3-plugins.yaml` (capacity 2,237,040, utilThreshold 1.0, idle lease 30 s, backstop 1800 s, eviction TTL 3600 s, flow control TTL 0, envoy ext_proc timeout 2400 s). **baseline-60m**: no router, the client talks to the pod directly |
| Client | agentx-harness agentx-v1.0.6, `--scenario agentx` (60 min profiling, 10 warmup requests per lane), dataset `semianalysis_cc_traces_weka_062126_256k`, seed 42. thunder sends `X-Session-ID`; baseline does not. aiperf never sends `x-session-final` |
| Grid | concurrency 32, 24, 20, 16, 12; one point per lane (4 lanes on 4 pods, the fifth point on the first free lane); fresh vLLM pod (and lane EPP) per point; 1 replicate |
| SLO | TTFT <= 60 s |
| Dates and nodes | 2026-10-09; nodes and neighbors per point in `meta/` |

## Phase 2: 400 GiB CPU KV offloading

After phase 1, `run-offload.sh` replaces the vLLM deployment with `results/vllm-deploy-offload400.json` (made by the skill's `vllm-offload.py` from the live deployment, saved as `results/vllm-deploy-before.json`): `--kv-offloading-size=400`, memory request and limit 450Gi, `/dev/shm` 410Gi, and a required pod anti-affinity so each node holds one replica (two 450 Gi pods do not fit an 895 GiB node). Replicas stay 4 when 4 spot H100 nodes are available; with fewer nodes the run uses the ready pods as lanes. It runs **offload-thunder-60m** (same lane EPPs and gate config, still sized to GPU KV) and **offload-baseline-60m** (no router) at concurrency 192, 128, 96, 64, 32, restores the original deployment on every exit path, builds the four-arm comparison in `results/compare-all/report/`, and removes the lane EPPs.

The 400 GiB tier holds about 8.74M tokens (48 KiB per token), 3.9x the GPU KV. vLLM's connector copies every computed block to CPU, so the tier holds a copy of the GPU contents and a pod's reach is about the tier size (step 20, "Sizing the gate to the CPU tier").

## Expectations (written before the run)

1. c=12 to c=20: thunder within about 5% of baseline on output throughput and P90 TTFT (the working set mostly fits, the gate should rarely hold).
2. c=24 and c=32: thunder keeps the GPU hit rate near the c=20 level (above 80%) and output throughput at least 1.5x baseline, by delaying sessions at the router (`gate_delayed_dispatches` > 0, EPP queue wait > 0).
3. Cost: thunder's P90 TTFT at c=24 and c=32 includes router queue wait; it should still be below baseline's 35 s and 105 s from step 23, but the worst-turn TTFT per session can be longer for held sessions.
4. Falsified if, at c=24 and c=32, thunder's hit rate stays near baseline's 50% or its throughput is within 5% of baseline.
5. Offload, no router: the cliff moves from c = 20 to 24 to step 20's estimate of c = 130 to 175. At c = 32 to 96 the overall hit rate (GPU plus CPU tier) stays above 80% and output tok/s/GPU near the phase 1 c = 16 to 20 level; at c = 192 the hit rate falls.
6. Offload with thunder (gate sized to GPU KV): from c = 64 the gate holds sessions that the CPU tier could have served, so its throughput is at or below offload without a router, with a longer TTFT tail from router waits. If thunder still wins at c = 192, the gate's protection matters even with a tier.

## Smoke test

`results/smoke-epp/c4` (lane a through its lane EPP, c=4, 2 min, `--unsafe-override`): 13 requests, 0 errors; the EPP was scraped (11 EPP requests, 0 EPP errors, 14 gate releases, 0 pauses, gate working set at most 0.27 of capacity, as expected at c=4); no undeclared-key errors in the EPP log.

## How to run

```bash
nohup caffeinate -i ./run-all.sh > results/run-all.log 2>&1 &
```

`run-all.sh` deploys the four lane EPPs, runs the thunder points (`LANE_EPP=1`), then the baseline points, then the comparison report in `results/compare/report/`. Scripts are the agentic-benchmark skill's (`run-lanes.sh`, `run-point.sh`, `render-lane-epp.sh`, `analyze.py`, `make_figures.py`).

## Results

To be written after the runs.
