"""Regroup step bundles into one bundle per model and GPU, with one-hour points only.

Left out on purpose: the 900 s runs, Qwen forced admission 300 s (with and without the
reclaim fix) and GLM capacity 3.91M (set from a wrong CPU tier estimate); their data stays
in the step folders and reports.

  python3 dashboard/regroup_by_model.py STEP24.json GLM_1H.json GLM_EXTRA.json GLM_PARAMS.json

The inputs are the per-step bundles this replaced (in git history at commit a26515a:
dashboard/data/step24-thunder-pr3-lanes.json and step25-explore1h.json). STEP24.json is the step 24 bundle (export_bundle.py over 24-thunder-pr3-lanes/results),
GLM_1H.json the step 25 one-hour bundle (explore1h-*, r1/c12-16, thunder-r1),
GLM_EXTRA.json r1/c1, c4, c8 exported with --kv-bytes-per-token 48200,
GLM_PARAMS.json the capacity runs (explore1h-thunder-cap3m-l10-retry, cap6m-l10-retry), same flag.
The 900 s exploration points are left out. A point whose run did not need the CPU tier
(no-offload run with working-set peak <= the GPU KV pool, or offload run with < 1% of
prompt tokens from the CPU tier) is equivalent with and without offload, so it is put in
both arms, with "shared" in its id. Writes the two bundles into dashboard/data/ and
replaces index.json.
"""
import copy, json, sys
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
T = "llm-d-thunder-agent-simplified"


def load(p):
    return json.load(open(p))


def fits_gpu(pt, offload_run):
    s = pt["summary"]
    if offload_run:
        return (s.get("cpu_hit_pct") or 0) < 1.0
    return (s.get("working_set_over_pool_max") or 99) <= 1.0


def build(title, description, settings, arms, sources):
    """arms: [(id, name, baseline)]; sources: [(bundle, source arm, target arm, offload_run, share_arm or None
    [, allow_short])]."""
    points = []
    for bundle, src, dst, offload_run, share, *short in sources:
        for pt in bundle["points"]:
            if pt["arm"] != src or (pt.get("duration_min", 60) < 50 and not short):
                continue
            p = copy.deepcopy(pt)
            p["arm"] = dst
            p["replicate"] = None
            points.append(p)
            if share and fits_gpu(pt, offload_run):
                q = copy.deepcopy(p)
                q["arm"] = share
                q["id"] = f"{pt['id']} (shared)"
                points.append(q)
    used = {p["arm"] for p in points}
    return {
        "schema": "agentic-bench/1", "title": title, "description": description,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "settings": settings,
        "arms": [{"id": i, "name": n, "baseline": b} for i, n, b in arms if i in used],
        "points": sorted(points, key=lambda p: ([a[0] for a in arms].index(p["arm"]), p["conc"])),
    }


def main():
    s24, g1h, gx, gp = (load(p) for p in sys.argv[1:5])
    qwen = build(
        "Qwen3-Coder-30B-A3B-FP8 on 2x H100 (TP=2), vLLM v0.28: no-router vs " + T + ", with and without 400 GiB CPU offload",
        "Step 24. One vLLM pod (2 H100, GPU KV 2.24M tokens), AgentX replay of the Weka Claude Code trace, 60 min per point, "
        "fresh vLLM pod per point. CPU tier 400 GiB = 8.74M tokens. Shared points: the no-offload runs at c=4, 8, 12 have a "
        "working-set peak of 0.43x to 0.91x the GPU pool, so offload would not change them; they also appear in the offload "
        "arms with the same lease. From c=24 the " + T + " runs collapse after the 1800 s forced admissions at minute 30 to 35.",
        {"ttft_slo_s": 60.0, "skip_minutes": 5.0, "kv_bytes_per_token": 49152},
        [("no-router", "no-router + offload", True),
         ("thunder-l10", T + " lease 10 s + offload", False),
         ("thunder-l30", T + " lease 30 s + offload", False),
         ("no-router-nooff", "no-router, no offload", False),
         ("thunder-l30-nooff", T + " lease 30 s, no offload", False)],
        [(s24, "offload-baseline-60m", "no-router", True, None),
         (s24, "baseline-60m", "no-router-nooff", False, "no-router"),
         (s24, "offload-thunder-lease10-60m", "thunder-l10", True, None),
         (s24, "offload-thunder-60m", "thunder-l30", True, None),
         (s24, "thunder-60m", "thunder-l30-nooff", False, "thunder-l30")])
    glm = build(
        "GLM-5.2-NVFP4 on 8x B200 (TP=8), vLLM v0.31: no-router vs " + T + ", with and without 820 GiB CPU offload",
        "Step 25. One vLLM pod (8 B200, MTP 3, GPU KV 1.57M tokens), AgentX replay of the Weka Claude Code trace, 60 min per "
        "point. CPU tier 820 GiB = 18.17M tokens (MLA: one copy shared by the 8 GPUs, 48,408 B per token). no-router c=1 to 16 and "
        + T + " lease 30 s c=12, 16 ran on a fresh vLLM pod per point (max-num-seqs 2x concurrency); all other points "
        "reset the KV cache on a running pod (max-num-seqs 64). Shared points: no-router c=1 and 4 took < 1% of prompt "
        "tokens from the CPU tier, so they also appear in the no-offload arm. From c=48 the " + T + " runs collapse after "
        "the 1800 s forced admissions at minute 30 to 35. Capacity variants: the gate admits 2x or 4x the GPU pool "
        "(capacityTokens with vLLM cache info disabled).",
        {"ttft_slo_s": 60.0, "skip_minutes": 5.0, "kv_bytes_per_token": 48408},
        [("no-router", "no-router + offload", True),
         ("thunder-l10", T + " lease 10 s + offload", False),
         ("thunder-l30", T + " lease 30 s + offload", False),
         ("no-router-nooff", "no-router, no offload", False),
         ("thunder-l10-nooff", T + " lease 10 s, no offload", False),
         ("thunder-l10-cap3m", T + " lease 10 s, capacity 3.15M (2x GPU) + offload", False),
         ("thunder-l10-cap6m", T + " lease 10 s, capacity 6.29M (4x GPU) + offload", False)],
        [(gx, "r1", "no-router", True, "no-router-nooff"),
         (g1h, "explore1h-direct", "no-router", True, None),
         (g1h, "explore1h-direct-nooff", "no-router-nooff", False, None),
         (g1h, "explore1h-thunder-gpu-l10", "thunder-l10", True, None),
         (g1h, "explore1h-thunder-gpu-l10-nooff", "thunder-l10-nooff", False, None),
         (g1h, "explore1h-thunder-gpu-l30", "thunder-l30", True, None),
         (gp, "explore1h-thunder-cap3m-l10-retry", "thunder-l10-cap3m", True, None),
         (gp, "explore1h-thunder-cap6m-l10-retry", "thunder-l10-cap6m", True, None)])
    # GLM CPU tier, exact: vLLM keeps one copy for the 8 GPUs (MLA replicated layout), 48,408 B per token
    # per GPU (measured: 387,264 B loaded per CPU-tier token over 8 GPUs), a 64-token block padded to the
    # 4096 B page: 820 GiB // 3,100,672 B = 283,960 blocks = 18,173,440 tokens.
    for p in glm["points"]:
        if p.get("cpu_tier_tokens"):
            p["cpu_tier_tokens"] = 18_173_440
    index = []
    for name, b in (("glm52-nvfp4-8xb200.json", glm), ("qwen3-coder-30b-fp8-2xh100.json", qwen)):
        json.dump(b, open(DATA / name, "w"), separators=(",", ":"))
        index.append({"file": name, "title": b["title"], "created_utc": b["created_utc"], "points": len(b["points"])})
        print(name, len(b["points"]), {a["id"]: sorted(p["conc"] for p in b["points"] if p["arm"] == a["id"]) for a in b["arms"]})
    json.dump(index, open(DATA / "index.json", "w"), indent=1)


if __name__ == "__main__":
    main()
