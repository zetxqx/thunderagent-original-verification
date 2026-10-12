# Each arm against `offload-baseline-60m` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                                                     |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:--------------------------------------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| llm-d-thunder-simplified (lease 10 s) + 400 GiB offload |     16 |              1.006 |             1.012 |           1.006 |               0.987 |      0.993 |      0.968 |            1.000 |      1.000 |                1.020 |
| llm-d-thunder-simplified (lease 10 s) + 400 GiB offload |     20 |              0.987 |             1.015 |           0.968 |               1.084 |      0.526 |      0.149 |            0.991 |      1.000 |                1.018 |
| llm-d-thunder-simplified (lease 10 s) + 400 GiB offload |     24 |              1.068 |             1.015 |           1.003 |               1.151 |      0.048 |      0.172 |            0.989 |      1.001 |                0.945 |
| llm-d-thunder-simplified (lease 10 s) + 400 GiB offload |     28 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
| llm-d-thunder-simplified (lease 10 s) + 400 GiB offload |     32 |              1.148 |             1.138 |           1.325 |               1.072 |      0.018 |      0.154 |            1.204 |      0.998 |                1.173 |
| llm-d-thunder-simplified (lease 10 s) + 400 GiB offload |     48 |              1.042 |             1.056 |           6.371 |               1.033 |      0.008 |      0.439 |            7.170 |      0.978 |                1.120 |
| llm-d-thunder-simplified (lease 10 s) + 400 GiB offload |     64 |              1.160 |             1.037 |          46.131 |               1.079 |      0.005 |      0.537 |           57.126 |      0.971 |                1.095 |
| llm-d-thunder-simplified (lease 10 s) + 400 GiB offload |    128 |              2.910 |             2.448 |         nan     |               2.427 |      0.001 |      0.125 |          nan     |      5.846 |                3.583 |
| llm-d-thunder-simplified (lease 10 s) + 400 GiB offload |    192 |              3.475 |             2.995 |         nan     |               2.685 |      0.000 |      0.040 |          nan     |      6.267 |                5.275 |
