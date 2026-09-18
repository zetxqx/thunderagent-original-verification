# Step 12 results: three EPP policies on the whole 4-pod pool

Run `results/rep-20260918-012350-c338-t1900`: one EPP (image `thunder-agent-v3`) over the four vLLM pods, c=338 (the whole kept corpus), 45 minutes per cell, client timeout 1900 s, three replicates per arm in Latin-square order, prefix caches reset and the EPP restarted before every cell, load generator with the session-replay permit fix (`results/inference-perf-image.txt`). Nine cells; `epp-baseline-r2` was lost to a transient API-server timeout during its Helm upgrade (the arm check refused to run under the wrong config) and was rerun as a make-up cell after the others, under the same conditions. Figures: `pool.png` (bars) and `timeseries.png` (per replicate) in the run directory.

## Headline

| metric | epp-baseline (llm-d default) | epp-affinity (session pin) | epp-thunder (port) | thunder / baseline |
|---|---|---|---|---|
| output throughput (tok/s) | 1020 (1018-1023) | 1023 (1020-1027) | 1447 (1443-1450) | 1.42x |
| requests completed | 4225 | 4227 | 6096 | 1.44x |
| hit rate, steady state (after 10 min) | 0.002 | 0.002 | 0.248 (0.237-0.255) | 139x |
| TTFT p50 (s) | 122.9 | 126.1 | 3.7 | 0.03x |
| TTFT p90 (s) | 217.2 | 217.0 | 113.3 | 0.52x |
| requests with zero cache hit | 0.90 | 0.92 | 0.67 | |
| client timeouts (1900 s) per cell | 1 | 1 | 25 | |
| pool in flight (mean) | 123 | 123 | 129 | |
| pool KV usage (mean) | 0.86 | 0.87 | 0.79 | |
| EPP holds / pauses / resumes per cell | - | - | 2399 / 4720 / 4470 | |
| programs paused at once, peak | - | - | 250 | |
| forced admissions per cell | - | - | 55 | |
| resumes that changed pod per cell | - | - | about 3100 of 4470 | |

All three arms are reproducible to about 1 percent across replicates on throughput; the thunder arm's throughput spread is 1443 to 1450.

## Findings

1. **Placement policy alone does nothing on an oversubscribed pool.** llm-d's default profile (prefix-cache scorer with queue and KV scorers) and plain session pinning are indistinguishable on every metric: the same 1020 tok/s, the same 0.002 hit rate, the same 123 s median TTFT, the same KV at 0.87. With about 85 active sessions per pod and no admission control, every pod's cache thrashes whether or not a session keeps landing on the same pod. This matches step 10, where the single-pod sticky arm ended at the same hit rate as the Python proxy.
2. **Admission control is the whole effect, and it survives the move to four pods.** The port is 1.42x the llm-d default on throughput with a 33x lower median TTFT, and the effect comes entirely from the prefix cache: 0.248 steady-state hit rate against 0.002, with the pool's KV held at 0.79 instead of 0.87 because about 250 programs are paused at any time.
3. **The port leaves a lot on the table on multiple pods, and the reason was identified before the run.** Its steady-state hit rate on the pool is 0.25 against 0.49 on a single pod at comparable per-pod pressure (step 10). About 70 percent of resumes moved the program to a different pod (3100 of 4470 per cell), because a paused program's origin pod rarely has room at the instant its turn comes up while the pod with the most room does; each move pays a full re-prefill and evicts others' prefixes. This is also what upstream's best-fit-decreasing placement does across backends. An origin-only resume policy (wait for the origin pod unless it is gone or the forced-admission backstop fires) is the obvious follow-up and should lift the pool hit rate toward the single-pod value.
4. **The tail is upstream's.** 55 forced admissions and 25 client timeouts per thunder cell against 1 in the other arms: heads that waited the full 1800 s and requests that then exceeded the 1900 s client. Proposal Part 1's starvation applies at pool scale.

## Load and validity

- The fixed load generator drove all 338 sessions in every cell (338 issued a first request in all nine). Per pod: 30 to 33 requests in flight, KV 0.78 to 0.87.
- Arm order was rotated across replicates, caches were reset and the EPP restarted between cells, and the spread within each arm is about 1 percent, so drift is not a factor.
- Baseline and affinity each lost 1 request per cell to the client timeout; thunder lost 25. Session churn is therefore small in all arms and does not trim the workload the way step 08's 600 s client did.
- Per-pod tables in `analysis.md` show the same picture on every pod.

## Where requests wait (`waiting.png`, `plot_waiting.py`)

Every arm has 200 to 370 requests waiting somewhere at all times; the arms differ in where and in what order.

| after minute 10, mean per replicate | waiting inside vLLM (pool) | running inside vLLM | held in the EPP |
|---|---|---|---|
| epp-baseline | 187 to 189, growing from 150 to 240 over the run | 113 to 114 | 0 |
| epp-affinity | 188 to 190, same shape | 113 to 115 | 0 |
| epp-thunder | 1.2 to 1.3 | 119 to 120 | about 370 |

Under baseline and affinity the queue lives inside vLLM: the engine's scheduler admits waiting requests first come first served as blocks free, it knows nothing about sessions, and the prefixes of the waiting requests are evicted while they wait. The queue grows through the run because contexts grow and fewer requests fit. Under thunder the engine's queue is empty after the first four minutes (the cold-start burst of 338 first turns, which the gate lets through because every program is new and the pods are empty, until the sweep catches up), the wait moves into the EPP where the next admission is chosen by program class and size and where a paused program's context stops counting, and the engine runs slightly more requests (120 against 114) because the blocks freed by paused programs are usable. The wait is not shorter, it is placed where a scheduler can make it useful.

## Comparison with the single-pod runs

| | one pod (step 10, port, 1900 s) | 4-pod pool (this step, port) |
|---|---|---|
| active sessions per pod | about 60 (v0.7.0 generator) | about 85 |
| throughput per pod | 351 tok/s | 362 tok/s |
| steady-state hit rate | 0.49 | 0.25 |
| resumes that changed pod | 0 (nowhere to go) | about 70 percent |

Per-pod throughput is similar despite the lower hit rate because the pool cells carried more active sessions and the port held more requests in flight; the hit-rate gap is the cost of pod hopping.

## Next step

An origin-only resume policy in the port (a config knob, default matching upstream's move-to-most-room behaviour so the port stays faithful, `origin-only` for the experiment), rebuilt as `thunder-agent-v4`, and one more pool arm `epp-thunder-origin` with the same three-replicate protocol. Prediction: rebinds near zero, steady-state hit rate toward 0.45, throughput above 1447 tok/s. That arm would also settle whether the 55 forced admissions per cell shrink when sessions stop paying for moves.

## Cluster state after this step

The main release was returned to its step 09 configuration (thunder plugin, 1000 s envoy timeout, image `thunder-agent-v3`). The three step 10 lane EPPs were torn down afterwards (2026-09-18). Both are logged in `../08-cluster-changes.md`.
