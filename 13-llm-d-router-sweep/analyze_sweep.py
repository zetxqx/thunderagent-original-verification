#!/usr/bin/env python3
"""Step 13 sweep analysis: per concurrency level, epp-baseline vs epp-thunder.
Reuses the per-cell statistics of step 12's analyzer. Produces sweep.md and a
four-panel curve figure (throughput, steady-state hit rate, TTFT p50, requests
waiting inside vLLM) against active sessions per pod.
Usage: analyze_sweep.py <run_dir>
"""
import csv
import importlib.util
import re
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

spec = importlib.util.spec_from_file_location("pool_analyze", Path(__file__).resolve().parent.parent / "12-llm-d-router-pool" / "analyze.py")
pa = importlib.util.module_from_spec(spec); spec.loader.exec_module(pa)

ARMS = (("epp-baseline", "#767676", "baseline (llm-d default)"), ("epp-thunder", "#0F4D92", "thunder (port)"))
PODS = 4


def waiting_mean(cell, lo=600.0):
    return pa.series_mean(cell / "results" / "vllm-metrics.csv", "num_requests_waiting", lo)


def sessions_completed(cell):
    """Sessions that ran their whole trace inside the window; the generator replaced each with a fresh trace.
    inference-perf writes no session summary when none completed (INFERENCE-PERF-BUGS.md issue 3), hence 0."""
    f = cell / "results" / "report" / "summary_session_lifecycle_metrics.json"
    if not f.exists():
        return 0
    import json
    def find(d, key):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == key:
                    return v
                r = find(v, key)
                if r is not None:
                    return r
    return find(json.loads(f.read_text()), "num_sessions") or 0


def main():
    root = Path(sys.argv[1])
    levels = sorted({int(m.group(1)) for d in root.iterdir() for m in [re.search(r"-c(\d+)$", d.name)] if m})
    data = {}
    for c in levels:
        for arm, _, _ in ARMS:
            cell = root / f"{arm}-c{c}"
            if (cell / "results").exists():
                s = pa.cell_stats(cell); s["waiting"] = waiting_mean(cell); s["completed"] = sessions_completed(cell); data[(arm, c)] = s
    rows = [("throughput (tok/s)", "throughput", "{:.0f}"), ("steady-state hit rate", "hit_steady", "{:.3f}"), ("TTFT p50 (s)", "ttft_p50", "{:.1f}"),
            ("TTFT p90 (s)", "ttft_p90", "{:.1f}"), ("requests completed", "requests", "{:.0f}"), ("pool in flight", "inflight", "{:.0f}"),
            ("waiting inside vLLM", "waiting", "{:.0f}"), ("pool KV", "kv", "{:.2f}"), ("errors", "errors", "{:.0f}"), ("sessions completed and replaced", "completed", "{:.0f}"),
            ("EPP holds", "holds", "{:.0f}"), ("EPP pauses", "pauses", "{:.0f}"), ("EPP forced admissions", "forced", "{:.0f}")]
    L = ["# Step 13 sweep: epp-baseline vs epp-thunder by concurrency\n", "One cell per arm and level. `sessions/pod` = c / 4.\n"]
    for name, key, spec_ in rows:
        L.append(f"## {name}\n"); L.append("| c | sessions/pod | baseline | thunder | thunder / baseline |"); L.append("|---|---|---|---|---|")
        for c in levels:
            b = data.get(("epp-baseline", c)); t = data.get(("epp-thunder", c))
            fb = spec_.format(b[key]) if b and b[key] == b[key] else "-"; ft = spec_.format(t[key]) if t and t[key] == t[key] else "-"
            ratio = f"{t[key] / b[key]:.2f}x" if b and t and b[key] and b[key] == b[key] and t[key] == t[key] else "-"
            L.append(f"| {c} | {c / PODS:.0f} | {fb} | {ft} | {ratio} |")
        L.append("")
    (root / "sweep.md").write_text("\n".join(L)); print("\n".join(L[:40]))

    make_figure(root, levels, data)


PALETTE = {"blue_main": "#0F4D92", "red_strong": "#B64342", "neutral": "#CFCECE"}
STYLE = {"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"], "font.size": 15, "axes.linewidth": 2,
         "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "svg.fonttype": "none",
         "xtick.major.width": 2, "ytick.major.width": 2, "xtick.major.size": 5, "ytick.major.size": 5}
# semantic colours: blue for the proposed method, red for the baseline; square vs circle markers keep them apart in print
SERIES = (("epp-baseline", PALETTE["red_strong"], "s", "llm-d default (baseline)"), ("epp-thunder", PALETTE["blue_main"], "o", "ThunderAgent port"))
CROSSOVER = (24, 32)  # observed: the arms tie at 24 sessions per pod and separate by 32


def make_figure(root, levels, data):
    """Four data panels plus a legend-only panel, house style (see the scientific-figure-making skill)."""
    plt.rcParams.update(STYLE)
    panels = [("a", "throughput", "Throughput", "output tokens / s", True),
              ("b", "hit_steady", "Prefix-cache hit rate", "steady state, after 10 min", False),
              ("c", "ttft_p50", "Time to first token", "p50, seconds", False),
              ("d", "waiting", "Requests waiting inside vLLM", "pool mean, after 10 min", False)]
    fig, axes = plt.subplots(1, 5, figsize=(22, 5.2), gridspec_kw={"width_ratios": [1, 1, 1, 1, 0.5]})
    x = np.array([c / PODS for c in levels])
    for ax, (letter, key, title, unit, annotate_ratio) in zip(axes, panels):
        ax.axvspan(*CROSSOVER, color=PALETTE["neutral"], alpha=0.45, linewidth=0, zorder=0)
        ys = {}
        for arm, col, marker, label in SERIES:
            y = np.array([data[(arm, c)][key] if (arm, c) in data else np.nan for c in levels], dtype=float)
            ys[arm] = y
            ax.plot(x, y, color=col, marker=marker, markersize=7.5, linewidth=2.4, label=label, zorder=3)
        if annotate_ratio:
            for i, (xi, b, t) in enumerate(zip(x, ys["epp-baseline"], ys["epp-thunder"])):
                if b == b and t == t and b:  # ratio row along the bottom, staggered so neighbours (24, 32) do not touch
                    ax.annotate(f"{t / b:.2f}x", (xi, 0), xytext=(0, 6 + 15 * (i % 2)), textcoords="offset points", ha="center", fontsize=11, color=PALETTE["blue_main"])
            ax.text(0.01, 0.15, "port / baseline", transform=ax.transAxes, fontsize=10.5, color=PALETTE["blue_main"], va="bottom")
        ax.set_title(f"{letter}  {title}", loc="left", fontweight="bold", fontsize=16, pad=22)
        ax.text(0, 1.02, unit, transform=ax.transAxes, fontsize=12, color="0.35", va="bottom")
        ax.set_xlabel("active sessions per pod")
        ax.set_xticks(x); ax.set_xticklabels([f"{v:g}" for v in x])
        ax.set_xlim(x[0] - 4, x[-1] + 4)
        top = np.nanmax([np.nanmax(v) for v in ys.values()])
        ax.set_ylim(0, top * 1.08)
        ax.tick_params(labelsize=13)
    # legend-only panel
    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(plt.Rectangle((0, 0), 1, 1, color=PALETTE["neutral"], alpha=0.45)); labels.append("observed crossover\n(24 to 32 sessions per pod)")
    axes[4].set_axis_off(); axes[4].legend(handles, labels, loc="center left", fontsize=13, handlelength=2.2, labelspacing=1.1)
    fig.text(0.005, 0.005, "4 vLLM pods behind one EPP; one 30-minute cell per arm and level (first 10 minutes warm-up); client timeout 1900 s; x = c / 4 for c in 48, 96, 128, 192, 256, 338.",
             fontsize=11.5, color="0.35")
    fig.tight_layout(pad=1, rect=(0, 0.05, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"sweep.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"figure: {root}/sweep.png")


if __name__ == "__main__":
    main()
