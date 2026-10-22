# Each arm against `qwen35-1p1d-baseline` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                       |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:--------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| 1P1D + thunder lease 10 s |     64 |              0.953 |             0.950 |           0.945 |               1.047 |      0.983 |      1.191 |            0.996 |      0.996 |                0.962 |
| 1P1D + thunder lease 10 s |     96 |              1.234 |             1.216 |           1.227 |               0.937 |      0.130 |      0.283 |            1.008 |      1.028 |                1.216 |
| 1P1D + thunder lease 10 s |    128 |              4.562 |             4.973 |         272.198 |               0.469 |      0.015 |      0.048 |          120.018 |      1.679 |                4.397 |
