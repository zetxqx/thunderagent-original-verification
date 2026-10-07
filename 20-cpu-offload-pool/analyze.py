#!/usr/bin/env python3
"""Step 20 analysis: CPU KV offloading on single vLLM replicas, three arms.

Reads every results/rep-*/ run that has a step20.json (written by
run-cells.sh). Per cell it combines:

- step 16's per-cell statistics (throughput, TTFT, GPU hit rate from the
  prober CSV, session-level SLO), computed with the point's own warm-up;
- from the raw vLLM scrapes (raw-vllm-metrics.txt.gz, every 10 s): GPU, CPU
  and total prefix reuse, CPU store and load traffic, allocation failures;
- from the raw EPP scrapes: the gate capacity, its working set, holds, pauses
  and forced admissions;
- from the per-request report: the working set over time (each live session's
  latest prompt size, summed), against GPU KV and against the CPU tier.

Writes results/analysis.md, results/summary.png and
results/timeseries-<phase>-c<c>.png.

Usage: analyze.py   (uv run --with matplotlib --with numpy python analyze.py)
"""
import bisect
import gzip
import importlib.util
import json
import os
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = Path(os.environ["STEP_RESULTS"]) if os.environ.get("STEP_RESULTS") else HERE / "results"  # step 21 reuses this analyzer
GPU_KV_TOKENS = 2237040
TIER_TOKENS = 8738133  # 400 GiB at 48 KiB per token
ARM_LABEL = {"baseline": "llm-d default", "thunder-lease-main": "lease, GPU capacity",
             "thunder-lease-main-tier": "lease, CPU-tier capacity",
             "thunder-lease-budget30": "lease + tier budget, lease 30 s",
             "thunder-lease-budget5": "lease + tier budget, lease 5 s",
             "thunder-lease-main5": "lease, GPU capacity, lease 5 s"}
# chart labels (the tables keep the arm names above)
PLOT_LABEL = {"baseline": "llm-d default (no gate)", "thunder-lease-main": "llm-d-thunder-simplified (GPU tier)",
              "thunder-lease-main-tier": "llm-d-thunder-simplified (CPU tier)",
              "thunder-lease-budget30": "llm-d-thunder-simplified + tier budget (lease 30 s)",
              "thunder-lease-budget5": "llm-d-thunder-simplified + tier budget (lease 5 s)",
              "thunder-lease-main5": "llm-d-thunder-simplified (GPU tier, lease 5 s)"}
ARM_COLOR = {"baseline": "#B64342", "thunder-lease-main": "#0F4D92", "thunder-lease-main-tier": "#42949E",
             "thunder-lease-budget30": "#9A4D8E", "thunder-lease-budget5": "#E08A00", "thunder-lease-main5": "#3775BA"}  # same as make_figures.py


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s16 = load("step16", HERE.parent / "16-thunder-minimal-pool" / "analyze.py")


def set_warmup(seconds):
    for mod in (s16.s15.step10, s16.s15, s16, s16.s13):
        mod.WARMUP_S = seconds


def raw_snapshots(path, keep):
    """[(ts, {metric: value summed over series})] from a gzip of '# ts=' snapshots.
    keep(name) selects metrics; names are normalised by dropping a '_total' suffix."""
    snaps, cur = [], None
    if not path.exists():
        return snaps
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("# ts="):
                cur = {}
                snaps.append((float(line[5:].strip()), cur))
                continue
            if cur is None or line.startswith("#") or not line.strip():
                continue
            name = line.split("{", 1)[0].split(" ", 1)[0]
            if name.endswith("_created"):
                continue
            base = name[:-6] if name.endswith("_total") else name
            k = keep(base)
            if k:
                cur[k] = cur.get(k, 0.0) + float(line.rsplit(" ", 1)[1])
    return snaps


VLLM_KEEP = {"vllm:prefix_cache_queries": "q", "vllm:prefix_cache_hits": "gpu_hits",
             "vllm:external_prefix_cache_hits": "cpu_hits", "vllm:external_prefix_cache_queries": "cpu_q",
             "vllm:kv_offload_store_bytes": "store_bytes", "vllm:kv_offload_load_bytes": "load_bytes",
             "vllm:kv_offload_load_time": "load_time", "vllm:kv_offload_store_time": "store_time",
             "vllm:kv_offload_allocation_failure": "alloc_fail"}


def epp_keep(name):
    i = name.find("thunder_agent_")
    if i < 0:
        return None
    k = name[i + len("thunder_agent_"):]
    return k if k in ("endpoint_capacity_tokens", "endpoint_working_set_tokens", "holds", "pauses",
                      "resumes", "starvation_promotions", "releases") else None


def window_delta(snaps, key, t_from):
    pts = [(t, m.get(key, 0.0)) for t, m in snaps if t >= t_from]
    return pts[-1][1] - pts[0][1] if len(pts) >= 2 else float("nan")


def offload_stats(cell, warmup):
    snaps = raw_snapshots(cell / "results" / "raw-vllm-metrics.txt.gz", VLLM_KEEP.get)
    if len(snaps) < 2:
        return {}
    t0 = snaps[0][0]
    out = {}
    for tag, t_from in (("window", t0), ("steady", t0 + warmup)):
        q = window_delta(snaps, "q", t_from)
        g = window_delta(snaps, "gpu_hits", t_from)
        c = window_delta(snaps, "cpu_hits", t_from)
        out[f"gpu_hit_{tag}"] = g / q if q > 0 else float("nan")
        out[f"cpu_hit_{tag}"] = c / q if q > 0 else float("nan")
        out[f"reuse_{tag}"] = (g + c) / q if q > 0 else float("nan")
    for k in ("store_bytes", "load_bytes", "load_time", "alloc_fail"):
        out[k] = window_delta(snaps, k, t0)
    out["store_gb"], out["load_gb"] = out.pop("store_bytes") / 1e9, out.pop("load_bytes") / 1e9
    return out


def epp_stats(cell, warmup):
    snaps = raw_snapshots(cell / "results" / "raw-epp-metrics.txt.gz", epp_keep)
    if len(snaps) < 2:
        return {}
    t0 = snaps[0][0]
    caps = [m["endpoint_capacity_tokens"] for _, m in snaps if m.get("endpoint_capacity_tokens")]
    ws = [m.get("endpoint_working_set_tokens", 0.0) for t, m in snaps if t >= t0 + warmup]
    out = {"epp_capacity": caps[-1] if caps else float("nan")}
    if caps and ws:
        out["epp_ws_over_cap"] = st.mean(ws) / caps[-1]
    for k in ("holds", "pauses", "starvation_promotions"):
        out[f"epp_{k}"] = window_delta(snaps, k, t0)
    return out


def working_set(cell, warmup):
    """Mean over the steady state of the summed latest prompt size of live sessions."""
    path = cell / "results" / "report" / "per_request_lifecycle_metrics.json"
    if not path.exists():
        return {}
    recs = json.loads(path.read_text())
    sess = {}
    for r in recs:
        sid = r.get("session_id")
        pt = (((r.get("info") or {}).get("response_metrics") or {}).get("server_usage") or {}).get("prompt_tokens")
        if sid and r.get("start_time") is not None:
            sess.setdefault(sid, []).append((r["start_time"], r.get("end_time") or r["start_time"], pt))
    if not sess:
        return {}
    t0 = min(x[0] for v in sess.values() for x in v)
    t1 = max(x[1] for v in sess.values() for x in v)
    live = []
    for v in sess.values():
        v.sort()
        starts, sizes, last = [], [], 0
        for s, _, pt in v:
            last = pt if pt else last
            starts.append(s)
            sizes.append(last)
        live.append((v[0][0], max(x[1] for x in v), starts, sizes))
    grid = np.arange(t0 + warmup, t1, 10.0)
    if len(grid) == 0:
        return {}
    ws = []
    for t in grid:
        total = 0
        for first, end, starts, sizes in live:
            if first <= t <= end:
                i = bisect.bisect_right(starts, t) - 1
                total += sizes[i] if i >= 0 else 0
        ws.append(total)
    m = float(np.mean(ws))
    return {"ws_tokens": m, "ws_over_gpu": m / GPU_KV_TOKENS, "ws_over_tier": m / TIER_TOKENS}


def cell_stats(cell, meta):
    set_warmup(meta["warmup_s"])
    try:
        s = s16.stats(cell)
    except Exception as e:  # keep the other sources even if step 16's reader fails
        s = {"stats_error": str(e)}
    s.update(offload_stats(cell, meta["warmup_s"]))
    s.update(epp_stats(cell, meta["warmup_s"]))
    s.update(working_set(cell, meta["warmup_s"]))
    if isinstance(s.get("prefill_tokens_total"), float):
        s["prefill_tps"] = s["prefill_tokens_total"] / meta["window_s"]
    return s


ROWS = [
    ("output throughput (tok/s)", "throughput", "{:.0f}", 1),
    ("requests completed / errors", ("requests", "errors"), "{:.0f}", 1),
    ("sessions ended in window / turns not issued at stage end", ("sessions_ended", "turns_dropped"), "{:.0f}", 1),
    ("GPU hit rate, steady", "gpu_hit_steady", "{:.3f}", 1),
    ("CPU hit rate, steady", "cpu_hit_steady", "{:.3f}", 1),
    ("total reuse (GPU + CPU), steady", "reuse_steady", "{:.3f}", 1),
    ("GPU / CPU / total, whole window", ("gpu_hit_window", "cpu_hit_window", "reuse_window"), "{:.3f}", 1),
    ("prefill tokens computed (M)", "prefill_tokens_total", "{:.1f}", 1e-6),
    ("prefill tok/s (k)", "prefill_tps", "{:.1f}", 1e-3),
    ("TTFT p50 / p90 / p99 (s)", ("ttft_p50", "ttft_p90", "ttft_p99"), "{:.1f}", 1),
    ("E2E latency p50 / p90 (s)", ("e2e_p50", "e2e_p90"), "{:.1f}", 1),
    ("vLLM running / waiting, mean steady", ("running_mean_steady", "waiting_mean_steady"), "{:.1f}", 1),
    ("vLLM GPU KV usage, mean steady", "kv_mean_steady", "{:.2f}", 1),
    ("vLLM preemptions", "preemptions", "{:.0f}", 1),
    ("CPU tier stored / loaded (GB)", ("store_gb", "load_gb"), "{:.0f}", 1),
    ("CPU tier load time (s) / allocation failures", ("load_time", "alloc_fail"), "{:.0f}", 1),
    ("working set, mean steady (M tokens)", "ws_tokens", "{:.2f}", 1e-6),
    ("working set / GPU KV / CPU tier", ("ws_over_gpu", "ws_over_tier"), "{:.2f}", 1),
    ("gate capacity (M tokens)", "epp_capacity", "{:.2f}", 1e-6),
    ("gate working set / capacity, mean steady", "epp_ws_over_cap", "{:.2f}", 1),
    ("gate holds / pauses / forced admissions", ("epp_holds", "epp_pauses", "epp_starvation_promotions"), "{:.0f}", 1),
    ("goodput within SLO, TTFT <= 30 s (turns/s)", "goodput_slo", "{:.2f}", 1),
    ("session SLO attainment, strict", "attain_strict", "{:.2f}", 1),
    ("per-session worst TTFT, p90 (s)", "worst_ttft_p90", "{:.0f}", 1),
]


def fmt(s, keys, spec, scale):
    keys = keys if isinstance(keys, tuple) else (keys,)
    parts = []
    for k in keys:
        v = s.get(k)
        parts.append(spec.format(v * scale) if isinstance(v, (int, float)) and np.isfinite(v) else "-")
    return " / ".join(parts)


def collect():
    runs = []
    for run in sorted(RESULTS.glob("rep-*")):
        mp = run / "step20.json"
        if not mp.exists():
            continue
        meta = json.loads(mp.read_text())
        cells = []
        for lane, arm in sorted(meta["lane_arms"].items()):
            cell = run / f"epp-{arm}-{lane}"
            if not cell.is_dir():
                continue
            s = cell_stats(cell, meta)
            s.update({"arm": arm, "lane": lane, "node": (meta["lanes"].get(lane) or {}).get("node", "?"), "cell": cell})
            cells.append(s)
        runs.append((meta, run, cells))
    return runs


def fmt_cells(cells, keys, spec, scale):
    """One value, or mean (min-max) over repeated cells, per key."""
    keys = keys if isinstance(keys, tuple) else (keys,)
    parts = []
    for k in keys:
        v = [c[k] * scale for c in cells if isinstance(c.get(k), (int, float)) and np.isfinite(c[k])]
        if not v:
            parts.append("-")
        elif len(v) == 1:
            parts.append(spec.format(v[0]))
        else:
            parts.append(f"{spec.format(np.mean(v))} ({spec.format(min(v))}-{spec.format(max(v))})")
    return " / ".join(parts)


def tables(runs):
    L = ["# Step 20: CPU KV offloading (400 GiB) on single vLLM replicas\n",
         "The three lanes of a run ran at the same time on three replicas. Where an arm has several cells at a "
         "point (phase B replicates, or phase A's two lease cells), values are mean (min-max). "
         "Hit rates and CPU traffic are from vLLM's counters; the CPU hit rate is external hits over all prompt "
         "tokens queried. Working set: each live session's latest prompt size, summed. "
         "Phase A has offloading off, so its CPU rows must be 0.\n"]
    groups = {}
    for meta, run, cells in runs:
        g = groups.setdefault((meta["phase"], meta["concurrency"]), {"meta": meta, "runs": [], "arms": {}})
        g["runs"].append(run.name)
        for c in cells:
            g["arms"].setdefault(c["arm"], []).append(c)
    for (phase, conc), g in sorted(groups.items()):
        meta = g["meta"]
        arms = [a for a in ARM_LABEL if a in g["arms"]]
        L.append(f"## Phase {phase}, c={conc} "
                 f"({'offload ' + str(meta['offload_gib']) + ' GiB' if meta['offload_gib'] else 'offload off'}, "
                 f"window {meta['window_s'] // 60} min, warm-up {meta['warmup_s'] // 60} min)\n")
        L.append("Runs: " + ", ".join(f"`{r}`" for r in sorted(g["runs"])) + ".\n")
        L.append("| metric | " + " | ".join(f"{ARM_LABEL[a]} (n={len(g['arms'][a])})" for a in arms) + " |")
        L.append("|" + "---|" * (1 + len(arms)))
        L.append("| pods (node) | " + " | ".join(", ".join(c["node"].rsplit("-", 1)[-1] for c in g["arms"][a]) for a in arms) + " |")
        for name, keys, spec, scale in ROWS:
            L.append(f"| {name} | " + " | ".join(fmt_cells(g["arms"][a], keys, spec, scale) for a in arms) + " |")
        L.append("")
    return L


def by_arm(runs, phase):
    out = {}
    for meta, _, cells in runs:
        if meta["phase"] != phase:
            continue
        for c in cells:
            out.setdefault(c["arm"], []).append((meta["concurrency"], c))
    return {a: sorted(v, key=lambda x: x[0]) for a, v in out.items()}


def summary(runs, out):
    panels = [("throughput", "Output throughput", "tokens / s", 1),
              ("reuse_steady", "Total prefix reuse (GPU + CPU)", "steady state", 1),
              ("cpu_hit_steady", "CPU tier hit rate", "steady state", 1),
              ("prefill_tps", "Prefill work", "k tokens / s", 1e-3),
              ("ttft_p90", "TTFT p90", "seconds", 1),
              ("ws_over_tier", "Working set / CPU tier", "mean, steady state", 1)]
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
    for ax, (key, title, ylabel, scale) in zip(axes.flat, panels):
        for phase, style in (("B", dict(ls="-", marker="o")), ("T", dict(ls="-", marker="s")),
                             ("A", dict(ls="--", marker="o", mfc="white"))):
            for arm, pts in by_arm(runs, phase).items():
                per_c = {}
                for c, s in pts:
                    if isinstance(s.get(key), (int, float)) and np.isfinite(s[key]):
                        per_c.setdefault(c, []).append(s[key] * scale)
                xs = sorted(per_c)
                ys = [np.mean(per_c[c]) for c in xs]
                if xs:
                    ax.plot(xs, ys, color=ARM_COLOR.get(arm, "#333333"), lw=2, ms=6, **style,
                            label=f"{PLOT_LABEL.get(arm, arm)}{', offload off' if phase == 'A' else ''}")
        if key == "ws_over_tier":
            ax.axhspan(0.75, 0.87, color="#e5e5e5", zorder=0)
        ax.set_ylim(bottom=0)
        ax.set_xscale("log", base=2)
        ax.set_xticks([32, 64, 128, 192, 256], ["32", "64", "128", "192", "256"])
        ax.set_title(title, loc="left", fontweight="bold")
        ax.set_ylabel(ylabel)
        ax.set_xlabel("concurrent sessions per replica (mean over cells)")
        ax.grid(axis="y", color="#e5e5e5", lw=0.8)
        ax.set_axisbelow(True)
    h, l = axes.flat[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.02))
    fig.text(0.01, 0.005, "Solid: 400 GiB CPU tier (phase B). Dashed, hollow: offloading off (phase A). "
             "Shaded band: 0.75 to 0.87 of reach, where step 13's hit rate collapsed.", fontsize=8, color="#666666")
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(out, dpi=150)
    plt.close(fig)


def timeseries(meta, cells, out):
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.6), sharey=True)
    for c in cells:
        snaps = raw_snapshots(c["cell"] / "results" / "raw-vllm-metrics.txt.gz", VLLM_KEEP.get)
        if len(snaps) < 3:
            continue
        t0 = snaps[0][0]
        ts, gpu, cpu = [], [], []
        for (ta, a), (tb, b) in zip(snaps[:-6], snaps[6:]):  # 60 s windows
            dq = b.get("q", 0) - a.get("q", 0)
            if dq > 0:
                ts.append((tb - t0) / 60)
                gpu.append((b.get("gpu_hits", 0) - a.get("gpu_hits", 0)) / dq)
                cpu.append((b.get("cpu_hits", 0) - a.get("cpu_hits", 0)) / dq)
        col = ARM_COLOR.get(c["arm"], "#333333")
        axes[0].plot(ts, gpu, color=col, lw=1.5, label=f"{PLOT_LABEL.get(c['arm'], c['arm'])} (lane {c['lane']})")
        axes[1].plot(ts, cpu, color=col, lw=1.5)
    axes[0].set_ylim(0, 1.02)
    for ax, title in zip(axes, ("GPU hit rate, 60 s windows", "CPU tier hit rate, 60 s windows")):
        ax.axvline(meta["warmup_s"] / 60, color="#999999", lw=1, ls=":")
        ax.set_title(title, loc="left", fontweight="bold")
        ax.set_xlabel("minutes since the bench started")
        ax.grid(axis="y", color="#e5e5e5", lw=0.8)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"Phase {meta['phase']}, c={meta['concurrency']}, replicate {meta.get('replicate', 1)}", x=0.01, ha="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)


def main():
    runs = collect()
    if not runs:
        print("no step 20 runs (results/rep-*/step20.json) found")
        return
    L = tables(runs)
    (RESULTS / "analysis.md").write_text("\n".join(L))
    print("\n".join(L))
    summary(runs, RESULTS / "summary.png")
    for meta, _, cells in runs:
        r = meta.get("replicate", 1)
        timeseries(meta, cells, RESULTS / f"timeseries-{meta['phase']}{'' if r == 1 else f'-r{r}'}-c{meta['concurrency']}.png")
    print(f"wrote {RESULTS / 'analysis.md'}, summary.png, timeseries-*.png")


if __name__ == "__main__":
    main()
