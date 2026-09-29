| metric | llm-d default (no admission) | v3 port, most-room | v4 port, origin-only | minimal, half-life 1 s | minimal, half-life 10 s | minimal, half-life 10 s, sweep 1 s | lease, lease 30 s | lease, lease 5 s |
|---|---|---|---|---|---|---|---|---|
| output throughput (tok/s) | 1151 | 1382 | 1571 | 1752 | 1817 | 1867 | 1871 | 1863 |
| steady-state hit rate | 0.040 | 0.353 | 0.629 | 0.691 | 0.733 | 0.752 | 0.778 | 0.766 |
| prefill tokens computed (M) | 122.7 | 115.4 | 83.2 | 75.4 | 67.5 | 65.3 | 62.0 | 63.3 |
| TTFT p50 (s) | 8.2 | 2.3 | 1.3 | 0.9 | 0.6 | 0.5 | 0.5 | 0.6 |
| TTFT p90 (s) | 32.9 | 9.9 | 12.5 | 10.4 | 8.2 | 8.0 | 8.5 | 8.6 |
| TTFT p99 (s) | 50 | 66 | 102 | 149 | 129 | 119 | 227 | 164 |
| vLLM waiting, mean steady | 14.8 | 1.0 | 0.7 | 1.2 | 1.4 | 1.0 | 1.2 | 0.9 |
| goodput within SLO, TTFT <= 30 s (turns/s) | n/a | n/a | n/a | 1.50 | 1.63 | 1.64 | 1.60 | 1.69 |
| session SLO attainment, strict | n/a | n/a | n/a | 0.64 | 0.58 | 0.57 | 0.61 | 0.60 |
| per-session worst TTFT, p90 (s) | n/a | n/a | n/a | 268 | 319 | 367 | 435 | 386 |
| EPP pauses | n/a | 1912 | 1895 | 495 | 391 | 572 | 308 | 475 |
| EPP holds (paused + new) | 0 | 698 | 1079 | 349 | 265 | 397 | 227 | 362 |
| forced admissions | n/a | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| request errors | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| cell | `13-llm-d-router-sweep/.../epp-baseline-c128` | `13-llm-d-router-sweep/.../epp-thunder-c128` | `13-llm-d-router-sweep/.../epp-thunder-origin-c128` | `16-thunder-minimal-pool/.../epp-thunder-min-c128` | `16-thunder-minimal-pool/.../epp-thunder-min-hl10-c128` | `16-thunder-minimal-pool/.../epp-thunder-min-hl10-s1-c128` | `17-thunder-lease-pool/.../epp-thunder-lease-c128` | `17-thunder-lease-pool/.../epp-thunder-lease5-c128` |
