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


def main():
    root = Path(sys.argv[1])
    levels = sorted({int(m.group(1)) for d in root.iterdir() for m in [re.search(r"-c(\d+)$", d.name)] if m})
    data = {}
    for c in levels:
        for arm, _, _ in ARMS:
            cell = root / f"{arm}-c{c}"
            if (cell / "results").exists():
                s = pa.cell_stats(cell); s["waiting"] = waiting_mean(cell); data[(arm, c)] = s
    rows = [("throughput (tok/s)", "throughput", "{:.0f}"), ("steady-state hit rate", "hit_steady", "{:.3f}"), ("TTFT p50 (s)", "ttft_p50", "{:.1f}"),
            ("TTFT p90 (s)", "ttft_p90", "{:.1f}"), ("requests completed", "requests", "{:.0f}"), ("pool in flight", "inflight", "{:.0f}"),
            ("waiting inside vLLM", "waiting", "{:.0f}"), ("pool KV", "kv", "{:.2f}"), ("errors", "errors", "{:.0f}"),
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

    plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"], "font.size": 12, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "axes.linewidth": 1.4})
    panels = [("throughput", "Throughput", "output tokens / s"), ("hit_steady", "Prefix-cache hit rate", "steady state (after 10 min)"), ("ttft_p50", "TTFT p50", "seconds"), ("waiting", "Requests waiting inside vLLM", "pool mean after 10 min")]
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.3))
    x = [c / PODS for c in levels]
    for ax, (key, title, unit) in zip(axes, panels):
        for arm, col, label in ARMS:
            y = [data[(arm, c)][key] if (arm, c) in data else np.nan for c in levels]
            ax.plot(x, y, marker="o", color=col, linewidth=2, markersize=6, label=label)
        ax.set_title(title, fontsize=13, fontweight="bold", loc="left"); ax.set_ylabel(unit); ax.set_xlabel("active sessions per pod"); ax.set_xticks(x); ax.set_ylim(bottom=0)
        ax.axvline(2237040 / 50000 / 1.0, color="#BBBBBB", linewidth=1, linestyle=":")  # ~45 sessions of 50k tokens fill one pod's KV
    axes[0].legend(loc="upper left", fontsize=11)
    fig.text(0.01, 0.01, "4-pod pool through one EPP, 30 min per cell (10 min warm-up), client timeout 1900 s. Dotted line: about 45 sessions of 50k tokens fill one pod's KV.", fontsize=10.5, color="#555555")
    fig.tight_layout(rect=(0, 0.05, 1, 1), w_pad=2.0)
    for ext in ("png", "pdf"):
        fig.savefig(root / f"sweep.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.06)
    print(f"figure: {root}/sweep.png")


if __name__ == "__main__":
    main()
