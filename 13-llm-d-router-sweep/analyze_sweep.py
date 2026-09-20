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

ARMS = ("epp-baseline", "epp-thunder", "epp-thunder-origin")  # cells are named <arm>-c<level>
PODS = 4


def waiting_mean(cell, lo=600.0):
    return pa.series_mean(cell / "results" / "vllm-metrics.csv", "num_requests_waiting", lo)


def epp_last(cell, field):
    """Final value of a cumulative EPP counter from the prober's time series (0 for arms without the plugin)."""
    f = cell / "results" / "epp-metrics.csv"
    if not f.exists():
        return 0.0
    rows = list(csv.DictReader(f.open()))
    if not rows:
        return 0.0
    v = rows[-1].get(field)
    return float(v) if v not in (None, "") else 0.0


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
        for arm in ARMS:
            cell = root / f"{arm}-c{c}"
            if (cell / "results").exists():
                s = pa.cell_stats(cell); s["waiting"] = waiting_mean(cell); s["completed"] = sessions_completed(cell)
                s["rebinds"] = epp_last(cell, "rebinds_total"); s["origin_waits"] = epp_last(cell, "origin_waits_total")
                data[(arm, c)] = s
    rows = [("throughput (tok/s)", "throughput", "{:.0f}"), ("steady-state hit rate", "hit_steady", "{:.3f}"), ("TTFT p50 (s)", "ttft_p50", "{:.1f}"),
            ("TTFT p90 (s)", "ttft_p90", "{:.1f}"), ("requests completed", "requests", "{:.0f}"), ("pool in flight", "inflight", "{:.0f}"),
            ("waiting inside vLLM", "waiting", "{:.0f}"), ("pool KV", "kv", "{:.2f}"), ("errors", "errors", "{:.0f}"), ("sessions completed and replaced", "completed", "{:.0f}"),
            ("EPP holds", "holds", "{:.0f}"), ("EPP pauses", "pauses", "{:.0f}"), ("EPP forced admissions", "forced", "{:.0f}")]
    rows += [("EPP rebinds (resumes that changed pod)", "rebinds", "{:.0f}"), ("EPP origin waits (origin-only resumes delayed while another pod had room)", "origin_waits", "{:.0f}")]
    arms = [a for a in ARMS if any((a, c) in data for c in levels)]
    short = {"epp-baseline": "baseline", "epp-thunder": "thunder", "epp-thunder-origin": "origin"}
    ratios = [(n, d) for n, d in (("epp-thunder", "epp-baseline"), ("epp-thunder-origin", "epp-thunder")) if n in arms and d in arms]

    def val(arm, c, key):
        st_ = data.get((arm, c))
        return st_[key] if st_ and st_[key] == st_[key] else None

    L = ["# Step 13 sweep: epp-baseline vs epp-thunder (vs epp-thunder-origin) by concurrency\n", "One cell per arm and level. `sessions/pod` = c / 4. origin = the port with `resumePlacement: origin-only` (thunder-agent-v4).\n"]
    for name, key, spec_ in rows:
        L.append(f"## {name}\n")
        L.append("| c | sessions/pod | " + " | ".join(short[a] for a in arms) + " | " + " | ".join(f"{short[n]} / {short[d]}" for n, d in ratios) + " |")
        L.append("|---|---|" + "---|" * (len(arms) + len(ratios)))
        for c in levels:
            cells = [spec_.format(val(a, c, key)) if val(a, c, key) is not None else "-" for a in arms]
            rs = []
            for n, d in ratios:
                vn, vd = val(n, c, key), val(d, c, key)
                rs.append(f"{vn / vd:.2f}x" if vn is not None and vd else "-")
            L.append(f"| {c} | {c / PODS:.0f} | " + " | ".join(cells) + " | " + " | ".join(rs) + " |")
        L.append("")
    (root / "sweep.md").write_text("\n".join(L)); print("\n".join(L[:40]))

    make_figure(root, levels, data)


PALETTE = {"blue_main": "#0F4D92", "red_strong": "#B64342", "green_3": "#3E9B4F", "neutral": "#CFCECE"}  # green darkened from the skill palette for line legibility
STYLE = {"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"], "font.size": 15, "axes.linewidth": 2,
         "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "svg.fonttype": "none",
         "xtick.major.width": 2, "ytick.major.width": 2, "xtick.major.size": 5, "ytick.major.size": 5}
# semantic colours: blue for the proposed method, red for the baseline; square vs circle markers keep them apart in print
SERIES = (("epp-baseline", PALETTE["red_strong"], "s", "llm-d default (baseline)"), ("epp-thunder", PALETTE["blue_main"], "o", "ThunderAgent port"),
          ("epp-thunder-origin", PALETTE["green_3"], "^", "ThunderAgent port,\norigin-only resume"))
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
            if not any((arm, c) in data for c in levels):
                continue
            y = np.array([data[(arm, c)][key] if (arm, c) in data else np.nan for c in levels], dtype=float)
            ys[arm] = y
            keep = ~np.isnan(y)  # an arm measured at a subset of levels is drawn only there
            ax.plot(x[keep], y[keep], color=col, marker=marker, markersize=7.5, linewidth=2.4, label=label, zorder=3)
        if annotate_ratio:
            for i, (xi, b, t) in enumerate(zip(x, ys["epp-baseline"], ys["epp-thunder"])):
                if b == b and t == t and b:  # ratio row along the bottom, staggered so neighbours (24, 32) do not touch
                    ax.annotate(f"{t / b:.2f}x", (xi, 0), xytext=(0, 6 + 15 * (i % 2)), textcoords="offset points", ha="center", fontsize=11, color=PALETTE["blue_main"])
            ax.text(0.01, 0.15, "port / baseline", transform=ax.transAxes, fontsize=10.5, color=PALETTE["blue_main"], va="bottom")
        ax.set_title(f"{letter}  {title}", loc="left", fontweight="bold", fontsize=16, pad=22)
        ax.text(0, 1.02, unit, transform=ax.transAxes, fontsize=12, color="0.35", va="bottom")
        ax.set_xlabel("active sessions per pod (log scale)")
        ax.set_xscale("log", base=2)  # levels are roughly geometric (4 to 84 per pod); a log axis keeps the low end legible
        ax.set_xticks(x); ax.set_xticklabels([f"{v:g}" for v in x]); ax.minorticks_off()
        ax.set_xlim(x[0] / 1.25, x[-1] * 1.25)
        top = np.nanmax([np.nanmax(v) for v in ys.values()])
        ax.set_ylim(0, top * 1.08)
        ax.tick_params(labelsize=13)
    # legend-only panel
    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(plt.Rectangle((0, 0), 1, 1, color=PALETTE["neutral"], alpha=0.45)); labels.append("observed crossover\n(24 to 32 sessions per pod)")
    axes[4].set_axis_off(); axes[4].legend(handles, labels, loc="center left", fontsize=13, handlelength=2.2, labelspacing=1.1)
    fig.text(0.005, 0.005, "4 vLLM pods behind one EPP; one 30-minute cell per arm and level (first 10 minutes warm-up); client timeout 1900 s; x = c / 4 for c in 16, 32, 48, 64, 96, 128, 192, 256, 338.",
             fontsize=11.5, color="0.35")
    fig.tight_layout(pad=1, rect=(0, 0.05, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"sweep.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"figure: {root}/sweep.png")


if __name__ == "__main__":
    main()
