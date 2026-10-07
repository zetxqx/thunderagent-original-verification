#!/usr/bin/env python3
"""Figures for THUNDER-AGENT-SUMMARY.md, from data already in this repo.

Inputs: data/ (written by extract.py), step 13's sweep.md, step 20's
results/figure-data.json and step 22's results/goodput-data.json.
Writes figures/*.png.

Usage: uv run --with matplotlib --with numpy python make_figures.py
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
# step 17 lease 30 s, mean of 3 cells (17-thunder-lease-pool/README.md), against the
# step 13 llm-d default cell at the same load, c=128 on the 4-pod pool (versions-report/README.md)
LEASE_C128, DEFAULT_C128 = 1931, 1151

spec = importlib.util.spec_from_file_location("figs20", ROOT / "20-cpu-offload-pool" / "make_figures.py")
m20 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m20)
P = m20.PALETTE
RED, BLUE, TEAL, VIOLET, GRAY = P["red_strong"], P["blue_main"], P["teal"], P["violet"], "#7a7a7a"
ORANGE = "#E08A00"


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


def sweep_table(title):
    """{arm: {c: value}} from one table of step 13's sweep.md."""
    text = (SWEEP / "sweep.md").read_text()
    block = text.split(f"## {title}\n", 1)[1].split("\n## ", 1)[0]
    out = {"baseline": {}, "thunder": {}, "thunder-origin": {}}
    for line in block.splitlines():
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cells) < 5 or not cells[0].isdigit():
            continue
        c = int(cells[0])
        for arm, v in zip(("baseline", "thunder", "thunder-origin"), cells[2:5]):
            if re.fullmatch(r"[0-9.]+", v):
                out[arm][c] = float(v)
    return out


def pool():
    rows = json.loads((DATA / "pool-sweep.json").read_text())
    d = {}
    for r in rows:
        d.setdefault(r["arm"], {})[r["c"]] = r
    return d


def step20():
    """{(phase, arm): {c: [cells]}} from step 20's figure data (official per-cell numbers)."""
    d = {}
    for r in json.loads((ROOT / "20-cpu-offload-pool" / "results" / "figure-data.json").read_text()):
        d.setdefault((r["phase"], r["arm"]), {}).setdefault(r["c"], []).append(r)
    return d


def mean(cells, key):
    return float(np.mean([x[key] for x in cells if x.get(key) is not None]))


# ---------------------------------------------------------------- figure 1
def fig1_gain():
    pd = pool()
    s20 = step20()
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    ax.axvspan(0.1, 0.75, color="#EEF4EA", lw=0, zorder=0)
    ax.axvline(1.0, color=GRAY, lw=1.2, ls=":", zorder=1)
    ax.axhline(1.0, color="#9a9a9a", lw=1.2, zorder=1)
    ax.text(0.14, 1.86, "Working set fits:\nsmall gain (0.98 to 1.13x)", fontsize=11.5, color="#4f6b45", va="top")
    ax.text(2.05, 1.86, "Working set > KV reach:\nKV thrashes, 1.2 to 1.85x gain", fontsize=11.5, color="#555555", va="top")

    def x_pool(c):
        r = pd["baseline"][c]
        mean_prompt = r["prompt_tps"] * r["window_s"] / r["requests"]
        return c * mean_prompt / (4 * GPU_KV)

    cs = sorted(pd["baseline"])
    for arm, label, color, marker in (("thunder", "4-pod pool, llm-d-thunder (v3 port, most-room), step 13", "#7FA7D6", "s"),
                                      ("thunder-origin", "4-pod pool, llm-d-thunder (v4 port, origin-only), step 13", BLUE, "D")):
        pts = [(x_pool(c), pd[arm][c]["output_tps"] / pd["baseline"][c]["output_tps"]) for c in cs if c in pd.get(arm, {})]
        ax.plot(*zip(*pts), color=color, marker=marker, ms=7, lw=2, label=label, zorder=3)
    ax.plot([x_pool(128)], [LEASE_C128 / DEFAULT_C128], marker="*", ms=17, color=BLUE, ls="none", zorder=4,
            label="4-pod pool, llm-d-thunder (30s lease, step 17, 3 runs) vs step 13 default")

    def ratio(phase, gate, c):
        return mean(s20[(phase, gate)][c], "throughput") / mean(s20[(phase, "baseline")][c], "throughput")

    a_cs = sorted(s20[("A", "baseline")])
    xa = [mean(s20[("A", "baseline")][c], "ws_over_tier") * TIER / GPU_KV for c in a_cs]
    ax.plot(xa, [ratio("A", "thunder-lease-main", c) for c in a_cs], color=RED, marker="o", ms=8, lw=2,
            label="1 replica, offload off, llm-d-thunder (30s lease, GPU KV gate; x-axis: vs GPU KV), step 20", zorder=3)
    b_cs = sorted(s20[("B", "baseline")])
    xb = [mean(s20[("B", "baseline")][c], "ws_over_tier") for c in b_cs]
    ax.plot(xb, [ratio("B", "thunder-lease-main", c) for c in b_cs], color=TEAL, marker="o", ms=8, lw=2,
            label="1 replica, 400 GiB offload, llm-d-thunder (30s lease, GPU KV gate; x-axis: vs CPU tier), step 20", zorder=3)
    ax.plot(xb, [ratio("B", "thunder-lease-main-tier", c) for c in b_cs], color=TEAL, marker="o", ms=8, lw=2, ls="--",
            mfc="white", label="1 replica, 400 GiB offload, llm-d-thunder (30s lease, CPU tier gate), step 20", zorder=3)
    ax.set_xscale("log")
    ax.set_xticks([0.2, 0.5, 1, 2, 5], ["0.2", "0.5", "1", "2", "5"])
    ax.minorticks_off()
    ax.set_xlim(0.13, 6.5)
    ax.set_ylim(0.85, 1.9)
    ax.set_xlabel("Working set / KV reach (measured on llm-d default arm)")
    ax.set_ylabel("Throughput: llm-d-thunder / llm-d default")
    grid(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=1, fontsize=10.5)
    save(fig, "fig1-gain-vs-load")


# ---------------------------------------------------------------- figure 2
def fig2_pool():
    pd = pool()
    hit = sweep_table("steady-state hit rate")
    kv = sweep_table("pool KV")
    wait = sweep_table("waiting inside vLLM")
    arms = (("baseline", "llm-d default (no admission)", RED, "o"),
            ("thunder", "llm-d-thunder (v3 port, most-room)", "#7FA7D6", "s"),
            ("thunder-origin", "llm-d-thunder (v4 port, origin-only)", BLUE, "D"))
    ticks = [4, 8, 12, 16, 24, 32, 48, 64, 84]
    fig, axes = plt.subplots(2, 3, figsize=(15.5, 8.6), sharex=True)
    panels = [
        ("(a) Output throughput per pod (tok/s)", lambda a, c: pd[a][c]["output_tps"] / 4, None),
        ("(b) Steady-state prefix hit rate", lambda a, c: hit[a].get(c), (0, 1.02)),
        ("(c) Prefill computed per pod (k tok/s)", lambda a, c: pd[a][c]["prefill_tps"] / 4 / 1000, None),
        ("(d) KV occupancy (pool mean)", lambda a, c: kv[a].get(c), (0, 1.0)),
        ("(e) Decode ITL p50 (ms)", lambda a, c: 1000 * pd[a][c]["itl_p50"], None),
        ("(f) Requests waiting in vLLM per pod", lambda a, c: (wait[a][c] / 4) if c in wait[a] else None, None),
    ]
    for ax, (title, get, ylim) in zip(axes.flat, panels):
        ax.axvspan(11, 17, color="#EEF4EA", lw=0, zorder=0)
        ax.axvspan(22, 34, color="#FBE9E7", lw=0, zorder=0)
        for arm, label, color, marker in arms:
            pts = [(c / 4, get(arm, c)) for c in sorted(pd.get(arm, {}))]
            pts = [p for p in pts if p[1] is not None]
            ax.plot(*zip(*pts), color=color, marker=marker, ms=6, lw=2, label=label)
        ax.set_title(title, loc="left", fontsize=13.5, fontweight="bold")
        ax.set_xscale("log", base=2)
        ax.set_xticks(ticks, [str(t) for t in ticks])
        ax.minorticks_off()
        if ylim:
            ax.set_ylim(*ylim)
        else:
            ax.set_ylim(bottom=0)
        grid(ax)
    axes[0][0].text(13.3, 80, "Peak tok/s\n(bandwidth)", ha="center", fontsize=10.5, color="#4f6b45")
    axes[0][0].text(27.5, 80, "KV knee\n(thrash)", ha="center", fontsize=10.5, color="#9b3b2e")
    for ax in axes[1]:
        ax.set_xlabel("Concurrent sessions per pod")
    h = [Line2D([], [], color=c, marker=m, ms=6, lw=2, label=l) for _, l, c, m in arms]
    h += [Patch(color="#EEF4EA", label="Peak throughput: 12 to 16 / pod"),
          Patch(color="#FBE9E7", label="KV knee: 24 to 32 / pod")]
    fig.legend(handles=h, loc="lower center", ncol=3, fontsize=11.5, bbox_to_anchor=(0.5, -0.06))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "fig2-pool-saturation")


# ---------------------------------------------------------------- figure 3
def engine_fit():
    iv = [r for r in json.loads((DATA / "engine-intervals.json").read_text()) if r["steps"] > 50 and r["running"] >= 1]
    step = np.array([1000 * r["dt"] / r["steps"] for r in iv])
    pre = np.array([max(r["sched"] - r["gen"], 0) / r["steps"] / 1000 for r in iv])
    X = np.c_[np.ones_like(pre), pre]
    coef, *_ = np.linalg.lstsq(X, step, rcond=None)
    r2 = 1 - ((step - X @ coef) ** 2).sum() / ((step - step.mean()) ** 2).sum()
    return iv, step, pre, coef, r2


def family(r):
    if r["arm"] == "baseline":
        return "default-off" if r["phase"] == "A" else "default-on"
    if r["arm"] == "thunder-lease-main-tier":
        return "tier"
    return "gate-off" if r["phase"] == "A" else "gate-on"


FAM = {
    "default-off": ("llm-d default, offload off", RED, "white"),
    "default-on": ("llm-d default, 400 GiB offload", RED, RED),
    "gate-off": ("llm-d-thunder (GPU KV gate), offload off", BLUE, "white"),
    "gate-on": ("llm-d-thunder (GPU KV gate), offload (incl. step 21)", BLUE, BLUE),
    "tier": ("llm-d-thunder (CPU tier gate), offload", TEAL, TEAL),
}


def fig3_engine():
    iv, step, pre, coef, r2 = engine_fit()
    cells = json.loads((DATA / "engine-cells.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(17.5, 5.8), gridspec_kw={"width_ratios": [1.15, 1.35, 1]})
    ax = axes[0]
    fams = [family(r) for r in iv]
    for f, (label, color, face) in FAM.items():
        m = np.array([x == f for x in fams])
        ax.scatter(pre[m], step[m], s=7, color=color if face != "white" else "none", edgecolor=color, lw=0.6, alpha=0.35,
                   label=label, zorder=2)
    xs = np.linspace(0, 4.2, 10)
    ax.plot(xs, coef[0] + coef[1] * xs, color="black", lw=2, zorder=3)
    ax.text(0.15, 175, f"Step time = {coef[0]:.0f} ms + {coef[1]:.0f} ms x (k prefill tok / step)\nR2 = {r2:.2f}, 7618 10s intervals",
            fontsize=10.5, va="top")
    ax.set_xlim(0, 4.2)
    ax.set_ylim(0, 190)
    ax.set_xlabel("Prefill computed per step (k tokens)")
    ax.set_ylabel("Engine step time (ms)")
    ax.set_title("(a) Step time is driven by prefill work", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    leg = ax.legend(loc="lower right", fontsize=9.0, markerscale=2.2)
    for lh in leg.legend_handles:
        lh.set_alpha(1)

    # (b) decomposition of the mean step per arm and c (phase A and B)
    ax = axes[1]
    groups = [("A", "baseline"), ("A", "thunder-lease-main"), ("B", "baseline"), ("B", "thunder-lease-main"),
              ("B", "thunder-lease-main-tier")]
    xpos, xt, xl = 0, [], []
    for c in (32, 64, 128, 192, 256):
        first = xpos
        for phase, arm in groups:
            v = [x for x in cells if x["step"] == "20" and x["phase"] == phase and x["arm"] == arm and x["c"] == c]
            if not v:
                continue
            steps = sum(x["steps"] for x in v)
            st_ms = 1000 * sum(x["dt"] for x in v) / steps
            p = sum(x["sched"] - x["gen"] for x in v) / steps / 1000
            f = family(v[0])
            _, color, face = FAM[f]
            ax.bar(xpos, coef[0], color="#D9D9D9", edgecolor="white", width=0.8)
            ax.bar(xpos, coef[1] * p, bottom=coef[0], color=color if face != "white" else "white", edgecolor=color,
                   hatch=None if face != "white" else "///", width=0.8, lw=1)
            ax.plot(xpos, st_ms, marker="_", color="black", ms=14, mew=2.2)
            xpos += 1
        xt.append((first + xpos - 1) / 2)
        xl.append(f"c={c}")
        xpos += 0.8
    ax.set_xticks(xt, xl)
    ax.set_ylabel("Mean step time (ms)")
    ax.set_title("(b) Step time breakdown: gray = decode, color = prefill", loc="left", fontsize=13.5, fontweight="bold")
    ax.set_ylim(0, 150)
    grid(ax)
    h = [Patch(facecolor="#D9D9D9", label=f"Decode cost (constant {coef[0]:.0f} ms)"),
         Line2D([], [], marker="_", color="black", ls="none", ms=14, mew=2.2, label="Measured step time")]
    h += [Patch(facecolor=c if face != "white" else "white", edgecolor=c, hatch=None if face != "white" else "///", label=l)
          for k, (l, c, face) in FAM.items()]
    ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=9.0, ncol=2)

    # (c) decode batch per step: bounded by GPU KV
    ax = axes[2]
    for (phase, arm), ls in ((("B", "baseline"), "-"), (("B", "thunder-lease-main"), "-"), (("B", "thunder-lease-main-tier"), "-"),
                             (("A", "baseline"), "--"), (("A", "thunder-lease-main"), "--")):
        f = family({"phase": phase, "arm": arm})
        label, color, face = FAM[f]
        cs, vals = [], []
        for c in (32, 64, 128, 192, 256):
            v = [x for x in cells if x["step"] == "20" and x["phase"] == phase and x["arm"] == arm and x["c"] == c]
            if v:
                cs.append(c)
                vals.append(sum(x["gen"] for x in v) / sum(x["steps"] for x in v))
        ax.plot(cs, vals, color=color, ls=ls, marker="o", mfc=face, ms=7, lw=2, label=label)
    kvm = np.mean([x["kv"] for x in cells])
    ax.text(34, 43.5, f"GPU KV occupancy: {kvm:.2f} mean across cells\n(KV is always full)", fontsize=10.5, va="top")
    ax.set_xscale("log", base=2)
    ax.set_xticks([32, 64, 128, 192, 256], ["32", "64", "128", "192", "256"])
    ax.minorticks_off()
    ax.set_ylim(0, 45)
    ax.set_xlabel("Concurrent sessions per replica")
    ax.set_ylabel("Requests decoding per step")
    ax.set_title("(c) Decode batch size is bounded by KV", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax.legend(loc="lower right", fontsize=9.0)
    fig.tight_layout()
    save(fig, "fig3-engine-step")
    return coef, r2


# ---------------------------------------------------------------- figure 4
def fig4_goodput():
    rows = json.loads((ROOT / "22-slo-goodput" / "results" / "goodput-data.json").read_text())
    arms = (("baseline", "llm-d default (no admission)", RED),
            ("thunder-lease-main", "llm-d-thunder (30s lease, GPU KV gate)", BLUE),
            ("thunder-lease-main-tier", "llm-d-thunder (30s lease, CPU tier gate)", TEAL))
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4))
    ax = axes[0]
    for arm, label, color in arms:
        by_c = {}
        for r in rows:
            if r["phase"] == "B" and r["arm"] == arm:
                by_c.setdefault(r["c"], []).append(r)
        cs = sorted(by_c)
        ax.plot(cs, [mean(by_c[c], "throughput_steady") for c in cs], color=color, lw=1.6, ls=":", marker="o", mfc="white", ms=6)
        ax.plot(cs, [mean(by_c[c], "goodput_30") for c in cs], color=color, lw=2.6, marker="o", ms=7, label=label)
    ax.set_xscale("log", base=2)
    ax.set_xticks([32, 64, 128, 192, 256], ["32", "64", "128", "192", "256"])
    ax.minorticks_off()
    ax.set_ylim(0, 650)
    ax.set_xlabel("Concurrent sessions per replica")
    ax.set_ylabel("tok/s")
    ax.set_title("(a) Throughput (dotted) vs goodput, TTFT <= 30 s (solid)", loc="left", fontsize=13.5, fontweight="bold")
    grid(ax)
    ax = axes[1]
    x = np.logspace(-1, np.log10(2000), 61)
    for arm, label, color in arms:
        cdf = [r["cdf"] for r in rows if r["phase"] == "B" and r["arm"] == arm and r["c"] == 128]
        ax.plot(x, np.mean(cdf, axis=0), color=color, lw=2.6, label=label)
    ax.axvline(30, color=GRAY, lw=1.2, ls=":")
    ax.text(33, 0.04, "30 s", color="#555555", fontsize=10.5)
    ax.set_xscale("log")
    ax.set_xticks([0.1, 1, 10, 100, 1000], ["0.1 s", "1 s", "10 s", "100 s", "1000 s"])
    ax.minorticks_off()
    ax.set_xlim(0.1, 2000)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("TTFT")
    ax.set_ylabel("Share of turns with TTFT <= x")
    ax.set_title("(b) TTFT distribution at c = 128", loc="left", fontsize=13.5, fontweight="bold")
    ax.grid(color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)
    h = [Line2D([], [], color=c, lw=2.6, marker="o", ms=7, label=l) for _, l, c in arms]
    h.append(Line2D([], [], color=GRAY, lw=1.6, ls=":", marker="o", mfc="white", ms=6, label="Dotted in (a): steady-state throughput"))
    fig.legend(handles=h, loc="lower center", ncol=2, fontsize=11, bbox_to_anchor=(0.5, -0.09))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    save(fig, "fig4-goodput")


# ---------------------------------------------------------------- figure 5
def fig5_decode_cost(coef):
    pd = pool()
    kv = sweep_table("pool KV")
    iv, step, pre, _, _ = engine_fit()
    m = pre < 0.1
    kv20 = np.median([r["kv"] for r, ok in zip(iv, m) if ok]) * GPU_KV / 1e6
    st20 = float(np.median(step[m]))
    fig, ax = plt.subplots(figsize=(9, 5.4))
    for arm, label, color, marker in (("baseline", "4-pod pool, llm-d default (step 13)", RED, "o"),
                                      ("thunder", "4-pod pool, llm-d-thunder (v3 port, most-room, step 13)", "#7FA7D6", "s"),
                                      ("thunder-origin", "4-pod pool, llm-d-thunder (v4 port, origin-only, step 13)", BLUE, "D")):
        pts = sorted((kv[arm][c] * GPU_KV / 1e6, 1000 * pd[arm][c]["itl_p50"]) for c in pd.get(arm, {}) if c in kv[arm])
        ax.plot(*zip(*pts), color=color, marker=marker, ms=7, lw=1.8, label=label)
    ax.plot([kv20], [st20], marker="*", ms=18, color=TEAL, ls="none",
            label=f"1 replica, steps with almost no prefill (step 20): {st20:.0f} ms")
    # example: an ITL target of 25 ms, read off the llm-d default curve
    pts = sorted((kv["baseline"][c] * GPU_KV / 1e6, 1000 * pd["baseline"][c]["itl_p50"]) for c in pd["baseline"] if c in kv["baseline"])
    xs, ys = zip(*pts)
    target = 25.0
    i = next(k for k in range(len(ys)) if ys[k] >= target)
    budget = xs[i - 1] + (target - ys[i - 1]) * (xs[i] - xs[i - 1]) / (ys[i] - ys[i - 1])
    ax.plot([0, budget], [target, target], color=ORANGE, lw=1.6, ls="--")
    ax.plot([budget, budget], [0, target], color=ORANGE, lw=1.6, ls="--")
    ax.text(budget + 0.04, 3, f"Example: 25 ms ITL target\n-> max {budget:.2f}M resident tokens / pod\n(~{budget * 1e6 / GPU_KV:.0%} of GPU KV)",
            color="#8a5300", fontsize=10.5)
    ax.axvline(GPU_KV / 1e6, color=GRAY, lw=1.2, ls=":")
    ax.text(GPU_KV / 1e6 - 0.03, 52, "GPU KV capacity\n2.24M tokens", ha="right", fontsize=10.5, color="#555555")
    ax.set_xlim(0, 2.4)
    ax.set_ylim(0, 60)
    ax.set_xlabel("Resident KV per pod (M tokens)")
    ax.set_ylabel("Decode ITL (ms)")
    grid(ax)
    ax.legend(loc="upper left", fontsize=10)
    save(fig, "fig5-decode-cost")
    return budget


def main():
    style()
    fig1_gain()
    fig2_pool()
    coef, r2 = fig3_engine()
    fig4_goodput()
    budget = fig5_decode_cost(coef)
    print(f"step time fit: {coef[0]:.1f} ms + {coef[1]:.1f} ms per k prefill tokens, R2 {r2:.3f}; 25 ms ITL budget {budget:.2f}M tokens")


if __name__ == "__main__":
    main()
