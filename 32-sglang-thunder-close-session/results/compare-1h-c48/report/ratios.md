# Each arm against `sglang-baseline-lru-1h` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                              |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   completed requests |
|:---------------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|---------------------:|
| ThunderAgent (closeSession=true) |     48 |              0.960 |             0.987 |           0.949 |               0.909 |      1.080 |      1.608 |            0.996 |                0.979 |
