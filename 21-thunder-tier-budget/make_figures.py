#!/usr/bin/env python3
"""Report figures for step 21, in step 20's publication style.

Compares the three step 21 arms (one run) with step 20's GPU tier and CPU tier
arms (phase B, mean of 3 runs, min-max lines), at c = 64 to 256. Per-cell
statistics come from step 20's analyze.py (cached in results/figure-data.json;
delete it to recompute). Writes to figures/, PNG and PDF:

  fig1-throughput    output throughput against concurrency
  fig2-reuse         total prefix reuse and CPU tier hit rate
  fig3-wait          median TTFT, p99 TTFT, forced admissions
  fig4-tier-budget   the budget arms' resident footprint against the tier
                     budget, and forced admissions accumulating, over time

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

HERE = Path(__file__).resolve().parent
STEP20 = HERE.parent / "20-cpu-offload-pool"
CACHE = HERE / "results" / "figure-data.json"
CS = [64, 128, 192, 256]
TIER_TOKENS = 8738133


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m20 = load("figs20", STEP20 / "make_figures.py")
m20.OUT = HERE / "figures"
P = m20.PALETTE
# (key, label, color, line style, marker): step 20 references first, then the step 21 arms
ARMS = [("B:thunder-lease-main", "GPU tier (step 20, 3 runs)", P["blue_main"], "-", "o"),
        ("B:thunder-lease-main-tier", "CPU tier (step 20, 3 runs)", P["teal"], "-", "o"),
        ("T:thunder-lease-budget30", "tier budget, lease 30 s", P["violet"], "-", "s"),
        ("T:thunder-lease-budget5", "tier budget, lease 5 s", "#E08A00", "-", "s"),
        ("T:thunder-lease-main5", "GPU tier, lease 5 s", P["blue_secondary"], "--", "s")]
KEYS = ["throughput", "reuse_steady", "cpu_hit_steady", "gpu_hit_steady", "ttft_p50", "ttft_p99",
        "epp_starvation_promotions", "epp_holds"]


def load_data():
    """{"phase:arm": {c: [stats of each cell]}} for the arms in ARMS."""
    if CACHE.exists():
        raw = json.loads(CACHE.read_text())
    else:
        a = load("a20", STEP20 / "analyze.py")
        raw = []
        for results in (STEP20 / "results", HERE / "results"):
            a.RESULTS = results
            for meta, _, cells in a.collect():
                for c in cells:
                    raw.append({"key": f"{meta['phase']}:{c['arm']}", "c": meta["concurrency"],
                                "cell": str(c["cell"]), **{k: c.get(k) for k in KEYS}})
        CACHE.write_text(json.dumps(raw, indent=1))
    want = {k for k, *_ in ARMS}
    data = {}
    for r in raw:
        if r["key"] in want and r["c"] in CS:
            data.setdefault(r["key"], {}).setdefault(r["c"], []).append(r)
    return data


def lines(ax, data, key, scale=1.0):
    for k, _, color, ls, marker in ARMS:
        if k not in data:
            continue
        c, m, lo, hi = m20.series(data[k], key, scale)
        ax.plot(c, m, color=color, lw=2.4, ls=ls, marker=marker, ms=7, zorder=3)
        ax.vlines(c, lo, hi, color=color, lw=1.8, zorder=2)


def axis(ax):
    ax.set_xscale("log", base=2)
    ax.set_xticks(CS, [str(c) for c in CS])
    ax.minorticks_off()
    ax.set_xlim(56, 290)
    ax.set_xlabel("concurrent sessions per vLLM replica")
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)


def legend(fig, ncol=3, y=-0.02):
    handles = [Line2D([], [], color=c, lw=2.4, ls=ls, marker=mk, ms=7, label=lab) for _, lab, c, ls, mk in ARMS]
    fig.legend(handles=handles, loc="lower center", ncol=ncol, fontsize=11.5, bbox_to_anchor=(0.5, y))


def fig1_throughput(data):
    fig, ax = plt.subplots(figsize=(8.4, 5.6))
    lines(ax, data, "throughput")
    ax.set_ylim(0, 720)
    ax.set_ylabel("output throughput (tokens/s)")
    axis(ax)
    ax.set_title("CPU offloading 400 GiB; step 21 arms: one run; vertical line: min-max", loc="left",
                 fontsize=10.5, color="#555555")
    legend(fig, ncol=2, y=-0.06)
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    m20.finalize_figure(fig, "fig1-throughput")


def fig2_reuse(data):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    for ax, (key, title) in zip(axes, (("reuse_steady", "(a) total prefix reuse (GPU + CPU)"),
                                       ("cpu_hit_steady", "(b) CPU tier hit rate"))):
        lines(ax, data, key)
        ax.set_ylim(0, 1)
        ax.set_ylabel("share of prompt tokens, steady state")
        ax.set_title(title, loc="left", fontweight="bold", fontsize=14)
        axis(ax)
    legend(fig)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    m20.finalize_figure(fig, "fig2-reuse")


def fig3_wait(data):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    for ax, (key, title, log) in zip(axes, (("ttft_p50", "(a) median TTFT", True),
                                            ("ttft_p99", "(b) p99 TTFT", True),
                                            ("epp_starvation_promotions", "(c) forced admissions per cell", False))):
        lines(ax, data, key)
        if log:
            ax.set_yscale("log")
            ax.set_ylim(0.3, 4000)
            ax.set_yticks([1, 10, 100, 1000], ["1 s", "10 s", "100 s", "1000 s"])
            ax.minorticks_off()
            ax.set_ylabel("time to first token")
        else:
            ax.set_ylim(bottom=0)
            ax.set_ylabel("sessions admitted after waiting 1800 s")
        if key == "ttft_p99":
            ax.axhline(1800, color="#7a7a7a", lw=1.4, ls=":")
            ax.text(58, 2150, "forced admission at 1800 s", fontsize=10.5, color="#555555")
        ax.set_title(title, loc="left", fontweight="bold", fontsize=14)
        axis(ax)
    axes[2].text(0.03, 0.95, "windows: 30 min at c = 64, 128;\n45 min at c = 192, 256",
                 transform=axes[2].transAxes, fontsize=10, color="#555555", va="top")
    legend(fig)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    m20.finalize_figure(fig, "fig3-wait")


def epp_series(cell):
    """minutes, resident tokens and cumulative forced admissions from a cell's raw EPP scrapes."""
    a = load("a20ts", STEP20 / "analyze.py")
    keep = lambda n: {"endpoint_resident_tokens": "res", "starvation_promotions": "forced"}.get(
        n[n.find("thunder_agent_") + len("thunder_agent_"):] if "thunder_agent_" in n else "")
    snaps = a.raw_snapshots(Path(cell) / "results" / "raw-epp-metrics.txt.gz", keep)
    t0 = snaps[0][0]
    t = np.array([(ts - t0) / 60 for ts, _ in snaps])
    return t, np.array([s.get("res", 0.0) for _, s in snaps]), np.array([s.get("forced", 0.0) for _, s in snaps])


def fig4_tier_budget(data):
    budget = [k for k in ("T:thunder-lease-budget30", "T:thunder-lease-budget5") if k in data]
    style = {k: (lab, col) for k, lab, col, *_ in ARMS}
    fig, axes = plt.subplots(2, 2, figsize=(14, 8.2), sharex=True)
    for row, c in enumerate((192, 256)):
        for k in ("T:thunder-lease-budget30", "T:thunder-lease-budget5", "T:thunder-lease-main5"):
            if k not in data or c not in data[k]:
                continue
            t, res, forced = epp_series(data[k][c][0]["cell"])
            lab, col = style[k]
            if k in budget:
                axes[row][0].plot(t, res / 1e6, color=col, lw=2.0)
            axes[row][1].plot(t, forced, color=col, lw=2.0, ls="--" if k.endswith("main5") else "-")
        axes[row][0].axhline(TIER_TOKENS / 1e6, color="#555555", lw=1.4, ls=":")
        axes[row][0].text(33, TIER_TOKENS / 1e6 - 0.5, "tier budget 8.74M tokens", fontsize=10.5, color="#555555",
                          va="top")
        axes[row][0].set_ylabel(f"c = {c}\nresident footprint (M tokens)")
        axes[row][1].set_ylabel("forced admissions, cumulative")
        for ax in axes[row]:
            ax.axvline(15, color="#9a9a9a", lw=1, ls=":")
            ax.grid(axis="y", color="#E5E5E5", lw=1)
            ax.set_axisbelow(True)
            ax.set_ylim(bottom=0)
    axes[0][0].set_title("(a) tier budget arms: resident footprint vs budget", loc="left", fontweight="bold", fontsize=13)
    axes[0][1].set_title("(b) forced admissions accumulate (1800 s backstop)", loc="left", fontweight="bold", fontsize=13)
    for ax in axes[-1]:
        ax.set_xlabel("minutes since the bench started (dotted: end of warm-up)")
    handles = [Line2D([], [], color=style[k][1], lw=2.2, ls="--" if k.endswith("main5") else "-", label=style[k][0])
               for k in ("T:thunder-lease-budget30", "T:thunder-lease-budget5", "T:thunder-lease-main5") if k in data]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=11.5, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    m20.finalize_figure(fig, "fig4-tier-budget")


def main():
    m20.apply_publication_style()
    data = load_data()
    fig1_throughput(data)
    fig2_reuse(data)
    fig3_wait(data)
    fig4_tier_budget(data)


if __name__ == "__main__":
    main()
