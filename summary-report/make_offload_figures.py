#!/usr/bin/env python3
"""Figures for CPU-OFFLOAD-SUMMARY.md, focused exclusively on CPU KV offloading
and system bottlenecks (vLLM + llm-d default, without admission control gates).

Inputs:
  - data/engine-intervals.json, data/engine-cells.json, data/pool-sweep.json
  - ../13-llm-d-router-sweep/results/sweep-20260918-134248-t1900/sweep.md
  - ../20-cpu-offload-pool/results/figure-data.json
  - ../22-slo-goodput/results/goodput-data.json
Writes:
  - figures/offload-fig1-throughput-reuse.png
  - figures/offload-fig2-engine-bottleneck.png
  - figures/offload-fig3-latency-goodput.png
  - figures/offload-fig4-decode-bandwidth.png

Usage: uv run --with matplotlib --with numpy python make_offload_figures.py
"""
import importlib.util
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
OUT = HERE / "figures"
SWEEP = ROOT / "13-llm-d-router-sweep" / "results" / "sweep-20260918-134248-t1900"
GPU_KV = 2237040
TIER = 8738133
GIB_PER_TOKEN = 49152 / 2**30  # 48 layers x K,V x 4 KV heads x 128 dims x 1B (FP8)

spec = importlib.util.spec_from_file_location("figs20", ROOT / "20-cpu-offload-pool" / "make_figures.py")
m20 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m20)
P = m20.PALETTE
RED, BLUE, TEAL, VIOLET, GRAY = P["red_strong"], P["blue_main"], P["teal"], P["violet"], "#7a7a7a"
LIGHT_BLUE = "#C9D8EC"
LIGHT_RED = P["red_1"]
ORANGE = "#E08A00"
C_ALL = [32, 64, 128, 192, 256]


def style():
    m20.apply_publication_style(font_size=13)
    plt.rcParams["font.family"] = ["DejaVu Sans", "Helvetica", "Arial", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=220, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def grid(ax):
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)


def step20():
    """{phase: {c: [cells]}} for the llm-d default ('baseline') arm."""
    d = {"A": {}, "B": {}}
    for r in json.loads((ROOT / "20-cpu-offload-pool" / "results" / "figure-data.json").read_text()):
        if r["arm"] == "baseline":
            d[r["phase"]].setdefault(r["c"], []).append(r)
    return d


def engine_cells():
    """{phase: {c: [cells]}} from data/engine-cells.json for step 20 baseline."""
    d = {"A": {}, "B": {}}
    for r in json.loads((DATA / "engine-cells.json").read_text()):
        if r["step"] == "20" and r["arm"] == "baseline":
            d[r["phase"]].setdefault(r["c"], []).append(r)
    return d


def mean(cells, key):
    return float(np.mean([x[key] for x in cells if x.get(key) is not None]))


def series(by_c, key, scale=1.0):
    cs = sorted(by_c)
    vals = [[x[key] * scale for x in by_c[c] if x.get(key) is not None] for c in cs]
    return (np.array(cs), np.array([np.mean(v) for v in vals]),
            np.array([min(v) for v in vals]), np.array([max(v) for v in vals]))


def c_axis(ax):
    ax.set_xscale("log", base=2)
    ax.set_xticks(C_ALL, [str(c) for c in C_ALL])
    ax.minorticks_off()
    ax.set_xlim(27, 300)
    ax.set_xlabel("Concurrent sessions per replica")


# ---------------------------------------------------------------- figure 1
def fig1_throughput_reuse():
    s20 = step20()
    fig, axes = plt.subplots(1, 3, figsize=(17.5, 5.5))

    # (a) Output throughput vs concurrency
    ax = axes[0]
    ax.axvspan(128, 192, color=P["neutral"], alpha=0.35, lw=0, zorder=0)
    ax.text(157, 45, "CPU tier fills\n(working set\n0.81x -> 1.07x)", ha="center", va="bottom",
            fontsize=10.5, color="#555555")

    cb, mb, lob, hib = series(s20["B"], "throughput")
    ca, ma, loa, hia = series(s20["A"], "throughput")
    ax.plot(cb, mb, color=BLUE, lw=2.8, marker="o", ms=8, label="400 GiB CPU offloading (3 runs)", zorder=3)
    ax.vlines(cb, lob, hib, color=BLUE, lw=2, zorder=2)
    ax.plot(ca, ma, color=RED, lw=2.2, ls="--", marker="o", ms=8, mfc="white", mew=2,
            label="CPU offloading off (GPU KV only)", zorder=3)
    ax.vlines(ca, loa, hia, color=RED, lw=2, zorder=2)

    for c_val, y_on, y_off in ((32, dict(zip(cb, mb))[32], dict(zip(ca, ma))[32]),
                               (128, dict(zip(cb, mb))[128], dict(zip(ca, ma))[128]),
                               (256, dict(zip(cb, mb))[256], dict(zip(ca, ma))[256])):
        ax.annotate(f"{y_on / y_off:.2f}x\n({y_on:.0f} vs {y_off:.0f})",
                    (c_val, max(y_on, y_off)), xytext=(0, 12), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10, fontweight="bold", color=BLUE)

    ax.set_ylim(0, 720)
    ax.set_ylabel("Output throughput (tok/s)")
    ax.set_title("(a) Output throughput vs concurrency", loc="left", fontsize=13.5, fontweight="bold")
    c_axis(ax)
    grid(ax)
    ax.legend(loc="lower left", fontsize=10.5)

    # (b) Steady-state cache hit rate split into GPU vs CPU tier
    ax = axes[1]
    x = np.arange(len(C_ALL))
    width = 0.36
    gpu_b = np.array([mean(s20["B"][c], "gpu_hit_steady") for c in C_ALL])
    cpu_b = np.array([mean(s20["B"][c], "cpu_hit_steady") for c in C_ALL])
    tot_b = [[r["gpu_hit_steady"] + r["cpu_hit_steady"] for r in s20["B"][c]] for c in C_ALL]
    lo_b, hi_b = np.array([min(t) for t in tot_b]), np.array([max(t) for t in tot_b])

    pos_b = x - width / 2 - 0.02
    ax.bar(pos_b, gpu_b, width, color=BLUE, edgecolor="black", lw=1.1, zorder=3,
           label="400 GiB offload: GPU KV hit")
    ax.bar(pos_b, cpu_b, width, bottom=gpu_b, color=LIGHT_BLUE, edgecolor="black", lw=1.1, hatch="//",
           zorder=3, label="400 GiB offload: CPU tier hit")
    ax.vlines(pos_b, lo_b, hi_b, color="black", lw=1.4, zorder=4)
    for p, t, h in zip(pos_b, gpu_b + cpu_b, hi_b):
        ax.text(p, h + 0.02, f"{t:.2f}", ha="center", va="bottom", fontsize=9.5, color=BLUE, fontweight="bold")

    pos_a = x + width / 2 + 0.02
    for idx, c in enumerate(C_ALL):
        if c in s20["A"]:
            g_a = mean(s20["A"][c], "gpu_hit_steady")
            ax.bar(pos_a[idx], max(g_a, 0.008), width, color=LIGHT_RED, edgecolor=RED, lw=1.4, hatch="..", zorder=3)
            ax.text(pos_a[idx], max(g_a, 0.008) + 0.02, f"{g_a:.2f}\n(off)", ha="center", va="bottom",
                    fontsize=9.0, color=RED, fontweight="bold")

    handles_b = [
        Patch(facecolor=BLUE, edgecolor="black", lw=1.1, label="400 GiB offload: GPU KV hit"),
        Patch(facecolor=LIGHT_BLUE, edgecolor="black", lw=1.1, hatch="//", label="400 GiB offload: CPU tier hit"),
        Patch(facecolor=LIGHT_RED, edgecolor=RED, lw=1.4, hatch="..", label="Offload off: GPU KV hit (c=32, 128, 256)"),
    ]
    ax.set_xticks(x, [str(c) for c in C_ALL])
    ax.set_xlabel("Concurrent sessions per replica")
    ax.set_ylabel("Steady-state prompt cache hit rate")
    ax.set_ylim(0, 1.15)
    ax.set_title("(b) Cache hit rate by tier (GPU vs CPU)", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax.legend(handles=handles_b, loc="upper right", fontsize=9.5)

    # (c) Workload KV working set vs GPU KV and CPU tier capacity
    ax = axes[2]
    tok = np.array([mean(s20["B"][c], "ws_over_tier") * TIER for c in C_ALL])
    tok_lo = np.array([min(r["ws_over_tier"] for r in s20["B"][c]) * TIER for c in C_ALL])
    tok_hi = np.array([max(r["ws_over_tier"] for r in s20["B"][c]) * TIER for c in C_ALL])
    ax.bar(x, tok / 1e6, 0.52, color="#D9D9D9", edgecolor="black", lw=1.1, zorder=3)
    ax.vlines(x, tok_lo / 1e6, tok_hi / 1e6, color="black", lw=1.4, zorder=4)
    for xi, t, h in zip(x, tok, tok_hi):
        ax.text(xi, h / 1e6 + 0.22, f"{t / 1e6:.2f}M\n({t * GIB_PER_TOKEN:.0f} GiB)",
                ha="center", va="bottom", fontsize=9.5)
    ax.axhline(GPU_KV / 1e6, color=RED, lw=2.2, ls="--", zorder=4,
               label=f"GPU KV: {GPU_KV / 1e6:.2f}M tok ({GPU_KV * GIB_PER_TOKEN:.0f} GiB)")
    ax.axhline(TIER / 1e6, color=BLUE, lw=2.2, ls="--", zorder=4,
               label=f"CPU tier: {TIER / 1e6:.2f}M tok (400 GiB)")
    ax.set_xticks(x, [str(c) for c in C_ALL])
    ax.set_xlabel("Concurrent sessions per replica")
    ax.set_ylabel("Active KV working set (M tokens)")
    ax.set_ylim(0, 13.8)
    ax.set_title("(c) Active working set vs tier capacity", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax.legend(loc="upper left", fontsize=10)

    fig.tight_layout()
    save(fig, "offload-fig1-throughput-reuse")


# ---------------------------------------------------------------- figure 2
def engine_fit_all():
    iv_all = [r for r in json.loads((DATA / "engine-intervals.json").read_text()) if r["steps"] > 50 and r["running"] >= 1]
    step_all = np.array([1000 * r["dt"] / r["steps"] for r in iv_all])
    pre_all = np.array([max(r["sched"] - r["gen"], 0) / r["steps"] / 1000 for r in iv_all])
    X = np.c_[np.ones_like(pre_all), pre_all]
    coef, *_ = np.linalg.lstsq(X, step_all, rcond=None)
    r2 = 1 - ((step_all - X @ coef) ** 2).sum() / ((step_all - step_all.mean()) ** 2).sum()
    return iv_all, coef, r2


def fig2_engine_bottleneck():
    iv_all, coef, r2 = engine_fit_all()
    iv_base = [r for r in iv_all if r["arm"] == "baseline"]
    ec = engine_cells()

    fig, axes = plt.subplots(1, 3, figsize=(17.5, 5.6), gridspec_kw={"width_ratios": [1.15, 1.15, 1.1]})

    # (a) Engine step duration vs prefill computed per step
    ax = axes[0]
    for phase, label, color, face in (("A", "CPU offloading off (step 20 Phase A)", RED, "none"),
                                      ("B", "400 GiB CPU offloading (step 20 Phase B)", BLUE, BLUE)):
        pts = [r for r in iv_base if r["phase"] == phase]
        pre = np.array([max(r["sched"] - r["gen"], 0) / r["steps"] / 1000 for r in pts])
        st = np.array([1000 * r["dt"] / r["steps"] for r in pts])
        ax.scatter(pre, st, s=12, color=face, edgecolor=color, lw=0.8, alpha=0.45, label=label, zorder=2)

    xs = np.linspace(0, 4.2, 10)
    ax.plot(xs, coef[0] + coef[1] * xs, color="black", lw=2.2, zorder=3,
            label=f"Linear fit: {coef[0]:.0f} ms + {coef[1]:.0f} ms / k prefill tok")
    ax.text(0.15, 175, f"Step time = {coef[0]:.0f} ms + {coef[1]:.0f} ms x (k prefill tok / step)\n"
                       f"Decode floor = {coef[0]:.0f} ms (full GPU KV)\n"
                       f"Prefill slope = {coef[1]:.0f} ms per 1k tokens",
            fontsize=10.2, va="top")
    ax.set_xlim(0, 4.2)
    ax.set_ylim(0, 190)
    ax.set_xlabel("Prefill computed per step (k tokens)")
    ax.set_ylabel("Engine step duration (ms)")
    ax.set_title("(a) Step duration vs prefill work per step", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    leg = ax.legend(loc="lower right", fontsize=9.8, markerscale=1.8)
    for lh in leg.legend_handles:
        lh.set_alpha(1)

    # (b) Step time decomposition across c
    ax = axes[1]
    xpos, xt, xl = 0, [], []
    for c in C_ALL:
        first = xpos
        for phase, color, face in (("A", RED, "white"), ("B", BLUE, BLUE)):
            v = ec[phase].get(c, [])
            if not v:
                continue
            steps = sum(x["steps"] for x in v)
            st_ms = 1000 * sum(x["dt"] for x in v) / steps
            p = sum(x["sched"] - x["gen"] for x in v) / steps / 1000
            ax.bar(xpos, coef[0], color="#D9D9D9", edgecolor="black", lw=0.9, width=0.78)
            ax.bar(xpos, coef[1] * p, bottom=coef[0], color=face, edgecolor=color,
                   hatch=".." if face == "white" else None, width=0.78, lw=1.2)
            ax.plot(xpos, st_ms, marker="_", color="black", ms=15, mew=2.4, zorder=4)
            ax.text(xpos, max(st_ms, coef[0] + coef[1] * p) + 3, f"{st_ms:.0f}", ha="center", va="bottom",
                    fontsize=9.5, color=color, fontweight="bold")
            xpos += 1
        xt.append((first + xpos - 1) / 2)
        xl.append(f"c={c}")
        xpos += 0.7
    ax.set_xticks(xt, xl)
    ax.set_ylabel("Mean engine step duration (ms)")
    ax.set_ylim(0, 178)
    ax.set_title("(b) Step duration breakdown (decode + prefill)", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    h = [Patch(facecolor="#D9D9D9", edgecolor="black", label=f"Constant decode floor ({coef[0]:.0f} ms)"),
         Patch(facecolor=BLUE, edgecolor=BLUE, label="Prefill cost: 400 GiB CPU offload"),
         Patch(facecolor="white", edgecolor=RED, hatch="..", label="Prefill cost: CPU offload off"),
         Line2D([], [], marker="_", color="black", ls="none", ms=14, mew=2.4, label="Measured mean step duration")]
    ax.legend(handles=h, loc="upper left", fontsize=9.2)

    # (c) Decoding batch B (gen/steps) vs waiting queue in vLLM
    ax = axes[2]
    cs_b = sorted(ec["B"])
    dec_b = [sum(x["gen"] for x in ec["B"][c]) / sum(x["steps"] for x in ec["B"][c]) for c in cs_b]
    wait_b = [np.mean([x["waiting"] for x in ec["B"][c]]) for c in cs_b]
    cs_a = sorted(ec["A"])
    dec_a = [sum(x["gen"] for x in ec["A"][c]) / sum(x["steps"] for x in ec["A"][c]) for c in cs_a]
    wait_a = [np.mean([x["waiting"] for x in ec["A"][c]]) for c in cs_a]

    ax.plot(cs_b, wait_b, color=ORANGE, lw=2.6, marker="s", ms=7, label="Waiting in vLLM queue (400 GiB offload)")
    ax.plot(cs_a, wait_a, color=ORANGE, lw=2.0, ls="--", marker="s", mfc="white", ms=7,
            label="Waiting in vLLM queue (offload off)")
    ax.plot(cs_b, dec_b, color=BLUE, lw=2.6, marker="o", ms=7, label="Decoding batch B (400 GiB offload)")
    ax.plot(cs_a, dec_a, color=RED, lw=2.0, ls="--", marker="o", mfc="white", ms=7,
            label="Decoding batch B (offload off)")

    for c_val, w_val in zip(cs_b, wait_b):
        offset_y = 9 if c_val != 32 else -15
        ax.annotate(f"{w_val:.0f}", (c_val, w_val), xytext=(0, offset_y), textcoords="offset points",
                    ha="center", fontsize=9.5, color="#9a5b00", fontweight="bold")
    for c_val, r_val in zip(cs_b, dec_b):
        offset_y = -15 if c_val != 32 else 9
        ax.annotate(f"{r_val:.0f}", (c_val, r_val), xytext=(0, offset_y), textcoords="offset points",
                    ha="center", fontsize=9.5, color=BLUE, fontweight="bold")

    ax.axhspan(22, 36, color="#DCE8F7", alpha=0.55, lw=0, zorder=0)
    ax.text(85, 44, "Decoding batch B capped at 26-36\nby 2.24M-token GPU KV capacity", fontsize=9.5, color=BLUE)
    ax.set_ylim(0, 245)
    c_axis(ax)
    ax.set_ylabel("Requests in vLLM (steady-state mean)")
    ax.set_title("(c) Decoding batch B vs waiting queue", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax.legend(loc="upper left", fontsize=9.2)

    fig.tight_layout()
    save(fig, "offload-fig2-engine-bottleneck")
    return coef, r2


# ---------------------------------------------------------------- figure 3
def fig3_latency_goodput():
    gp_rows = [r for r in json.loads((ROOT / "22-slo-goodput" / "results" / "goodput-data.json").read_text())
               if r["arm"] == "baseline"]
    gp = {"A": {}, "B": {}}
    for r in gp_rows:
        gp[r["phase"]].setdefault(r["c"], []).append(r)

    fig, axes = plt.subplots(1, 3, figsize=(17.5, 5.5))

    # (a) Steady-state median and p99 TTFT vs concurrency
    ax = axes[0]
    cb, p50_b, lo50_b, hi50_b = series(gp["B"], "ttft_p50")
    _, p99_b, lo99_b, hi99_b = series(gp["B"], "ttft_p99")
    ca, p50_a, lo50_a, hi50_a = series(gp["A"], "ttft_p50")

    ax.plot(cb, p50_b, color=BLUE, lw=2.6, marker="o", ms=7, label="p50 TTFT, 400 GiB offload")
    ax.vlines(cb, lo50_b, hi50_b, color=BLUE, lw=1.8)
    ax.plot(cb, p99_b, color=BLUE, lw=1.8, ls=":", marker="^", ms=6, label="p99 TTFT, 400 GiB offload")
    ax.plot(ca, p50_a, color=RED, lw=2.2, ls="--", marker="o", mfc="white", ms=7, label="p50 TTFT, offload off")

    for x_val, y_val in zip(cb, p50_b):
        ax.annotate(f"{y_val:.0f}s", (x_val, y_val),
                    xytext=(0, -15), textcoords="offset points",
                    ha="center", fontsize=9.8, color=BLUE, fontweight="bold")
    for x_val, y_val in zip(ca, p50_a):
        ax.annotate(f"{y_val:.0f}s", (x_val, y_val), xytext=(0, 10), textcoords="offset points",
                    ha="center", fontsize=9.5, color=RED, fontweight="bold")

    ax.axhline(30, color=GRAY, lw=1.4, ls=":")
    ax.text(95, 34, "30 s interactive SLO", fontsize=10, color="#555555")
    ax.set_yscale("log")
    ax.set_ylim(3, 1500)
    ax.set_yticks([10, 100, 1000], ["10 s", "100 s", "1000 s"])
    ax.minorticks_off()
    c_axis(ax)
    ax.set_ylabel("Steady-state TTFT")
    ax.set_title("(a) Steady-state TTFT vs concurrency", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax.legend(loc="upper left", fontsize=9.5)

    # (b) Steady-state throughput vs Goodput (TTFT <= 30 s and <= 60 s)
    ax = axes[1]
    cs_b = sorted(gp["B"])
    tp_b = [mean(gp["B"][c], "throughput_steady") for c in cs_b]
    gp30_b = [mean(gp["B"][c], "goodput_30") for c in cs_b]
    gp60_b = [mean(gp["B"][c], "goodput_60") for c in cs_b]
    cs_a = sorted(gp["A"])
    gp30_a = [mean(gp["A"][c], "goodput_30") for c in cs_a]

    ax.plot(cs_b, tp_b, color=BLUE, lw=1.8, ls=":", marker="o", mfc="white", ms=6,
            label="Raw steady-state throughput (400 GiB offload)")
    ax.plot(cs_b, gp60_b, color=TEAL, lw=2.2, ls="-.", marker="s", ms=6,
            label="Goodput, TTFT <= 60 s (400 GiB offload)")
    ax.plot(cs_b, gp30_b, color=BLUE, lw=2.8, marker="o", ms=7,
            label="Goodput, TTFT <= 30 s (400 GiB offload)")
    ax.plot(cs_a, gp30_a, color=RED, lw=2.2, ls="--", marker="o", mfc="white", ms=7,
            label="Goodput, TTFT <= 30 s (offload off)")

    ax.annotate("465 tok/s\n(2.0x vs offload off)", (32, gp30_b[0]), xytext=(14, -22),
                textcoords="offset points", fontsize=9.8, color=BLUE, fontweight="bold")
    ax.annotate("231 tok/s", (32, gp30_a[0]), xytext=(12, -4),
                textcoords="offset points", fontsize=9.5, color=RED, fontweight="bold")
    ax.annotate("0 tok/s for c >= 64\n(every turn waits > 30 s in FCFS queue)",
                (64, 5), xytext=(12, 38), textcoords="offset points",
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.2),
                fontsize=9.8, color=RED, fontweight="bold")

    ax.set_ylim(-15, 650)
    c_axis(ax)
    ax.set_ylabel("Tokens/s (steady-state window)")
    ax.set_title("(b) Raw throughput vs SLO goodput", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax.legend(loc="upper right", fontsize=9.2)

    # (c) TTFT CDF across concurrencies with 400 GiB CPU offloading
    ax = axes[2]
    x_cdf = np.logspace(-1, np.log10(2000), 61)
    c_colors = {32: BLUE, 64: TEAL, 128: ORANGE, 192: VIOLET, 256: RED}
    for c in C_ALL:
        cdf = np.mean([r["cdf"] for r in gp["B"][c]], axis=0)
        ax.plot(x_cdf, cdf, color=c_colors[c], lw=2.4, label=f"c = {c} (400 GiB offload)")
    cdf_a32 = np.mean([r["cdf"] for r in gp["A"][32]], axis=0)
    ax.plot(x_cdf, cdf_a32, color=BLUE, lw=1.8, ls="--", label="c = 32 (offload off)")

    ax.axvline(30, color=GRAY, lw=1.4, ls=":")
    ax.text(33, 0.06, "30 s SLO", color="#555555", fontsize=10)
    ax.set_xscale("log")
    ax.set_xticks([0.1, 1, 10, 100, 1000], ["0.1 s", "1 s", "10 s", "100 s", "1000 s"])
    ax.minorticks_off()
    ax.set_xlim(0.5, 1200)
    ax.set_ylim(0, 1.03)
    ax.set_xlabel("TTFT")
    ax.set_ylabel("Fraction of turns with TTFT <= x")
    ax.set_title("(c) Whole-queue shift in TTFT distribution", loc="left", fontsize=13.5, fontweight="bold")
    ax.grid(color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", fontsize=9.2)

    fig.tight_layout()
    save(fig, "offload-fig3-latency-goodput")


# ---------------------------------------------------------------- figure 4
def sweep_kv():
    text = (SWEEP / "sweep.md").read_text()
    block = text.split("## pool KV\n", 1)[1].split("\n## ", 1)[0]
    out = {}
    for line in block.splitlines():
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and cells[0].isdigit() and re.fullmatch(r"[0-9.]+", cells[2]):
            out[int(cells[0])] = float(cells[2])
    return out


def fig4_decode_bandwidth():
    pd = {r["c"]: r for r in json.loads((DATA / "pool-sweep.json").read_text()) if r["arm"] == "baseline"}
    kv13 = sweep_kv()
    iv_all, _, _ = engine_fit_all()
    iv_base = [r for r in iv_all if r["arm"] == "baseline"]
    pre = np.array([max(r["sched"] - r["gen"], 0) / r["steps"] / 1000 for r in iv_base])
    step = np.array([1000 * r["dt"] / r["steps"] for r in iv_base])
    m = pre < 0.1
    kv20 = np.median([r["kv"] for r, ok in zip(iv_base, m) if ok]) * GPU_KV / 1e6
    st20 = float(np.median(step[m]))

    fig, ax = plt.subplots(figsize=(9.2, 5.4))

    pts = sorted((kv13[c] * GPU_KV / 1e6, 1000 * pd[c]["itl_p50"], c) for c in pd if c in kv13)
    xs, ys, cs13 = zip(*pts)
    ax.plot(xs, ys, color=RED, marker="o", ms=7, lw=2.2,
            label="4-pod pool sweep, llm-d default (step 13, c = 16..336)")
    ax.plot([kv20], [st20], marker="*", ms=17, color=BLUE, ls="none",
            label=f"1 replica with 400 GiB offload, pure-decode steps: {st20:.0f} ms")

    for x_v, y_v, c_v in pts:
        if c_v in (16, 48, 96, 192):
            ax.annotate(f"{c_v // 4}/pod", (x_v, y_v), xytext=(0, 9), textcoords="offset points",
                        ha="center", fontsize=9.5, color=RED)

    ax.axvline(GPU_KV / 1e6, color=GRAY, lw=1.3, ls=":")
    ax.text(GPU_KV / 1e6 - 0.04, 51, "GPU KV capacity\n2.24M tokens (102 GiB)",
            ha="right", fontsize=10, color="#555555")
    ax.text(0.10, 46, "HBM bandwidth scaling:\nReading 2.18M tokens (100 GiB across 2x H100)\n"
                      "every decode step takes ~44-46 ms\n(~1.2 TB/s per GPU, ~22 tok/s/req max)",
            fontsize=10, color="#333333", bbox=dict(boxstyle="round,pad=0.35", facecolor="#F7F7F7", edgecolor="#CCCCCC"))
    ax.set_xlim(0, 2.4)
    ax.set_ylim(0, 60)
    ax.set_xlabel("Resident GPU KV per replica (M tokens)")
    ax.set_ylabel("Decode inter-token latency, ITL (ms)")
    ax.set_title("HBM bandwidth bottleneck: decode step time vs resident GPU KV", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax.legend(loc="lower right", fontsize=9.8)

    fig.tight_layout()
    save(fig, "offload-fig4-decode-bandwidth")


def main():
    style()
    fig1_throughput_reuse()
    coef, r2 = fig2_engine_bottleneck()
    fig3_latency_goodput()
    fig4_decode_bandwidth()
    print(f"Done. Step fit: {coef[0]:.1f} ms + {coef[1]:.1f} ms/k-tok (R2={r2:.3f})")


if __name__ == "__main__":
    main()
