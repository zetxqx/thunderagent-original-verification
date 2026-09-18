# Step 10: replicated A/B through the EPP, 1 run(s) of the same configuration

Each cell shows mean (min-max) over replicates.

| metric | epp-sticky | epp-thunder | ratio of means |
|---|---|---|---|
| throughput (output tok/s) | - | 445 | - |
| requests completed | - | 519 | - |
| hit rate, whole window | - | 0.343 | - |
| hit rate, first 10 min (warm-up) | - | 0.363 | - |
| hit rate, after 10 min (STEADY) | - | 0.233 | - |
| TTFT p50 (s) | - | 4.3 | - |
| TTFT p90 (s) | - | 30.5 | - |
| requests with zero cache hit | - | 0.55 | - |
| errors | - | 0 | - |
| EPP holds (paused + new) | - | 217 | - |
| EPP pauses | - | 363 | - |
| EPP resumes | - | 325 | - |
| EPP max programs paused at once | - | 38 | - |
| EPP forced admissions | - | 0 | - |
| EPP mean queue wait (s) | - | 13.4 | - |
| EPP max queue size | - | 38 | - |

## Against step 08 (Python router, same protocol)

| metric | py default | epp-sticky | py tr-decay | epp-thunder |
|---|---|---|---|---|
| throughput (output tok/s) | 221 | - | 469 | 445 |
| requests completed | 1059 | - | 1994 | 519 |
| hit rate, after 10 min (STEADY) | 0.008 | - | 0.685 | 0.233 |
| TTFT p50 (s) | 52.7 | - | 3.0 | 4.3 |
| TTFT p90 (s) | 92.5 | - | 18.0 | 30.5 |

## Same sessions only (turns completed)

Restricted to the sessions BOTH arms of a replicate started, so the faster arm pulling extra traces out of the corpus cannot flatter it.

| replicate | shared sessions | turns: epp-sticky | turns: epp-thunder | ratio |
|---|---|---|---|---|
