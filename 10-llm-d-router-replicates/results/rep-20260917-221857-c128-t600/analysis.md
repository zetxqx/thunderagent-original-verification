# Step 10: repeated A/B through the EPP, 3 run(s) of the same configuration

Each cell shows mean (min-max) over runs.

| metric | epp-sticky | epp-thunder | ratio of means |
|---|---|---|---|
| throughput (output tok/s) | 225 (215-230) | 405 (375-434) | 1.80x |
| requests completed | 1075 (1029-1154) | 1706 (1525-1799) | 1.59x |
| hit rate, whole window | 0.082 (0.051-0.123) | 0.486 (0.428-0.519) | 5.95x |
| hit rate, first 10 min (warm-up) | 0.275 (0.175-0.404) | 0.489 (0.337-0.565) | 1.78x |
| hit rate, after 10 min (STEADY) | 0.010 (0.009-0.011) | 0.483 (0.453-0.503) | 47.43x |
| TTFT p50 (s) | 48.5 (43.9-54.3) | 3.3 (2.9-4.0) | 0.07x |
| TTFT p90 (s) | 80.2 (70.1-86.2) | 17.9 (15.6-22.4) | 0.22x |
| TTFT p99 (s) | 90.6 (77.8-97.1) | 237.4 (199.0-275.7) | 2.62x |
| requests with zero cache hit | 0.85 (0.80-0.89) | 0.41 (0.38-0.47) | 0.48x |
| errors | 18 (16-19) | 39 (37-44) | 2.23x |
| EPP holds (paused + new) | 0 (0-0) | 744 (726-771) | - |
| EPP pauses | 0 (0-0) | 1187 (1118-1247) | - |
| EPP resumes | 0 (0-0) | 1107 (1036-1162) | - |
| EPP max programs paused at once | 0 (0-0) | 81 (75-85) | - |
| EPP forced admissions | 0 (0-0) | 0 (0-0) | - |
| EPP mean queue wait (s) | - | 5.8 (3.2-9.1) | nanx |
| EPP max queue size | 0 (0-0) | 40 (36-42) | - |

## Against step 08 (Python router, same protocol)

| metric | py default | epp-sticky | py tr-decay | epp-thunder |
|---|---|---|---|---|
| throughput (output tok/s) | 221 | 225 (215-230) | 469 | 405 (375-434) |
| requests completed | 1059 | 1075 (1029-1154) | 1994 | 1706 (1525-1799) |
| hit rate, after 10 min (STEADY) | 0.008 | 0.010 (0.009-0.011) | 0.685 | 0.483 (0.453-0.503) |
| TTFT p50 (s) | 52.7 | 48.5 (43.9-54.3) | 3.0 | 3.3 (2.9-4.0) |
| TTFT p90 (s) | 92.5 | 80.2 (70.1-86.2) | 18.0 | 17.9 (15.6-22.4) |

## Same sessions only (turns completed)

Restricted to the sessions BOTH arms of a run started, so the faster arm pulling extra traces out of the corpus cannot flatter it.

| run | shared sessions | turns: epp-sticky | turns: epp-thunder | ratio |
|---|---|---|---|---|
| r1 | n/a (the EPP state dump lists no program ids) | - | - | - |
| r2 | n/a (the EPP state dump lists no program ids) | - | - | - |
| r3 | n/a (the EPP state dump lists no program ids) | - | - | - |
