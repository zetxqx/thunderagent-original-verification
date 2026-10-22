# Each arm against `sglang-baseline-lru` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                              |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   completed requests |
|:---------------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|---------------------:|
| ThunderAgent (closeSession=true) |     16 |              1.117 |             1.117 |           1.117 |               1.035 |      1.056 |      1.195 |            1.003 |                1.103 |
| ThunderAgent (closeSession=true) |     24 |              1.001 |             1.003 |           1.001 |               0.906 |      1.014 |      1.136 |            0.998 |                1.016 |
| ThunderAgent (closeSession=true) |     32 |              1.030 |             1.047 |           1.030 |               1.028 |      1.018 |      1.250 |            0.997 |                1.039 |
| ThunderAgent (closeSession=true) |     48 |              0.894 |             0.939 |           0.886 |               0.724 |      1.146 |      4.282 |            0.987 |                0.910 |
