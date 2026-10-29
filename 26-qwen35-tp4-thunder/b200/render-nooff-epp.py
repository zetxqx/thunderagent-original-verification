#!/usr/bin/env python3
"""Render a thunder lane EPP for step 26 part 2 (CPU tier off) from step 26's rendered lane-epp-qd.yaml.

Same EPP image, envoy config (ext_proc message timeout 2400 s, upstream idle timeout 4 s) and thunder
settings as step 26 (utilThreshold 1.0, idle lease 10 s, forced admission after 1800 s, no
cacheInfoSpec). Only the lane name, the one endpoint (server Service ClusterIP) and capacityTokens
(= that server's vLLM kv_cache_size_tokens) change.

  ./render-nooff-epp.py <lane> <server> <cluster-ip> <capacity-tokens> [util-threshold] > lane-epp-<lane>.yaml

util-threshold (default 1.0) scales the gate capacity: 0.8 admits sessions up to 80% of capacityTokens.
"""
import os
import re
import sys
from pathlib import Path

lane, server, ip, cap = sys.argv[1:5]
util = sys.argv[5] if len(sys.argv) > 5 else "1.0"
assert re.fullmatch(r"[a-z0-9]+", lane), lane
assert re.fullmatch(r"\d+", cap), cap
assert re.fullmatch(r"(0\.\d+|1\.0)", util), util
src = (Path(__file__).resolve().parent / "lane-epp-qd.yaml").read_text()
for old in ["agentx-epp-qd-", "agentx-lane=qd", "qwen35-tp4-d", '"10.0.47.250"', "capacityTokens: 4780827",
            "capacity 4780827 tokens", "lane qd (", "utilThreshold: 1.0"]:
    assert old in src, old
out = (src.replace("agentx-epp-qd-", f"agentx-epp-{lane}-")
          .replace("agentx-lane=qd", f"agentx-lane={lane}")
          .replace("qwen35-tp4-d", server)
          .replace('"10.0.47.250"', f'"{ip}"')
          .replace("capacityTokens: 4780827", f"capacityTokens: {cap}")
          .replace("capacity 4780827 tokens", f"capacity {cap} tokens")
          .replace("lane qd (", f"lane {lane} (")
          .replace("utilThreshold: 1.0", f"utilThreshold: {util}")
          .replace("for step 26,", "for step 26 part 2 (CPU tier off),"))
for left in ["agentx-epp-qd-", "agentx-lane=qd", "qwen35-tp4-d", "10.0.47.250"]:
    assert left not in out, left
# EPP_SMALL_REQUESTS=1 lowers the envoy and EPP containers' resource requests (not limits) from 1 CPU / 2Gi to
# 250m / 1Gi, so more lane EPPs fit next to the clients on node pool pool-1. Both use far less (step 26 part 2,
# 2026-10-29: pool-1 nodes at about 1 core in use). Behavior is unchanged.
if os.environ.get("EPP_SMALL_REQUESTS") == "1":
    big = 'requests:\n              cpu: "1"\n              memory: 2Gi'
    assert out.count(big) == 2, out.count(big)
    out = out.replace(big, 'requests:\n              cpu: 250m\n              memory: 1Gi')
sys.stdout.write(out)
