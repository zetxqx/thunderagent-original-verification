# Step 24: thunder-agent PR3 gate vs no router, one vLLM replica per lane, AgentX workload

Status: runs done (2026-10-09 to 11), 48 valid points in six arms; results of the gate-setting variants below, the main sweep's takeaways not written yet. Interactive view: repo `dashboard/` (`step24-thunder-pr3-lanes.json`); report and figures: [results/compare-all/report/](results/compare-all/report/). Failed first runs are kept in `results/*-invalid/` (claim bug, envoy 503, connection reset, and three vLLM crashes, "CUDA error: an illegal memory access", all on node gke-bobbm-bobbm-spoth100-ef0c964e-czgg, which was then cordoned and later left the cluster). The 300 s c128 and c192 points were stopped in warmup after 75 min (`results/offload-thunder-fa300-60m-stopped/`). Offload-thunder c=32 and offload-baseline c=192 were fetched from the PVC after kubectl lost its GKE credentials (offload-baseline c=192 has no end-of-run pod check or vLLM log, see its `meta/finish.json`).

## Takeaways

To be written after the runs.

## Code changes suggested to the PR author (PR3 `a025437b`)

**What we saw.** With the 1800 s forced admission (`headWaitStarvationMs`), every thunder point at c >= 24 has two phases. Before minute 30 the gate works; after it, forced admissions arrive in a burst, GPU prefix hit drops to about 0 and stays there to the end of the run (vLLM's own `prefix_cache_hits` counter agrees):

| point | output tok/s/GPU, minutes 5 to 30 | minutes 36 to 60 | GPU hit, before / after | forced admissions before / after minute 30 |
|---|---|---|---|---|
| thunder c32 (no offload) | 160 | 60 | 73% / 11% | 0 / 13 |
| thunder + offload c128 | 420 | 70 | 87% / 0% | 0 / 146 |
| thunder + offload c192 | 425 | 78 | 87% / 1% | 0 / 247 (101 in minute 36) |
| thunder lease 10 s + offload c192 | 467 | 73 | | 0 / 220 |

The idle lease does not change this (10 s and 30 s give the same picture), so the 60-minute averages mix a working gate with a collapsed one.

**Why, in the code** (`pkg/epp/framework/plugins/thunderagent/fairness.go`):

- `betterThan` (line 270) orders held sessions by starving first, then class, then smallest footprint. A large new or paused session loses every comparison to smaller ones, so it waits the full `headWaitStarvationMs`. Sessions held since the start all reach it at about the same time.
- `sizeAndFitLocked` (line 212) lets a starving head dispatch without room, and `admitLocked` (line 243) pauses idle sessions only for an admitted turn or when the session fits a pod (`fitPod`). A forced admission therefore pauses nobody. Once admitted, the session's turns always dispatch and it cannot be paused while active, so the pod stays over capacity until those sessions end.

**Suggested changes:**

1. **Age-aware ordering:** weigh waiting time when ordering held sessions, so a large session does not starve behind a stream of smaller ones until the backstop. For example, add aging to the footprint key, or switch to oldest-first once a wait passes a fraction of `headWaitStarvationMs`. Then a large session is admitted when room appears, instead of starving to the backstop.
2. **Gradual forced admission:** force in at most one session per pod at a time (or per interval). Make room for it by pausing idle sessions the same way a normal admission does (`reclaimLocked` with `fitTokens`), instead of releasing every starving head in back-to-back dispatch cycles without pausing anyone.

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

## Forced admission 300 s: expectations (written before the run, 2026-10-11)

`run-fa300.sh`, label `offload-thunder-fa300-60m`: as `offload-thunder-60m` (400 GiB offload, lease 30 s, GPU-sized capacity) with `headWaitStarvationMs` 300 s instead of 1800 s, at c = 24, 32, 64, 96, 128, 192.

1. Forced admissions start about 5 minutes into profiling and spread over the hour, instead of a burst around minute 30.
2. No cliff: output tok/s/GPU in minutes 36 to 60 within about 20% of minutes 5 to 30.
3. Shorter TTFT tail: the router wait stops near 300 s, so the worst turn per session drops well below the 1800 s seen now.
4. Risk, and the question this answers: if forced admissions keep the working set above capacity all the time, the cache thrashes all hour and the 60-minute result is at or below the 1800 s arm's average.

## Forced admission 300 s with the reclaim fix: expectations (written before the run, 2026-10-11)

`run-reclaim.sh`, label `offload-thunder-fa300-reclaim-60m`: the 300 s arm above with image `thunder-agent-pr3-a025437b-forced-7ae26276` (a025437b + b9a70488 "forced admission reclaims idle sessions" + the `Produces()` fix 7ae26276), at c = 32, 64, 96. A forced-in session now goes to one pod (its own if paused, else the one with the most room) after that pod's sessions idle past the lease are paused; before, it paused nobody. It still forces in every starving head and still orders smallest first.

1. Smaller overflow per forced admission: fewer requests waiting in vLLM and a higher prefix hit rate than the plain 300 s arm at the same c.
2. More pauses (each forced admission now pauses idle sessions), so paused sessions come back from the CPU tier more often.
3. Falsified if hit rate and output tok/s/GPU match the plain 300 s arm within about 5%: then the overflow comes from the number of forced admissions, not from where they land.

## Smoke test

`results/smoke-epp/c4` (lane a through its lane EPP, c=4, 2 min, `--unsafe-override`): 13 requests, 0 errors; the EPP was scraped (11 EPP requests, 0 EPP errors, 14 gate releases, 0 pauses, gate working set at most 0.27 of capacity, as expected at c=4); no undeclared-key errors in the EPP log.

## How to run

```bash
nohup caffeinate -i ./run-all.sh > results/run-all.log 2>&1 &
```

`run-all.sh` deploys the four lane EPPs, runs the thunder points (`LANE_EPP=1`), then the baseline points, then the comparison report in `results/compare/report/`. Scripts are the agentic-benchmark skill's (`run-lanes.sh`, `run-point.sh`, `render-lane-epp.sh`, `analyze.py`, `make_figures.py`).

## Results

### Gate settings with 400 GiB offload: lease 10 s, forced admission 300 s, and the reclaim fix

All arms 60 min, one vLLM pod per lane, 400 GiB CPU offload, GPU-sized gate capacity; one point per arm and c. Steady state (minutes 5 to 60); the SLO share counts unserved requests (no first token at the end) as misses.

| c | arm | output tok/s/GPU | TTFT <= 60 s | TTFT p50 / p90 | prefix hit | forced admissions | pauses | worst turn per session, p90 |
|---|---|---|---|---|---|---|---|---|
| 32 | no router | 167 | 79% | 43 s / 71 s | 96% | | | 105 s |
| 32 | thunder, 1800 s, lease 30 s | **188** | **95%** | 0.7 s / 9 s | 96% | 8 | 201 | 1813 s |
| 32 | thunder, 1800 s, lease 10 s | 192 | 95% | 0.8 s / 11 s | 95% | 6 | 270 | 1807 s |
| 32 | thunder, 300 s | 171 | 91% | 16 s / 47 s | 96% | 114 | 168 | 338 s |
| 32 | thunder, 300 s + reclaim | 167 | 90% | 18 s / 54 s | 96% | 117 | 160 | 357 s |
| 64 | no router | 168 | 2% | 150 s / 210 s | 93% | | | 262 s |
| 64 | thunder, 1800 s, lease 30 s | 173 | **83%** | 0.6 s / 121 s | 90% | 37 | 305 | 2128 s |
| 64 | thunder, 1800 s, lease 10 s | **194** | 84% | 0.7 s / 113 s | 90% | 36 | 358 | 2107 s |
| 64 | thunder, 300 s | 152 | 24% | 135 s / 458 s | 87% | 221 | 277 | 683 s |
| 64 | thunder, 300 s + reclaim | 158 | 23% | 112 s / 419 s | 88% | 223 | 278 | 676 s |
| 96 | no router | 57 | 0% | 805 s / 849 s | 12% | | | 885 s |
| 96 | thunder, 1800 s, lease 30 s | **144** | **80%** | 0.7 s / 218 s | 79% | 75 | 365 | 2560 s |
| 96 | thunder, 300 s | 70 | 33% | 814 s / 1137 s | 34% | 183 | 153 | 1167 s |
| 96 | thunder, 300 s + reclaim | 67 | 30% | 769 s / 1095 s | 32% | 177 | 162 | 1166 s |

Readings:

1. **The idle lease does not matter.** Lease 10 s and 30 s are within about 5% at c = 16 to 192 (lease 10 s 7% to 12% higher at c = 64 and 192), with 15% to 35% more pauses and slightly fewer forced admissions.
2. **A shorter forced admission makes things worse, not better.** 300 s ties 1800 s at c = 24, loses 9% throughput at c = 32 and half of it at c = 96, where it is close to no router. Forced admissions still come in bursts, only earlier (c = 96: 60 in minute 10), and the cache thrashes from then on. Against the expectations written before the run: 1 held only in part (earlier, not spread), 2 and 3 failed (no plateau; the 25-minute tail is the same, 10.7% against 10.1% of turns at c = 96), 4, the risk, happened. Its one gain is the worst turn per session (338 to 1167 s against 1813 to 2560 s), paid for by every turn.
3. **The reclaim fix (b9a70488) has no measurable effect.** Every metric is within about 5% of plain 300 s, which meets the falsification rule written before the run. Its pause counts are unchanged (160 against 168, 278 against 277, 162 against 153): under load almost no session is idle past the 30 s lease, because their turns are queued in vLLM, so a forced admission still finds nothing to pause.
4. **1800 s remains the best setting tested**, because the gate works for the first 30 minutes (c = 128 and 192: 392 to 467 output tok/s/GPU in minutes 5 to 30, about twice no router's best) before the burst. The two code changes above (age-aware ordering; one forced admission per pod at a time) address the cause directly and are the next thing to test.
