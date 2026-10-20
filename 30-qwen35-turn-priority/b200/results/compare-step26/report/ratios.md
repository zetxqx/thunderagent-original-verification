# Each arm against `qwen35-direct` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                           |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:------------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| TP=4 thunder-agent lease 10 s |     32 |              0.996 |             0.997 |           0.996 |               0.972 |      1.058 |      0.987 |            1.000 |      1.000 |                0.997 |
| TP=4 thunder-agent lease 10 s |     48 |              1.002 |             0.999 |           1.001 |               1.019 |      0.938 |      0.642 |            0.999 |      0.998 |                0.998 |
| TP=4 thunder-agent lease 10 s |     64 |              0.965 |             0.960 |           0.934 |               0.971 |      0.148 |      0.460 |            0.981 |      0.998 |                0.965 |
| TP=4 turn-priority (v1.0.0)   |     32 |              1.012 |             1.010 |           1.012 |               1.018 |      1.018 |      1.037 |            1.000 |      1.000 |                1.014 |
| TP=4 turn-priority (v1.0.0)   |     48 |              1.026 |             1.016 |           1.026 |               1.104 |      1.187 |      1.391 |            1.000 |      0.999 |                1.018 |
| TP=4 turn-priority (v1.0.0)   |     64 |              1.031 |             1.025 |           1.031 |               0.953 |      0.999 |      1.273 |            1.000 |      1.001 |                1.026 |
