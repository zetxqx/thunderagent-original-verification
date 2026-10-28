# Each arm against `qwen35-nooff-direct` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                         |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:----------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| llm-d thunder, CPU tier off |     24 |              0.999 |             1.002 |           0.999 |               1.001 |      1.034 |      1.082 |            1.000 |      1.000 |                0.999 |
| llm-d thunder, CPU tier off |     32 |              0.957 |             0.944 |           0.957 |               0.999 |      1.295 |      1.101 |            1.001 |      0.937 |                0.942 |
| llm-d thunder, CPU tier off |     48 |              1.070 |             1.024 |           1.129 |               1.021 |      0.422 |      0.613 |            1.112 |      1.564 |                1.072 |
| llm-d thunder, CPU tier off |     64 |              1.037 |             1.072 |         nan     |               0.989 |      0.249 |      0.464 |          nan     |      4.766 |                1.163 |
| llm-d thunder, CPU tier off |     96 |              0.942 |             1.013 |         152.993 |               0.976 |      0.137 |      0.592 |          134.287 |      3.162 |                1.121 |
