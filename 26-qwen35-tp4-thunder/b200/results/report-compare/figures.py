# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib"]
# ///
"""Figures for the GLM-5.2 vs Qwen3.5 llm-d-thunder-agent-simplified report: step 25 report1h/metrics.json
(GLM-5.2) and metrics-qwen.json (Qwen3.5, collect_qwen.py), c=32, 48, 64; fig4 from metrics-util.json
(collect_util.py, the utilThreshold test)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / ".claude/skills/agentic-benchmark/scripts"))
import figstyle as fs  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

G = json.load(open(ROOT / "25-glm52-tp8-offload/b200/results/report1h/metrics.json"))
Q = json.load(open(HERE / "metrics-qwen.json"))
MODELS = [("GLM-5.2-NVFP4 on 8x B200 (TP8)", G), ("Qwen3.5-397B-A17B-FP8 on 4x B200 (TP4)", Q)]
C = [32, 48, 64]
ARMS = [("no-router", "passthrough", fs.BASELINE_COLOR), ("llm-d-thunder-agent-simplified", "thunder", fs.PALETTE["blue_main"])]
fs.apply_publication_style()


def style(ax):
    ax.set_xticks(C); ax.grid(axis="y", color=fs.GRID_COLOR); ax.set_axisbelow(True)


# fig1 and fig2, one file per model so the two models never share a figure.
PANELS2 = [("running_mean", "requests running in vLLM"), ("waiting_mean", "requests waiting in vLLM"),
           ("prompt_from_gpu_pct", "prompt tokens from GPU cache (%)"), ("cpu_to_gpu_tb", "CPU-to-GPU KV traffic (TB per run)")]
for tag, (title, m) in zip(("glm52", "qwen35"), MODELS):
    # fig1: throughput, the agent latency metrics and TTFT
    fig, ax = plt.subplots(1, 4, figsize=(24, 4.8))
    for name, key, col in ARMS:
        v = [m[f"{key}/{c}"] for c in C]
        ax[0].plot(C, [x["out_tok_s_gpu"] for x in v], "-o", color=col, lw=2.2, ms=7, label=name)
        for k, (metric, solid, dashed) in enumerate((("e2e_norm_intvty", "p50", "p90"), ("e2el", "p90", "p99"), ("ttft", "p50", "p99")), 1):
            ax[k].plot(C, [x[f"{metric}_{solid}"] for x in v], "-o", color=col, lw=2.2, ms=7, label=f"{name} {solid}")
            ax[k].plot(C, [x[f"{metric}_{dashed}"] for x in v], "--o", color=col, lw=1.8, ms=7, mfc="white", label=f"{name} {dashed}")
    ax[0].set_ylim(0, None); ax[0].set_ylabel("output tok/s per GPU")
    ax[1].set_ylim(0, 115); ax[1].set_ylabel("output tokens / request latency")
    ax[2].set_yscale("log"); ax[2].set_ylim(1, 3000); ax[2].set_ylabel("request latency (s, log)")
    ax[3].set_yscale("log"); ax[3].set_ylim(0.3, 3000); ax[3].set_ylabel("TTFT (s, log)")
    fs.panel_title(ax[0], "(a) output throughput")
    fs.panel_title(ax[1], "(b) E2E normalized interactivity p50, p90")
    fs.panel_title(ax[2], "(c) request latency p90, p99")
    fs.panel_title(ax[3], "(d) TTFT p50, p99")
    for a in ax:
        style(a); a.set_xlabel("concurrency (sessions)")
    ax[0].legend(loc="lower right", fontsize=11)
    for a in ax[1:]:
        a.legend(loc="upper left", ncol=2, fontsize=8)
    fig.suptitle(title, y=1.04, fontsize=17, fontweight="bold")
    fs.finalize_figure(fig, HERE, f"fig1-{tag}-throughput-ttft")
    # fig2: why
    fig, ax = plt.subplots(1, 4, figsize=(20, 4.6))
    w = 2.6
    for k, (key, ptitle) in enumerate(PANELS2):
        for i, (name, akey, col) in enumerate(ARMS):
            ax[k].bar([c + (i - 0.5) * w * 1.1 for c in C], [m[f"{akey}/{c}"][key] for c in C], w, color=col, label=name)
        # same y range in both models' figures, so bar heights compare across models
        ax[k].set_ylim(0, 1.08 * max(mm[f"{ak}/{c}"][key] for _, mm in MODELS for _, ak, _ in ARMS for c in C))
        fs.panel_title(ax[k], f"({'abcd'[k]}) {ptitle}")
        style(ax[k]); ax[k].set_xlabel("concurrency (sessions)")
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.12), fontsize=12)
    fig.suptitle(title, y=1.05, fontsize=17, fontweight="bold")
    fs.finalize_figure(fig, HERE, f"fig2-{tag}-mechanism")

# fig3: the ratio llm-d-thunder-agent-simplified / no-router per model, for the agent metrics
fig, ax = plt.subplots(1, 4, figsize=(22, 4.8))
for title, m, col in ((MODELS[0][0], G, fs.PALETTE["teal"]), (MODELS[1][0], Q, fs.PALETTE["violet"])):
    r = lambda k: [m[f"thunder/{c}"][k] / m[f"passthrough/{c}"][k] for c in C]
    ax[0].plot(C, r("out_tok_s_gpu"), "-o", color=col, lw=2.2, ms=7, label=title)
    ax[1].plot(C, r("e2e_norm_intvty_p90"), "-o", color=col, lw=2.2, ms=7, label=title)
    ax[2].plot(C, r("e2el_p99"), "-o", color=col, lw=2.2, ms=7, label=title)
    ax[3].plot(C, [m[f"thunder/{c}"]["progress_ratio_turns"] for c in C], "-o", color=col, lw=2.2, ms=7, label=title)
fs.panel_title(ax[0], "(a) output throughput, ratio to no-router")
fs.panel_title(ax[1], "(b) E2E normalized interactivity p90, ratio (log)")
fs.panel_title(ax[2], "(c) request latency p99, ratio (log)")
fs.panel_title(ax[3], "(d) session progress, turns / no-router")
for a in ax:
    style(a); a.axhline(1, color="black", lw=1, ls=":"); a.set_xlabel("concurrency (sessions)")
ax[1].set_yscale("log"); ax[2].set_yscale("log")
ax[0].legend(loc="lower left", fontsize=10)
fig.suptitle("llm-d-thunder-agent-simplified relative to no-router", y=1.03, fontsize=15)
fs.finalize_figure(fig, HERE, "fig3-ratios")

# fig4: Qwen3.5 at 48 sessions, no-router and llm-d-thunder-agent-simplified at utilThreshold 1.0, 0.8, 0.6
U = json.load(open(HERE / "metrics-util.json"))
names = list(U)
xs = list(range(len(names)))
xlab = ["no-router"] + [f"thunder\nutil {n}" for n in names[1:]]
cols = [fs.BASELINE_COLOR, fs.PALETTE["blue_main"], fs.PALETTE["blue_secondary"], fs.PALETTE["teal"]]
fig, axs = plt.subplots(2, 3, figsize=(20, 10))
ax = axs.ravel()


def labels(a, ys, fmt):
    for x, y in zip(xs, ys):
        a.text(x, y, fmt.format(y), ha="center", va="bottom", fontsize=11)


# (a) sessions admitted
run = [U[n]["admitted_running"] or 0 for n in names]
idle = [U[n]["admitted_idle"] or 0 for n in names]
ax[0].bar(xs, run, 0.6, color=fs.PALETTE["blue_main"], label="running")
ax[0].bar(xs, idle, 0.6, bottom=run, color=fs.PALETTE["green_2"], label="idle (between turns)")
for x, r, i in zip(xs[1:], run[1:], idle[1:]):
    ax[0].text(x, r + i, f"{r + i:.1f}", ha="center", va="bottom", fontsize=11)
ax[0].text(0, 1, "no admission\ncontrol", ha="center", va="bottom", fontsize=11)
ax[0].set_ylim(0, 56); ax[0].set_ylabel("sessions admitted at once (mean)")
ax[0].legend(loc="upper right", fontsize=11)
fs.panel_title(ax[0], "(a) sessions admitted")
# (b) prompt token sources
bottom = [0] * len(names)
for key, lab, col in (("gpu_pct", "GPU cache", fs.PALETTE["blue_main"]), ("cpu_pct", "CPU tier", fs.PALETTE["blue_secondary"]),
                      ("computed_pct", "computed", fs.PALETTE["neutral"])):
    v = [U[n][key] for n in names]
    ax[1].bar(xs, v, 0.6, bottom=bottom, color=col, label=lab, alpha=1 if key == "gpu_pct" else 0.55)
    if key == "gpu_pct":
        for x, y in zip(xs, v):
            ax[1].text(x, y / 2, f"{y:.0f}%", ha="center", va="center", color="white", fontsize=12, fontweight="bold")
    bottom = [b + y for b, y in zip(bottom, v)]
ax[1].set_ylim(0, 100); ax[1].set_ylabel("% of prompt tokens (steady state)")
ax[1].legend(loc="upper left", fontsize=10, ncol=3)
fs.panel_title(ax[1], "(b) prompt token source")
# (c) throughput
v = [U[n]["out_tok_s_gpu"] for n in names]
ax[2].bar(xs, v, 0.6, color=cols)
labels(ax[2], v, "{:.0f}")
ax[2].set_ylim(0, 460); ax[2].set_ylabel("output tok/s per GPU")
fs.panel_title(ax[2], "(c) output throughput")
# (d) decode-only interactivity against E2E normalized interactivity
w = 0.38
for i, (key, lab, col) in enumerate((("intvty_p90", "interactivity p90 (decode only)", fs.PALETTE["neutral"]),
                                     ("e2e_norm_intvty_p90", "E2E normalized interactivity p90", fs.PALETTE["violet"]))):
    v = [U[n][key] for n in names]
    pos = [x + (i - 0.5) * w for x in xs]
    ax[3].bar(pos, v, w, color=col, label=lab)
    for x, y in zip(pos, v):
        ax[3].text(x, y, f"{y:.0f}", ha="center", va="bottom", fontsize=11)
ax[3].set_ylim(0, 60); ax[3].set_ylabel("tok/s per user (slowest 10%)")
ax[3].legend(loc="upper left", fontsize=10)
fs.panel_title(ax[3], "(d) speed per user, without and with the wait")
# (e) request latency
for i, (key, lab, col) in enumerate((("e2el_p90", "p90", fs.PALETTE["blue_secondary"]), ("e2el_p99", "p99", fs.PALETTE["red_strong"]))):
    v = [U[n][key] for n in names]
    pos = [x + (i - 0.5) * w for x in xs]
    ax[4].bar(pos, v, w, color=col, label=lab)
    for x, y in zip(pos, v):
        ax[4].text(x, y, f"{y:.0f}", ha="center", va="bottom", fontsize=11)
ax[4].set_ylim(0, 225); ax[4].set_ylabel("request latency (s)")
ax[4].legend(loc="upper left", fontsize=11)
fs.panel_title(ax[4], "(e) request latency p90 and p99")
# (f) session progress and sessions held over 60 s
v = [U[n]["progress_ratio_turns"] for n in names]
ax[5].bar(xs, v, 0.6, color=cols)
labels(ax[5], v, "{:.2f}")
ax[5].axhline(1, color="black", lw=1, ls=":")
ax[5].set_ylim(0, 1.2); ax[5].set_ylabel("turns / no-router turns, shared traces")
for x, n in zip(xs, names):
    ax[5].text(x, 0.05, f"{U[n]['sessions_over_60s_pct']:.0f}%\nsessions\nwith a turn\nover 60 s", ha="center", va="bottom",
               fontsize=10, color="white" if x else "black")
fs.panel_title(ax[5], "(f) session progress")
for a in ax:
    a.set_xticks(xs, xlab); a.grid(axis="y", color=fs.GRID_COLOR); a.set_axisbelow(True)
fig.suptitle("Qwen3.5-397B-A17B-FP8 on 4x B200 (TP4), 48 sessions: llm-d-thunder-agent-simplified with free space",
             y=1.01, fontsize=17, fontweight="bold")
fig.tight_layout()
fs.finalize_figure(fig, HERE, "fig4-qwen35-utilthreshold")
print("ok")
