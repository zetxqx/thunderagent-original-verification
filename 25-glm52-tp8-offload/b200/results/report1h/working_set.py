# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""fig4-working-set-kv: (a) live sessions' working set against the GPU KV pool and the CPU
tier; (b) where the prompt tokens came from (GPU prefix cache, CPU tier, computed).
Reads metrics.json (collect.py: working_set_* from analyze.py, steady state; prompt token
sources from vLLM's prompt_tokens_by_source counter)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = HERE.parent
sys.path.insert(0, str(HERE.parents[3] / ".claude/skills/agentic-benchmark/scripts"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

C = [12, 16, 20, 24, 32, 48, 64, 96, 128]
GPU_POOL = 1_572_864   # 24,576 blocks x 64 tokens (exploration points; 1.64M to 1.65M at c=12/16 no-router)
CPU_TIER = 18_200_000  # 820 GiB / 48.4 KB per token: one copy for all 8 GPUs (MLA replicated_layout); holds the GPU blocks too
ARMS = [("no-router", "passthrough", fs.BASELINE_COLOR), ("llm-d-thunder-agent-simplified", "thunder", fs.PALETTE["blue_main"])]
m = json.load(open(HERE / "metrics.json"))

fs.apply_publication_style()
fig, ax = plt.subplots(1, 2, figsize=(17, 5.4), gridspec_kw={"width_ratios": [1, 1.4]})
for name, key, col in ARMS:
    rows = [m[f"{key}/{c}"] for c in C]
    ax[0].plot(C, [r["working_set_mean"] / 1e6 for r in rows], "-o", color=col, lw=2.2, ms=7, label=f"{name}, working set mean")
    ax[0].plot(C, [r["working_set_max"] / 1e6 for r in rows], "--o", color=col, lw=1.8, ms=7, mfc="white", label=f"{name}, working set max")
admitted = [m[f"thunder/{c}"]["gate_ws_over_cap_mean"] * m[f"thunder/{c}"]["gate_capacity"] / 1e6 for c in C]
ax[0].plot(C, admitted, ":s", color=fs.PALETTE["blue_main"], lw=2, ms=6, label="llm-d-thunder-agent-simplified, admitted sessions mean")
for y, text, ls in ((GPU_POOL, f"GPU KV pool {GPU_POOL / 1e6:.2f}M", ":"),
                    (CPU_TIER, f"CPU tier about {CPU_TIER / 1e6:.1f}M (includes the GPU copy)", "-.")):
    ax[0].axhline(y / 1e6, color="black", lw=1.5, ls=ls)
    ax[0].annotate(text, (0.98, y / 1e6), xycoords=("axes fraction", "data"), xytext=(0, 4),
                   textcoords="offset points", fontsize=11, ha="right")
ax[0].set_xscale("log", base=2); ax[0].set_xticks(C, [str(c) for c in C]); ax[0].minorticks_off(); ax[0].set_ylim(0, None)
ax[0].set_xlabel("concurrency (sessions)"); ax[0].set_ylabel("tokens (M)")
ax[0].grid(axis="y", color=fs.GRID_COLOR); ax[0].set_axisbelow(True)
ax[0].legend(loc="upper left", fontsize=10)
fs.panel_title(ax[0], "(a) working set vs GPU pool and CPU tier")

# (b) stacked shares per concurrency, two bars per concurrency: dark = GPU, light = CPU tier, grey = computed
w = 0.38
for i, (name, key, col) in enumerate(ARMS):
    xs = [j + (i - 0.5) * w for j in range(len(C))]
    v = [m[f"{key}/{c}"] for c in C]
    gpu = [x["prompt_from_gpu_pct"] for x in v]
    cpu = [x["prompt_from_cpu_pct"] for x in v]
    comp = [x["prompt_computed_pct"] for x in v]
    ax[1].bar(xs, gpu, w, color=col, edgecolor="white")
    ax[1].bar(xs, cpu, w, bottom=gpu, color=col, alpha=0.4, edgecolor="white")
    ax[1].bar(xs, comp, w, bottom=[a + b for a, b in zip(gpu, cpu)], color="#BBBBBB", edgecolor="white")
    for x, g, c_ in zip(xs, gpu, cpu):
        ax[1].text(x, g / 2, f"{g:.0f}", ha="center", va="center", fontsize=9, color="white")
        ax[1].text(x, g + c_ / 2, f"{c_:.0f}", ha="center", va="center", fontsize=9)
    for x, g, c_, k in zip(xs, gpu, cpu, comp):
        if k >= 5:
            ax[1].text(x, g + c_ + k / 2, f"{k:.0f}", ha="center", va="center", fontsize=9)
ax[1].set_xticks(range(len(C)), [f"c{c}" for c in C]); ax[1].set_ylim(0, 118)
ax[1].set_ylabel("% of prompt tokens")
ax[1].grid(axis="y", color=fs.GRID_COLOR); ax[1].set_axisbelow(True)
ax[1].legend(handles=[Patch(color=fs.BASELINE_COLOR, label="no-router GPU cache"),
                      Patch(color=fs.BASELINE_COLOR, alpha=0.4, label="no-router CPU tier"),
                      Patch(color=fs.PALETTE["blue_main"], label="llm-d-thunder-agent-simplified GPU cache"),
                      Patch(color=fs.PALETTE["blue_main"], alpha=0.4, label="llm-d-thunder-agent-simplified CPU tier"),
                      Patch(color="#BBBBBB", label="computed")],
             loc="upper center", ncol=3, fontsize=9.5)
fs.panel_title(ax[1], "(b) prompt token source (%)")
fs.finalize_figure(fig, HERE, "fig4-working-set-kv")
