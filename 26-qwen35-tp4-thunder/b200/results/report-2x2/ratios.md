# Each arm against `qwen35-nooff-direct` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                         |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:----------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| no router, CPU tier on      |     32 |              1.867 |             1.767 |           1.868 |               5.369 |      0.294 |      0.081 |            1.000 |      1.547 |                1.720 |
| no router, CPU tier on      |     48 |              5.285 |             3.912 |           6.216 |               4.548 |      0.020 |      0.055 |            1.175 |     33.132 |                3.678 |
| no router, CPU tier on      |     64 |              4.954 |             3.999 |         nan     |               3.743 |      0.109 |      0.153 |          nan     |    102.095 |                3.921 |
| llm-d thunder, CPU tier off |     24 |              0.999 |             1.002 |           0.999 |               1.001 |      1.034 |      1.082 |            1.000 |      1.000 |                0.999 |
| llm-d thunder, CPU tier off |     32 |              0.957 |             0.944 |           0.957 |               0.999 |      1.295 |      1.101 |            1.001 |      0.937 |                0.942 |
| llm-d thunder, CPU tier off |     48 |              1.070 |             1.024 |           1.129 |               1.021 |      0.422 |      0.613 |            1.112 |      1.564 |                1.072 |
| llm-d thunder, CPU tier off |     64 |              1.037 |             1.072 |         nan     |               0.989 |      0.249 |      0.464 |          nan     |      4.766 |                1.163 |
| llm-d thunder, CPU tier off |     96 |              0.942 |             1.013 |         152.993 |               0.976 |      0.137 |      0.592 |          134.287 |      3.162 |                1.121 |
| llm-d thunder, CPU tier on  |     32 |              1.860 |             1.761 |           1.860 |               5.217 |      0.311 |      0.080 |            1.001 |      1.547 |                1.715 |
| llm-d thunder, CPU tier on  |     48 |              5.295 |             3.908 |           6.222 |               4.632 |      0.019 |      0.035 |            1.173 |     33.080 |                3.671 |
| llm-d thunder, CPU tier on  |     64 |              4.781 |             3.839 |         nan     |               3.636 |      0.016 |      0.070 |          nan     |    101.925 |                3.782 |
