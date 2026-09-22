#!/usr/bin/env python3
"""Where do requests wait? vLLM's own waiting queue (pool sum) per arm, the
running count, and for the thunder arm the split between requests held in the
EPP flow-control queue and requests waiting inside the engines.
Usage: plot_waiting.py <run_dir>
"""
import csv, sys, statistics as st
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ARMS = (("epp-baseline", "#767676", "llm-d default"), ("epp-affinity", "#B64342", "session affinity"), ("epp-thunder", "#0F4D92", "ThunderAgent (llm-d router)"))

def load(p): return list(csv.DictReader(open(p))) if p.exists() else []
def f(r, k):
    v = r.get(k); return float(v) if v not in (None, "") else np.nan
def series(rows, key):
    t0 = float(rows[0]["ts"]); return np.array([(float(r["ts"]) - t0) / 60 for r in rows]), np.array([f(r, key) for r in rows])
def smooth(y, n=15):
    y = np.nan_to_num(y); k = np.ones(n) / n; return np.convolve(y, k, mode="same")

root = Path(sys.argv[1])
reps = sorted({int(d.name.split("-r")[-1]) for d in root.iterdir() if d.is_dir() and "-r" in d.name and d.name[-1].isdigit()})
plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"], "font.size": 12, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "axes.linewidth": 1.4})
fig, axes = plt.subplots(len(reps), 3, figsize=(15, 3.3 * len(reps)), sharex=True); axes = np.atleast_2d(axes)
summary = []
for i, r in enumerate(reps):
    for arm, col, label in ARMS:
        cell = root / f"{arm}-r{r}" / "results"; v = load(cell / "vllm-metrics.csv")
        if not v: continue
        x, w = series(v, "num_requests_waiting"); x, run = series(v, "num_requests_running")
        axes[i, 0].plot(x, smooth(w), color=col, linewidth=1.5, label=label)
        axes[i, 1].plot(x, smooth(run), color=col, linewidth=1.5, label=label)
        m = x >= 10
        summary.append((f"r{r}", arm, np.nanmean(w[m]), np.nanmax(w), np.nanmean(run[m])))
        if arm == "epp-thunder":
            e = load(cell / "epp-metrics.csv")
            if e:
                xe, q = series(e, "fc_queue_size")
                axes[i, 2].plot(xe, smooth(q), color=col, linewidth=1.6, label="held in EPP (flow-control queue)")
                axes[i, 2].plot(x, smooth(w), color=col, linewidth=1.4, linestyle="--", label="waiting inside vLLM (ThunderAgent)")
    for j, (title, sub) in enumerate([("Requests waiting inside vLLM", "pool sum of num_requests_waiting, 30 s smoothing"), ("Requests running inside vLLM", "pool sum of num_requests_running"), ("ThunderAgent: where requests wait", "EPP queue vs engine queue")]):
        ax = axes[i, j]; ax.axvline(10, color="#BBBBBB", linewidth=1.0, linestyle=":"); ax.set_xlim(0, 47)
        if i == 0:
            ax.set_title(f"{title}\n", fontsize=13, fontweight="bold", loc="left"); ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=10, color="#555555", va="bottom")
        if i == len(reps) - 1: ax.set_xlabel("minutes since start")
    axes[i, 0].set_ylabel(f"run r{r}", fontsize=12, fontweight="bold"); axes[i, 1].set_ylim(0, 200); axes[i, 2].set_ylim(0, 400)
h0, l0 = axes[0, 0].get_legend_handles_labels(); h2, l2 = axes[0, 2].get_legend_handles_labels()
fig.legend(h0 + h2, l0 + l2, loc="lower center", ncol=5, fontsize=11, bbox_to_anchor=(0.5, -0.01))
fig.tight_layout(rect=(0, 0.04, 1, 1), h_pad=1.5, w_pad=2.0)
for ext in ("png", "pdf"): fig.savefig(root / f"waiting.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.08)
print(f"figure: {root}/waiting.png\n")
print(f"{'rep':4s} {'arm':13s} {'vLLM waiting mean (after 10 min)':>34s} {'peak':>6s} {'running mean':>13s}")
for rep, arm, wm, wx, rm in summary: print(f"{rep:4s} {arm:13s} {wm:34.1f} {wx:6.0f} {rm:13.0f}")
