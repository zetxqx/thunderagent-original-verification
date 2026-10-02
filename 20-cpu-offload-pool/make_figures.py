#!/usr/bin/env python3
"""Report figures for step 20, in the figures4papers publication style.

Reads the per-cell statistics through analyze.py (cached in
results/figure-data.json, delete it to recompute) and writes to figures/:

  fig1-throughput      output throughput against concurrency, every arm, offload off and on
  fig2-reuse-source    steady-state prefix reuse split into GPU hits and CPU tier hits
  fig3-ttft            median and p99 TTFT against concurrency, offloading on, values labeled
  fig4-offload-effect  throughput with offloading off and on, at the points that have both
  fig5-kv-budget       the setup, the KV cache one replica has, and the KV cache the workload needs
  fig6-vllm-queues-offload  vLLM running and waiting requests over time, offloading on (phase B)
  fig7-vllm-queues-off      the same with offloading off (phase A)

Each as PNG (300 dpi) and PDF.
Usage: uv run --with matplotlib --with numpy python make_figures.py
"""
import csv
import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
CACHE = HERE / "results" / "figure-data.json"
OUT = HERE / "figures"

PALETTE = {
    "blue_main": "#0F4D92", "blue_secondary": "#3775BA",
    "green_1": "#DDF3DE", "green_2": "#AADCA9", "green_3": "#8BCF8B",
    "red_1": "#F6CFCB", "red_2": "#E9A6A1", "red_strong": "#B64342",
    "neutral": "#CFCECE", "highlight": "#FFD700",
    "teal": "#42949E", "violet": "#9A4D8E",
}
# Blue: llm-d-thunder-simplified sized to GPU KV (the key method); teal: sized to
# the CPU tier; red: the llm-d default baseline.
ARMS = [("baseline", "llm-d default (no gate)", PALETTE["red_strong"], PALETTE["red_1"]),
        ("thunder-lease-main", "llm-d-thunder-simplified (GPU tier)", PALETTE["blue_main"], "#C9D8EC"),
        ("thunder-lease-main-tier", "llm-d-thunder-simplified (CPU tier)", PALETTE["teal"], "#CDE6E8")]
LABEL = {a: l for a, l, _, _ in ARMS}
COLOR = {a: c for a, _, c, _ in ARMS}
LIGHT = {a: c for a, _, _, c in ARMS}
C_ALL = [32, 64, 128, 192, 256]
KEYS = ["throughput", "gpu_hit_steady", "cpu_hit_steady", "reuse_steady", "ttft_p50", "ttft_p90", "ttft_p99",
        "goodput_slo", "prefill_tps", "ws_over_tier", "epp_starvation_promotions"]


def apply_publication_style(font_size=15, axes_linewidth=2.0):
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial", "sans-serif"],
        "font.size": font_size, "axes.linewidth": axes_linewidth,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.major.width": axes_linewidth * 0.75, "ytick.major.width": axes_linewidth * 0.75,
        "legend.frameon": False, "pdf.fonttype": 42, "svg.fonttype": "none",
    })


def finalize_figure(fig, name):
    OUT.mkdir(exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def load_data():
    """{phase: {arm: {c: [stats of each cell]}}} with only the plotted keys."""
    if CACHE.exists():
        raw = json.loads(CACHE.read_text())
    else:
        spec = importlib.util.spec_from_file_location("a20", HERE / "analyze.py")
        a20 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(a20)
        raw = []
        for meta, _, cells in a20.collect():
            for c in cells:
                raw.append({"phase": meta["phase"], "c": meta["concurrency"], "arm": c["arm"], "lane": c["lane"],
                            **{k: c.get(k) for k in KEYS}})
        CACHE.write_text(json.dumps(raw, indent=1))
    data = {}
    for r in raw:
        data.setdefault(r["phase"], {}).setdefault(r["arm"], {}).setdefault(r["c"], []).append(r)
    return data


def series(d, key, scale=1.0):
    """(c, mean, min, max) over the cells of each concurrency."""
    cs = sorted(d)
    vals = [[x[key] * scale for x in d[c] if x.get(key) is not None] for c in cs]
    return (np.array(cs), np.array([np.mean(v) for v in vals]),
            np.array([min(v) for v in vals]), np.array([max(v) for v in vals]))


def c_axis(ax):
    ax.set_xscale("log", base=2)
    ax.set_xticks(C_ALL, [str(c) for c in C_ALL])
    ax.minorticks_off()
    ax.set_xlim(27, 300)
    ax.set_xlabel("concurrent sessions per vLLM replica")


def fig1_throughput(data):
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    ax.axvspan(128, 192, color=PALETTE["neutral"], alpha=0.35, lw=0, zorder=0)
    ax.text(157, 60, "CPU tier fills\n(working set\n0.8 to 1.1 of tier)", ha="center", va="bottom", fontsize=11, color="#555555")
    for arm in LABEL:
        if arm in data.get("B", {}):
            c, m, lo, hi = series(data["B"][arm], "throughput")
            ax.plot(c, m, color=COLOR[arm], lw=2.8, marker="o", ms=8, zorder=3)
            ax.vlines(c, lo, hi, color=COLOR[arm], lw=2, zorder=2)
        if arm in data.get("A", {}):
            c, m, lo, hi = series(data["A"][arm], "throughput")
            ax.plot(c, m, color=COLOR[arm], lw=2.2, ls="--", marker="o", ms=8, mfc="white", mew=2, zorder=3)
            ax.vlines(c, lo, hi, color=COLOR[arm], lw=2, zorder=2)
    ax.set_ylim(0, 700)
    ax.set_ylabel("output throughput (tokens/s)")
    c_axis(ax)
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)
    handles = [Line2D([], [], color=COLOR[a], lw=2.8, marker="o", ms=8, label=LABEL[a]) for a in LABEL]
    handles += [Line2D([], [], color="#333333", lw=2.8, marker="o", ms=8, label="CPU offloading 400 GiB"),
                Line2D([], [], color="#333333", lw=2.2, ls="--", marker="o", ms=8, mfc="white", mew=2, label="offloading off")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=12, handlelength=2.6)
    finalize_figure(fig, "fig1-throughput")


def fig2_reuse_source(data):
    b = data["B"]
    arms = [a for a in LABEL if a in b]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    width, gap = 0.26, 0.04
    x = np.arange(len(C_ALL))
    for i, arm in enumerate(arms):
        pos = x + (i - (len(arms) - 1) / 2) * (width + gap)
        gpu = np.array([np.mean([r["gpu_hit_steady"] for r in b[arm][c]]) for c in C_ALL])
        cpu = np.array([np.mean([r["cpu_hit_steady"] for r in b[arm][c]]) for c in C_ALL])
        ax.bar(pos, gpu, width, color=COLOR[arm], edgecolor="black", lw=1.2, zorder=3)
        ax.bar(pos, cpu, width, bottom=gpu, color=LIGHT[arm], edgecolor="black", lw=1.2, hatch="//", zorder=3)
        tot = [[r["gpu_hit_steady"] + r["cpu_hit_steady"] for r in b[arm][c]] for c in C_ALL]
        lo, hi = np.array([min(t) for t in tot]), np.array([max(t) for t in tot])
        ax.vlines(pos, lo, hi, color="black", lw=1.4, zorder=4)
        for p, t, h in zip(pos, gpu + cpu, hi):
            ax.text(p, h + 0.015, f"{t:.2f}", ha="center", va="bottom", fontsize=9.5)
    ax.set_xticks(x, [str(c) for c in C_ALL])
    ax.set_xlabel("concurrent sessions per vLLM replica (CPU offloading 400 GiB; mean of 3 runs, line: min-max)")
    ax.set_ylabel("prompt tokens served from cache\n(steady state)")
    ax.set_ylim(0, 1.08)
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)
    handles = [Patch(facecolor=COLOR[a], edgecolor="black", label=LABEL[a]) for a in arms]
    handles += [Patch(facecolor="white", edgecolor="black", label="solid: GPU prefix cache hit"),
                Patch(facecolor="white", edgecolor="black", hatch="//", label="hatched: CPU tier hit")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3, fontsize=11.5)
    finalize_figure(fig, "fig2-reuse-source")


def fig3_ttft(data):
    b = data["B"]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))
    for ax, (key, title) in zip(axes, (("ttft_p50", "(a) median TTFT: a typical turn"),
                                       ("ttft_p99", "(b) p99 TTFT: the slowest 1% of turns"))):
        means = {}
        for arm in LABEL:
            if arm not in b:
                continue
            c, m, lo, hi = series(b[arm], key)
            ax.plot(c, m, color=COLOR[arm], lw=2.6, marker="o", ms=7, zorder=3)
            ax.vlines(c, lo, hi, color=COLOR[arm], lw=2, zorder=2)
            means[arm] = dict(zip(c, m))
        # label each point above if its line is the highest there, below if the lowest; the middle one
        # goes to the side with more room (log distance to the nearest neighbour)
        for x in sorted(next(iter(means.values()))):
            ranked = sorted(means, key=lambda a: means[a][x])
            for i, arm in enumerate(ranked):
                y = means[arm][x]
                if i == len(ranked) - 1:
                    up = True
                elif i == 0:
                    up = False
                else:
                    up = np.log10(means[ranked[i + 1]][x] / y) > np.log10(y / means[ranked[i - 1]][x])
                ax.annotate(f"{y:.0f}" if y >= 10 else f"{y:.1f}", (x, y), xytext=(0, 12 if up else -16),
                            textcoords="offset points", ha="center", va="center", fontsize=10.5,
                            color=COLOR[arm], fontweight="bold")
        if key == "ttft_p50":
            ax.axhline(30, color="#7a7a7a", lw=1.4, ls=":")
            ax.text(29, 36, "30 s SLO", fontsize=11, color="#555555")
        else:
            ax.axhline(1800, color="#7a7a7a", lw=1.4, ls=":")
            ax.text(29, 2150, "forced admission at 1800 s", fontsize=11, color="#555555")
        ax.set_yscale("log")
        ax.set_ylim(0.15, 5000)
        ax.set_yticks([1, 10, 100, 1000], ["1 s", "10 s", "100 s", "1000 s"])
        ax.minorticks_off()
        c_axis(ax)
        ax.set_title(title, loc="left", fontweight="bold", fontsize=14)
        ax.set_ylabel("time to first token")
        ax.grid(axis="y", color="#E5E5E5", lw=1)
        ax.set_axisbelow(True)
    handles = [Line2D([], [], color=COLOR[a], lw=2.6, marker="o", ms=7, label=LABEL[a]) for a in LABEL if a in b]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=12.5, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("One vLLM replica per arm, CPU offloading 400 GiB; mean of 3 runs, vertical line: min-max",
                 x=0.01, ha="left", fontsize=12, color="#555555")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))
    finalize_figure(fig, "fig3-ttft")


def fig4_offload_effect(data):
    both = sorted(set(data["A"]["baseline"]) & set(data["B"]["baseline"]))
    groups = [("baseline", "A"), ("baseline", "B"), ("thunder-lease-main", "A"), ("thunder-lease-main", "B")]
    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.19
    x = np.arange(len(both))
    for i, (arm, phase) in enumerate(groups):
        pos = x + (i - 1.5) * (width + 0.02)
        cell = [[r["throughput"] for r in data[phase][arm][c]] for c in both]
        vals = np.array([np.mean(v) for v in cell])
        lo, hi = np.array([min(v) for v in cell]), np.array([max(v) for v in cell])
        on = phase == "B"
        ax.bar(pos, vals, width, color=COLOR[arm] if on else LIGHT[arm], edgecolor="black", lw=1.2,
               hatch=None if on else "..", zorder=3)
        ax.vlines(pos, lo, hi, color="black", lw=1.4, zorder=4)
        for p, v, h in zip(pos, vals, hi):
            ax.text(p, h + 8, f"{v:.0f}", ha="center", va="bottom", fontsize=9.5)
        if on:
            off = np.array([np.mean([r["throughput"] for r in data["A"][arm][c]]) for c in both])
            for p, v, o in zip(pos, vals, off):
                ax.text(p - (width + 0.02) / 2, max(v, o) + 42, f"x{v / o:.2f}", ha="center", va="bottom",
                        fontsize=11, fontweight="bold", color=COLOR[arm])
    ax.set_xticks(x, [str(c) for c in both])
    ax.set_xlabel("concurrent sessions per vLLM replica (bars: mean; line: min-max over cells)")
    ax.set_ylabel("output throughput (tokens/s)")
    ax.set_ylim(0, 760)
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)
    handles = [Patch(facecolor=LIGHT["baseline"], edgecolor="black", hatch="..", label="llm-d default, offloading off"),
               Patch(facecolor=COLOR["baseline"], edgecolor="black", label="llm-d default, offloading 400 GiB"),
               Patch(facecolor=LIGHT["thunder-lease-main"], edgecolor="black", hatch="..", label="llm-d-thunder-simplified (GPU tier), offloading off"),
               Patch(facecolor=COLOR["thunder-lease-main"], edgecolor="black", label="llm-d-thunder-simplified (GPU tier), offloading 400 GiB")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=11.5)
    finalize_figure(fig, "fig4-offload-effect")


def fig5_kv_budget(data):
    GIB_PER_TOKEN = 49152 / 2**30  # 48 layers x K,V x 4 KV heads x 128 dims x 1 byte (FP8)
    gpu_tok, tier_tok = 2237040, 8738133
    need = data["B"]["baseline"]
    cs = [c for c in C_ALL if c in need]
    tok = np.array([np.mean([r["ws_over_tier"] for r in need[c]]) * tier_tok for c in cs])
    tok_lo = np.array([min(r["ws_over_tier"] for r in need[c]) * tier_tok for c in cs])
    tok_hi = np.array([max(r["ws_over_tier"] for r in need[c]) * tier_tok for c in cs])

    fig = plt.figure(figsize=(14, 5.4))
    box = fig.add_axes([0.0, 0.0, 0.34, 1.0])
    box.set_axis_off()
    lines = [("Setup", None),
             ("model", "Qwen3-Coder-30B-A3B-Instruct-FP8"),
             ("engine", "vLLM v0.28.0"),
             ("replica", "2 x H100 80GB, tensor parallel 2"),
             ("KV cache", "FP8, 48 KiB per token"),
             ("GPU KV", f"{gpu_tok / 1e6:.2f}M tokens = {gpu_tok * GIB_PER_TOKEN:.0f} GiB"),
             ("CPU tier", f"400 GiB = {tier_tok / 1e6:.2f}M tokens"),
             ("", "(copies GPU blocks, so it can hold about"),
             ("", f" {tier_tok / 1e6:.2f}M tokens in total, not GPU + CPU)"),
             ("workload", "weka agentic coding traces;"),
             ("", "each turn resends the whole history;"),
             ("", "tool-call gaps capped at 10 s"),
             ("router", "one EPP per replica, 3 replicas in parallel")]
    y = 0.93
    for k, v in lines:
        if v is None:
            box.text(0.06, y, k, fontsize=15, fontweight="bold", transform=box.transAxes)
        else:
            box.text(0.06, y, k, fontsize=11.5, color="#555555", transform=box.transAxes)
            box.text(0.30, y, v, fontsize=11.5, transform=box.transAxes)
        y -= 0.072

    ax = fig.add_axes([0.46, 0.14, 0.52, 0.78])
    x = np.arange(len(cs))
    ax.bar(x, tok / 1e6, 0.55, color=PALETTE["neutral"], edgecolor="black", lw=1.2, zorder=3)
    ax.vlines(x, tok_lo / 1e6, tok_hi / 1e6, color="black", lw=1.4, zorder=4)
    for xi, t, h in zip(x, tok, tok_hi):
        ax.text(xi, h / 1e6 + 0.2, f"{t / 1e6:.1f}M\n({t * GIB_PER_TOKEN:.0f} GiB)", ha="center", va="bottom", fontsize=10.5)
    for level, color, label in ((gpu_tok, PALETTE["red_strong"], "GPU KV cache"),
                                (tier_tok, PALETTE["blue_main"], "CPU tier (offloading)")):
        ax.axhline(level / 1e6, color=color, lw=2.4, ls="--", zorder=4,
                   label=f"{label}: {level / 1e6:.2f}M tokens ({level * GIB_PER_TOKEN:.0f} GiB)")
    ax.set_xticks(x, [str(c) for c in cs])
    ax.set_xlabel("concurrent sessions per vLLM replica")
    ax.set_ylabel("KV cache the workload needs\n(M tokens, working set)")
    ax.set_ylim(0, 13.5)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[::-1], labels[::-1], loc="upper left", fontsize=11.5)
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)
    ax.set_title("Working set: live sessions' latest prompt sizes, summed (mean over steady state;\n"
                 "llm-d default with offloading on, so no gate holds sessions back; mean of 3 runs, line: min-max)",
                 loc="left", fontsize=10.5, color="#555555")
    finalize_figure(fig, "fig5-kv-budget")


def queue_series(phase):
    """{c: [(arm, lane, minutes, running, waiting)]} from each cell's prober CSV (every 2 s)."""
    out, warm = {}, {}
    for run in sorted((HERE / "results").glob("rep-*")):
        mp = run / "step20.json"
        if not mp.exists():
            continue
        meta = json.loads(mp.read_text())
        if meta["phase"] != phase:
            continue
        warm[meta["concurrency"]] = meta["warmup_s"] / 60
        for lane, arm in sorted(meta["lane_arms"].items()):
            path = run / f"epp-{arm}-{lane}" / "results" / "vllm-metrics.csv"
            if not path.exists():
                continue
            rows = list(csv.DictReader(open(path)))
            t0 = float(rows[0]["ts"])
            t = np.array([(float(r["ts"]) - t0) / 60 for r in rows])
            run_ = np.array([float(r["num_requests_running"] or 0) for r in rows])
            wait = np.array([float(r["num_requests_waiting"] or 0) for r in rows])
            out.setdefault(meta["concurrency"], []).append((arm, lane, t, run_, wait))
    return out, warm


def rolling(y, n=15):  # 15 samples of 2 s = 30 s
    k = np.ones(n) / n
    return np.convolve(np.pad(y, (n // 2, n - 1 - n // 2), mode="edge"), k, mode="valid")


def queues_figure(phase, name, title):
    series, warm = queue_series(phase)
    cs = sorted(series)
    fig, axes = plt.subplots(len(cs), 2, figsize=(13, 2.35 * len(cs) + 1.0), sharex=True, squeeze=False)
    wmax = max(max(w.max() for *_, w in series[c]) for c in cs)
    rmax = max(max(rolling(r).max() for *_, r, _ in series[c]) for c in cs)
    grid = np.arange(0, 55, 0.1)
    for row, c in enumerate(cs):
        for col, (idx, ylabel) in enumerate(((3, "running"), (4, "waiting"))):
            ax = axes[row][col]
            for arm in LABEL:
                cells = [x for x in series[c] if x[0] == arm]
                if not cells:
                    continue
                # each cell resampled onto one minute grid (0 after it ended), then mean and min-max over cells
                ys = np.array([np.interp(grid, x[2], rolling(x[idx]), right=0.0) for x in cells])
                ax.plot(grid, ys.mean(axis=0), color=COLOR[arm], lw=2.0)
                if len(cells) > 1:
                    ax.fill_between(grid, ys.min(axis=0), ys.max(axis=0), color=COLOR[arm], alpha=0.18, lw=0)
            ax.axvline(warm[c], color="#7a7a7a", lw=1.2, ls=":")
            ax.set_ylim(0, rmax * 1.08 if idx == 3 else wmax * 1.08)
            ax.grid(axis="y", color="#E5E5E5", lw=1)
            ax.set_axisbelow(True)
            if row == 0:
                ax.set_title(f"vLLM requests {ylabel}", loc="left", fontweight="bold", fontsize=14)
            if col == 0:
                ax.set_ylabel(f"c = {c}", fontsize=13)
            ax.tick_params(labelsize=11)
    for ax in axes[-1]:
        ax.set_xlabel("minutes since the bench started")
    present = [a for a in LABEL if any(x[0] == a for c in cs for x in series[c])]
    handles = [Line2D([], [], color=COLOR[a], lw=2.4, label=LABEL[a]) for a in present]
    handles.append(Patch(facecolor="#7a7a7a", alpha=0.25, label="min-max over cells (replicates or pods)"))
    handles.append(Line2D([], [], color="#7a7a7a", lw=1.2, ls=":", label="end of warm-up"))
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=12, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(title, x=0.01, ha="left", fontsize=14)
    fig.tight_layout(rect=(0, 0.06 if len(cs) > 3 else 0.09, 1, 0.97))
    finalize_figure(fig, name)


def main():
    apply_publication_style()
    data = load_data()
    fig1_throughput(data)
    fig2_reuse_source(data)
    fig3_ttft(data)
    fig4_offload_effect(data)
    fig5_kv_budget(data)
    queues_figure("B", "fig6-vllm-queues-offload", "One vLLM replica per arm, CPU offloading 400 GiB (30 s rolling mean)")
    queues_figure("A", "fig7-vllm-queues-off", "One vLLM replica per arm, offloading off (30 s rolling mean)")


if __name__ == "__main__":
    main()
