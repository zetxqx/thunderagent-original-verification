# Each arm against `glm52-2p1d-baseline` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                         |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:----------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| 2P1D + thunder (D capacity) |     32 |              0.872 |             0.743 |           0.832 |               1.137 |      0.153 |      0.315 |            0.976 |      0.997 |                0.923 |
| 2P1D + thunder (D capacity) |     48 |              0.965 |             0.734 |           0.936 |               1.130 |      0.054 |      0.213 |            0.986 |      0.994 |                1.027 |
| 2P1D + thunder (D capacity) |     64 |              1.171 |             0.773 |           1.535 |               1.056 |      0.022 |      0.111 |            1.303 |      0.991 |                1.337 |
| 2P1D + thunder (D capacity) |     96 |              1.080 |             0.786 |           2.883 |               1.030 |      0.014 |      0.084 |            2.717 |      0.984 |                1.319 |
| 2P1D + thunder (D capacity) |    144 |              1.054 |             0.893 |          36.121 |               1.347 |      0.006 |      0.137 |           65.225 |      0.967 |                1.215 |
