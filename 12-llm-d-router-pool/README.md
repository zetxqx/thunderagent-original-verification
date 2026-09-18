# Step 12: three EPP scheduling policies on the whole 4-pod pool

Question: on the real llm-d deployment shape, one EPP over the 4-pod InferencePool, how does the ThunderAgent plugin compare with llm-d's own two standard policies on the weka agentic workload.

## Arms (one EPP release, only the plugin config changes)

| arm | config | what it represents |
|---|---|---|
| `epp-baseline` | `baseline-plugins.yaml`: prefix-cache-scorer 3, kv-cache-utilization 2, queue 2 (this deployment's `default-plugins.yaml`) | llm-d's optimized baseline, no session concept |
| `epp-affinity` | `affinity-plugins.yaml`: session-affinity-scorer (session_id from `x-session-id`, 1 h binding TTL) plus active-request-scorer | pinning only, no admission |
| `epp-thunder` | `thunder-plugins.yaml`: the step 09 config | pinning plus program-aware admission |

## Load generator: fixed first

Every run in steps 07 to 10 used inference-perf v0.7.0, in which an event parked on its predecessors keeps its worker permit, so only about half of the dispatched sessions ever issued a request (`../INFERENCE-PERF-BUGS.md`, issue 4 root cause). Step 12 uses an image built from the fix (`build-inference-perf.sh`, branch `fix-session-replay-permits`, commit `d5a7c8c`), digest in `results/inference-perf-image.txt`. Calibration of the fixed image on one pod at c=128 for 10 minutes (`../10-llm-d-router-replicates/results/cal-20260918-004115-c128-t1900`):

| signal | v0.7.0 | fixed image |
|---|---|---|
| sessions that issued a request | 58 to 62 of 128 | 128 of 128 |
| vLLM in flight, mean / peak | 34 / 48 | 46 / 58, engine queue non-empty |
| EPP queue, mean / peak | 16 / 38 | 111 / 170 |
| programs paused at once, peak | 38 | 93 |
| throughput over 10 min | 445 tok/s | 539 tok/s |
| bench pod CPU, median / peak | 1.5 / 8 cores | 2.0 / 7.9 cores |

The corpus is the whole Hugging Face file (640 MB, 391 traces, 338 after the turns filter), so 512 distinct sessions do not exist. The pool run uses c=338, the whole kept corpus in one job: about 85 concurrently active sessions per pod, heavier per pod than any earlier run actually delivered.

## Design

Cells run sequentially on the shared pool, 45 minutes each. Per cell: prefix-cache reset on all four pods, the main EPP release upgraded to the arm's config and restarted (clean plugin state), one inference-perf job at c=338 with a 1900 s client timeout. Arm order is a Latin square across replicates (r1 baseline, affinity, thunder; r2 affinity, thunder, baseline; r3 thunder, baseline, affinity). The main release's envoy config carries the ext_proc `message_timeout` raised to 2400 s (`main-values.yaml`), otherwise a held request would fail at envoy before the 1800 s forced admission. The prober scrapes every pod (per-pod files plus a pool aggregate) and the EPP.

Pre-registered expectations: baseline's hit rate clearly above affinity's (it has the prefix-cache scorer) but with sessions moved between pods and a worse TTFT tail; affinity near step 10's sticky arm; thunder with the highest hit rate. The thunder-over-baseline throughput ratio is the number this step exists to produce. On four pods the port's multi-pod placement and sticky-if-fits resume are exercised for the first time.

## Files

- `baseline-plugins.yaml`, `affinity-plugins.yaml`, `thunder-plugins.yaml`: the arms.
- `main-values.yaml`: the main release's user values (step 09) plus the envoy override; `run-pool.sh` passes it with `-f` on every arm switch.
- `build-inference-perf.sh`, `results/inference-perf-image.txt`: the fixed load generator image.
- `config-tmpl.yaml`, `job-weka.yaml`, `filter_traces.py`, `prober.py`: the benchmark cell (single job, multi-pod prober).
- `run-pool.sh [conc] [reps] [window_s] [arms] [client_timeout_s]`: the driver. `338 1 600 thunder` is the calibration.
- `analyze.py`: per-arm tables with ratios to baseline, a per-pod table, and a three-bar figure.

## Steps

1. Calibration on the pool: `./run-pool.sh 338 1 600 thunder`; check all 338 sessions issue a request, per-pod in-flight, bench CPU, errors.
2. Main run: `./run-pool.sh` (about 7.5 hours for 9 cells).
3. Revert when done: `helm upgrade` the main release back to the step 09 config, or `helm rollback`.

## Pool calibration (2026-09-18, `results/cal-20260918-010226-c338-t1900`, thunder arm, 10 min)

| signal | value |
|---|---|
| sessions that issued a request | 338 of 338 |
| pool in flight, mean | 151 (36 to 38 per pod), KV 0.75 |
| throughput | 1574 tok/s (393 per pod) |
| hit rate, whole window / steady | 0.176 / 0.115; zero-hit share 0.74 |
| EPP pauses / resumes / holds | 1697 / 1448 / 678; peak paused 249; queue mean 159, max 326 |
| rebinds | 1025 |
| errors, forced admissions | 0, 0 |
| bench pod / EPP CPU, median | 2.3 / 1.3 cores |

Known before the main run, recorded here so it is not a post-hoc explanation: on four equally loaded pods the port's sticky-if-fits resume re-places most resumed programs. When a paused program's turn comes up its origin pod rarely has room at that instant while the pod with the most room does, so 1025 of 1448 resumes moved pods, each paying a full re-prefill and evicting others' prefixes. This is also what upstream's best-fit-decreasing placement does on multiple backends; the single-pod lanes of steps 08 to 10 could not show it. The decision (2026-09-18) was to run the main experiment with this behaviour unchanged and report it; an origin-only resume policy is the obvious follow-up.

## Results (2026-09-18, `results/rep-20260918-012350-c338-t1900`)

Nine cells complete (one rerun as a make-up after a transient API-server timeout). llm-d's default profile and plain session affinity are indistinguishable at 1020 tok/s, 0.002 hit rate and 123 s median TTFT: placement alone does nothing on an oversubscribed pool. The port reaches 1447 tok/s (1.42x, plus or minus 0.3 percent), a 0.248 steady-state hit rate and a 3.7 s median TTFT. Its hit rate is half the single-pod value because about 70 percent of resumes move the program to another pod, as observed in the calibration; an origin-only resume policy is the follow-up. Full write-up in `RESULTS.md`.
