#!/usr/bin/env python3
"""Versions report: one cell per thunder-agent version on the 4-pod pool at c=128.

Every version is represented by its first cell (r1) of the same protocol (one
EPP over the four vLLM pods, 30 min window, 10 min warm-up, client timeout
1900 s, fixed load generator): steps 13, 16 and 17. Metrics come from step
16's analyzer, so every number here matches the step READMEs' per-cell values.

Writes versions.png and versions-table.md next to this script.
Usage: uv run --with matplotlib --with numpy python make_report.py
"""
import importlib.util
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s16 = load("step16", ROOT / "16-thunder-minimal-pool" / "analyze.py")

S13 = ROOT / "13-llm-d-router-sweep" / "results" / "sweep-20260918-134248-t1900"
S16 = ROOT / "16-thunder-minimal-pool" / "results" / "rep-20260927-195200-c128-t1900"
S17 = ROOT / "17-thunder-lease-pool" / "results" / "rep-20260928-115246-c128-t1900"

# Family colors: llm-d default is the neutral reference; the three thunder
# families take categorical slots 1-3 of the validated reference palette.
FAMILIES = {
    "llm-d default": "#8f8e89",
    "llm-d-thunder (v3/v4 port)": "#2a78d6",
    "llm-d-thunder (minimal)": "#eb6834",
    "llm-d-thunder (lease)": "#1baf7a",
}
VERSIONS = [
    ("llm-d default", "llm-d default (no admission)", S13 / "epp-baseline-c128"),
    ("llm-d-thunder (v3/v4 port)", "llm-d-thunder (v3 port, most-room)", S13 / "epp-thunder-c128"),
    ("llm-d-thunder (v3/v4 port)", "llm-d-thunder (v4 port, origin-only)", S13 / "epp-thunder-origin-c128"),
    ("llm-d-thunder (minimal)", "llm-d-thunder (minimal, 1s half-life)", S16 / "epp-thunder-min-c128"),
    ("llm-d-thunder (minimal)", "llm-d-thunder (minimal, 10s half-life)", S16 / "epp-thunder-min-hl10-c128"),
    ("llm-d-thunder (minimal)", "llm-d-thunder (minimal, 10s half-life, 1s sweep)", S16 / "epp-thunder-min-hl10-s1-c128"),
    ("llm-d-thunder (lease)", "llm-d-thunder (30s lease)", S17 / "epp-thunder-lease-c128"),
    ("llm-d-thunder (lease)", "llm-d-thunder (5s lease)", S17 / "epp-thunder-lease5-c128"),
]
PANELS = [
    ("throughput", "Output throughput (tok/s)", "higher is better", "{:.0f}", 1),
    ("hit_steady", "Prefix-cache hit rate, steady state", "higher is better", "{:.2f}", 1),
    ("ttft_p90", "TTFT p90 (s)", "lower is better", "{:.1f}", 1),
    ("ttft_p99", "TTFT p99 (s)", "lower is better", "{:.0f}", 1),
]
TABLE = [
    ("output throughput (tok/s)", "throughput", "{:.0f}", 1),
    ("steady-state hit rate", "hit_steady", "{:.3f}", 1),
    ("prefill tokens computed (M)", "prefill_tokens_total", "{:.1f}", 1e-6),
    ("TTFT p50 (s)", "ttft_p50", "{:.1f}", 1),
    ("TTFT p90 (s)", "ttft_p90", "{:.1f}", 1),
    ("TTFT p99 (s)", "ttft_p99", "{:.0f}", 1),
    ("vLLM waiting, mean steady", "waiting_mean_steady", "{:.1f}", 1),
    ("goodput within SLO, TTFT <= 30 s (turns/s)", "goodput_slo", "{:.2f}", 1),
    ("session SLO attainment, strict", "attain_strict", "{:.2f}", 1),
    ("per-session worst TTFT, p90 (s)", "worst_ttft_p90", "{:.0f}", 1),
    ("EPP pauses", "pauses", "{:.0f}", 1),
    ("EPP holds (paused + new)", ("holds_paused", "holds_new"), "{:.0f}", 1),
    ("forced admissions", "starved", "{:.0f}", 1),
    ("request errors", "errors", "{:.0f}", 1),
]

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def value(s, key, scale):
    if isinstance(key, tuple):
        vals = [s.get(k) for k in key]
        if all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
            return sum(vals) * scale
        return None
    v = s.get(key)
    return v * scale if isinstance(v, (int, float)) and math.isfinite(v) else None


def figure(stats, out):
    plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                         "xtick.color": MUTED, "ytick.color": INK})
    fig, axes = plt.subplots(1, len(PANELS), figsize=(16, 5.2), sharey=True, facecolor=SURFACE)
    names = [name for _, name, _ in VERSIONS]
    y = list(range(len(VERSIONS)))[::-1]
    for ax, (key, title, sense, spec, scale) in zip(axes, PANELS):
        ax.set_facecolor(SURFACE)
        vals = [value(s, key, scale) for s in stats]
        top = max(v for v in vals if v is not None)
        for yi, (fam, _, _), v in zip(y, VERSIONS, vals):
            if v is None:
                continue
            ax.barh(yi, v, height=0.7, color=FAMILIES[fam], edgecolor=SURFACE, linewidth=2)
            ax.text(v + top * 0.015, yi, spec.format(v), va="center", ha="left", fontsize=9, color=INK)
        ax.set_xlim(0, top * 1.22)
        ax.set_title(f"{title}\n", loc="left", fontsize=11, color=INK)
        ax.text(0, 1.01, sense, transform=ax.transAxes, fontsize=9, color=MUTED)
        ax.xaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(names)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in FAMILIES.values()]
    fig.legend(handles, FAMILIES.keys(), loc="lower center", ncol=len(FAMILIES), frameon=False,
               bbox_to_anchor=(0.5, -0.01), fontsize=10)
    fig.suptitle("thunder-agent versions on the 4-pod pool, c=128, one cell (r1) per version",
                 x=0.01, ha="left", fontsize=13, color=INK)
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(out, dpi=150, facecolor=SURFACE)


def table(stats):
    head = "| metric | " + " | ".join(name for _, name, _ in VERSIONS) + " |"
    L = [head, "|" + "---|" * (len(VERSIONS) + 1)]
    for label, key, spec, scale in TABLE:
        cells = []
        for s in stats:
            v = value(s, key, scale)
            cells.append(spec.format(v) if v is not None else "n/a")
        L.append(f"| {label} | " + " | ".join(cells) + " |")
    L.append("| cell | " + " | ".join(f"`{c.parent.parent.parent.name}/.../{c.name}`" for _, _, c in VERSIONS) + " |")
    return "\n".join(L) + "\n"


def main():
    stats = [s16.stats(cell) for _, _, cell in VERSIONS]
    figure(stats, HERE / "versions.png")
    (HERE / "versions-table.md").write_text(table(stats))
    print((HERE / "versions-table.md").read_text())


if __name__ == "__main__":
    main()
