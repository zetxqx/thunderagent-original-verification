# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Step 37: GLM-5.2-NVFP4 2P1D (24 GPUs, no router) against aggregated TP=8 (8 GPUs, no router and
thunder-l10, step 25) and 1P1D (16 GPUs, step 35). Steady-state points; the references come from the
GLM dashboard bundle, the 2P1D points from this step's analyze.py summary.csv.

  uv run 37-glm52-2p1d/make_figure.py <glm bundle.json> <2p1d summary.csv> <out.png>

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

REFS = [("no-router", "TP=8 aggregated, no router (8 GPUs)", dict(color=figstyle.BASELINE_COLOR, ls="-", marker="o")),
        ("thunder-l10", "TP=8 aggregated + thunder (8 GPUs)", dict(color=figstyle.ARM_COLORS[0], ls="-", marker="o")),
        ("glm52-1p1d-baseline", "PD 1P1D, no router (16 GPUs)", dict(color="#1B7837", ls="--", marker="s"))]
P2 = ("PD 2P1D, no router (24 GPUs)", dict(color="#D6249F", ls="--", marker="D"))
MAX_CPG = 8


def ref_series(bundle, arm):
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


def csv_series(path):
    pts = []
    for r in csv.DictReader(open(path)):
        g = int(r["num_gpus"])
        pts.append(dict(conc=int(r["conc"]), cpg=int(r["conc"]) / g, tpg=float(r["ss_output_tput_per_gpu"]),
                        tot=float(r["ss_output_tput"]), ttft=float(r["ss_p50_ttft_s"]),
                        e2e=float(r["ss_p50_e2e_norm_intvty"])))
    return sorted(pts, key=lambda d: d["cpg"])


bundle = json.load(open(sys.argv[1]))
series = [(label, st, ref_series(bundle, arm)) for arm, label, st in REFS]
series.append((P2[0], P2[1], csv_series(sys.argv[2])))

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
fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.005))
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(sys.argv[3], dpi=200)
print("wrote", sys.argv[3])
