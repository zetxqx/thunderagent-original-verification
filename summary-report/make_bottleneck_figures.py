#!/usr/bin/env python3
"""Figures for CPU-OFFLOAD-BOTTLENECK.md: where is the bottleneck once CPU KV
offloading is on? All three step 20 arms are shown with explicit labels:

  llm-d default                 no admission control
  thunder agent, GPU tier gate  admitted working set bounded to GPU KV (2.24M tok)
  thunder agent, CPU tier gate  admitted working set bounded to CPU tier (8.74M tok)

Inputs: data/engine-cells.json, data/engine-intervals.json, data/pool-sweep.json,
        ../20-cpu-offload-pool/results/figure-data.json,
        ../22-slo-goodput/results/goodput-data.json
Writes: figures/bottleneck-fig1..6.png

Usage: uv run --with matplotlib --with numpy python make_bottleneck_figures.py
"""
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
GIB_PER_TOKEN = 49152 / 2**30
C_ALL = [32, 64, 128, 192, 256]

P = {"blue_main": "#0F4D92", "red_strong": "#B64342", "red_1": "#F6CFCB", "teal": "#42949E", "neutral": "#CFCECE"}
RED, BLUE, TEAL, GRAY, ORANGE = P["red_strong"], P["blue_main"], P["teal"], "#7a7a7a", "#E08A00"

ARMS = [("baseline", "llm-d default (no admission control)", RED, "o"),
        ("thunder-lease-main", "thunder agent, GPU tier gate (2.24M tok)", BLUE, "s"),
        ("thunder-lease-main-tier", "thunder agent, CPU tier gate (8.74M tok)", TEAL, "D")]
LABEL = {a: l for a, l, _, _ in ARMS}
COLOR = {a: c for a, _, c, _ in ARMS}
MARK = {a: m for a, _, _, m in ARMS}


def style():
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial", "sans-serif"],
        "font.size": 13, "axes.linewidth": 2.0,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.major.width": 1.5, "ytick.major.width": 1.5,
        "legend.frameon": False, "axes.unicode_minus": False,
    })


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=220, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print("wrote", OUT / f"{name}.png")


def grid(ax):
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)


def c_axis(ax, label="Concurrent sessions per replica (c)"):
    ax.set_xscale("log", base=2)
    ax.set_xticks(C_ALL, [str(c) for c in C_ALL])
    ax.minorticks_off()
    ax.set_xlim(27, 300)
    ax.set_xlabel(label)


def step20():
    """{(phase, arm): {c: [cells]}} from step 20's figure data."""
    d = {}
    for r in json.loads((ROOT / "20-cpu-offload-pool" / "results" / "figure-data.json").read_text()):
        d.setdefault((r["phase"], r["arm"]), {}).setdefault(r["c"], []).append(r)
    return d


def engine():
    """{(phase, arm): {c: [cells]}} from data/engine-cells.json (step 20 only)."""
    d = {}
    for r in json.loads((DATA / "engine-cells.json").read_text()):
        if r["step"] == "20":
            d.setdefault((r["phase"], r["arm"]), {}).setdefault(r["c"], []).append(r)
    return d


def goodput():
    d = {}
    for r in json.loads((ROOT / "22-slo-goodput" / "results" / "goodput-data.json").read_text()):
        d.setdefault((r["phase"], r["arm"]), {}).setdefault(r["c"], []).append(r)
    return d


def mean(cells, key):
    return float(np.mean([x[key] for x in cells if x.get(key) is not None]))


def series(by_c, key):
    cs = sorted(by_c)
    vals = [[x[key] for x in by_c[c] if x.get(key) is not None] for c in cs]
    return (np.array(cs), np.array([np.mean(v) for v in vals]),
            np.array([min(v) for v in vals]), np.array([max(v) for v in vals]))


def agg(cells, fn):
    """fn(sum_gen, sum_steps, sum_dt, sum_sched) over the cells of a point."""
    return fn(sum(x["gen"] for x in cells), sum(x["steps"] for x in cells),
              sum(x["dt"] for x in cells), sum(x["sched"] for x in cells))


def plot_arms(ax, data, key, phases=("B", "A"), scale=1.0, annotate=None, annotate_arms=("baseline",)):
    """Lines per arm: solid = 400 GiB offloading (phase B), dashed hollow = offloading off (phase A)."""
    for arm in LABEL:
        for phase in phases:
            if (phase, arm) not in data:
                continue
            c, m, lo, hi = series(data[(phase, arm)], key)
            m, lo, hi = m * scale, lo * scale, hi * scale
            on = phase == "B"
            ax.plot(c, m, color=COLOR[arm], lw=2.6 if on else 2.0, ls="-" if on else "--",
                    marker=MARK[arm], ms=7, mfc=COLOR[arm] if on else "white", mew=2, zorder=3)
            ax.vlines(c, lo, hi, color=COLOR[arm], lw=1.6, zorder=2)
            if annotate and on and arm in annotate_arms:
                for x, y in zip(c, m):
                    ax.annotate(annotate(y), (x, y), xytext=(0, 9), textcoords="offset points",
                                ha="center", fontsize=9, color=COLOR[arm], fontweight="bold")


def arm_legend(ax_or_fig, phases_note=True, **kw):
    h = [Line2D([], [], color=COLOR[a], marker=MARK[a], ms=7, lw=2.6, label=LABEL[a]) for a in LABEL]
    if phases_note:
        h += [Line2D([], [], color="#333333", lw=2.6, marker="o", ms=7, label="solid: CPU offloading 400 GiB (3 runs)"),
              Line2D([], [], color="#333333", lw=2.0, ls="--", marker="o", ms=7, mfc="white", mew=2,
                     label="dashed, hollow: CPU offloading off")]
    return ax_or_fig.legend(handles=h, **kw)


# ---------------------------------------------------------------- figure 1
def fig1_capacity_not_binding():
    s20 = step20()
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.6))

    ax = axes[0]
    ax.axvspan(128, 192, color=P["neutral"], alpha=0.35, lw=0, zorder=0)
    ax.text(157, 40, "CPU tier fills\n(llm-d default\nworking set\n0.81x -> 1.07x)", ha="center", va="bottom",
            fontsize=9.5, color="#555555")
    plot_arms(ax, s20, "throughput")
    ax.annotate("", xy=(128, 690), xytext=(32, 690), arrowprops=dict(arrowstyle="<->", color=RED, lw=1.6))
    ax.text(64, 700, "llm-d default: 4x concurrency, 86-92% cache hit,\nthroughput flat (560 -> 567 tok/s)",
            ha="center", va="bottom", fontsize=9.5, color=RED, fontweight="bold")
    ax.set_ylim(0, 800)
    ax.set_ylabel("Output throughput (tok/s)")
    ax.set_title("(a) Throughput does not scale with concurrency", loc="left", fontsize=13, fontweight="bold")
    c_axis(ax)
    grid(ax)

    ax = axes[1]
    for key in ("gpu_hit_steady", "cpu_hit_steady"):
        pass
    for arm in LABEL:
        for phase in ("B", "A"):
            if (phase, arm) not in s20:
                continue
            c, g, _, _ = series(s20[(phase, arm)], "gpu_hit_steady")
            _, cp, _, _ = series(s20[(phase, arm)], "cpu_hit_steady")
            on = phase == "B"
            ax.plot(c, g + cp, color=COLOR[arm], lw=2.6 if on else 2.0, ls="-" if on else "--",
                    marker=MARK[arm], ms=7, mfc=COLOR[arm] if on else "white", mew=2, zorder=3)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Steady-state prompt cache hit rate (GPU + CPU tier)")
    ax.set_title("(b) Total KV reach is enough up to c = 128", loc="left", fontsize=13, fontweight="bold")
    ax.text(30, 0.97, "with 400 GiB CPU tier: 86-92% of every prompt is already cached",
            fontsize=9.5, color="#333333", va="top")
    c_axis(ax)
    grid(ax)

    ax = axes[2]
    x = np.arange(len(C_ALL))
    need = s20[("B", "baseline")]
    tok = np.array([mean(need[c], "ws_over_tier") * TIER for c in C_ALL])
    ax.bar(x, tok / 1e6, 0.52, color="#D9D9D9", edgecolor="black", lw=1.1, zorder=3)
    for xi, t in zip(x, tok):
        ax.text(xi, t / 1e6 + 0.2, f"{t / 1e6:.1f}M\n({t * GIB_PER_TOKEN:.0f} GiB)", ha="center", va="bottom", fontsize=9.5)
    ax.axhline(GPU_KV / 1e6, color=RED, lw=2.2, ls="--", label=f"GPU KV (HBM): {GPU_KV / 1e6:.2f}M tok, 102 GiB")
    ax.axhline(TIER / 1e6, color=BLUE, lw=2.2, ls="--", label=f"CPU tier (host RAM): {TIER / 1e6:.2f}M tok, 400 GiB")
    ax.set_xticks(x, [str(c) for c in C_ALL])
    ax.set_xlabel("Concurrent sessions per replica (c)")
    ax.set_ylabel("Active KV working set, llm-d default (M tokens)")
    ax.set_ylim(0, 13.8)
    ax.set_title("(c) Working set vs the two KV capacities", loc="left", fontsize=13, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9.5)
    grid(ax)

    arm_legend(fig, loc="lower center", ncol=3, fontsize=10.5, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    save(fig, "bottleneck-fig1-capacity-not-binding")


# ---------------------------------------------------------------- figure 2
def fig2_hbm_caps_running():
    ec = engine()
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.6))

    def per_point(data, fn):
        out = {}
        for key, by_c in data.items():
            out[key] = {c: [dict(v=fn(v)) for v in [cells]] for c, cells in by_c.items()}
        return out

    # (a) decoding batch B = gen / steps
    ax = axes[0]
    bdata = per_point(ec, lambda cells: agg(cells, lambda g, s, dt, sc: g / s))
    cs = np.array(C_ALL)
    ax.plot(cs, cs, color=GRAY, lw=1.4, ls=":", zorder=1)
    ax.text(150, 185, "if every session ran at once (B = c)", color="#555555", fontsize=9.5, rotation=36)
    plot_arms(ax, bdata, "v", annotate=lambda y: f"{y:.0f}")
    ax.axhspan(26, 39, color="#FBE9E7", alpha=0.7, lw=0, zorder=0)
    ax.text(30, 262, "measured B: 26 to 39 for every arm,\nwith or without CPU offloading\n(numbers: llm-d default, 400 GiB)",
            fontsize=9.5, color="#9b3b2e", va="top")
    ax.set_ylim(0, 270)
    ax.set_ylabel("Requests decoding per engine step (B)")
    ax.set_title("(a) Running batch B stays at 26-39 as c grows 8x", loc="left", fontsize=13, fontweight="bold")
    c_axis(ax)
    grid(ax)

    # (b) GPU KV occupancy
    ax = axes[1]
    kvdata = per_point(ec, lambda cells: np.mean([x["kv"] for x in cells]))
    plot_arms(ax, kvdata, "v")
    ax.axhline(1.0, color=GRAY, lw=1.2, ls=":")
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("GPU KV occupancy (vLLM gauge, steady-state mean)")
    ax.set_title("(b) GPU HBM is full at every concurrency", loc="left", fontsize=13, fontweight="bold")
    ax.text(30, 0.12, "0.94 to 0.98 everywhere: each running request needs\n60k-90k tokens of KV in HBM; 2.24M tokens fit ~26-39",
            fontsize=9.5, color="#333333")
    c_axis(ax)
    grid(ax)

    # (c) waiting inside vLLM
    ax = axes[2]
    wdata = per_point(ec, lambda cells: np.mean([x["waiting"] for x in cells]))
    plot_arms(ax, wdata, "v", annotate=lambda y: f"{y:.0f}")
    ax.set_ylim(0, 260)
    ax.set_ylabel("Requests waiting inside vLLM (steady-state mean)")
    ax.set_title("(c) Everything beyond B queues inside vLLM", loc="left", fontsize=13, fontweight="bold")
    ax.text(30, 235, "llm-d default and CPU tier gate: c - B sessions wait inside vLLM\nGPU tier gate: held at the router instead (0.2 to 9 waiting)\n(numbers: llm-d default, 400 GiB)",
            fontsize=9.5, color="#333333", va="top")
    c_axis(ax)
    grid(ax)

    arm_legend(fig, loc="lower center", ncol=3, fontsize=10.5, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    save(fig, "bottleneck-fig2-hbm-caps-running")


# ---------------------------------------------------------------- figure 3
def fit():
    iv = [r for r in json.loads((DATA / "engine-intervals.json").read_text()) if r["steps"] > 50 and r["running"] >= 1]
    step = np.array([1000 * r["dt"] / r["steps"] for r in iv])
    pre = np.array([max(r["sched"] - r["gen"], 0) / r["steps"] / 1000 for r in iv])
    X = np.c_[np.ones_like(pre), pre]
    coef, *_ = np.linalg.lstsq(X, step, rcond=None)
    r2 = 1 - ((step - X @ coef) ** 2).sum() / ((step - step.mean()) ** 2).sum()
    return coef, r2


def fig3_throughput_is_b_over_t():
    ec = engine()
    coef, r2 = fit()
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.8), gridspec_kw={"width_ratios": [1.5, 1]})

    # (a) step time decomposition per arm and c
    ax = axes[0]
    groups = [("A", "baseline"), ("B", "baseline"), ("B", "thunder-lease-main"), ("B", "thunder-lease-main-tier")]
    xpos, xt, xl = 0, [], []
    for c in C_ALL:
        first = xpos
        for phase, arm in groups:
            v = ec.get((phase, arm), {}).get(c)
            if not v:
                continue
            st_ms = agg(v, lambda g, s, dt, sc: 1000 * dt / s)
            p = agg(v, lambda g, s, dt, sc: (sc - g) / s / 1000)
            on = phase == "B"
            ax.bar(xpos, coef[0], color="#D9D9D9", edgecolor="black", lw=0.8, width=0.8)
            ax.bar(xpos, coef[1] * p, bottom=coef[0], color=COLOR[arm] if on else "white", edgecolor=COLOR[arm],
                   hatch=None if on else "..", width=0.8, lw=1.3)
            ax.plot(xpos, st_ms, marker="_", color="black", ms=14, mew=2.2, zorder=4)
            ax.text(xpos, max(st_ms, coef[0] + coef[1] * p) + 2.5, f"{st_ms:.0f}", ha="center", va="bottom",
                    fontsize=8.8, color=COLOR[arm], fontweight="bold")
            xpos += 1
        xt.append((first + xpos - 1) / 2)
        xl.append(f"c = {c}")
        xpos += 0.9
    ax.set_xticks(xt, xl)
    ax.set_ylim(0, 165)
    ax.set_ylabel("Mean engine step time T (ms)")
    ax.set_title(f"(a) Step time T = {coef[0]:.0f} ms decode floor + {coef[1]:.0f} ms per 1k prefill tokens",
                 loc="left", fontsize=13, fontweight="bold")
    grid(ax)
    h = [Patch(facecolor="#D9D9D9", edgecolor="black", label=f"Decode floor ({coef[0]:.0f} ms, HBM bandwidth)"),
         Patch(facecolor="white", edgecolor=RED, hatch="..", label="Prefill: llm-d default, offloading off"),
         Patch(facecolor=RED, label="Prefill: llm-d default, 400 GiB offloading"),
         Patch(facecolor=BLUE, label="Prefill: thunder agent, GPU tier gate, 400 GiB"),
         Patch(facecolor=TEAL, label="Prefill: thunder agent, CPU tier gate, 400 GiB"),
         Line2D([], [], marker="_", color="black", ls="none", ms=14, mew=2.2, label="Measured mean step time")]
    ax.legend(handles=h, loc="upper left", fontsize=9, ncol=2)

    # (b) throughput = B / T, per cell
    ax = axes[1]
    for (phase, arm), by_c in ec.items():
        for c, cells in by_c.items():
            for x in cells:
                B = x["gen"] / x["steps"]
                T = x["dt"] / x["steps"]
                ax.scatter(B / T, x["gen"] / x["dt"], s=46, color=COLOR[arm] if phase == "B" else "white",
                           edgecolor=COLOR[arm], lw=1.4, marker=MARK[arm], zorder=3)
    ax.plot([200, 700], [200, 700], color=GRAY, lw=1.2, ls=":")
    ax.set_xlim(200, 700)
    ax.set_ylim(200, 700)
    ax.set_xlabel("B / T (requests per step / step time)")
    ax.set_ylabel("Measured output throughput (tok/s)")
    ax.set_title("(b) Output throughput = B / T (every cell)", loc="left", fontsize=13, fontweight="bold")
    ax.text(215, 670, "B capped at 26-39 by HBM capacity\nT floored at 46 ms by HBM bandwidth\n=> ceiling ~ 30 / 0.05 s = 600 tok/s",
            fontsize=9.5, va="top", color="#333333")
    ax.grid(color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)
    h = [Line2D([], [], color=COLOR[a], marker=MARK[a], ms=7, lw=0, label=LABEL[a]) for a in LABEL]
    h += [Line2D([], [], color="#333333", marker="o", ms=7, lw=0, label="filled: 400 GiB offloading"),
          Line2D([], [], color="#333333", marker="o", ms=7, lw=0, mfc="white", mew=1.4, label="hollow: offloading off")]
    ax.legend(handles=h, loc="lower right", fontsize=8.8)

    fig.tight_layout()
    save(fig, "bottleneck-fig3-throughput-b-over-t")
    return coef, r2


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


def fig4_hbm_bandwidth():
    pd = {r["c"]: r for r in json.loads((DATA / "pool-sweep.json").read_text()) if r["arm"] == "baseline"}
    kv13 = sweep_kv()
    iv = [r for r in json.loads((DATA / "engine-intervals.json").read_text())
          if r["steps"] > 50 and r["running"] >= 1 and r["step"] == "20" if True]
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    pts = sorted((kv13[c] * GPU_KV / 1e6, 1000 * pd[c]["itl_p50"], c) for c in pd if c in kv13)
    xs, ys, _ = zip(*pts)
    ax.plot(xs, ys, color=RED, marker="o", ms=7, lw=2.2, label="4-pod pool, llm-d default, offloading off (step 13)")
    for x_v, y_v, c_v in pts:
        if c_v in (16, 48, 96, 192):
            ax.annotate(f"{c_v // 4} sessions/pod", (x_v, y_v), xytext=(0, 9), textcoords="offset points",
                        ha="center", fontsize=9.5, color=RED)
    # pure-decode steps of each step 20 arm, 400 GiB offloading
    for arm in LABEL:
        sel = [r for r in iv if r["phase"] == "B" and r["arm"] == arm]
        pre = np.array([max(r["sched"] - r["gen"], 0) / r["steps"] / 1000 for r in sel])
        st = np.array([1000 * r["dt"] / r["steps"] for r in sel])
        kv = np.array([r["kv"] for r in sel]) * GPU_KV / 1e6
        m = pre < 0.1
        if m.sum() == 0:
            continue
        ax.plot([np.median(kv[m])], [np.median(st[m])], marker="*", ms=16, color=COLOR[arm], ls="none",
                label=f"{LABEL[arm]}, 400 GiB offloading: pure-decode steps = {np.median(st[m]):.0f} ms")
    ax.axvline(GPU_KV / 1e6, color=GRAY, lw=1.3, ls=":")
    ax.text(GPU_KV / 1e6 - 0.04, 54, "GPU KV capacity\n2.24M tokens (102 GiB)", ha="right", fontsize=10, color="#555555")
    ax.text(0.08, 47, "Each decode step reads every running request's KV from HBM.\n"
                      "At ~2.2M resident tokens (100 GiB on 2x H100) that is ~45 ms,\n"
                      "so a full GPU KV caps per-request decode at ~22 tok/s.",
            fontsize=10, color="#333333", bbox=dict(boxstyle="round,pad=0.35", facecolor="#F7F7F7", edgecolor="#CCCCCC"))
    ax.set_xlim(0, 2.45)
    ax.set_ylim(0, 60)
    ax.set_xlabel("Resident GPU KV per replica (M tokens)")
    ax.set_ylabel("Decode step time / inter-token latency (ms)")
    ax.set_title("Decode step time grows with resident GPU KV (HBM bandwidth)", loc="left", fontsize=13, fontweight="bold")
    grid(ax)
    ax.legend(loc="lower right", fontsize=9)
    save(fig, "bottleneck-fig4-hbm-bandwidth")


# ---------------------------------------------------------------- figure 5
def fig5_latency():
    s20 = step20()
    gp = goodput()
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.6))

    ax = axes[0]
    plot_arms(ax, s20, "ttft_p50")
    ax.axhline(30, color=GRAY, lw=1.4, ls=":")
    ax.text(29, 36, "30 s interactive SLO", fontsize=10, color="#555555")
    ax.set_yscale("log")
    ax.set_ylim(0.3, 1500)
    ax.set_yticks([1, 10, 100, 1000], ["1 s", "10 s", "100 s", "1000 s"])
    ax.minorticks_off()
    ax.set_ylabel("Median TTFT, whole window")
    ax.set_title("(a) Median TTFT: queueing inside vLLM vs at the router", loc="left", fontsize=13, fontweight="bold")
    c_axis(ax)
    grid(ax)

    ax = axes[1]
    plot_arms(ax, s20, "ttft_p99")
    ax.axhline(1800, color=GRAY, lw=1.4, ls=":")
    ax.text(29, 2100, "forced admission at 1800 s (GPU tier gate)", fontsize=9.5, color="#555555")
    ax.set_yscale("log")
    ax.set_ylim(10, 5000)
    ax.set_yticks([10, 100, 1000], ["10 s", "100 s", "1000 s"])
    ax.minorticks_off()
    ax.set_ylabel("p99 TTFT, whole window")
    ax.set_title("(b) p99 TTFT: the price of holding sessions", loc="left", fontsize=13, fontweight="bold")
    c_axis(ax)
    grid(ax)

    ax = axes[2]
    for arm in LABEL:
        for phase in ("B", "A"):
            if (phase, arm) not in gp:
                continue
            c, m, lo, hi = series(gp[(phase, arm)], "goodput_30")
            on = phase == "B"
            ax.plot(c, m, color=COLOR[arm], lw=2.6 if on else 2.0, ls="-" if on else "--",
                    marker=MARK[arm], ms=7, mfc=COLOR[arm] if on else "white", mew=2, zorder=3)
            ax.vlines(c, lo, hi, color=COLOR[arm], lw=1.6, zorder=2)
    ax.set_ylim(-15, 650)
    ax.set_ylabel("Goodput, turns with TTFT <= 30 s (tok/s)")
    ax.set_title("(c) Goodput under a 30 s TTFT SLO", loc="left", fontsize=13, fontweight="bold")
    ax.text(90, 150, "llm-d default and CPU tier gate:\n0 tok/s for c >= 64 (the FCFS queue\ninside vLLM shifts every TTFT past 30 s)",
            fontsize=9.5, color="#9b3b2e", va="bottom")
    c_axis(ax)
    grid(ax)

    arm_legend(fig, loc="lower center", ncol=3, fontsize=10.5, bbox_to_anchor=(0.5, -0.1))
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    save(fig, "bottleneck-fig5-latency")


# ---------------------------------------------------------------- figure 6
def fig6_cpu_tier_overflow():
    """llm-d default with 400 GiB offloading: where the hits come from, and CPU tier traffic."""
    s20 = step20()
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6))
    x = np.arange(len(C_ALL))
    on, off = s20[("B", "baseline")], s20[("A", "baseline")]

    # (a) hit rate split by tier, offloading on, with the offloading-off GPU hit beside it
    ax = axes[0]
    width = 0.36
    gpu = np.array([mean(on[c], "gpu_hit_steady") for c in C_ALL])
    cpu = np.array([mean(on[c], "cpu_hit_steady") for c in C_ALL])
    tot = [[r["gpu_hit_steady"] + r["cpu_hit_steady"] for r in on[c]] for c in C_ALL]
    lo, hi = np.array([min(t) for t in tot]), np.array([max(t) for t in tot])
    pos_on = x - width / 2 - 0.02
    ax.bar(pos_on, gpu, width, color=RED, edgecolor="black", lw=1.1, zorder=3)
    ax.bar(pos_on, cpu, width, bottom=gpu, color=P["red_1"], edgecolor="black", lw=1.1, hatch="//", zorder=3)
    ax.vlines(pos_on, lo, hi, color="black", lw=1.4, zorder=4)
    for p_, t, h in zip(pos_on, gpu + cpu, hi):
        ax.text(p_, h + 0.02, f"{t:.2f}", ha="center", va="bottom", fontsize=9.5, color=RED, fontweight="bold")
    pos_off = x + width / 2 + 0.02
    for i, c in enumerate(C_ALL):
        if c in off:
            g = mean(off[c], "gpu_hit_steady")
            ax.bar(pos_off[i], max(g, 0.008), width, color="white", edgecolor=RED, lw=1.4, hatch="..", zorder=3)
            ax.text(pos_off[i], max(g, 0.008) + 0.02, f"{g:.2f}\n(off)", ha="center", va="bottom", fontsize=9,
                    color=RED, fontweight="bold")
    h = [Patch(facecolor=RED, edgecolor="black", label="400 GiB offloading: hit in GPU KV"),
         Patch(facecolor=P["red_1"], edgecolor="black", hatch="//", label="400 GiB offloading: hit in CPU tier"),
         Patch(facecolor="white", edgecolor=RED, hatch="..", label="offloading off: hit in GPU KV (c = 32, 128, 256)")]
    ax.legend(handles=h, loc="upper right", fontsize=9.5)
    ax.set_xticks(x, [str(c) for c in C_ALL])
    ax.set_xlabel("Concurrent sessions per replica (c)")
    ax.set_ylabel("Steady-state prompt cache hit rate")
    ax.set_ylim(0, 1.15)
    ax.set_title("(a) llm-d default: hits come from the CPU tier until it overflows", loc="left", fontsize=13,
                 fontweight="bold")
    grid(ax)

    # (b) CPU tier traffic per cell, whole window (20-cpu-offload-pool/results/analysis.md, mean of 3 runs)
    ax = axes[1]
    load_gb = [2383, 3585, 3162, 994, 16]
    store_gb = [428, 521, 831, 2696, 3147]
    ax.bar(x - width / 2, load_gb, width, color=BLUE, edgecolor="black", lw=1.1, label="CPU tier -> GPU: blocks loaded (GB per cell)")
    ax.bar(x + width / 2, store_gb, width, color=ORANGE, edgecolor="black", lw=1.1, hatch="//",
           label="GPU -> CPU tier: blocks stored (GB per cell)")
    for xi, l_v, s_v in zip(x, load_gb, store_gb):
        ax.text(xi - width / 2, l_v + 60, f"{l_v}", ha="center", va="bottom", fontsize=9.5, color=BLUE, fontweight="bold")
        ax.text(xi + width / 2, s_v + 60, f"{s_v}", ha="center", va="bottom", fontsize=9.5, color="#9a5b00", fontweight="bold")
    ax.annotate("working set > 8.74M tokens:\nblocks are stored, evicted,\nand never read back",
                (3 + width / 2, store_gb[3]), xytext=(1.9, 3500),
                arrowprops=dict(arrowstyle="->", color="#9a5b00", lw=1.3), fontsize=9.8, color="#9a5b00", fontweight="bold")
    ax.set_xticks(x, [str(c) for c in C_ALL])
    ax.set_xlabel("Concurrent sessions per replica (c)")
    ax.set_ylabel("KV moved between GPU and CPU tier (GB per cell)")
    ax.set_ylim(0, 4400)
    ax.set_title("(b) llm-d default: CPU tier traffic flips from reads to writes", loc="left", fontsize=13, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9.5)
    grid(ax)

    fig.tight_layout()
    save(fig, "bottleneck-fig6-cpu-tier-overflow")


def main():
    style()
    fig1_capacity_not_binding()
    fig2_hbm_caps_running()
    coef, r2 = fig3_throughput_is_b_over_t()
    fig4_hbm_bandwidth()
    fig5_latency()
    fig6_cpu_tier_overflow()
    print(f"step fit: {coef[0]:.1f} ms + {coef[1]:.1f} ms / k prefill tok, R2 {r2:.3f}")


if __name__ == "__main__":
    main()
