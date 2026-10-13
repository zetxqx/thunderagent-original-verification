# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""fig1 for the PR comment: throughput and TTFT p50/p90 against concurrency, from ../metrics.json."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / ".claude/skills/agentic-benchmark/scripts"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

m = json.load(open(HERE.parent / "metrics.json"))
C = [12, 16, 20, 24, 32]
P = [m[f"passthrough/{c}"] for c in C]
T = [m[f"thunder/{c}"] for c in C]
ARMS = [("no router", P, fs.BASELINE_COLOR), ("llm-d-thunder-agent-simplified", T, fs.PALETTE["blue_main"])]
fs.apply_publication_style()

fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
for name, v, col in ARMS:
    ax[0].plot(C, [x["out_tok_s"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
fs.panel_title(ax[0], "(a) output throughput (tok/s, 8 GPUs)")
ax[0].set_xlabel("concurrency (sessions)"); ax[0].set_ylabel("output tok/s")
for name, v, col in ARMS:
    ax[1].plot(C, [x["ttft_p90"] for x in v], "-o", color=col, lw=2.2, ms=7, label=f"{name} p90")
    ax[1].plot(C, [x["ttft_p50"] for x in v], "--o", color=col, lw=1.8, ms=7, mfc="white", label=f"{name} p50")
ax[1].set_yscale("log"); ax[1].set_ylim(0.4, 400); fs.panel_title(ax[1], "(b) time to first token (s, log scale)")
ax[1].set_xlabel("concurrency (sessions)"); ax[1].set_ylabel("TTFT (s)")
for a in ax:
    a.set_xticks(C); a.grid(axis="y", color=fs.GRID_COLOR); a.set_axisbelow(True)
ax[0].legend(loc="lower right"); ax[1].legend(loc="upper left")
fs.finalize_figure(fig, HERE, "fig1-throughput-ttft")
