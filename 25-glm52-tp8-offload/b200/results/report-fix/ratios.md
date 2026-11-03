# Each arm against `fix-direct` at the same concurrency

Ratio of means over the steady state (ss_* columns). Treat ratios within about 0.95 to 1.05 as ties (cell-to-cell variance was 2% to 6%).

| arm                                               |   conc |   output tok/s/GPU |   total tok/s/GPU |   goodput tok/s |   P90 interactivity |   TTFT p50 |   TTFT p90 |   turn SLO share |   hit rate |   completed requests |
|:--------------------------------------------------|-------:|-------------------:|------------------:|----------------:|--------------------:|-----------:|-----------:|-----------------:|-----------:|---------------------:|
| TP=8, no-router unfixed (60m)                     |     24 |              0.835 |             0.995 |           0.835 |               0.859 |      1.143 |      1.088 |            1.000 |      1.008 |                1.730 |
| TP=8, no-router unfixed (60m)                     |     32 |              0.879 |             0.984 |           0.876 |               0.749 |      0.961 |      0.984 |            1.001 |      1.005 |                1.979 |
| TP=8, no-router unfixed (60m)                     |     48 |              0.964 |             0.954 |           0.866 |               0.743 |      1.036 |      1.146 |            0.918 |      1.005 |                1.943 |
| TP=8, thunder lease 10 s unfixed (60m)            |     24 |              0.856 |             0.984 |           0.832 |               1.228 |      0.114 |      0.274 |            0.982 |      1.006 |                1.835 |
| TP=8, thunder lease 10 s unfixed (60m)            |     32 |              1.014 |             1.000 |           0.971 |               1.197 |      0.033 |      0.205 |            0.975 |      0.999 |                2.431 |
| TP=8, thunder lease 10 s unfixed (60m)            |     48 |              1.094 |             0.829 |           1.088 |               0.954 |      0.016 |      0.210 |            1.027 |      0.976 |                2.375 |
| TP=8, thunder lease 10 s + bounded-load fix (30m) |     24 |              1.051 |             1.028 |           1.018 |               1.231 |      0.099 |      0.174 |            0.989 |      0.999 |                1.095 |
| TP=8, thunder lease 10 s + bounded-load fix (30m) |     32 |              1.184 |             1.028 |           1.149 |               1.064 |      0.031 |      0.109 |            0.981 |      0.994 |                1.325 |
| TP=8, thunder lease 10 s + bounded-load fix (30m) |     48 |              1.437 |             1.059 |           1.461 |               0.963 |      0.015 |      0.094 |            1.046 |      0.991 |                1.503 |
