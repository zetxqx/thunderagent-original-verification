# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "matplotlib", "tabulate"]
# ///
"""Across-arm report figures and baseline ratios from one or more analyze.py summary.csv files.

Usage: uv run make_figures.py --out DIR [--baseline LABEL] [--name LABEL=TEXT ...] [--window steady|whole]
                              SUMMARY_CSV [...]

Labels that differ only by a replicate suffix (default "-r<N>", see
--replicate-suffix) are one arm: figures show the mean with min-max bars.
--window steady (default) uses the ss_* columns (requests started after
analyze.py's --skip-minutes), like the sweep figures; --window whole uses the
whole profiling window (AgentX's definition, to compare with InferenceX).
Figures whose columns are missing are skipped. Writes fig1..fig5 as png and
ratios.md (each arm against --baseline at the same concurrency).
See ../references/figures.md for what each figure is for and the style rules.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figstyle import (  # noqa: E402
    ARM_COLORS, BASELINE_COLOR, GRID_COLOR, PALETTE, apply_publication_style, finalize_figure, panel_title,
)

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

RATIO_COLS = [
    ("output_tput_per_gpu", "output tok/s/GPU"), ("total_tput_per_gpu", "total tok/s/GPU"),
    ("goodput_output_tput", "goodput tok/s"), ("p90_intvty", "P90 interactivity"),
    ("p50_ttft_s", "TTFT p50"), ("p90_ttft_s", "TTFT p90"), ("turn_slo_share_pct", "turn SLO share"),
    ("overall_hit_pct", "hit rate"), ("completed", "completed requests"),
]
# P90 is the headline (AgentX): solid with filled markers. P50 and other second
# series: dashed with hollow markers, same color.
SOLID = {"fmt": "-", "marker": "o"}
DASHED = {"fmt": "--", "marker": "o", "markerfacecolor": "white"}


def load(paths: list[Path], suffix: str, window: str) -> pd.DataFrame:
    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    df["arm"] = df["label"].str.replace(suffix, "", regex=True)
    if window == "steady":
        for c in [c for c in df.columns if c.startswith("ss_")]:
            base = c.removeprefix("ss_")
            df[base] = df[c].where(df[c].notna(), df.get(base))
    return df


def agg(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Per arm and concurrency: mean, min, max, n of one column."""
    g = df.dropna(subset=[col]).groupby(["arm", "conc"])[col]
    return g.agg(["mean", "min", "max", "count"]).reset_index()


class Arms:
    def __init__(self, arms: list[str], baseline: str | None, names: dict[str, str]):
        others = iter(ARM_COLORS)
        self.color = {a: BASELINE_COLOR if a == baseline else next(others, PALETTE["neutral"]) for a in arms}
        self.name = {a: names.get(a, a) for a in arms}
        self.order = sorted(arms, key=lambda a: (a != baseline, a))


def style(ax, title: str) -> None:
    panel_title(ax, title)
    ax.grid(axis="y", color=GRID_COLOR, lw=1)
    ax.set_axisbelow(True)


def line_vs_conc(ax, df: pd.DataFrame, col: str, arms: Arms, kind: dict = SOLID) -> None:
    a = agg(df, col)
    for arm in arms.order:
        g = a[a["arm"] == arm].sort_values("conc")
        if g.empty:
            continue
        err = [g["mean"] - g["min"], g["max"] - g["mean"]] if (g["count"] > 1).any() else None
        ax.errorbar(g["conc"], g["mean"], yerr=err, color=arms.color[arm], capsize=3, linewidth=2, markersize=6,
                    markeredgewidth=1.6, **kind)
    concs = sorted(df["conc"].unique())
    ax.set_xscale("log", base=2)
    ax.set_xticks(concs, [str(c) for c in concs])
    ax.minorticks_off()
    ax.set_xlim(concs[0] / 1.5, concs[-1] * 1.5)
    ax.set_xlabel("concurrency")


def has(df: pd.DataFrame, *cols: str) -> bool:
    return all(c in df and df[c].notna().any() for c in cols)


def headroom(ax, factor: float = 1.3) -> None:
    lo, hi = ax.get_ylim()
    ax.set_ylim(0, hi * factor)


def style_legend(ax, solid: str, dashed: str) -> None:
    ax.legend(handles=[Line2D([], [], color="black", lw=2, marker="o", label=solid),
                       Line2D([], [], color="black", lw=2, ls="--", marker="o", mfc="white", label=dashed)],
              loc="upper left")


def arm_legend(fig, arms: Arms) -> None:
    if len(arms.order) > 1:
        fig.legend(handles=[Line2D([], [], color=arms.color[a], lw=2, marker="o", label=arms.name[a]) for a in arms.order],
                   loc="lower center", ncol=len(arms.order), bbox_to_anchor=(0.5, -0.08))


def fig_pareto(df, arms, out):
    charts = [("intvty", "total_tput_per_gpu", "interactivity (tok/s/user)", "Total tok/s/GPU"),
              ("intvty", "output_tput_per_gpu", "interactivity (tok/s/user)", "Output tok/s/GPU"),
              ("ttft_s", "input_tput_per_gpu", "TTFT (s)", "Input tok/s/GPU"),
              ("e2e_norm_intvty", "total_tput_per_gpu", "E2E norm. interactivity", "Total tok/s/GPU")]
    charts = [c for c in charts if has(df, f"p90_{c[0]}", c[1])]
    if not charts:
        return
    fig, axes = plt.subplots(1, len(charts), figsize=(4.6 * len(charts), 4.2))
    for i, (ax, (x, y, xl, title)) in enumerate(zip(np.atleast_1d(axes), charts)):
        my = agg(df, y)
        xs = []
        for pct, kind in ((f"p50_{x}", DASHED), (f"p90_{x}", SOLID)):
            if not has(df, pct):
                continue
            m = agg(df, pct).merge(my, on=["arm", "conc"], suffixes=("_x", "_y"))
            xs += list(m["mean_x"])
            for arm in arms.order:
                g = m[m["arm"] == arm].sort_values("conc")
                ax.plot(g["mean_x"], g["mean_y"], ls=kind["fmt"], marker="o", ms=6, mew=1.6, lw=2,
                        color=arms.color[arm], mfc=kind.get("markerfacecolor", arms.color[arm]))
                if kind is SOLID:
                    for k, (_, r) in enumerate(g.iterrows()):  # alternate above and below so close points stay readable
                        ax.annotate(f"c{r['conc']}", (r["mean_x"], r["mean_y"]), fontsize=9,
                                    xytext=(5, 5 if k % 2 == 0 else -13), textcoords="offset points")
        if "ttft" in x:  # spans orders of magnitude once the server saturates
            ax.set_xscale("log")
            ax.set_xlim(min(xs) / 1.6, max(xs) * 1.6)
        else:
            ax.set_xlim(0, max(xs) * 1.25)
        ax.set_ylim(0, my["mean"].max() * 1.25)
        ax.set_xlabel(xl)
        style(ax, f"({'abcd'[i]}) {title}")
    style_legend(np.atleast_1d(axes)[0], "P90", "P50")
    arm_legend(fig, arms)
    finalize_figure(fig, out, "fig1-pareto")


def fig_load(df, arms, out):
    if not has(df, "output_tput_per_gpu"):
        return
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.4))
    line_vs_conc(ax[0], df, "output_tput_per_gpu", arms)
    if has(df, "goodput_output_tput", "num_gpus"):
        line_vs_conc(ax[0], df.assign(goodput_per_gpu=df["goodput_output_tput"] / df["num_gpus"]),
                     "goodput_per_gpu", arms, DASHED)
        style_legend(ax[0], "all output", "goodput")
    headroom(ax[0])
    style(ax[0], "(a) Output tok/s/GPU")
    if has(df, "p90_ttft_s"):
        line_vs_conc(ax[1], df, "p90_ttft_s", arms)
        if has(df, "p50_ttft_s"):
            line_vs_conc(ax[1], df, "p50_ttft_s", arms, DASHED)
            style_legend(ax[1], "p90", "p50")
        ax[1].set_yscale("log")
        lo, hi = ax[1].get_ylim()
        ax[1].set_ylim(lo, hi * 6)
        style(ax[1], "(b) TTFT (s), log scale")
    if has(df, "turn_slo_share_pct"):
        line_vs_conc(ax[2], df, "turn_slo_share_pct", arms)
        slo = df["ttft_slo_s"].dropna().iloc[0] if has(df, "ttft_slo_s") else None
        ax[2].set_ylim(0, 105)
        style(ax[2], f"(c) Turns with TTFT <= {slo:g} s (%)" if slo else "(c) Turns meeting the SLO (%)")
    arm_legend(fig, arms)
    finalize_figure(fig, out, "fig2-load")


def fig_cache(df, arms, out):
    if not has(df, "gpu_hit_pct", "recompute_pct"):
        return
    fig, ax = plt.subplots(1, 2, figsize=(15, 4.6), gridspec_kw={"width_ratios": [1.6, 1]})
    concs = sorted(df["conc"].unique())
    width = 0.8 / len(arms.order)
    parts = [("gpu_hit_pct", "GPU hit", 1.0), ("cpu_hit_pct", "CPU tier hit", 0.55), ("recompute_pct", "computed", 0.18)]
    parts = [p for p in parts if has(df, p[0]) and df[p[0]].fillna(0).sum() > 0]
    for j, arm in enumerate(arms.order):
        x = np.arange(len(concs)) + (j - (len(arms.order) - 1) / 2) * width
        bottom = np.zeros(len(concs))
        for col, _, alpha in parts:
            v = agg(df[df["arm"] == arm], col).set_index("conc")["mean"].reindex(concs).fillna(0).to_numpy()
            ax[0].bar(x, v, width * 0.95, bottom=bottom, color=arms.color[arm], alpha=alpha, edgecolor="white")
            bottom += v
        if has(df, "theoretical_hit_pct"):
            th = agg(df[df["arm"] == arm], "theoretical_hit_pct").set_index("conc")["mean"].reindex(concs)
            ax[0].scatter(x, th, marker="_", s=250, linewidths=2.5, color="black", zorder=3)
    ax[0].set_xticks(np.arange(len(concs)), [f"c{c}" for c in concs])
    ax[0].set_ylim(0, 128)
    ax[0].set_yticks(range(0, 101, 20))
    shade = [Patch(color="black", alpha=alpha, label=lab) for _, lab, alpha in parts]
    ax[0].legend(handles=shade + [Line2D([], [], color="black", lw=2.5, label="theoretical max hit")],
                 loc="upper center", ncol=len(shade) + 1)
    style(ax[0], "(a) Prompt token source (%)")
    if has(df, "working_set_over_pool_mean"):
        line_vs_conc(ax[1], df, "working_set_over_pool_mean", arms)
        if has(df, "working_set_over_pool_max"):
            line_vs_conc(ax[1], df, "working_set_over_pool_max", arms, DASHED)
            style_legend(ax[1], "mean", "max")
        ax[1].axhline(1, color=PALETTE["red_strong"], ls=":", lw=1.5)
        headroom(ax[1], 1.35)
        style(ax[1], "(b) Working set / GPU KV pool")
    arm_legend(fig, arms)
    finalize_figure(fig, out, "fig3-cache")


def fig_engine(df, arms, out):
    """Why throughput moves, in plain terms (the B / T columns stay in summary.csv)."""
    panels = [("step_time_T_ms", "(a) ms per output token"),
              ("recompute_pct", "(b) Prompt tokens computed (%)"),
              ("engine_request_queue_time_avg_s", "(c) Wait in the vLLM queue (s)"),
              ("waiting_avg_sum", "(d) vLLM waiting requests")]
    panels = [p for p in panels if has(df, p[0])]
    if not panels:
        return
    fig, ax = plt.subplots(1, len(panels), figsize=(4.6 * len(panels), 4.2))
    for a, (col, title) in zip(np.atleast_1d(ax), panels):
        line_vs_conc(a, df, col, arms)
        headroom(a)
        style(a, title)
    arm_legend(fig, arms)
    finalize_figure(fig, out, "fig4-engine")


def fig_gate(df, arms, out):
    if not has(df, "gate_pauses", "duration_s"):
        return
    df = df.copy()
    for c in ("gate_delayed_dispatches", "gate_pauses", "gate_starvation_promotions"):
        if c in df:
            df[c + "_per_h"] = df[c] / df["duration_s"] * 3600
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.4))
    line_vs_conc(ax[0], df, "gate_delayed_dispatches_per_h", arms)
    line_vs_conc(ax[0], df, "gate_pauses_per_h", arms, DASHED)
    style_legend(ax[0], "delayed dispatches", "pauses")
    headroom(ax[0])
    style(ax[0], "(a) Gate events per hour")
    if has(df, "epp_queue_wait_mean_s"):
        line_vs_conc(ax[1], df, "epp_queue_wait_mean_s", arms)
        if has(df, "epp_queue_wait_p99_s"):
            line_vs_conc(ax[1], df, "epp_queue_wait_p99_s", arms, DASHED)
            style_legend(ax[1], "mean", "p99")
        headroom(ax[1])
        style(ax[1], "(b) Wait at the router (s)")
    if has(df, "gate_starvation_promotions_per_h"):
        line_vs_conc(ax[2], df, "gate_starvation_promotions_per_h", arms)
        headroom(ax[2])
        style(ax[2], "(c) Forced admissions per hour")
    arm_legend(fig, arms)
    finalize_figure(fig, out, "fig5-gate")


def ratios(df: pd.DataFrame, arms: Arms, baseline: str, out: Path, window: str) -> None:
    what = "steady state (ss_* columns)" if window == "steady" else "whole profiling window"
    lines = [f"# Each arm against `{baseline}` at the same concurrency", "",
             f"Ratio of means over the {what}. Treat ratios within about 0.95 to 1.05 as ties "
             "(cell-to-cell variance was 2% to 6%).", ""]
    cols = [(c, n) for c, n in RATIO_COLS if c in df]
    base = {c: agg(df[df["arm"] == baseline], c).set_index("conc")["mean"] for c, _ in cols}
    rows = []
    for arm in arms.order:
        if arm == baseline:
            continue
        for conc in sorted(df.loc[df["arm"] == arm, "conc"].unique()):
            r = {"arm": arms.name[arm], "conc": conc}
            for c, n in cols:
                m = agg(df[df["arm"] == arm], c).set_index("conc")["mean"]
                b = base[c].get(conc)
                r[n] = m.get(conc) / b if b else None
            rows.append(r)
    if rows:
        lines.append(pd.DataFrame(rows).to_markdown(index=False, floatfmt=".3f"))
    (out / "ratios.md").write_text("\n".join(lines) + "\n")
    print("wrote", out / "ratios.md")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("summaries", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("report"))
    ap.add_argument("--baseline", help="arm drawn in red and used for ratios.md")
    ap.add_argument("--name", action="append", default=[], help="LABEL=TEXT display name for an arm")
    ap.add_argument("--replicate-suffix", default=r"-r\d+$", help="regex stripped from labels to group replicates")
    ap.add_argument("--window", choices=["steady", "whole"], default="steady",
                    help="steady: ss_* columns (default, like the sweep figures); whole: AgentX whole window")
    args = ap.parse_args()
    df = load(args.summaries, args.replicate_suffix, args.window)
    names = dict(n.split("=", 1) for n in args.name)
    arms = Arms(sorted(df["arm"].unique()), args.baseline, names)
    apply_publication_style()
    for f in (fig_pareto, fig_load, fig_cache, fig_engine, fig_gate):
        f(df, arms, args.out)
    if args.baseline:
        ratios(df, arms, args.baseline, args.out, args.window)


if __name__ == "__main__":
    main()
