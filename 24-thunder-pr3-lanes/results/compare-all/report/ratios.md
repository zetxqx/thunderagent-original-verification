# Each arm against `baseline-60m` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                         |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:----------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| no router + 400 GiB offload |     32 |              2.728 |             2.563 |         166.245 |               3.475 |      0.341 |      0.443 |           64.712 |      8.392 |                2.061 |
| no router + 400 GiB offload |     64 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
| no router + 400 GiB offload |     96 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
| no router + 400 GiB offload |    128 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
| no router + 400 GiB offload |    192 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
| thunder + 400 GiB offload   |     32 |              3.067 |             2.914 |         222.734 |               3.862 |      0.005 |      0.059 |           78.315 |      8.386 |                2.423 |
| thunder + 400 GiB offload   |     64 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
| thunder + 400 GiB offload   |     96 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
| thunder + 400 GiB offload   |    128 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
| thunder + 400 GiB offload   |    192 |            nan     |           nan     |         nan     |             nan     |    nan     |    nan     |          nan     |    nan     |              nan     |
| thunder gate (PR3)          |     12 |              0.996 |             0.997 |           0.996 |               0.992 |      1.031 |      1.067 |            1.000 |      1.000 |                1.000 |
| thunder gate (PR3)          |     16 |              1.217 |             1.135 |           1.214 |               1.365 |      0.957 |      0.343 |            0.998 |      1.070 |                1.130 |
| thunder gate (PR3)          |     20 |              1.555 |             1.602 |           1.573 |               2.684 |      0.550 |      0.129 |            1.035 |      1.534 |                1.663 |
| thunder gate (PR3)          |     24 |              2.330 |             1.985 |           3.044 |               2.421 |      0.016 |      0.240 |            1.230 |      6.110 |                1.844 |
| thunder gate (PR3)          |     32 |              1.753 |             1.870 |         120.298 |               1.623 |      0.006 |      0.312 |           75.486 |      6.159 |                1.585 |
