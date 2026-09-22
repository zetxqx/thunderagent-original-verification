# Step 10: repeated A/B through the EPP, 3 run(s) of the same configuration

Each cell shows mean (min-max) over runs.

| metric | epp-sticky | epp-thunder | ratio of means |
|---|---|---|---|
| throughput (output tok/s) | 227 (221-236) | 351 (327-367) | 1.54x |
| requests completed | 979 (965-987) | 1398 (1319-1469) | 1.43x |
| hit rate, whole window | 0.066 (0.030-0.111) | 0.486 (0.460-0.506) | 7.41x |
| hit rate, first 10 min (warm-up) | 0.225 (0.110-0.373) | 0.470 (0.372-0.521) | 2.09x |
| hit rate, after 10 min (STEADY) | 0.003 (0.002-0.003) | 0.489 (0.482-0.502) | 172.67x |
| TTFT p50 (s) | 49.4 (28.4-68.6) | 4.0 (3.6-4.6) | 0.08x |
| TTFT p90 (s) | 113.5 (88.2-136.6) | 22.0 (19.8-24.1) | 0.19x |
| TTFT p99 (s) | 146.6 (117.8-168.3) | 409.7 (352.9-462.7) | 2.79x |
| requests with zero cache hit | 0.86 (0.83-0.89) | 0.38 (0.36-0.41) | 0.44x |
| errors | 0 (0-0) | 6 (5-6) | - |
| EPP holds (paused + new) | 0 (0-0) | 648 (615-674) | - |
| EPP pauses | 0 (0-0) | 971 (938-1009) | - |
| EPP resumes | 0 (0-0) | 921 (886-952) | - |
| EPP max programs paused at once | 0 (0-0) | 50 (42-57) | - |
| EPP forced admissions | 0 (0-0) | 10 (8-11) | - |
| EPP mean queue wait (s) | - | 8.0 (3.6-13.6) | nanx |
| EPP max queue size | 0 (0-0) | 50 (40-60) | - |

## Against step 08 (Python router, same protocol)

| metric | py default | epp-sticky | py tr-decay | epp-thunder |
|---|---|---|---|---|
| throughput (output tok/s) | 221 | 227 (221-236) | 469 | 351 (327-367) |
| requests completed | 1059 | 979 (965-987) | 1994 | 1398 (1319-1469) |
| hit rate, after 10 min (STEADY) | 0.008 | 0.003 (0.002-0.003) | 0.685 | 0.489 (0.482-0.502) |
| TTFT p50 (s) | 52.7 | 49.4 (28.4-68.6) | 3.0 | 4.0 (3.6-4.6) |
| TTFT p90 (s) | 92.5 | 113.5 (88.2-136.6) | 18.0 | 22.0 (19.8-24.1) |

## Same sessions only (turns completed)

Restricted to the sessions BOTH arms of a run started, so the faster arm pulling extra traces out of the corpus cannot flatter it.

| run | shared sessions | turns: epp-sticky | turns: epp-thunder | ratio |
|---|---|---|---|---|
| r1 | n/a (the EPP state dump lists no program ids) | - | - | - |
| r2 | n/a (the EPP state dump lists no program ids) | - | - | - |
| r3 | n/a (the EPP state dump lists no program ids) | - | - | - |
