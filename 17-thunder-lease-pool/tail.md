# Where the TTFT tail comes from

Per request: hold = EPP dispatch minus EPP arrival (flow control); engine = TTFT minus hold. Class from the client side: first request of a session = new; later request held > 1 s = paused; else admitted. Tail = requests at or above their cell's TTFT p99, pooled over three cells per arm.

| | minimal, half-life 10 s, sweep 1 s (step 16) | lease 30 s | lease 5 s |
|---|---|---|---|
| cells | epp-thunder-min-hl10-s1-c128, epp-thunder-min-hl10-s1-c128-r2, epp-thunder-min-hl10-s1-c128-r3 | epp-thunder-lease-c128, epp-thunder-lease-c128-r2, epp-thunder-lease-c128-r3 | epp-thunder-lease5-c128, epp-thunder-lease5-c128-r2, epp-thunder-lease5-c128-r3 |
| matched share of requests | 1.000-1.000 | 1.000-1.000 | 1.000-1.000 |
| TTFT p99 per cell (s) | 119 / 133 / 171 | 229 / 280 / 221 | 165 / 130 / 122 |
| tail requests (TTFT >= its cell's p99), all cells | 141 | 135 | 134 |
| tail share, class paused | 1.00 | 1.00 | 1.00 |
| tail share, class new | 0.00 | 0.00 | 0.00 |
| tail share, class admitted | 0.00 | 0.00 | 0.00 |
| tail: hold share of TTFT, median | 0.99 | 0.99 | 0.98 |
| tail: hold p50 / p90 (s) | 459 / 1295 | 665 / 1473 | 383 / 1290 |
| tail: engine time (TTFT - hold) p50 / p90 (s) | 5.0 / 10.1 | 3.9 / 19.9 | 5.6 / 15.9 |
| tail: prompt tokens, median (k) | 87 | 73 | 90 |
| tail: cache hit share of prompt, median | 0.00 | 0.00 | 0.00 |
| tail: idle gap before the request, median (s) | 3.2 | 4.1 | 5.5 |
| tail: start minute in the window, p10 / p50 / p90 | 4 / 14 / 26 | 3 / 9 / 23 | 4 / 14 / 24 |
| paused requests (held > 1 s), per cell | 353 | 220 | 341 |
| paused requests: hold p50 / p90 / p99 (s) | 13 / 248 / 1349 | 26 / 671 / 1611 | 15 / 199 / 1393 |
| paused requests: share held over 60 s / over 120 s | 0.19 / 0.14 | 0.37 / 0.29 | 0.21 / 0.14 |
| paused requests: prompt tokens, median (k) | 67 | 60 | 68 |
| paused requests: cache hit share, median | 0.00 | 0.00 | 0.00 |
| paused (steady), prompt at or below the median: hold p50 / p90 (s) | 9 / 40 | 13 / 147 | 11 / 57 |
| paused (steady), prompt above the median: hold p50 / p90 (s) | 26 / 359 | 59 / 589 | 25 / 405 |
| steady pauses / releases of paused sessions, three cells | 1193 / 1014 | 693 / 561 | 1071 / 910 |
| releases of paused sessions in a 2 s interval that also has a pause | 0.90 | 0.81 | 0.91 |
| EPP queue, mean steady / admission rate (paused + new, per s) | 27.0 / 0.264 | 32.4 / 0.152 | 24.8 / 0.239 |
| Little's law mean wait, queue / rate (s) | 102 | 213 | 104 |
| measured mean hold of paused requests, steady (s) | 72 | 123 | 74 |
| holds > 60 s released 28-32 s after a session's last response (random times) | 0.06 (0.10) | 0.08 (0.11) | 0.06 (0.10) |
| admitted requests (steady): engine time p99 (s) | 11.3 | 17.1 | 15.1 |
| all requests (steady): hold p99 (s) | 172 | 204 | 185 |
