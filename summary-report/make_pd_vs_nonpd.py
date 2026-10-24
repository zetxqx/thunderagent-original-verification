# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""PD (1P1D) against non-PD, with and without llm-d-thunder-agent-simplified, per GPU, for
Qwen3.5-397B (steps 26, 33, 34) and GLM-5.2 (steps 25, 35, 36). Steady-state points from the
dashboard bundles, aligned by concurrency per GPU (concurrency / GPUs of the deployment).

  uv run summary-report/make_pd_vs_nonpd.py <qwen bundle.json> <glm bundle.json> <out.png>

Row 1 Qwen3.5 (non-PD: one TP=4 server, 4 GPUs; PD: 1P1D TP=4 + TP=4, 8 GPUs, one node).
Row 2 GLM-5.2 (non-PD: one TP=8 server, 8 GPUs; PD: 1P1D TP=8 + TP=8, 16 GPUs, two nodes).
Panels: (a) output tok/s/GPU and (b) E2E-normalized interactivity p50 against concurrency per GPU,
(c) the two against each other (Pareto; up and right is better), labelled with concurrency per GPU.
"""
import json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude/skills/agentic-benchmark/scripts"))
import figstyle  # noqa: E402

ARMS = {
    "qwen": [("qwen35-direct", "non-PD, no router"), ("qwen35-thunder-gpu-l10", "non-PD + thunder"),
             ("qwen35-1p1d-baseline", "PD 1P1D, no router"), ("qwen35-1p1d-thunder-l10", "PD 1P1D + thunder")],
    "glm": [("no-router", "non-PD, no router"), ("thunder-l10", "non-PD + thunder"),
            ("glm52-1p1d-baseline", "PD 1P1D, no router"), ("glm52-1p1d-thunder-l10", "PD 1P1D + thunder")],
}
STYLE = {  # non-PD solid, PD dashed; no router warm, thunder cool
    "non-PD, no router": dict(color=figstyle.BASELINE_COLOR, ls="-", marker="o"),
    "non-PD + thunder": dict(color=figstyle.ARM_COLORS[0], ls="-", marker="o"),
    "PD 1P1D, no router": dict(color="#E0A33A", ls="--", marker="s"),
    "PD 1P1D + thunder": dict(color="#1F1F1F", ls="--", marker="s"),
}
TITLES = {"qwen": "Qwen3.5-397B-A17B-FP8", "glm": "GLM-5.2-NVFP4"}
MAXCPG = {"qwen": 16, "glm": 4}  # the range both deployments cover


def series(bundle, arm, max_cpg):
    pts = []
    for p in bundle["points"]:
        if p["arm"] != arm:
            continue
        s = p["summary"]
        cpg = p["conc"] / s["num_gpus"]
        if cpg <= max_cpg + 1e-9:
            pts.append((cpg, s["ss_output_tput_per_gpu"], s["ss_p50_e2e_norm_intvty"]))
    return sorted(pts)


bundles = {"qwen": json.load(open(sys.argv[1])), "glm": json.load(open(sys.argv[2]))}
figstyle.apply_publication_style(font_size=12)
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
for row, model in enumerate(["qwen", "glm"]):
    ax_t, ax_i, ax_p = axes[row]
    for arm, label in ARMS[model]:
        pts = series(bundles[model], arm, MAXCPG[model])
        if not pts:
            continue
        x, t, i = zip(*pts)
        st = STYLE[label]
        kw = dict(color=st["color"], ls=st["ls"], marker=st["marker"], lw=2.3, ms=7, label=label)
        ax_t.plot(x, t, **kw)
        ax_i.plot(x, i, **kw)
        ax_p.plot(i, t, **kw)
        for xi, ti, ii in pts:
            ax_p.annotate(f"{xi:g}", (ii, ti), textcoords="offset points", xytext=(4, 3), fontsize=8.5, color=st["color"])
    for ax in (ax_t, ax_i):
        ax.set_xlabel("concurrency per GPU")
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color=figstyle.GRID_COLOR)
    ax_p.set_xlabel("E2E-normalized interactivity p50 (tok/s/user)")
    ax_p.set_ylabel("output tok/s/GPU")
    ax_p.set_xlim(left=0)
    ax_p.set_ylim(bottom=0)
    ax_p.grid(color=figstyle.GRID_COLOR)
    tag = "abc" if row == 0 else "def"
    figstyle.panel_title(ax_t, f"({tag[0]}) {TITLES[model]}: output tok/s/GPU")
    figstyle.panel_title(ax_i, f"({tag[1]}) {TITLES[model]}: E2E-norm. interactivity p50")
    figstyle.panel_title(ax_p, f"({tag[2]}) {TITLES[model]}: Pareto (labels: conc/GPU)")
handles, labels = axes[0][0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.005))
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(sys.argv[3], dpi=200)
print("wrote", sys.argv[3])
