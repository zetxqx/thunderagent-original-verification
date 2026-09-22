# Step 14: turn-priority (PR 2116, upstream defaults) vs step 10's sticky and thunder lanes

Single pod per lane, c=128, 45-minute window, client timeout 1900 s, inference-perf v0.7.0 (permit bug: about half of the sessions active, the same for every arm). Cells: mean (min-max) over replicates. sticky and thunder from `rep-20260917-173839-c128-t1900`; turn-priority from `rep-20260921-174322-c128-t1900`.

| metric | epp-sticky | epp-thunder | epp-turnprio-005-ttl60 | turnprio / sticky | turnprio / thunder |
|---|---|---|---|---|---|
| throughput (output tok/s) | 227 (221-236) | 351 (327-367) | 264 (252-273) | 1.16x | 0.75x |
| requests completed | 979 (965-987) | 1398 (1319-1469) | 1063 (1032-1086) | 1.09x | 0.76x |
| hit rate, steady state (after 10 min) | 0.003 (0.002-0.003) | 0.489 (0.482-0.502) | 0.047 (0.040-0.055) | 16.64x | 0.10x |
| TTFT p50 (s) | 49.4 (28.4-68.6) | 4.0 (3.6-4.6) | 40.2 (37.3-41.8) | 0.81x | 10.03x |
| TTFT p90 (s) | 113.5 (88.2-136.6) | 22.0 (19.8-24.1) | 76.9 (75.0-79.1) | 0.68x | 3.50x |
| in flight, mean | 30 (29-30) | 30 (29-31) | 29 (28-30) | 0.98x | 0.97x |
| waiting inside vLLM, mean after 10 min | 20 (14-26) | 0 (0-0) | 8 (8-9) | 0.40x | 24.94x |
| KV usage, mean | 0.91 (0.91-0.92) | 0.89 (0.88-0.89) | 0.87 (0.86-0.87) | 0.95x | 0.98x |
| failed requests | 0 (0-0) | 6 (5-6) | 45 (43-46) | - | 7.88x |
| of which 429 (shed by the flow controller) | 0 (0-0) | 0 (0-0) | 44 (43-45) | - | - |

Turn-priority failure labels summed over its cells: `429 - Rate Limit`: 133, `503 - Service Unavailable`: 1
