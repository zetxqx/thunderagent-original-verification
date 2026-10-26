# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Step 40: GLM-5.2-NVFP4 1P2D + thunder (24 GPUs) against every other GLM-5.2 deployment: 1P2D without
router (step 39), 2P1D with and without thunder (24 GPUs, steps 37 and 38), 1P1D with and without thunder
(16 GPUs, steps 35 and 36) and aggregated TP=8 with and without thunder (8 GPUs, step 25). Steady-state
points; the step 25/35/36 arms come from the GLM dashboard bundle, the 2P1D arms from step 38's analyze.py
summary.csv, the 1P2D arms from step 40's (it holds step 39's points too).

  uv run 40-glm52-1p2d-thunder/make_figure.py <glm bundle.json> <step 38 summary.csv> <step 40 summary.csv> <out.png>

(a) output tok/s/GPU and (b) TTFT p50 against concurrency per GPU, (c) total output tok/s against
total concurrency, (d) E2E-normalized interactivity p50 against output tok/s/GPU (Pareto; up and
right is better), labelled with concurrency per GPU.
"""
import csv, json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude/skills/agentic-benchmark/scripts"))
import figstyle  # noqa: E402

BUNDLE_ARMS = [
    ("no-router", "TP=8 aggregated, no router (8 GPUs)", dict(color=figstyle.BASELINE_COLOR, ls="-", marker="o")),
    ("thunder-l10", "TP=8 aggregated + thunder (8 GPUs)", dict(color=figstyle.ARM_COLORS[0], ls="-", marker="o")),
    ("glm52-1p1d-baseline", "PD 1P1D, no router (16 GPUs)", dict(color="#1B7837", ls="--", marker="s")),
    ("glm52-1p1d-thunder-l10", "PD 1P1D + thunder (16 GPUs)", dict(color="#1F1F1F", ls="--", marker="s")),
]
CSV_ARMS = [
    ("glm52-2p1d-baseline", "PD 2P1D, no router (24 GPUs)", dict(color="#D6249F", ls=":", marker="D")),
    ("glm52-2p1d-thunder-l10", "PD 2P1D + thunder (24 GPUs)", dict(color="#E66101", ls=":", marker="D")),
    ("glm52-1p2d-baseline", "PD 1P2D, no router (24 GPUs)", dict(color="#8C510A", ls="-.", marker="^")),
    ("glm52-1p2d-thunder-l10", "PD 1P2D + thunder (24 GPUs)", dict(color="#762A83", ls="-.", marker="^")),
]
MAX_CPG = 8


def bundle_series(bundle, arm):
    pts = []
    for p in bundle["points"]:
        if p["arm"] != arm:
            continue
        s = p["summary"]
        cpg = p["conc"] / s["num_gpus"]
        if cpg <= MAX_CPG + 1e-9:
            pts.append(dict(conc=p["conc"], cpg=cpg, tpg=s["ss_output_tput_per_gpu"], tot=s["ss_output_tput"],
                            ttft=s["ss_p50_ttft_s"], e2e=s["ss_p50_e2e_norm_intvty"]))
    return sorted(pts, key=lambda d: d["cpg"])


def csv_series(rows, label):
    pts = []
    for r in rows:
        if r["label"] != label:
            continue
        g = int(r["num_gpus"])
        pts.append(dict(conc=int(r["conc"]), cpg=int(r["conc"]) / g, tpg=float(r["ss_output_tput_per_gpu"]),
                        tot=float(r["ss_output_tput"]), ttft=float(r["ss_p50_ttft_s"]),
                        e2e=float(r["ss_p50_e2e_norm_intvty"])))
    return sorted(pts, key=lambda d: d["cpg"])


bundle = json.load(open(sys.argv[1]))
rows = list(csv.DictReader(open(sys.argv[2])))
rows += [r for r in csv.DictReader(open(sys.argv[3])) if r["label"] in ("glm52-1p2d-baseline", "glm52-1p2d-thunder-l10")]
series = [(label, st, bundle_series(bundle, arm)) for arm, label, st in BUNDLE_ARMS]
series += [(label, st, csv_series(rows, arm)) for arm, label, st in CSV_ARMS]

figstyle.apply_publication_style(font_size=12)
fig, axes = plt.subplots(2, 2, figsize=(14, 10.5))
ax_t, ax_f, ax_tot, ax_p = axes.flat
for label, st, pts in series:
    if not pts:
        continue
    kw = dict(color=st["color"], ls=st["ls"], marker=st["marker"], lw=2.3, ms=7, label=label)
    x = [d["cpg"] for d in pts]
    ax_t.plot(x, [d["tpg"] for d in pts], **kw)
    ax_f.plot(x, [d["ttft"] for d in pts], **kw)
    ax_tot.plot([d["conc"] for d in pts], [d["tot"] for d in pts], **kw)
    ax_p.plot([d["tpg"] for d in pts], [d["e2e"] for d in pts], **kw)
    for d in pts:
        ax_p.annotate(f"{d['cpg']:.3g}", (d["tpg"], d["e2e"]), textcoords="offset points", xytext=(4, 3),
                      fontsize=8.5, color=st["color"])
for ax in (ax_t, ax_f):
    ax.set_xlabel("concurrency per GPU")
    ax.grid(axis="y", color=figstyle.GRID_COLOR)
ax_t.set_ylabel("output tok/s/GPU")
ax_t.set_ylim(bottom=0)
ax_f.set_ylabel("TTFT p50 (s)")
ax_f.set_yscale("log")
ax_f.axhline(60, color="#888888", ls=":", lw=1.2)
ax_f.annotate("60 s SLO", (0.1, 60), xytext=(2, 3), textcoords="offset points", fontsize=8.5, color="#666666")
ax_tot.set_xlabel("total concurrency (sessions)")
ax_tot.set_ylabel("total output tok/s")
ax_tot.set_ylim(bottom=0)
ax_tot.grid(axis="y", color=figstyle.GRID_COLOR)
ax_p.set_xlabel("output tok/s/GPU")
ax_p.set_ylabel("E2E-normalized interactivity p50 (tok/s/user)")
ax_p.set_xlim(left=0)
ax_p.set_ylim(bottom=0)
ax_p.grid(color=figstyle.GRID_COLOR)
figstyle.panel_title(ax_t, "(a) output tok/s/GPU")
figstyle.panel_title(ax_f, "(b) TTFT p50 (log scale)")
figstyle.panel_title(ax_tot, "(c) total output tok/s by total concurrency")
figstyle.panel_title(ax_p, "(d) Pareto (labels: conc/GPU)")
handles, labels = ax_t.get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.005))
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(sys.argv[4], dpi=200)
print("wrote", sys.argv[4])
