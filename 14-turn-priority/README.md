# Step 14: llm-d's turn-priority fairness (PR 2116) on a single pod, against step 10's lanes

Question: how does the `turn-priority` strategy that llm-d-router merged in [PR 2116](https://github.com/llm-d/llm-d-router/pull/2116) (program-aware fairness, ordering waiting sessions by depth) compare with the ThunderAgent port and with plain sticky routing, under the step 08 / step 10 protocol.

## Design

- Same protocol as step 10: one EPP per vLLM pod (lanes a/b/c), c=128, 45-minute window, client timeout 1900 s, three replicates in parallel (one per lane), weka trace replay.
- Same load generator as step 10: inference-perf v0.7.0 (`quay.io/inference-perf/inference-perf@sha256:d247e6ad...`), which has the parked-permit bug (`../INFERENCE-PERF-BUGS.md` issue 4): only about half of the 128 sessions are active at any time. Kept on purpose so that the sticky and thunder numbers of `../10-llm-d-router-replicates/results/rep-20260917-173839-c128-t1900` are directly comparable; all three arms saw the same effective load. The absolute numbers are therefore lower than steps 12 and 13 and not comparable with them.
- Arm `epp-turnprio-005-ttl60`: EPP image `upstream-main-dc6538a1` built from llm-d-router upstream `main` at `dc6538a1` (includes PR 2116, merged 2026-09-13 as `449637db`), config `../10-llm-d-router-replicates/turnprio-005-ttl60-plugins.yaml`: the upstream sample (`deploy/config/sim-program-aware-config.yaml`) plus `agent-identity` mapping `x-session-id` to the fairness ID, with the strategy's documented defaults: `turnPriorityTimeWeight: 0.05`, `turnPriorityInactivitySeconds: 120`, the flow controller's default request TTL of 60 s, and the default utilization saturation detector (queue depth >= 5 or KV >= 80 percent). Placement is the sample's `queue-scorer`; on a single pod it is moot.
- What the strategy does, from its README: when the flow controller is holding requests (the detector reports saturation), dispatch the waiting session with the highest `turn + 0.05 x wait_seconds`; a waiting request is shed with 429 when it reaches the 60 s TTL, so under sustained contention a new session (turn 1, at most 4 points) never overtakes a session at turn 5 or deeper and is shed instead. That is the documented intent ("capacity goes to sessions whose prefix is already resident").
- Tooling: `../10-llm-d-router-replicates/run-replicates.sh` with `EPP_IMAGE_TAG`, the `turnprio*` arm check (flow control on, `strategy: turn-priority` in the ConfigMap, image tag), `analyze.py` here (per-cell stats via step 12's analyzer plus 429 counts).

## Results

Run `../10-llm-d-router-replicates/results/rep-20260921-174322-c128-t1900` (2026-09-21 17:44 to 18:36), three cells, no preemption. Cells: mean (min-max).

| metric | epp-sticky (step 10) | epp-thunder (step 10) | **epp-turnprio-005-ttl60** | turnprio / sticky | turnprio / thunder |
|---|---|---|---|---|---|
| throughput (output tok/s) | 227 (221-236) | 351 (327-367) | **264 (252-273)** | 1.16x | 0.75x |
| requests completed | 979 | 1398 | 1063 | 1.09x | 0.76x |
| hit rate, steady state | 0.003 | 0.489 | **0.047** (0.040-0.055) | | 0.10x |
| TTFT p50 / p90 (s) | 49.4 / 113.5 | 4.0 / 22.0 | 40.2 / 76.9 | 0.81x / 0.68x | 10x / 3.5x |
| in flight, mean | 30 | 30 | 29 | | |
| waiting inside vLLM, mean | 20 | 0 | 8 | | |
| KV usage, mean | 0.91 | 0.89 | 0.87 | | |
| failed requests per cell | 0 | 6 (client timeouts) | **45**, of which 44 are `429` sheds | | |
| turns skipped because a predecessor failed | 0 | 118 | **3,000 to 3,500** | | |
| sessions dispatched (128 slots plus replacements) | 128 | 137 | 173 | | |

Reading:

1. **turn-priority lands between plain sticky and the ThunderAgent port, much closer to sticky**: 16 percent more throughput than sticky, 25 percent less than the port; steady-state hit rate 0.05 against the port's 0.49; TTFT p50 40 s against 4 s. The engine is still thrashing: 29 requests in flight and 8 waiting inside vLLM at 87 percent KV, the same regime as sticky.
2. **Even that gain is bought with shed sessions.** Each cell shed 44 sessions with 429 at the 60 s TTL and inference-perf then skipped 3,000 to 3,500 of their later turns, so the pod served a trimmed workload; the port's cells in step 10 skipped 118 turns (6 client timeouts). Correcting for trimming would move turn-priority further toward sticky, not away from it. The shed sessions are new ones: at weight 0.05 a turn-one request can gain at most 3 points in 60 s and never overtakes established sessions, exactly as the strategy's README describes.
3. **Why ordering by depth does not protect the cache here.** turn-priority only reorders the queue while the utilization detector reports saturation; it never limits how many sessions are resident on the pod. With about 30 sessions in flight and 87 percent KV, the running set alone exceeds what the KV can hold with their prefixes, so prefixes are evicted by the sessions that are running, not by the order of the ones waiting. The ThunderAgent port's gain comes from the opposite lever: it pauses idle sessions so that the resident set fits (0 waiting inside vLLM), which is what keeps hit rate at 0.49. Depth ordering is a tiebreaker on top of admission control, not a substitute for it.
4. Per-arm fairness differs in kind: sticky and the port completed every session's turns (the port's 6 failures were 1900 s client timeouts); turn-priority never served 44 of 173 sessions past their first turn.

Caveats: one generator with the permit bug (same for all arms); one weight (0.05) and one TTL (60 s), the documented defaults; the 0.5 weight the README mentions for letting newcomers overtake within the TTL was not run; single pod, so placement and prefix-aware routing play no role; 45-minute cells (the same three-replicate protocol as step 10).

## Files

- `analyze.py <turnprio_run_dir> [step10_run_dir]`: the table above (`step14-analysis.md` in the run directory).
- `../10-llm-d-router-replicates/turnprio-005-ttl60-plugins.yaml`: the arm's EPP config.
- Image provenance: `../09-llm-d-router-smoke/image-source.md`.
