# Saturation test results (2026-09-15)

Goal: verify the paper's core scheduling behavior - admission control. When the sum of tracked program tokens would exceed a backend's KV capacity, ThunderAgent must PAUSE new programs and RESUME them as capacity frees. The earlier run (04-benchmark) could not show this because the workload was tiny relative to capacity.

Run: `./run-saturation.sh` -> in-cluster Job (script from `04-benchmark/benchmark.py`, config in `job.yaml`). Artifacts: `results/sat-20260915-152924/`, figure `results/sat-20260915-152924-figure.png`.

## Workload sizing

- Each vLLM pod: 2,237,040 tokens KV capacity (4 pods, 8.95M total).
- 320 sessions x 3 turns, each session with a unique random-word preamble. Planned ~40k tokens; actual tokenization came out at **~61k prompt tokens per session** (random words tokenize at ~1.5 tokens/word).
- Total resident demand: 320 x 61k = **19.6M tokens = 2.2x total capacity**. Only ~36 sessions fit per pod, so sustained over-subscription is guaranteed.
- Sessions release their program right after their last turn (this run required changing the benchmark script: without prompt releases, paused programs could never resume and the run would deadlock).

## Outcome: all 6 checks PASS

| Check | Result |
|---|---|
| All requests succeeded | 960/960 HTTP 200 (makespan 279.8s) |
| Sticky routing | 320/320 observed; 96 programs re-placed (informational - re-placement from the paused pool at admission is upstream behavior, not a bug) |
| Aggregate prefix-cache hit rate >= 0.1 | 0.458 (26.9M / 58.8M tokens) |
| KV utilization > 0 | **peak 96.0%** - pods genuinely saturated |
| All tracked and released | 320/320 tracked, 320/320 released |
| **Scheduler paused programs** | **max 186 paused concurrently; 318/320 programs experienced a pause; median per-step pause 46s, max 77s** |

## What the run demonstrates (the paper's mechanism, live)

1. **Pause under pressure.** Within ~20s of the arrival wave, the router pinned paused programs at a ~170-186 plateau (panel c of the figure) while admitted programs ran. `/health` live samples: `paused` went 131 -> 168 -> 186 while all 320 programs existed.
2. **Resume as capacity frees.** From t=150s, finished sessions release their programs and the paused plateau drains: 179 -> 96 -> 39 -> 27 -> 0. Every held program eventually ran; none hit the 900s client timeout (turn-0 latency max 258s).
3. **Admitted programs keep their cache benefit even under saturation.** Turn latency (panel d) is bimodal at turn 0: admitted-immediately sessions finish in ~8-80s, held sessions in ~150-260s (wait + prefill). Turns 1-2 drop to median 59s and 15s as prefixes hit.
4. **Hit rate under over-subscription is 0.46**, down from 0.80 in the unsaturated run - expected: at 2.2x over-subscription vLLM's LRU must evict, and the 96 paused-pool re-placements each pay one full re-prefill. This matches the paper's premise that capacity-aware admission (not placement alone) is what protects cache reuse.
5. **Active programs bypass admission**: no program was paused mid-trajectory; turns 2-3 of admitted sessions never waited on admission (pause time concentrates entirely in turn 0). This is the "REASONING bypass" semantic.

## Notes and caveats

- `avg_pause_s` in `profiles.json` is averaged over the session's 3 steps; since only turn 0 can pause, total wait ~= 3x that value (max avg 76.7s -> ~230s wait, consistent with max turn-0 latency 258s).
- The 96 backend moves are all admission-time re-placements of paused programs (upstream re-resolves the backend after a pause; `app.py` comment "honor migrations"). After first dispatch, no program moved.
- Turn latencies here include deep vLLM queueing (up to ~80 concurrent 61k-token prefills per pod); this run measures scheduler behavior, not serving latency.
