# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Figures for PD-VS-AGGREGATED.md: every P/D and aggregated deployment of GLM-5.2-NVFP4 (steps 25, 27,
35 to 40) and Qwen3.5-397B-A17B-FP8 (steps 26, 33, 34), steady-state points.

  uv run summary-report/make_pd_report_figures.py <glm bundle.json> <qwen bundle.json> \
      <step 38 summary.csv> <step 40 summary.csv> <out dir>

The bundles are the dashboard bundles (dashboard/data/*.json on main); step 38's summary.csv holds the
2P1D arms (with and without thunder), step 40's the 1P2D arms.

pd-fig1-glm-pareto.png   GLM-5.2: (a) E2E-normalized interactivity p50 and (b) per-user decode speed
                         (interactivity p50) against output tok/s/GPU, labelled with concurrency per GPU.
pd-fig2-qwen-pareto.png  The same for Qwen3.5.
pd-fig3-decode-gpu.png   Output per decode GPU and per GPU of the whole deployment at each P/D deployment's
                         peak, against the best aggregated per-GPU output (the prefill tax).
"""
import csv, json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude/skills/agentic-benchmark/scripts"))
import figstyle  # noqa: E402

glm_b, qwen_b, s38, s40, out = sys.argv[1:6]
out = Path(out)
out.mkdir(parents=True, exist_ok=True)


def bundle_pts(path, arm):
    pts = []
    for p in json.load(open(path))["points"]:
        if p["arm"] == arm:
            s = p["summary"]
            pts.append(dict(c=p["conc"], g=s["num_gpus"], tpg=s["ss_output_tput_per_gpu"], tot=s["ss_output_tput"],
                            iv=s["ss_p50_intvty"], e2e=s["ss_p50_e2e_norm_intvty"]))
    return sorted(pts, key=lambda d: d["c"])


def csv_pts(path, label):
    pts = []
    for r in csv.DictReader(open(path)):
        if r["label"] == label:
            pts.append(dict(c=int(r["conc"]), g=int(r["num_gpus"]), tpg=float(r["ss_output_tput_per_gpu"]),
                            tot=float(r["ss_output_tput"]), iv=float(r["ss_p50_intvty"]),
                            e2e=float(r["ss_p50_e2e_norm_intvty"])))
    return sorted(pts, key=lambda d: d["c"])


AGG = dict(ls="-", marker="o")
PD = dict(ls="--", marker="s")
# (label, points, style, decode GPUs or 0 for aggregated)
GLM = [
    ("TP=8 aggregated (8 GPUs)", bundle_pts(glm_b, "no-router"), dict(color=figstyle.BASELINE_COLOR, **AGG), 0),
    ("TP=8 aggregated + thunder (8 GPUs)", bundle_pts(glm_b, "thunder-l10"), dict(color=figstyle.ARM_COLORS[0], **AGG), 0),
    ("DEP8 aggregated + thunder (8 GPUs)", bundle_pts(glm_b, "dep8-thunder-l10"), dict(color="#2B8CBE", ls="-", marker="P"), 0),
    ("1P1D (16 GPUs)", bundle_pts(glm_b, "glm52-1p1d-baseline"), dict(color="#1B7837", **PD), 8),
    ("1P1D + thunder (16 GPUs)", bundle_pts(glm_b, "glm52-1p1d-thunder-l10"), dict(color="#1F1F1F", **PD), 8),
    ("2P1D (24 GPUs)", csv_pts(s38, "glm52-2p1d-baseline"), dict(color="#D6249F", ls=":", marker="D"), 8),
    ("2P1D + thunder (24 GPUs)", csv_pts(s38, "glm52-2p1d-thunder-l10"), dict(color="#E66101", ls=":", marker="D"), 8),
    ("1P2D (24 GPUs)", csv_pts(s40, "glm52-1p2d-baseline"), dict(color="#8C510A", ls="-.", marker="^"), 16),
    ("1P2D + thunder (24 GPUs)", csv_pts(s40, "glm52-1p2d-thunder-l10"), dict(color="#762A83", ls="-.", marker="^"), 16),
]
QWEN = [
    ("TP=4 aggregated (4 GPUs)", bundle_pts(qwen_b, "qwen35-direct"), dict(color=figstyle.BASELINE_COLOR, **AGG), 0),
    ("TP=4 aggregated + thunder (4 GPUs)", bundle_pts(qwen_b, "qwen35-thunder-gpu-l10"), dict(color=figstyle.ARM_COLORS[0], **AGG), 0),
    ("1P1D (8 GPUs)", bundle_pts(qwen_b, "qwen35-1p1d-baseline"), dict(color="#E0A33A", **PD), 4),
    ("1P1D + thunder (8 GPUs)", bundle_pts(qwen_b, "qwen35-1p1d-thunder-l10"), dict(color="#1F1F1F", **PD), 4),
]

figstyle.apply_publication_style(font_size=12)


def pareto(arms, title, fname, ncol):
    fig, (ax_e, ax_i) = plt.subplots(1, 2, figsize=(16, 7.6))
    for label, pts, st, _ in arms:
        if not pts:
            continue
        kw = dict(color=st["color"], ls=st["ls"], marker=st["marker"], lw=2.2, ms=7, label=label)
        x = [d["tpg"] for d in pts]
        ax_e.plot(x, [d["e2e"] for d in pts], **kw)
        ax_i.plot(x, [d["iv"] for d in pts], **kw)
        for d in pts:
            lab = f"{d['c'] / d['g']:.3g}"
            ax_e.annotate(lab, (d["tpg"], d["e2e"]), textcoords="offset points", xytext=(4, 3), fontsize=8, color=st["color"])
            ax_i.annotate(lab, (d["tpg"], d["iv"]), textcoords="offset points", xytext=(4, 3), fontsize=8, color=st["color"])
    for ax, ylab in ((ax_e, "E2E-normalized interactivity p50 (tok/s/user)"), (ax_i, "interactivity p50 (decode tok/s/user)")):
        ax.set_xlabel("output tok/s/GPU")
        ax.set_ylabel(ylab)
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)
        ax.grid(color=figstyle.GRID_COLOR)
    figstyle.panel_title(ax_e, f"(a) {title}: E2E-normalized interactivity (TTFT included)")
    figstyle.panel_title(ax_i, f"(b) {title}: per-user decode speed")
    h, l = ax_e.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=ncol, frameon=False, bbox_to_anchor=(0.5, -0.005))
    fig.tight_layout(rect=(0, 0.1 if ncol < 4 else 0.08, 1, 1))
    fig.savefig(out / fname, dpi=200)
    print("wrote", out / fname)


pareto(GLM, "GLM-5.2", "pd-fig1-glm-pareto.png", 3)
pareto(QWEN, "Qwen3.5", "pd-fig2-qwen-pareto.png", 4)

# fig3: per decode GPU and per GPU at each P/D deployment's peak, against the best aggregated per GPU
fig, axes = plt.subplots(1, 2, figsize=(16, 6.4), gridspec_kw=dict(width_ratios=[3, 1.2]))
for ax, arms, title in ((axes[0], GLM, "GLM-5.2"), (axes[1], QWEN, "Qwen3.5")):
    agg_best = max(max(d["tpg"] for d in pts) for _, pts, _, dg in arms if dg == 0 and pts)
    pd_arms = [(l, pts, st, dg) for l, pts, st, dg in arms if dg and pts]
    xs = range(len(pd_arms))
    for i, (label, pts, st, dg) in enumerate(pd_arms):
        best = max(pts, key=lambda d: d["tpg"])
        per_d = best["tot"] / dg
        ax.bar(i - 0.2, per_d, 0.38, color=st["color"], alpha=0.45, edgecolor=st["color"])
        ax.bar(i + 0.2, best["tpg"], 0.38, color=st["color"], edgecolor="black", lw=0.6)
        ax.annotate(f"{per_d:.0f}", (i - 0.2, per_d), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9)
        ax.annotate(f"{best['tpg']:.0f}", (i + 0.2, best["tpg"]), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9)
    ax.axhline(agg_best, color=figstyle.ARM_COLORS[0], ls="--", lw=1.6)
    ax.annotate(f"best aggregated\nper GPU: {agg_best:.0f}", (-0.6, agg_best), xytext=(2, 4),
                textcoords="offset points", ha="left", fontsize=9, color=figstyle.ARM_COLORS[0])
    ax.set_xticks(list(xs))
    ax.set_xticklabels([l.split(" (")[0] for l, *_ in pd_arms], rotation=20, ha="right")
    ax.set_xlim(-0.65, len(pd_arms) - 0.4)
    ax.set_ylim(0, max(max(d["tot"] for d in pts) / dg for _, pts, _, dg in pd_arms) * 1.12)
    ax.set_ylabel("output tok/s per GPU")
    ax.grid(axis="y", color=figstyle.GRID_COLOR)
    figstyle.panel_title(ax, title)
fig.suptitle("Output tok/s at each P/D deployment's peak: per decode GPU (light) and per GPU of the whole deployment (dark)",
             fontsize=12, x=0.01, ha="left")
fig.tight_layout(rect=(0, 0, 1, 0.95))
fig.savefig(out / "pd-fig3-decode-gpu.png", dpi=200)
print("wrote", out / "pd-fig3-decode-gpu.png")
