# Step 12: three EPP policies on the 4-pod pool, 1 replicate(s)

Each cell shows mean (min-max) over replicates; ratios are against the baseline arm.

| metric | epp-baseline | epp-affinity | epp-thunder | affinity / baseline | thunder / baseline |
|---|---|---|---|---|---|
| throughput (output tok/s) | - | - | 1574 | - | - |
| requests completed | - | - | 2210 | - | - |
| sessions that issued a request | - | - | 338 | - | - |
| hit rate, whole window | - | - | 0.176 | - | - |
| hit rate, first 10 min | - | - | 0.193 | - | - |
| hit rate, after 10 min (STEADY) | - | - | 0.115 | - | - |
| TTFT p50 (s) | - | - | 3.7 | - | - |
| TTFT p90 (s) | - | - | 57.8 | - | - |
| requests with zero cache hit | - | - | 0.74 | - | - |
| errors | - | - | 0 | - | - |
| pool in-flight requests (mean) | - | - | 151.1 | - | - |
| pool KV usage (mean) | - | - | 0.75 | - | - |
| EPP holds | - | - | 678 | - | - |
| EPP pauses | - | - | 1697 | - | - |
| EPP resumes | - | - | 1448 | - | - |
| EPP max programs paused | - | - | 249 | - | - |
| EPP forced admissions | - | - | 0 | - | - |

## Per pod (steady-state hit rate / mean KV / mean in flight), first replicate of each arm

| pod | epp-baseline | epp-affinity | epp-thunder |
|---|---|---|---|
| 10-100-15-20 | - | - | 0.13 / 0.75 / 36 |
| 10-100-15-21 | - | - | 0.11 / 0.75 / 38 |
| 10-100-2-6 | - | - | 0.09 / 0.75 / 38 |
| 10-100-3-12 | - | - | 0.13 / 0.75 / 38 |
