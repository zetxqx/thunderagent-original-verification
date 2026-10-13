# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Figures for the 1-hour thunder-vs-passthrough report, from metrics.json."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3] / ".claude/skills/agentic-benchmark/scripts"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

m = json.load(open(HERE / "metrics.json"))
C = [12, 16, 20, 24, 32, 48, 64, 96, 128]
P = [m[f"passthrough/{c}"] for c in C]
T = [m[f"thunder/{c}"] for c in C]
ARMS = [("no-router", P, fs.BASELINE_COLOR), ("llm-d-thunder-agent-simplified", T, fs.PALETTE["blue_main"])]
fs.apply_publication_style()

fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
for name, v, col in ARMS:
    ax[0].plot(C, [x["out_tok_s"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
fs.panel_title(ax[0], "(a) output throughput (tok/s, 8 GPUs)")
ax[0].set_xlabel("concurrency (sessions)"); ax[0].set_ylabel("output tok/s")
for name, v, col in ARMS:
    ax[1].plot(C, [x["ttft_p90"] for x in v], "-o", color=col, lw=2.2, ms=7, label=f"{name} p90")
    ax[1].plot(C, [x["ttft_p99"] for x in v], "--o", color=col, lw=1.8, ms=7, mfc="white", label=f"{name} p99")
ax[1].set_yscale("log"); ax[1].set_ylim(1, 30000); fs.panel_title(ax[1], "(b) time to first token (s, log scale)")
ax[1].set_xlabel("concurrency (sessions)"); ax[1].set_ylabel("TTFT (s)")
for a in ax:
    a.set_xscale("log", base=2); a.set_xticks(C, [str(c) for c in C]); a.minorticks_off()
    a.grid(axis="y", color=fs.GRID_COLOR); a.set_axisbelow(True)
ax[0].set_ylim(0, None)
ax[0].legend(loc="lower right"); ax[1].legend(loc="upper left", ncol=2)
fs.finalize_figure(fig, HERE, "fig1-throughput-ttft")

fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
w, X = 0.4, range(len(C))
for i, (name, v, col) in enumerate(ARMS):
    ax[0].bar([j + (i - 0.5) * w for j in X], [x["turns_over_60s_pct"] for x in v], width=w, color=col, label=name)
fs.panel_title(ax[0], "(a) turns with TTFT over 60 s (% of turns)")
ax[0].set_xlabel("concurrency (sessions)"); ax[0].set_ylabel("% of turns")
for i, (name, v, col) in enumerate(ARMS):
    ax[1].bar([j + (i - 0.5) * w for j in X], [x["errors"] + x["cancelled"] for x in v], width=w, color=col, label=name)
ax[1].set_yscale("symlog", linthresh=10); ax[1].set_ylim(0, 400)
fs.panel_title(ax[1], "(b) requests failed or cancelled at the end (count)")
ax[1].set_xlabel("concurrency (sessions)"); ax[1].set_ylabel("requests")
for a in ax:
    a.set_xticks(list(X), [str(c) for c in C]); a.grid(axis="y", color=fs.GRID_COLOR); a.set_axisbelow(True); a.legend(loc="upper left")
fs.finalize_figure(fig, HERE, "fig2-tail-errors")

# Pareto: throughput against per-user speed and against TTFT; each point is one concurrency.
fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
for name, v, col in ARMS:
    ax[0].plot([x["intvty_p90"] for x in v], [x["out_tok_s_gpu"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
    ax[1].plot([x["ttft_p90"] for x in v], [x["out_tok_s_gpu"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
    for i, (c, x) in enumerate(zip(C, v)):
        dy = 6 if name == "llm-d-thunder-agent-simplified" else -14
        ax[0].annotate(f"c{c}", (x["intvty_p90"], x["out_tok_s_gpu"]), xytext=(5, dy), textcoords="offset points", fontsize=11, color=col)
        ax[1].annotate(f"c{c}", (x["ttft_p90"], x["out_tok_s_gpu"]), xytext=(5, dy), textcoords="offset points", fontsize=11, color=col)
fs.panel_title(ax[0], "(a) throughput vs interactivity p90")
ax[0].set_xlabel("interactivity p90 (tok/s/user, slow end)"); ax[0].set_ylabel("output tok/s/GPU")
fs.panel_title(ax[1], "(b) throughput vs TTFT p90")
ax[1].set_xscale("log"); ax[1].set_xlabel("TTFT p90 (s, log scale)"); ax[1].set_ylabel("output tok/s/GPU")
from matplotlib.ticker import FixedLocator, NullLocator, ScalarFormatter  # noqa: E402
ax[1].xaxis.set_major_locator(FixedLocator([2, 5, 10, 20, 50, 100, 200, 500])); ax[1].xaxis.set_minor_locator(NullLocator())
ax[1].xaxis.set_major_formatter(ScalarFormatter())
for a in ax:
    a.grid(axis="y", color=fs.GRID_COLOR); a.set_axisbelow(True)
ax[1].set_xlim(None, 5000)
ax[0].legend(loc="lower right"); ax[1].legend(loc="lower left")
for a in ax:
    a.set_ylim(25, None)
fs.finalize_figure(fig, HERE, "fig3-pareto")
print("ok")
