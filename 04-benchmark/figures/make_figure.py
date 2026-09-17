#!/usr/bin/env python3
"""Publication-style figure for a ThunderAgent benchmark run.

Usage: python make_figure.py <run_dir> [out_basename]

Panels:
  (a) interval prefix-cache hit rate per backend (time series)
  (b) KV cache utilization per backend (time series)
  (c) router program lifecycle counts (REASONING/ACTING/paused)
  (d) per-turn request latency across sessions, with median
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PALETTE = {
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "green_3": "#8BCF8B",
    "red_strong": "#B64342",
    "neutral": "#CFCECE",
    "teal": "#42949E",
    "violet": "#9A4D8E",
}
BACKEND_COLORS = [PALETTE["blue_main"], PALETTE["teal"], PALETTE["green_3"], PALETTE["violet"]]
BACKEND_MARKERS = ["o", "s", "^", "D"]


def apply_publication_style(font_size=15, axes_linewidth=2.0):
    plt.rcParams.update(
        {
            "font.family": ["DejaVu Sans", "Helvetica", "Arial", "sans-serif"],
            "font.size": font_size,
            "axes.linewidth": axes_linewidth,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def short_backend(url):
    # http://10.100.15.12:8000 -> pod .15.12
    host = url.split("//")[1].split(":")[0]
    return "pod ." + ".".join(host.split(".")[-2:])


def load_run(run_dir):
    with open(run_dir / "metrics-backends.csv") as f:
        backend_rows = list(csv.DictReader(f))
    with open(run_dir / "metrics-router.csv") as f:
        router_rows = list(csv.DictReader(f))
    with open(run_dir / "requests.csv") as f:
        request_rows = list(csv.DictReader(f))
    with open(run_dir / "summary.json") as f:
        summary = json.load(f)
    return backend_rows, router_rows, request_rows, summary


def main():
    run_dir = Path(sys.argv[1])
    out_base = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).parent / run_dir.name)
    backend_rows, router_rows, request_rows, summary = load_run(run_dir)

    t0 = min(float(r["ts"]) for r in backend_rows)
    t_max = max(float(r["ts"]) for r in backend_rows) - t0
    backends = sorted({r["backend"] for r in backend_rows})

    apply_publication_style()
    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    (ax_hit, ax_kv), (ax_prog, ax_lat) = axes

    # (a) interval prefix-cache hit rate per backend
    for b, color, marker in zip(backends, BACKEND_COLORS, BACKEND_MARKERS):
        rows = [r for r in backend_rows if r["backend"] == b]
        t = np.array([float(r["ts"]) - t0 for r in rows])
        y = np.array([float(r["interval_hit_rate"]) if r["interval_hit_rate"] else np.nan for r in rows])
        ax_hit.plot(t, y, "-", marker=marker, color=color, linewidth=2.5, markersize=7,
                    alpha=0.85, label=short_backend(b))
    agg = summary["aggregate_prefix_hit_rate"]
    ax_hit.axhline(agg, color=PALETTE["red_strong"], linestyle="--", linewidth=2)
    ax_hit.text(0.03, agg - 0.02, f"run aggregate {agg:.2f}", color=PALETTE["red_strong"],
                fontsize=12, transform=ax_hit.get_yaxis_transform(), va="top")
    ax_hit.set_ylim(0, 1.05)
    ax_hit.set_xlim(-0.5, t_max + 0.5)
    ax_hit.set_xlabel("Time since first sample (s)")
    ax_hit.set_ylabel("Prefix-cache hit rate\n(per probe interval)")
    ax_hit.set_title("(a) Prefix-cache hit rate", fontsize=15)
    ax_hit.legend(fontsize=10, loc="upper left", ncol=2, columnspacing=0.8)

    # (b) KV cache utilization per backend (percent of capacity)
    for b, color, marker in zip(backends, BACKEND_COLORS, BACKEND_MARKERS):
        rows = [r for r in backend_rows if r["backend"] == b]
        t = np.array([float(r["ts"]) - t0 for r in rows])
        y = np.array([float(r["kv_cache_usage_perc"] or 0) * 100 for r in rows])
        ax_kv.plot(t, y, "-", marker=marker, color=color, linewidth=2.5, markersize=7,
                   alpha=0.85, label=short_backend(b))
    ax_kv.set_xlim(-0.5, t_max + 0.5)
    ax_kv.set_xlabel("Time since first sample (s)")
    ax_kv.set_ylabel("KV cache utilization (%)")
    ax_kv.set_title("(b) KV cache utilization", fontsize=15)
    cap = 2_237_040
    peak_kv_pct = max(float(r["kv_cache_usage_perc"] or 0) for r in backend_rows) * 100
    pressure = "saturated" if peak_kv_pct > 50 else "far below pressure"
    ax_kv.text(0.02, 0.97,
               f"capacity {cap/1e6:.2f}M tokens/pod\npeak {peak_kv_pct:.2g}% ({pressure})",
               transform=ax_kv.transAxes, ha="left", va="top", fontsize=11, color="0.35")
    ax_kv.legend(fontsize=10, loc="center left")

    # (c) program lifecycle counts
    t = np.array([float(r["ts"]) - t0 for r in router_rows])
    series = [
        ("programs_count", "total programs", PALETTE["neutral"]),
        ("reasoning_count", "REASONING", PALETTE["blue_main"]),
        ("acting_count", "ACTING", PALETTE["teal"]),
        ("paused_count", "paused", PALETTE["red_strong"]),
    ]
    for key, label, color in series:
        y = np.array([int(r[key]) for r in router_rows])
        ax_prog.plot(t, y, "-o", color=color, linewidth=2.5, markersize=6, label=label)
    ax_prog.set_xlim(-0.5, t_max + 0.5)
    ax_prog.set_xlabel("Time since first sample (s)")
    ax_prog.set_ylabel("Programs")
    ax_prog.set_title("(c) Program lifecycle (router view)", fontsize=15)
    ax_prog.set_ylim(-0.5, max(int(r["programs_count"]) for r in router_rows) + 2)
    ax_prog.legend(fontsize=11, loc="center right")

    # (d) per-turn latency across sessions
    ok = [r for r in request_rows if r["status"] == "200" and r["latency_s"]]
    turns = sorted({int(r["turn"]) for r in ok})
    lat_by_turn = {k: [float(r["latency_s"]) for r in ok if int(r["turn"]) == k] for k in turns}
    rng = np.random.default_rng(0)
    for k in turns:
        vals = lat_by_turn[k]
        x = k + rng.uniform(-0.12, 0.12, len(vals))
        ax_lat.scatter(x, vals, s=28, color=PALETTE["neutral"], edgecolor="0.4", linewidth=0.6, zorder=2)
    medians = [float(np.median(lat_by_turn[k])) for k in turns]
    ax_lat.plot(turns, medians, "-o", color=PALETTE["blue_main"], linewidth=2.5, markersize=7,
                label="median", zorder=3)
    ax_lat.set_xlabel("Turn index")
    ax_lat.set_ylabel("Turn latency (s)")
    ax_lat.set_title(f"(d) Turn latency ({summary['config']['sessions']} sessions)", fontsize=15)
    ax_lat.set_xticks(turns)
    ax_lat.legend(fontsize=11, loc="upper right")

    fig.suptitle(
        f"Original ThunderAgent router, {run_dir.name}: "
        f"{summary['config']['sessions']} sessions x {summary['config']['turns']} turns, "
        f"makespan {summary['makespan_s']}s",
        fontsize=15, y=0.995,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    out = Path(out_base)
    out.parent.mkdir(parents=True, exist_ok=True)
    saved = []
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        p = out.with_suffix("." + ext)
        fig.savefig(p, bbox_inches="tight", pad_inches=0.06, **kw)
        saved.append(p)
    plt.close(fig)
    print("saved:", *saved)


if __name__ == "__main__":
    main()
