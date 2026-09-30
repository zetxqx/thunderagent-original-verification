"""Step 20 smoke checks 4 and 5, run inside one vLLM pod (stdin of kubectl exec).

1. Clear both tiers, send a fresh ~50k-token prompt (one output token).
2. Clear only the GPU prefix cache and send the same prompt: its prefix must
   come back from the CPU tier (external hits, cached_tokens) and much faster.
3. Clear both tiers (reset_external=true) and send it again: no hits at all.

Prints one JSON object. The prompt starts with a random tag, so no earlier
request can share its prefix.
"""
import json
import random
import sys
import time
import urllib.request

BASE = "http://localhost:8000"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8"
WORDS = ("time year people way day man thing woman life child world school state family student "
         "group country problem hand part place case week company system program question work "
         "government number night point home water room mother area money story fact month lot "
         "right study book eye job word business issue side kind head house service friend father "
         "power hour game line end member law car city community name president team minute idea").split()


def post(path, body=None, timeout=900):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method="POST", headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=timeout).read() or b"null")


def counters():
    text = urllib.request.urlopen(BASE + "/metrics", timeout=60).read().decode()
    out = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        name = line.split("{", 1)[0].split(" ", 1)[0]
        for key in ("vllm:prefix_cache_hits", "vllm:prefix_cache_queries", "vllm:external_prefix_cache_hits",
                    "vllm:external_prefix_cache_queries", "vllm:kv_offload_store_bytes", "vllm:kv_offload_load_bytes"):
            if name in (key, key + "_total"):
                out[key] = out.get(key, 0.0) + float(line.rsplit(" ", 1)[1])
    return out


def reset(external):
    path = "/reset_prefix_cache" + ("?reset_external=true" if external else "")
    for _ in range(60):
        r = post(path)
        if isinstance(r, dict) and r.get("success") is True:
            return True
        time.sleep(2)
    return False


def complete(prompt):
    t = time.monotonic()
    r = post("/v1/completions", {"model": MODEL, "prompt": prompt, "max_tokens": 1, "temperature": 0})
    u = r.get("usage") or {}
    return {"seconds": time.monotonic() - t, "prompt_tokens": u.get("prompt_tokens"),
            "cached_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0}


def delta(a, b):
    return {k: b.get(k, 0.0) - a.get(k, 0.0) for k in set(a) | set(b)}


rnd = random.Random(time.time_ns())
prompt = f"[step20 probe {rnd.getrandbits(64):016x}] " + " ".join(rnd.choice(WORDS) for _ in range(50000))
out = {"reset_both_before": reset(True)}
c0 = counters()
out["cold"] = complete(prompt)
time.sleep(5)  # let the asynchronous store to CPU finish
out["reset_gpu_only"] = reset(False)
c1 = counters()
out["from_cpu"] = complete(prompt)
c2 = counters()
out["reset_both"] = reset(True)
out["after_reset"] = complete(prompt)
c3 = counters()
out["counters_cold"] = delta(c0, c1)
out["counters_from_cpu"] = delta(c1, c2)
out["counters_after_reset"] = delta(c2, c3)
print(json.dumps(out))
