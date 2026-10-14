# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Figures for the llm-d-thunder-agent-simplified parameter report, from metrics.json."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / ".claude/skills/agentic-benchmark/scripts"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

m = json.load(open(HERE / "metrics.json"))
P = fs.PALETTE
CAP = [("no-router", "no-router", fs.BASELINE_COLOR),
       ("gpu-l10", "capacity 1.57M (GPU pool)", P["blue_main"]),
       ("cap3m-l10", "capacity 3.15M (2x)", P["teal"]),
       ("cap6m-l10", "capacity 6.29M (4x)", P["violet"])]
fs.apply_publication_style()


def style(ax):
    ax.grid(axis="y", color=fs.GRID_COLOR); ax.set_axisbelow(True)


# fig1: capacity at c=32 and 48
fig, ax = plt.subplots(1, 4, figsize=(20, 4.8))
C = [32, 48]; w = 0.2
panels = [("out_tok_s", "(a) output throughput (tok/s)", False), ("ttft_p50", "(b) TTFT p50 (s, log)", True),
          ("ttft_p99", "(c) TTFT p99 (s, log)", True), ("ss_gpu_hit", "(d) steady GPU prefix hit (%)", False)]
for j, (key, title, log) in enumerate(panels):
    for i, (arm, name, col) in enumerate(CAP):
        xs = [k + (i - 1.5) * w for k in range(len(C))]
        ys = [m[f"{arm}/{c}"][key] if f"{arm}/{c}" in m else 0 for c in C]
        ax[j].bar(xs, ys, w, color=col, label=name)
    ax[j].set_xticks(range(len(C)), [f"c={c}" for c in C])
    if log:
        ax[j].set_yscale("log")
    fs.panel_title(ax[j], title); style(ax[j])
h, l = ax[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.08), fontsize=12)
fs.finalize_figure(fig, HERE, "fig1-capacity")

# fig2: 5-minute timelines at c=32 and 48
fig, ax = plt.subplots(2, 2, figsize=(15, 8.5), sharex=True)
for r, c in enumerate(C):
    for arm, name, col in CAP[1:]:
        k = f"{arm}/{c}"
        if k not in m or "timeline" not in m[k]:
            continue
        t = m[k]["timeline"]
        x = [b["min"] + 2.5 for b in t]
        ax[r][0].plot(x, [b["out_tok_s"] for b in t], "-o", color=col, lw=2, ms=5, label=name)
        ax[r][1].plot(x, [b["ttft_p50"] or float("nan") for b in t], "-o", color=col, lw=2, ms=5, label=name)
    ax[r][0].set_ylabel("output tok/s"); ax[r][1].set_ylabel("TTFT p50 (s)"); ax[r][1].set_yscale("log")
    fs.panel_title(ax[r][0], f"({'ac'[r]}) c={c}: output throughput per 5 min")
    fs.panel_title(ax[r][1], f"({'bd'[r]}) c={c}: median TTFT per 5 min (log)")
    for a in ax[r]:
        style(a); a.axvline(30, color="grey", ls=":", lw=1.5)
for a in ax[1]:
    a.set_xlabel("minute of the profiling window (dotted: 30 min, 1800 s backstop)")
ax[1][0].legend(loc="lower left", fontsize=10)
fs.finalize_figure(fig, HERE, "fig2-timeline")

# fig3: idle lease 10 s vs 30 s, c=12 to 32
fig, ax = plt.subplots(1, 3, figsize=(18, 4.8))
LEASE = [("no-router", "no-router", fs.BASELINE_COLOR), ("gpu-l10", "lease 10 s", P["blue_main"]),
         ("gpu-l30", "lease 30 s", P["teal"])]
CL = [12, 16, 20, 24, 32]
for arm, name, col in LEASE:
    v = [m[f"{arm}/{c}"] for c in CL]
    ax[0].plot(CL, [x["out_tok_s"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
    ax[1].plot(CL, [x["ttft_p90"] for x in v], "-o", color=col, lw=2.2, ms=7, label=f"{name} p90")
    ax[1].plot(CL, [x["ttft_p99"] for x in v], "--o", color=col, lw=1.8, ms=7, mfc="white", label=f"{name} p99")
    ax[2].plot(CL, [x["sessions_over_60s_pct"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
fs.panel_title(ax[0], "(a) output throughput (tok/s)"); fs.panel_title(ax[1], "(b) TTFT p90 and p99 (s, log)")
fs.panel_title(ax[2], "(c) sessions with a turn over 60 s (%)")
ax[1].set_yscale("log")
for a in ax:
    a.set_xticks(CL); a.set_xlabel("concurrency (sessions)"); style(a)
ax[0].legend(loc="lower right", fontsize=11); ax[1].legend(loc="upper left", ncol=2, fontsize=9)
fs.finalize_figure(fig, HERE, "fig3-lease")

# fig4: throughput vs interactivity p90, every arm and point
fig, ax = plt.subplots(figsize=(9, 6))
ALL = CAP + [("gpu-l30", "lease 30 s (capacity 1.57M)", P["green_3"]), ("cap391-l10", "capacity 3.91M", P["blue_secondary"])]
for arm, name, col in ALL:
    pts = sorted((v for v in m.values() if v["arm"] == arm), key=lambda v: v["conc"])
    ax.plot([v["intvty_p90"] for v in pts], [v["out_tok_s_gpu"] for v in pts], "-o", color=col, lw=2, ms=7, label=name)
    for v in pts:
        ax.annotate(f"c{v['conc']}", (v["intvty_p90"], v["out_tok_s_gpu"]), xytext=(5, 4), textcoords="offset points",
                    fontsize=9, color=col)
ax.set_xlabel("interactivity p90 (tok/s/user, slow end)"); ax.set_ylabel("output tok/s/GPU")
fs.panel_title(ax, "throughput vs interactivity p90 (lease 10 s unless noted)"); style(ax)
ax.legend(loc="lower left", fontsize=9)
fs.finalize_figure(fig, HERE, "fig4-pareto")
print("ok")
