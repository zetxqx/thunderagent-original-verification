# Weka replay A/B: paired analysis

## c=8

- window progress: default 1403 requests / 1305448 output tokens; tr-decay 1408 / 1327852
- errors: default 0, tr-decay 0
- paired requests: 987 (of 1403 / 1408 successful)
- per-request cached_tokens unavailable (vLLM lacks --enable-prompt-tokens-details); use the pod-counter hit-rate time series + paired TTFT instead
- paired TTFT delta (tr - default): median +0.01s, p90 +0.17s

## c=24

- window progress: default 1494 requests / 1410142 output tokens; tr-decay 1482 / 1394922
- errors: default 1, tr-decay 0
- paired requests: 1059 (of 1494 / 1482 successful)
- per-request cached_tokens unavailable (vLLM lacks --enable-prompt-tokens-details); use the pod-counter hit-rate time series + paired TTFT instead
- paired TTFT delta (tr - default): median +0.00s, p90 +0.22s
