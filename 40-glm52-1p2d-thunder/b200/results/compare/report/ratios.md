# Each arm against `glm52-1p2d-baseline` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm            |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:---------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| 1P2D + thunder |     32 |              0.977 |             0.941 |           0.951 |               1.016 |      0.535 |      0.727 |            0.989 |      1.000 |                0.999 |
| 1P2D + thunder |     48 |              0.937 |             0.837 |           0.871 |               1.016 |      0.220 |      0.702 |            0.960 |      0.994 |                0.996 |
| 1P2D + thunder |     64 |              1.136 |             0.845 |           1.128 |               0.952 |      0.101 |      0.353 |            1.009 |      0.987 |                1.226 |
| 1P2D + thunder |     96 |              2.137 |             1.528 |          53.527 |               0.836 |      0.027 |      0.086 |           29.821 |      1.020 |                2.568 |
| 1P2D + thunder |    144 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
