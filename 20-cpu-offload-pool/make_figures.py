#!/usr/bin/env python3
"""Report figures for step 20, in the figures4papers publication style.

Reads the per-cell statistics through analyze.py (cached in
results/figure-data.json, delete it to recompute) and writes to figures/:

  fig1-throughput      output throughput against concurrency, every arm, offload off and on
  fig2-reuse-source    steady-state prefix reuse split into GPU hits and CPU tier hits
  fig3-latency         median TTFT, p99 TTFT and goodput within the 30 s TTFT SLO
  fig4-offload-effect  throughput with offloading off and on, at the points that have both

Each as PNG (300 dpi) and PDF.
Usage: uv run --with matplotlib --with numpy python make_figures.py
"""
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
# Blue: the lease gate as built (the key method); teal: its CPU-tier-sized
# variant; red: the llm-d default baseline.
ARMS = [("baseline", "llm-d default (no gate)", PALETTE["red_strong"], PALETTE["red_1"]),
        ("thunder-lease-main", "lease gate, GPU capacity", PALETTE["blue_main"], "#C9D8EC"),
        ("thunder-lease-main-tier", "lease gate, CPU-tier capacity", PALETTE["teal"], "#CDE6E8")]
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
        for p, t in zip(pos, gpu + cpu):
            ax.text(p, t + 0.015, f"{t:.2f}", ha="center", va="bottom", fontsize=9.5)
    ax.set_xticks(x, [str(c) for c in C_ALL])
    ax.set_xlabel("concurrent sessions per vLLM replica (CPU offloading 400 GiB)")
    ax.set_ylabel("prompt tokens served from cache\n(steady state)")
    ax.set_ylim(0, 1.08)
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)
    handles = [Patch(facecolor=COLOR[a], edgecolor="black", label=LABEL[a]) for a in arms]
    handles += [Patch(facecolor="white", edgecolor="black", label="solid: GPU prefix cache hit"),
                Patch(facecolor="white", edgecolor="black", hatch="//", label="hatched: CPU tier hit")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=3, fontsize=11.5)
    finalize_figure(fig, "fig2-reuse-source")


def fig3_latency(data):
    b = data["B"]
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.9))
    panels = [("ttft_p50", "median TTFT (s)", True), ("ttft_p99", "p99 TTFT (s)", True),
              ("goodput_slo", "turns/s within TTFT <= 30 s", False)]
    for ax, (key, ylabel, log) in zip(axes, panels):
        for arm in LABEL:
            if arm in b:
                c, m, _, _ = series(b[arm], key)
                ax.plot(c, m, color=COLOR[arm], lw=2.6, marker="o", ms=7)
        if key == "ttft_p99":
            ax.axhline(1800, color="#555555", lw=1.5, ls=":")
            ax.text(29, 1800 * 1.12, "forced admission at 1800 s", fontsize=10.5, color="#555555")
        if log:
            ax.set_yscale("log")
            ax.set_ylim(0.3, 4000)
        else:
            ax.set_ylim(0, 0.75)
        ax.set_ylabel(ylabel)
        c_axis(ax)
        ax.grid(axis="y", color="#E5E5E5", lw=1)
        ax.set_axisbelow(True)
    for ax, t in zip(axes, ("a", "b", "c")):
        ax.set_title(f"({t})", loc="left", fontweight="bold")
    handles = [Line2D([], [], color=COLOR[a], lw=2.6, marker="o", ms=7, label=LABEL[a]) for a in LABEL if a in b]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, -0.1), ncol=3, fontsize=12.5)
    fig.tight_layout()
    finalize_figure(fig, "fig3-latency")


def fig4_offload_effect(data):
    both = sorted(set(data["A"]["baseline"]) & set(data["B"]["baseline"]))
    groups = [("baseline", "A"), ("baseline", "B"), ("thunder-lease-main", "A"), ("thunder-lease-main", "B")]
    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.19
    x = np.arange(len(both))
    for i, (arm, phase) in enumerate(groups):
        pos = x + (i - 1.5) * (width + 0.02)
        vals = np.array([np.mean([r["throughput"] for r in data[phase][arm][c]]) for c in both])
        on = phase == "B"
        bars = ax.bar(pos, vals, width, color=COLOR[arm] if on else LIGHT[arm], edgecolor="black", lw=1.2,
                      hatch=None if on else "..", zorder=3)
        for p, v in zip(pos, vals):
            ax.text(p, v + 8, f"{v:.0f}", ha="center", va="bottom", fontsize=9.5)
        if on:
            off = np.array([np.mean([r["throughput"] for r in data["A"][arm][c]]) for c in both])
            for p, v, o in zip(pos, vals, off):
                ax.text(p - (width + 0.02) / 2, max(v, o) + 42, f"x{v / o:.2f}", ha="center", va="bottom",
                        fontsize=11, fontweight="bold", color=COLOR[arm])
    ax.set_xticks(x, [str(c) for c in both])
    ax.set_xlabel("concurrent sessions per vLLM replica")
    ax.set_ylabel("output throughput (tokens/s)")
    ax.set_ylim(0, 760)
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)
    handles = [Patch(facecolor=LIGHT["baseline"], edgecolor="black", hatch="..", label="llm-d default, offloading off"),
               Patch(facecolor=COLOR["baseline"], edgecolor="black", label="llm-d default, offloading 400 GiB"),
               Patch(facecolor=LIGHT["thunder-lease-main"], edgecolor="black", hatch="..", label="lease gate, offloading off"),
               Patch(facecolor=COLOR["thunder-lease-main"], edgecolor="black", label="lease gate, offloading 400 GiB")]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=11.5)
    finalize_figure(fig, "fig4-offload-effect")


def main():
    apply_publication_style()
    data = load_data()
    fig1_throughput(data)
    fig2_reuse_source(data)
    fig3_latency(data)
    fig4_offload_effect(data)


if __name__ == "__main__":
    main()
