# Each arm against `glm52-1p1d-baseline` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                               |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:----------------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| GLM-5.2 1P1D + thunder lease 10 s |     48 |              0.924 |             0.683 |           0.891 |               1.052 |      0.050 |      0.237 |            0.977 |      0.987 |                0.946 |
| GLM-5.2 1P1D + thunder lease 10 s |     64 |              1.029 |             0.706 |           1.309 |               0.942 |      0.025 |      0.206 |            1.255 |      0.977 |                1.189 |
