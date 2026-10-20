# Each arm against `dep8-affinity` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                                     |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:----------------------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| DEP=8 no-router (vLLM DP LB)            |     24 |              0.464 |             0.405 |           0.442 |               0.248 |      4.255 |      3.971 |            0.981 |      0.655 |                0.510 |
| DEP=8 no-router (vLLM DP LB)            |     32 |              0.481 |             0.427 |           0.428 |               0.445 |      3.549 |      3.140 |            0.936 |      0.598 |                0.551 |
| DEP=8 no-router (vLLM DP LB)            |     48 |              0.807 |             0.718 |           0.977 |               0.775 |      0.412 |      0.918 |            1.123 |      0.679 |                0.835 |
| DEP=8 no-router (vLLM DP LB)            |     64 |              0.991 |             0.941 |           1.550 |               0.740 |      0.622 |      0.866 |            1.618 |      0.803 |                1.085 |
| DEP=8 thunder-agent lease 10 s          |     24 |              1.157 |             1.151 |           1.163 |               1.928 |      0.952 |      0.619 |            1.000 |      1.051 |                1.171 |
| DEP=8 thunder-agent lease 10 s          |     32 |              1.557 |             1.595 |           1.563 |               3.434 |      0.655 |      0.322 |            1.012 |      1.108 |                1.573 |
| DEP=8 thunder-agent lease 10 s          |     48 |              4.046 |             3.168 |           6.227 |               5.096 |      0.050 |      0.031 |            1.427 |      1.483 |                3.011 |
| DEP=8 thunder-agent lease 10 s          |     64 |              6.832 |             5.306 |          27.151 |               3.103 |      0.008 |      0.026 |            4.333 |      2.052 |                5.908 |
| DEP=8 turn-priority + affinity (v1.0.0) |     24 |              1.071 |             1.080 |           1.075 |               1.337 |      1.023 |      0.881 |            0.999 |      1.024 |                1.083 |
| DEP=8 turn-priority + affinity (v1.0.0) |     32 |              1.157 |             1.141 |           1.140 |               1.409 |      0.876 |      1.457 |            0.982 |      1.049 |                1.137 |
| DEP=8 turn-priority + affinity (v1.0.0) |     48 |              1.987 |             1.790 |           2.633 |               1.609 |      0.361 |      0.576 |            1.230 |      1.343 |                1.590 |
| DEP=8 turn-priority + affinity (v1.0.0) |     64 |              1.181 |             1.214 |           0.600 |               0.861 |      1.551 |      0.786 |            0.544 |      1.057 |                1.111 |
