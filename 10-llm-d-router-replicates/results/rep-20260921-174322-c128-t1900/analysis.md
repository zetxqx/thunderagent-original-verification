# Step 10: replicated A/B through the EPP, 3 run(s) of the same configuration

Each cell shows mean (min-max) over replicates.

| metric | epp-sticky | epp-thunder | ratio of means |
|---|---|---|---|
| throughput (output tok/s) | - | - | - |
| requests completed | - | - | - |
| hit rate, whole window | - | - | - |
| hit rate, first 10 min (warm-up) | - | - | - |
| hit rate, after 10 min (STEADY) | - | - | - |
| TTFT p50 (s) | - | - | - |
| TTFT p90 (s) | - | - | - |
| requests with zero cache hit | - | - | - |
| errors | - | - | - |
| EPP holds (paused + new) | - | - | - |
| EPP pauses | - | - | - |
| EPP resumes | - | - | - |
| EPP max programs paused at once | - | - | - |
| EPP forced admissions | - | - | - |
| EPP mean queue wait (s) | - | - | - |
| EPP max queue size | - | - | - |

## Against step 08 (Python router, same protocol)

| metric | py default | epp-sticky | py tr-decay | epp-thunder |
|---|---|---|---|---|
| throughput (output tok/s) | 221 | - | 469 | - |
| requests completed | 1059 | - | 1994 | - |
| hit rate, after 10 min (STEADY) | 0.008 | - | 0.685 | - |
| TTFT p50 (s) | 52.7 | - | 3.0 | - |
| TTFT p90 (s) | 92.5 | - | 18.0 | - |

## Same sessions only (turns completed)

Restricted to the sessions BOTH arms of a replicate started, so the faster arm pulling extra traces out of the corpus cannot flatter it.

| replicate | shared sessions | turns: epp-sticky | turns: epp-thunder | ratio |
|---|---|---|---|---|
