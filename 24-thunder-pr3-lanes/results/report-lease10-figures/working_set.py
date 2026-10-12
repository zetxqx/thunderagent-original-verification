# /// script
# requires-python = ">=3.11"
# dependencies = ["pandas", "matplotlib"]
# ///
"""fig6-working-set: live sessions' working set against the GPU KV pool and the CPU tier,
from compare-all/report/summary.csv (analyze.py's working_set_* columns, steady state)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / ".claude/skills/agentic-benchmark/scripts"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

GPU_POOL = 2_237_040   # 139,815 blocks x 16 tokens
CPU_TIER = 8_738_133   # --kv-offloading-size=400 GiB at 48 KiB per token; holds a copy of the GPU blocks
d = pd.read_csv(HERE.parent / "compare-all/report/summary.csv")
PANELS = [("(a) with 400 GiB CPU offload", [("offload-baseline-60m", "no router + offload", fs.BASELINE_COLOR),
                                            ("offload-thunder-lease10-60m", "llm-d-thunder-simplified (lease 10 s) + offload", fs.PALETTE["blue_main"])], True),
          ("(b) without offload", [("baseline-60m", "no router", fs.BASELINE_COLOR),
                                   ("thunder-60m", "llm-d-thunder-simplified (lease 30 s)", fs.PALETTE["blue_main"])], False)]
fs.apply_publication_style()
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, (title, arms, tier) in zip(axes, PANELS):
    concs = set()
    for label, name, col in arms:
        g = d[d["label"] == label].sort_values("conc")
        concs |= set(g["conc"])
        ax.plot(g["conc"], g["working_set_mean"] / 1e6, "-o", color=col, lw=2.2, ms=6, label=f"{name}, mean")
        ax.plot(g["conc"], g["working_set_max"] / 1e6, "--o", color=col, lw=1.8, ms=6, mfc="white", label=f"{name}, max")
    ax.axhline(GPU_POOL / 1e6, color="black", lw=1.5, ls=":")
    ax.annotate(f"GPU KV pool {GPU_POOL / 1e6:.2f}M", (0.98, GPU_POOL / 1e6), xycoords=("axes fraction", "data"),
                xytext=(0, 4), textcoords="offset points", fontsize=11, ha="right")
    if tier:
        ax.axhline(CPU_TIER / 1e6, color="black", lw=1.5, ls="-.")
        ax.annotate(f"CPU tier {CPU_TIER / 1e6:.2f}M (includes the GPU copy)", (0.02, CPU_TIER / 1e6),
                    xycoords=("axes fraction", "data"), xytext=(0, 4), textcoords="offset points", fontsize=11)
    concs = sorted(concs)
    ax.set_xscale("log", base=2); ax.set_xticks(concs, [str(c) for c in concs]); ax.minorticks_off()
    ax.set_xlabel("concurrency (sessions)"); ax.set_ylabel("working set (M tokens)")
    ax.set_ylim(0, None)
    ax.grid(axis="y", color=fs.GRID_COLOR); ax.set_axisbelow(True)
    fs.panel_title(ax, title)
    ax.legend(loc="upper left", fontsize=10, bbox_to_anchor=(0, 0.93))
fs.finalize_figure(fig, HERE, "fig6-working-set")
