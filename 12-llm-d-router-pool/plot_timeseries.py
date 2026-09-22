#!/usr/bin/env python3
"""Pool time series per replicate for step 12: the three arms overlaid.

Columns: rolling token-weighted prefix-cache hit rate (pool, 60 s window),
pool KV usage (mean over pods), pool requests in flight (sum over pods),
and the EPP's paused programs and queue depth (thunder arm). Rows: runs.
Usage: plot_timeseries.py <run_dir>
"""
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ARMS = (("epp-baseline", "#767676", "llm-d default"),
        ("epp-affinity", "#B64342", "session affinity"),
        ("epp-thunder", "#0F4D92", "ThunderAgent (llm-d router)"))
WARMUP_MIN, ROLL_S = 10, 60


def load(p):
    return list(csv.DictReader(open(p))) if p.exists() else []


def f(r, k):
    v = r.get(k)
    return float(v) if v not in (None, "") else np.nan


def series(rows, key):
    t0 = float(rows[0]["ts"])
    return np.array([(float(r["ts"]) - t0) / 60 for r in rows]), np.array([f(r, key) for r in rows])


def rolling_hit_rate(rows, window_s=ROLL_S):
    ts = np.array([float(r["ts"]) for r in rows])
    q = np.nan_to_num(np.array([f(r, "interval_queries") for r in rows])); h = np.nan_to_num(np.array([f(r, "interval_hits") for r in rows]))
    out = np.full(len(rows), np.nan); j = 0
    for i in range(len(rows)):
        while ts[i] - ts[j] > window_s:
            j += 1
        qq = q[j:i + 1].sum(); out[i] = h[j:i + 1].sum() / qq if qq > 0 else np.nan
    return (ts - ts[0]) / 60, out


def main():
    root = Path(sys.argv[1])
    reps = sorted({int(d.name.split("-r")[-1]) for d in root.iterdir() if d.is_dir() and "-r" in d.name and d.name[-1].isdigit()})
    plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"], "font.size": 12,
                         "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "axes.linewidth": 1.4})
    cols = [("Prefix-cache hit rate", f"pool, token-weighted, {ROLL_S} s window"), ("KV cache usage", "mean over the 4 pods"),
            ("Requests in flight", "sum over the 4 pods"), ("Paused programs and queue", "llm-d router, ThunderAgent arm only")]
    fig, axes = plt.subplots(len(reps), 4, figsize=(18.4, 3.3 * len(reps)), sharex=True); axes = np.atleast_2d(axes)
    for i, r in enumerate(reps):
        for arm, col, label in ARMS:
            cell = root / f"{arm}-r{r}" / "results"; v = load(cell / "vllm-metrics.csv")
            if not v:
                continue
            x, hr = rolling_hit_rate(v); axes[i, 0].plot(x, hr, color=col, linewidth=1.8, label=label)
            x, kv = series(v, "kv_cache_usage_perc"); axes[i, 1].plot(x, kv, color=col, linewidth=1.2, label=label)
            x, run = series(v, "num_requests_running"); axes[i, 2].plot(x, run, color=col, linewidth=1.2, label=label)
            if arm == "epp-thunder":
                e = load(cell / "epp-metrics.csv")
                if e:
                    x, p = series(e, "programs_paused"); axes[i, 3].plot(x, p, color=col, linewidth=1.6, label="programs paused")
                    x, q = series(e, "fc_queue_size"); axes[i, 3].plot(x, q, color=col, linewidth=1.2, linestyle=":", label="requests queued")
        for j, (title, sub) in enumerate(cols):
            ax = axes[i, j]; ax.axvline(WARMUP_MIN, color="#BBBBBB", linewidth=1.0, linestyle=":"); ax.set_xlim(0, 47)
            if i == 0:
                ax.set_title(f"{title}\n", fontsize=13, fontweight="bold", loc="left")
                ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=10, color="#555555", va="bottom")
            if i == len(reps) - 1:
                ax.set_xlabel("minutes since start")
        axes[i, 0].set_ylim(0, 1.02); axes[i, 1].set_ylim(0, 1.02); axes[i, 2].set_ylim(0, 200); axes[i, 3].set_ylim(0, 400)
        axes[i, 0].set_ylabel(f"run r{r}", fontsize=12, fontweight="bold")
    h0, l0 = axes[0, 0].get_legend_handles_labels(); h3, l3 = axes[0, 3].get_legend_handles_labels()
    fig.legend(h0 + h3, l0 + l3, loc="lower center", ncol=5, fontsize=11, bbox_to_anchor=(0.5, -0.01))
    fig.text(0.01, -0.035, "c = 338 (whole corpus), 45 min per cell, 4-pod pool through one EPP. Dotted vertical line: end of the 10-minute warm-up.", fontsize=10, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1), h_pad=1.5, w_pad=2.0)
    for ext in ("png", "pdf"):
        fig.savefig(root / f"timeseries.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.08)
    print(f"figure: {root}/timeseries.png")


if __name__ == "__main__":
    main()
