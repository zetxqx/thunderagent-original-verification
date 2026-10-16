# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Figures for the step 27 report (GLM-5.2, TP=8 against DEP=8), from metrics.json (collect.py)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / ".claude/skills/agentic-benchmark/scripts"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

M = json.load(open(HERE / "metrics.json"))
C = [24, 32, 48, 64, 96, 128]
P = fs.PALETTE
# TP=8 dashed, DEP=8 solid
ARMS = [("tp8-direct", "TP=8, no-router", fs.BASELINE_COLOR, "--"),
        ("tp8-thunder", "TP=8, thunder", P["blue_main"], "--"),
        ("dep8-direct", "DEP=8, no-router (vLLM DP load balancer)", "#7A7A7A", "-"),
        ("dep8-affinity", "DEP=8, session affinity", P["violet"], "-"),
        ("dep8-thunder", "DEP=8, thunder", P["teal"], "-")]
fs.apply_publication_style()


def draw(name, panels, title):
    fig, ax = plt.subplots(1, len(panels), figsize=(5.6 * len(panels), 4.8))
    for a, (key, ylabel, ptitle, log) in zip(ax, panels):
        for arm, label, col, ls in ARMS:
            pts = [(c, M[f"{arm}/{c}"][key]) for c in C if f"{arm}/{c}" in M and M[f"{arm}/{c}"][key] is not None]
            a.plot([p[0] for p in pts], [p[1] for p in pts], ls, marker="o", color=col, lw=2.2, ms=7, label=label)
        if log:
            a.set_yscale("log")
        else:
            a.set_ylim(0, None)
        if key == "progress":
            a.axhline(1, color="black", lw=1, ls=":")
        a.set_xticks(C); a.set_xlabel("concurrency (sessions)"); a.set_ylabel(ylabel)
        a.grid(axis="y", color=fs.GRID_COLOR); a.set_axisbelow(True)
        fs.panel_title(a, ptitle)
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.1), fontsize=11)
    fig.suptitle(title, y=1.03, fontsize=16, fontweight="bold")
    fs.finalize_figure(fig, HERE, name)


draw("fig1-throughput-agent-metrics", [
    ("out_tok_s_gpu", "output tok/s per GPU", "(a) output throughput", False),
    ("e2e_norm_intvty_p90", "tok/s per user, slowest 10% (log)", "(b) E2E normalized interactivity p90", True),
    ("e2el_p99", "seconds (log)", "(c) request latency p99", True),
    ("progress", "turns / TP=8 no-router turns", "(d) session progress", False)],
    "GLM-5.2-NVFP4 on 8x B200: TP=8 against DEP=8")
draw("fig2-mechanism", [
    ("gpu_pct", "% of prompt tokens (steady state)", "(a) prompt tokens from GPU cache", False),
    ("computed_pct", "% of prompt tokens (steady state)", "(b) prompt tokens computed", False),
    ("waiting", "requests (mean, all ranks)", "(c) requests waiting in vLLM", False),
    ("intvty_p90", "tok/s per user, slowest 10%", "(d) interactivity p90 (decode only)", False)],
    "Why: cache hits, recompute, vLLM queue and decode speed")
print("ok")
