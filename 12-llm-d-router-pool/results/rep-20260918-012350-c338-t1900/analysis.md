# Step 12: three EPP policies on the 4-pod pool, 3 runs

Each cell shows mean (min-max) over runs; ratios are against the baseline arm.

| metric | epp-baseline | epp-affinity | epp-thunder | affinity / baseline | thunder / baseline |
|---|---|---|---|---|---|
| throughput (output tok/s) | 1020 (1018-1023) | 1023 (1020-1027) | 1447 (1443-1450) | 1.00x | 1.42x |
| requests completed | 4225 (4216-4234) | 4227 (4211-4253) | 6096 (6068-6120) | 1.00x | 1.44x |
| sessions that issued a request | 338 (338-338) | 338 (338-338) | 338 (338-338) | 1.00x | 1.00x |
| hit rate, whole window | 0.001 (0.001-0.001) | 0.001 (0.001-0.002) | 0.237 (0.229-0.241) | 1.09x | 173.20x |
| hit rate, first 10 min | 0.000 (0.000-0.000) | 0.000 (0.000-0.000) | 0.197 (0.189-0.202) | 1.01x | 2920.96x |
| hit rate, after 10 min (STEADY) | 0.002 (0.002-0.002) | 0.002 (0.002-0.002) | 0.248 (0.237-0.255) | 1.09x | 139.35x |
| TTFT p50 (s) | 122.9 (120.8-124.6) | 126.1 (123.9-129.0) | 3.7 (3.7-3.8) | 1.03x | 0.03x |
| TTFT p90 (s) | 217.2 (213.9-219.5) | 217.0 (214.0-218.5) | 113.3 (112.1-115.6) | 1.00x | 0.52x |
| TTFT p99 (s) | 259.5 (257.7-262.5) | 256.3 (253.9-257.9) | 1231.2 (1196.2-1262.5) | 0.99x | 4.74x |
| requests with zero cache hit | 0.90 (0.89-0.92) | 0.92 (0.91-0.93) | 0.67 (0.66-0.67) | 1.01x | 0.74x |
| errors | 1 (1-1) | 1 (1-1) | 25 (25-25) | 1.00x | 25.00x |
| pool in-flight requests (mean) | 122.9 (122.2-123.5) | 123.1 (122.5-123.7) | 129.0 (128.2-129.5) | 1.00x | 1.05x |
| pool KV usage (mean) | 0.86 (0.86-0.87) | 0.87 (0.86-0.87) | 0.79 (0.78-0.79) | 1.00x | 0.91x |
| EPP holds | - | - | 2399 (2364-2441) | - | - |
| EPP pauses | - | - | 4720 (4684-4789) | - | - |
| EPP resumes | - | - | 4470 (4433-4539) | - | - |
| EPP max programs paused | - | - | 250 (247-253) | - | - |
| EPP forced admissions | - | - | 55 (53-58) | - | - |

## Per pod (steady-state hit rate / mean KV / mean in flight), first run of each arm

| pod | epp-baseline | epp-affinity | epp-thunder |
|---|---|---|---|
| 10-100-15-20 | 0.00 / 0.87 / 33 | 0.00 / 0.86 / 30 | 0.23 / 0.79 / 32 |
| 10-100-15-21 | 0.00 / 0.86 / 28 | 0.00 / 0.86 / 30 | 0.23 / 0.78 / 32 |
| 10-100-2-6 | 0.00 / 0.87 / 32 | 0.00 / 0.87 / 31 | 0.25 / 0.78 / 32 |
| 10-100-3-12 | 0.00 / 0.87 / 30 | 0.01 / 0.87 / 31 | 0.23 / 0.78 / 32 |
