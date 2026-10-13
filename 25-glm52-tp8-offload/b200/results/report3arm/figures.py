# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Figures for the three-arm report and the offload comparison, from metrics.json."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / ".claude/skills/agentic-benchmark/scripts"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator, ScalarFormatter  # noqa: E402

m = json.load(open(HERE / "metrics.json"))
C = [12, 16, 20, 24, 32]
ARMS = [("passthrough", "passthrough", fs.BASELINE_COLOR),
        ("thunder lease 10 s", "thunder-l10", fs.PALETTE["blue_main"]),
        ("thunder lease 30 s (default)", "thunder-l30", fs.PALETTE["teal"])]
ARMS = [(name, [c for c in C if f"{key}/{c}" in m], [m[f"{key}/{c}"] for c in C if f"{key}/{c}" in m], col)
        for name, key, col in ARMS]
fs.apply_publication_style()

def style(ax, xticks=None):
    if xticks:
        ax.set_xticks(xticks)
    ax.grid(axis="y", color=fs.GRID_COLOR); ax.set_axisbelow(True)

fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
for name, cs, v, col in ARMS:
    ax[0].plot(cs, [x["out_tok_s"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
fs.panel_title(ax[0], "(a) output throughput (tok/s, 8 GPUs)")
ax[0].set_xlabel("concurrency (sessions)"); ax[0].set_ylabel("output tok/s")
for name, cs, v, col in ARMS:
    ax[1].plot(cs, [x["ttft_p90"] for x in v], "-o", color=col, lw=2.2, ms=7, label=f"{name} p90")
    ax[1].plot(cs, [x["ttft_p99"] for x in v], "--o", color=col, lw=1.8, ms=7, mfc="white", label=f"{name} p99")
ax[1].set_yscale("log"); fs.panel_title(ax[1], "(b) time to first token (s, log scale)")
ax[1].set_xlabel("concurrency (sessions)"); ax[1].set_ylabel("TTFT (s)")
for a in ax:
    style(a, C)
ax[0].legend(loc="upper left", fontsize=12); ax[1].legend(loc="upper left", ncol=2, fontsize=10)
fs.finalize_figure(fig, HERE, "fig1-throughput-ttft")

fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
w = 1.0
for i, (name, cs, v, col) in enumerate(ARMS):
    ax[0].bar([c + (i - 1) * w for c in cs], [x["turns_over_60s_pct"] for x in v], width=w, color=col, label=name)
    ax[1].bar([c + (i - 1) * w for c in cs], [x["errors"] + x["cancelled"] for x in v], width=w, color=col, label=name)
fs.panel_title(ax[0], "(a) turns with TTFT over 60 s (% of turns)")
ax[0].set_xlabel("concurrency (sessions)"); ax[0].set_ylabel("% of turns")
fs.panel_title(ax[1], "(b) requests failed or cancelled at the end (count)")
ax[1].set_xlabel("concurrency (sessions)"); ax[1].set_ylabel("requests"); ax[1].set_ylim(0, 8)
for a in ax:
    style(a, C); a.legend(loc="upper left", fontsize=12)
fs.finalize_figure(fig, HERE, "fig2-tail-errors")

# Pareto: throughput against per-user speed and against TTFT; each point is one concurrency.
fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
for j, (name, cs, v, col) in enumerate(ARMS):
    ax[0].plot([x["intvty_p90"] for x in v], [x["out_tok_s_gpu"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
    ax[1].plot([x["ttft_p90"] for x in v], [x["out_tok_s_gpu"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
    off_a, off_b = (((5, -14), (5, -14)), ((5, 6), (5, 6)), ((-30, -4), (8, -4)))[j]
    for c, x in zip(cs, v):
        ax[0].annotate(f"c{c}", (x["intvty_p90"], x["out_tok_s_gpu"]), xytext=off_a, textcoords="offset points", fontsize=10, color=col)
        ax[1].annotate(f"c{c}", (x["ttft_p90"], x["out_tok_s_gpu"]), xytext=off_b, textcoords="offset points", fontsize=10, color=col)
fs.panel_title(ax[0], "(a) throughput vs interactivity p90")
ax[0].set_xlabel("interactivity p90 (tok/s/user, slow end)"); ax[0].set_ylabel("output tok/s/GPU")
fs.panel_title(ax[1], "(b) throughput vs TTFT p90")
ax[1].set_xscale("log"); ax[1].set_xlabel("TTFT p90 (s, log scale)"); ax[1].set_ylabel("output tok/s/GPU")
ax[1].xaxis.set_major_locator(FixedLocator([1, 2, 5, 10, 20, 40])); ax[1].xaxis.set_minor_locator(NullLocator())
ax[1].xaxis.set_major_formatter(ScalarFormatter())
for a in ax:
    style(a)
ax[0].legend(loc="upper right", fontsize=12); ax[1].legend(loc="lower right", fontsize=12)
fs.finalize_figure(fig, HERE, "fig3-pareto")

# Offload on vs off, passthrough and thunder lease 10 s, at the concurrencies run both ways.
CO = [c for c in (16, 24, 32) if f"passthrough-nooff/{c}" in m or f"thunder-l10-nooff/{c}" in m]
if CO:
    VAR = [("passthrough, offload", "passthrough", fs.BASELINE_COLOR, None),
           ("passthrough, no offload", "passthrough-nooff", fs.BASELINE_COLOR, "//"),
           ("thunder l10, offload", "thunder-l10", fs.PALETTE["blue_main"], None),
           ("thunder l10, no offload", "thunder-l10-nooff", fs.PALETTE["blue_main"], "//")]
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.8))
    x0 = range(len(CO)); w = 0.2
    for i, (name, key, col, hatch) in enumerate(VAR):
        xs = [x + (i - 1.5) * w for x in x0]
        get = lambda f: [m[f"{key}/{c}"][f] if f"{key}/{c}" in m else 0 for c in CO]
        kw = dict(width=w, label=name, color="white" if hatch else col, edgecolor=col, hatch=hatch, lw=1.5)
        ax[0].bar(xs, get("out_tok_s"), **kw)
        ax[1].bar(xs, get("ttft_p90"), **kw)
        ax[2].bar(xs, get("prompt_computed_pct"), **kw)
    fs.panel_title(ax[0], "(a) output throughput (tok/s)")
    fs.panel_title(ax[1], "(b) TTFT p90 (s, log scale)"); ax[1].set_yscale("log")
    fs.panel_title(ax[2], "(c) prompt tokens computed (%)")
    for a in ax:
        a.set_xticks(list(x0)); a.set_xticklabels([f"c={c}" for c in CO]); style(a)
    ax[0].legend(loc="upper left", fontsize=10)
    fs.finalize_figure(fig, HERE, "fig4-offload")
print("ok")
