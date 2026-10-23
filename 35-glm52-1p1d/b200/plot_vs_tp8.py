# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Step 35 figure: 1P1D GLM-5.2 (16 GPUs) against step 25's TP=8 aggregated no-router (8 GPUs),
at equal concurrency per GPU (1P1D c=N against TP=8 c=N/2), steady state.

  uv run b200/plot_vs_tp8.py <step35 summary.csv> <out.png>

Step 25 points come from dashboard/data/glm52-nvfp4-8xb200.json (arm no-router, one-hour points).
"""
import csv, json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "../../.claude/skills/agentic-benchmark/scripts"))
import figstyle  # noqa: E402

pd_rows = sorted(csv.DictReader(open(sys.argv[1])), key=lambda r: float(r["conc"]))
bundle = json.load(open(HERE / "../../dashboard/data/glm52-nvfp4-8xb200.json"))
agg = sorted((p for p in bundle["points"] if p["arm"] == "no-router"), key=lambda p: p["conc"])

def pd_series(k):
    return [float(r["conc"]) / 16 for r in pd_rows], [float(r[k]) for r in pd_rows]

def agg_series(k, max_cpg):
    pts = [p for p in agg if p["conc"] / 8 <= max_cpg]
    return [p["conc"] / 8 for p in pts], [p["summary"][k] for p in pts]

figstyle.apply_publication_style(font_size=13)
fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
max_cpg = max(float(r["conc"]) for r in pd_rows) / 16
panels = [("ss_output_tput_per_gpu", "(a) Output tok/s/GPU", False),
          ("ss_p50_ttft_s", "(b) TTFT p50 (s), log scale", True),
          ("ss_p50_e2e_norm_intvty", "(c) E2E-normalized interactivity p50", False)]
for ax, (k, title, log) in zip(axes, panels):
    x, y = agg_series(k, max_cpg)
    ax.plot(x, y, "-o", color=figstyle.BASELINE_COLOR, lw=2.4, ms=7, label="TP=8 aggregated, 8 GPUs (step 25)")
    x, y = pd_series(k)
    ax.plot(x, y, "-o", color=figstyle.ARM_COLORS[0], lw=2.4, ms=7, label="1P1D TP=8 + TP=8, 16 GPUs (step 35)")
    for xi, yi, r in zip(x, y, pd_rows):
        ax.annotate(f"c{int(float(r['conc']))}", (xi, yi), textcoords="offset points", xytext=(4, 4), fontsize=9, color=figstyle.ARM_COLORS[0])
    if log:
        ax.set_yscale("log")
    else:
        ax.set_ylim(bottom=0)
    ax.set_xlabel("concurrency per GPU")
    figstyle.panel_title(ax, title)
    ax.grid(axis="y", color=figstyle.GRID_COLOR)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(sys.argv[2], dpi=200)
print("wrote", sys.argv[2])
