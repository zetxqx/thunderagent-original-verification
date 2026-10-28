#!/usr/bin/env python3
"""Render a thunder lane EPP for step 26 part 2 (CPU tier off) from step 26's rendered lane-epp-qd.yaml.

Same EPP image, envoy config (ext_proc message timeout 2400 s, upstream idle timeout 4 s) and thunder
settings as step 26 (utilThreshold 1.0, idle lease 10 s, forced admission after 1800 s, no
cacheInfoSpec). Only the lane name, the one endpoint (server Service ClusterIP) and capacityTokens
(= that server's vLLM kv_cache_size_tokens) change.

  ./render-nooff-epp.py <lane> <server> <cluster-ip> <capacity-tokens> > lane-epp-<lane>.yaml
"""
import re
import sys
from pathlib import Path

lane, server, ip, cap = sys.argv[1:5]
assert re.fullmatch(r"[a-z0-9]+", lane), lane
assert re.fullmatch(r"\d+", cap), cap
src = (Path(__file__).resolve().parent / "lane-epp-qd.yaml").read_text()
for old in ["agentx-epp-qd-", "agentx-lane=qd", "qwen35-tp4-d", '"10.0.47.250"', "capacityTokens: 4780827",
            "capacity 4780827 tokens", "lane qd ("]:
    assert old in src, old
out = (src.replace("agentx-epp-qd-", f"agentx-epp-{lane}-")
          .replace("agentx-lane=qd", f"agentx-lane={lane}")
          .replace("qwen35-tp4-d", server)
          .replace('"10.0.47.250"', f'"{ip}"')
          .replace("capacityTokens: 4780827", f"capacityTokens: {cap}")
          .replace("capacity 4780827 tokens", f"capacity {cap} tokens")
          .replace("lane qd (", f"lane {lane} (")
          .replace("for step 26,", "for step 26 part 2 (CPU tier off),"))
for left in ["agentx-epp-qd-", "agentx-lane=qd", "qwen35-tp4-d", "10.0.47.250"]:
    assert left not in out, left
sys.stdout.write(out)
