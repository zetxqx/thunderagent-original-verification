# Weka replay A/B: paired analysis

## c=96

- window progress: default 1026 requests / 575493 output tokens; tr-decay 1635 / 1123435
- errors: default 20, tr-decay 31
- paired requests: 842 (of 1026 / 1635 successful)
- paired hit-ratio delta (tr - default): median +0.000, mean +0.305, >0 in 45% of pairs
- paired TTFT delta (tr - default): median -27.64s, p90 +0.78s

## c=128

- window progress: default 1056 requests / 588306 output tokens; tr-decay 1972 / 1263832
- errors: default 14, tr-decay 49
- paired requests: 766 (of 1056 / 1972 successful)
- paired hit-ratio delta (tr - default): median +0.000, mean +0.123, >0 in 31% of pairs
- paired TTFT delta (tr - default): median -28.05s, p90 +5.51s

## c=192

- window progress: default 1107 requests / 572208 output tokens; tr-decay 1893 / 1388139
- errors: default 15, tr-decay 36
- paired requests: 810 (of 1107 / 1893 successful)
- paired hit-ratio delta (tr - default): median +0.000, mean +0.393, >0 in 50% of pairs
- paired TTFT delta (tr - default): median -51.62s, p90 -0.06s
