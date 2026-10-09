# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "pyarrow", "matplotlib", "tabulate"]
# ///
"""Report figures in the figures4papers publication style of steps 20 to 22.

analyze.py calls draw_point() for every point and pareto() for the sweep; this
file can also redraw one point on its own:

  uv run make_figures.py results/<label>/c<N> [--out DIR]

Per point (results/<label>/report/c<N>-<label>/), PNG at 300 dpi:
  timeline     client load, vLLM queues, server throughput, TTFT and interactivity
               per minute, KV usage (step 20 fig6/7)
  cache        working set against the KV pool, prompt token source (step 20 fig2/fig5)
  prefill      TTFT split into queue wait and prefill; prefill work against time per output token
  latency      TTFT CDF, goodput against the TTFT SLO, interactivity (step 22 fig1-3)
  isl-osl      input and output length distributions
Sweep (results/<label>/report/): pareto, concurrency.
"""

import argparse
import importlib.util
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.patches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("a23", HERE / "analyze.py")
a23 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a23)

PALETTE = {
    "blue_main": "#0F4D92", "blue_secondary": "#3775BA",
    "green_1": "#DDF3DE", "green_2": "#AADCA9", "green_3": "#8BCF8B",
    "red_1": "#F6CFCB", "red_2": "#E9A6A1", "red_strong": "#B64342",
    "neutral": "#CFCECE", "highlight": "#FFD700",
    "teal": "#42949E", "violet": "#9A4D8E",
}
SERIES_COLORS = [PALETTE["blue_main"], PALETTE["red_strong"], PALETTE["teal"], PALETTE["violet"], PALETTE["green_3"]]
BLUE, RED, TEAL = PALETTE["blue_main"], PALETTE["red_strong"], PALETTE["teal"]
GRID, MARK = "#E5E5E5", "#7a7a7a"
IDLE_CAP_S = 300  # agentx preset --trace-idle-gap-cap-seconds


def apply_publication_style(font_size=14, axes_linewidth=2.0):
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans", "Helvetica", "Arial", "sans-serif"],
        "font.size": font_size, "axes.linewidth": axes_linewidth,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.major.width": axes_linewidth * 0.75, "ytick.major.width": axes_linewidth * 0.75,
        "xtick.labelsize": 12, "ytick.labelsize": 12,
        "legend.frameon": False, "legend.fontsize": 10, "pdf.fonttype": 42, "svg.fonttype": "none",
    })


def finalize(fig, out: Path, name: str):
    out.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out / f"{name}.png", dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def panel(ax, title):
    ax.set_title(title, loc="left", fontweight="bold", fontsize=13)
    ax.grid(axis="y", color=GRID, lw=1)
    ax.set_axisbelow(True)


def top_legend(ax, ncol=2, headroom=1.5, handles=None):
    """Leave empty space above the data and put the legend there."""
    lo, hi = ax.get_ylim()
    ax.set_ylim(min(lo, 0), hi * headroom)
    ax.legend(handles=handles, loc="upper center", ncol=ncol, handlelength=1.6, columnspacing=1.2)


def minutes(ax, d):
    ax.set_xlim(0, d["duration"] / 60)
    ax.set_xlabel("minutes")
    ax.axvline(IDLE_CAP_S / 60, color=MARK, lw=1.0, ls=":")


def rolling(y, n):
    k = np.ones(n) / n
    return np.convolve(np.pad(np.asarray(y, float), (n // 2, n - 1 - n // 2), mode="edge"), k, mode="valid")


def load(point: Path) -> dict:
    meta = json.loads((point / "meta" / "point.json").read_text())
    art = point / "aiperf_artifacts"
    pj = json.loads((art / "profile_export_aiperf.json").read_text())
    df = a23.load_records(art / "profile_export.jsonl")
    prof = df[df["phase"] == "profiling"]
    ok = prof[prof["err_type"].isna() & ~prof["cancelled"]].dropna(subset=["start_ns", "end_ns", "lat_s", "osl"])
    t0 = int(ok["start_ns"].min())
    pods = {a23.netloc(u) for u in meta["server_metrics_urls"].split()}
    parquet = art / "server_metrics_export.parquet"
    pq = a23.load_server(parquet, pods)
    pq["t"] = (pq["timestamp_ns"] - t0) / 60e9
    cfg, _ = a23.series(pq, "vllm:cache_config_info")
    sizes = pd.to_numeric(cfg.groupby("pod")["kv_cache_size_tokens"].first(), errors="coerce") if not cfg.empty else []
    steps = a23.engine_step_bins(parquet, pods)
    if not steps.empty:
        steps["t"] = (steps["t_s"] - (t0 - pq["timestamp_ns"].min()) / 1e9) / 60
    itl = (ok["lat_s"] - ok["ttft_s"]) / (ok["osl"] - 1).where(ok["osl"] > 1)
    return {
        "meta": meta, "ok": ok.assign(intv=1 / itl), "errors": int(prof["err_type"].notna().sum()), "t0": t0,
        "duration": (ok["end_ns"].max() - t0) / 1e9, "pq": pq,
        "pool": int(sizes.sum()) if len(sizes) and sizes.notna().all() else None,
        "fl": a23.inflight(ok, t0), "steps": steps,
        "theoretical": a23.metric(pj, "theoretical_prefix_cache_hit"),
    }


def gauge_lines(ax, pq, name, color, label, scale=1.0, n=30):
    s, _ = a23.series(pq, name)
    for i, (_, x) in enumerate(s.sort_values("timestamp_ns").groupby("pod")):
        ax.plot(x["t"], scale * rolling(x["value"], n), color=color, lw=2.0, label=label if i == 0 else None)


def counter_rate(pq, name, bin_s=30, by=None):
    """Per-bin increase of a counter, summed over pods: index = bin start (minutes)."""
    c, _ = a23.series(pq, name)
    if c.empty:
        return pd.DataFrame()
    c = c.copy()
    c["b"] = (c["t"] * 60 // bin_s).astype(int)
    keys = ["pod"] + ([by] if by else [])
    last = c.sort_values("timestamp_ns").groupby([*keys, "b"])["value"].last()
    inc = last.groupby(level=keys).diff().fillna(last).clip(lower=0)
    out = inc.groupby(level=([by] if by else []) + ["b"]).sum()
    out = out.unstack(0) if by else out.to_frame("value")
    out.index = out.index * bin_s / 60
    return out


def fig_timeline(d, out):
    ok, fl, pq = d["ok"], d["fl"], d["pq"]
    fig, ax = plt.subplots(2, 3, figsize=(17, 8.2), sharex=True)

    a = ax[0, 0]
    a.plot(fl["t"] / 60, rolling(fl["requests"], 6), color=BLUE, lw=2.0, label="requests")
    a.plot(fl["t"] / 60, rolling(fl["sessions"], 6), color=TEAL, lw=2.0, label="sessions")
    a.axhline(d["meta"]["concurrency"], color=RED, lw=1.5, ls="--", label=f"c = {d['meta']['concurrency']}")
    panel(a, "(a) In flight (client)")
    top_legend(a, ncol=3)

    a = ax[0, 1]
    gauge_lines(a, pq, "vllm:num_requests_running", BLUE, "running")
    gauge_lines(a, pq, "vllm:num_requests_waiting", RED, "waiting")
    panel(a, "(b) vLLM requests")
    top_legend(a)

    a = ax[0, 2]
    inp = counter_rate(pq, "vllm:prompt_tokens")
    outp = counter_rate(pq, "vllm:generation_tokens")
    a.plot(inp.index, inp["value"] / 30 / 1e3, color=BLUE, lw=2.0, label="input (k tok/s)")
    a.plot(outp.index, outp["value"] / 30 / 1e2, color=RED, lw=2.0, label="output (100 tok/s)")
    panel(a, "(c) Server throughput")
    top_legend(a)

    b = (((ok["end_ns"] - d["t0"]) / 60e9) // 1).astype(int)
    g = ok.groupby(b)
    a = ax[1, 0]
    a.plot(g["ttft_s"].quantile(0.5).index + 0.5, g["ttft_s"].quantile(0.5), color=BLUE, lw=2.0, marker="o", ms=4, label="p50")
    a.plot(g["ttft_s"].quantile(0.9).index + 0.5, g["ttft_s"].quantile(0.9), color=RED, lw=2.0, marker="o", ms=4, label="p90")
    panel(a, "(d) TTFT (s), per minute")
    top_legend(a)

    a = ax[1, 1]
    a.plot(g["intv"].quantile(0.5).index + 0.5, g["intv"].quantile(0.5), color=BLUE, lw=2.0, marker="o", ms=4, label="p50")
    a.plot(g["intv"].quantile(0.10).index + 0.5, g["intv"].quantile(0.10), color=RED, lw=2.0, marker="o", ms=4, label="p90")
    panel(a, "(e) Interactivity (tok/s/user), per minute")
    top_legend(a)

    a = ax[1, 2]
    gauge_lines(a, pq, "vllm:kv_cache_usage_perc", BLUE, "KV usage", scale=100)
    a.set_ylim(0, 105)
    panel(a, "(f) vLLM KV cache usage (%)")

    for a in ax.flat:
        minutes(a, d)
    for a in ax[0]:
        a.set_xlabel("")
    finalize(fig, out, "timeline")


def fig_cache(d, out, bin_s=60):
    fl = d["fl"]
    fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.4))
    a = ax[0]
    a.plot(fl["t"] / 60, fl["working_set"] / 1e6, color=BLUE, lw=2.0, label="working set")
    a.plot(fl["t"] / 60, rolling(fl["unique_tokens"], 6) / 1e6, color=TEAL, lw=1.8, label="in flight")
    if d["pool"]:
        a.axhline(d["pool"] / 1e6, color=RED, lw=1.5, ls="--", label="KV pool")
    panel(a, "(a) Context tokens (M)")
    minutes(a, d)
    top_legend(a, ncol=3, headroom=1.35)

    a = ax[1]
    src = counter_rate(d["pq"], "vllm:prompt_tokens_by_source", bin_s=bin_s, by="source").fillna(0)
    share = 100 * src.div(src.sum(axis=1).replace(0, np.nan), axis=0)
    stack = [(k, lab, c) for k, lab, c in (("local_cache_hit", "GPU hit", BLUE),
                                            ("external_kv_transfer", "CPU tier", TEAL),
                                            ("local_compute", "computed", PALETTE["red_2"]))
             if k in share and share[k].sum() > 0]
    a.stackplot(share.index + bin_s / 120, *[share[k] for k, _, _ in stack],
                labels=[lab for _, lab, _ in stack], colors=[c for *_, c in stack], lw=0)
    if d["theoretical"] is not None:
        a.axhline(d["theoretical"], color="black", lw=1.4, ls="--", label="theoretical")
    a.set_ylim(0, 122)
    a.set_yticks(range(0, 101, 20))
    panel(a, "(b) Prompt token source (%)")
    minutes(a, d)
    a.legend(loc="upper center", ncol=len(stack) + 1)
    finalize(fig, out, "cache")


def hist_mean_per_bin(pq, name, bin_s=60):
    """Mean of a vLLM histogram per bin (sum delta / count delta over pods), index = bin start (minutes)."""
    h, _ = a23.series(pq, name)
    if h.empty:
        return pd.Series(dtype=float)
    h = h.copy()
    h["t"] = (h["timestamp_ns"] - pq["timestamp_ns"].min()) / 60e9 + pq["t"].min()
    h["b"] = (h["t"] * 60 // bin_s).astype(int)
    last = h.sort_values("timestamp_ns").groupby(["pod", "b"])[["sum", "count"]].last()
    inc = last.groupby(level="pod").diff().fillna(last).clip(lower=0).groupby(level="b").sum()
    mean = inc["sum"] / inc["count"].replace(0, np.nan)
    mean.index = mean.index * bin_s / 60
    return mean


def fig_prefill(d, out, bin_s=60):
    """Where the wait for the first token goes, and how prefill work slows every decoding request."""
    fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.4))
    a = ax[0]
    queue = hist_mean_per_bin(d["pq"], "vllm:request_queue_time_seconds", bin_s)
    prefill = hist_mean_per_bin(d["pq"], "vllm:request_prefill_time_seconds", bin_s).reindex(queue.index)
    x = queue.index + bin_s / 120
    a.bar(x, queue.fillna(0), width=0.8 * bin_s / 60, color=RED, label="waiting in queue")
    a.bar(x, prefill.fillna(0), width=0.8 * bin_s / 60, bottom=queue.fillna(0), color=BLUE, label="prefill")
    panel(a, "(a) Time to first token in vLLM (s)")
    minutes(a, d)
    top_legend(a, headroom=1.3)

    a = ax[1]
    computed = counter_rate(d["pq"], "vllm:prompt_tokens_by_source", bin_s=bin_s, by="source")
    if "local_compute" in computed:
        a.bar(computed.index + bin_s / 120, computed["local_compute"] / bin_s / 1e3, width=0.8 * bin_s / 60,
              color=PALETTE["red_2"], label="prefill computed (k tok/s)")
    st = d["steps"]
    if not st.empty:
        st = st[~st["impossible"]].copy()
        st["m"] = (st["t"] * 60 // bin_s).astype(int)
        per_min = st.groupby("m").agg(n=("steps", "size"), steps=("steps", "sum"))
        ms_per_token = 10_000 * per_min["n"] / per_min["steps"]  # busy 10 s bins / steps
        a2 = a.twinx()
        a2.spines["right"].set_visible(True)
        a2.plot(per_min.index * bin_s / 60 + bin_s / 120, ms_per_token, color=BLUE, lw=2.2, marker="o", ms=4)
        a2.set_ylim(0, ms_per_token.max() * 1.3)
        a2.set_ylabel("ms per output token", color=BLUE)
    panel(a, "(b) Prefill work and decode speed")
    minutes(a, d)
    top_legend(a, headroom=1.3, handles=[
        matplotlib.patches.Patch(color=PALETTE["red_2"], label="prefill computed (k tok/s)"),
        Line2D([], [], color=BLUE, lw=2.2, marker="o", ms=4, label="ms per output token")])
    finalize(fig, out, "prefill")


def cdf(ax, values, color, label, ls="-"):
    v = np.sort(np.asarray(values, float))
    ax.plot(v, 100 * np.arange(1, len(v) + 1) / len(v), color=color, lw=2.2, ls=ls, label=label)


def fig_latency(d, out):
    ok = d["ok"]
    worst = ok.groupby("root")["ttft_s"].max()
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.6))
    a = ax[0]
    cdf(a, ok["ttft_s"], BLUE, "per turn")
    cdf(a, worst, RED, "worst turn per session", ls="--")
    for q, dx, dy, ha in ((50, 8, -4, "left"), (90, 8, -12, "left"), (99, -10, -18, "right")):
        v = np.percentile(ok["ttft_s"], q)
        a.plot(v, q, "o", color=BLUE, ms=7, zorder=5)
        a.annotate(f"p{q} {v:.2f} s", (v, q), xytext=(dx, dy), textcoords="offset points", fontsize=10,
                   color=BLUE, ha=ha)
    a.set_xscale("log")
    a.set_ylim(0, 101)
    a.set_xlabel("time to first token (s, log scale)")
    a.set_ylabel("% of turns at or below")
    panel(a, "(a) TTFT distribution")
    a.legend(loc="upper left")

    a = ax[1]
    targets = np.geomspace(0.1, 300, 150)
    turns = [100 * (ok["ttft_s"] <= x).sum() / max(len(ok) + d["errors"], 1) for x in targets]
    tokens = [100 * ok.loc[ok["ttft_s"] <= x, "osl"].sum() / ok["osl"].sum() for x in targets]
    a.plot(targets, turns, color=BLUE, lw=2.2, label="% of turns")
    a.plot(targets, tokens, color=TEAL, lw=2.0, ls="--", label="% of output tokens (goodput)")
    rows = []
    for x in (0.5, 1, 2, 5, 10):
        t = 100 * (ok["ttft_s"] <= x).sum() / max(len(ok) + d["errors"], 1)
        g = 100 * ok.loc[ok["ttft_s"] <= x, "osl"].sum() / ok["osl"].sum()
        a.plot(x, t, "o", color=BLUE, ms=6, zorder=5)
        a.plot(x, g, "o", color=TEAL, ms=6, zorder=5)
        rows.append((f"{x:g} s", f"{t:.0f}%", f"{g:.0f}%"))
    table = a.table(cellText=rows, colLabels=["target", "turns", "goodput"], loc="lower right",
                    bbox=(0.46, 0.03, 0.52, 0.40), edges="open", cellLoc="right", colLoc="right")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.set_zorder(10)
    for (r, c), cell in table.get_celld().items():
        cell.set_facecolor("white")
        cell.get_text().set_color({1: BLUE, 2: TEAL}.get(c, "black"))
        if r == 0:
            cell.get_text().set_fontweight("bold")
    a.set_xscale("log")
    a.set_ylim(0, 101)
    a.set_xlabel("TTFT target, SLO (s, log scale)")
    a.set_ylabel("% meeting the target")
    panel(a, "(b) Share meeting a TTFT target")
    a.legend(loc="center right", bbox_to_anchor=(1.0, 0.62))

    a = ax[2]
    iv = ok["intv"].dropna()
    hi = np.percentile(iv, 99)
    a.hist(iv[iv <= hi], bins=50, weights=np.full((iv <= hi).sum(), 100 / len(iv)),
           color=PALETTE["blue_secondary"], alpha=0.85)
    # p90 = the slowest 10% of requests (AgentX convention), i.e. the 10th percentile of tok/s
    for q, lab, color in ((50, "p50", TEAL), (10, "p90", RED), (1, "p99", PALETTE["violet"])):
        v = np.percentile(iv, q)
        a.axvline(v, color=color, lw=2.0, ls="--", label=f"{lab} {v:.1f} tok/s/user")
    a.set_xlabel("tok/s/user")
    a.set_ylabel("% of requests")
    panel(a, "(c) Output speed per user")
    a.legend(loc="upper right")
    finalize(fig, out, "latency")


def fig_isl_osl(d, out):
    ok = d["ok"]
    fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.0))
    for a, col, scale, title, xlabel, log, unit in (
            (ax[0], "isl", 1e3, "(a) Input length per request", "input tokens (k)", False, "k tokens"),
            (ax[1], "osl", 1.0, "(b) Output length per request", "output tokens (log scale)", True, "tokens")):
        v = ok[col] / scale
        bins = np.geomspace(max(v.min(), 1), v.max(), 50) if log else 50
        a.hist(v, bins=bins, color=PALETTE["blue_secondary"], alpha=0.85)
        if log:
            a.set_xscale("log")
        a.axvline(v.median(), color=RED, lw=2.0, ls="--", label=f"median {v.median():.0f} {unit}")
        a.set_xlabel(xlabel)
        a.set_ylabel("number of requests")
        panel(a, title)
        a.legend(loc="upper right")
    finalize(fig, out, "isl-osl")


def draw_point(point: Path, out: Path):
    apply_publication_style()
    d = load(point)
    fig_timeline(d, out)
    fig_cache(d, out)
    fig_prefill(d, out)
    fig_latency(d, out)
    fig_isl_osl(d, out)


def series_colors(df: pd.DataFrame) -> dict[str, str]:
    return {label: SERIES_COLORS[i % len(SERIES_COLORS)] for i, label in enumerate(dict.fromkeys(df["label"]))}


def label_legend(fig, color: dict[str, str]):
    if len(color) > 1:
        fig.legend(handles=[Line2D([], [], color=c, lw=2, marker="o", label=l) for l, c in color.items()],
                   loc="lower center", ncol=len(color), bbox_to_anchor=(0.5, -0.08))


def pareto(df: pd.DataFrame, out: Path, cost: float | None = None):
    """Throughput against latency, one curve per label (AgentX axes)."""
    apply_publication_style()
    charts = [("p90_intvty", "total_tput_per_gpu", "P90 interactivity (tok/s/user)", "Total tok/s/GPU"),
              ("p90_intvty", "output_tput_per_gpu", "P90 interactivity (tok/s/user)", "Output tok/s/GPU"),
              ("p90_ttft_s", "input_tput_per_gpu", "P90 TTFT (s)", "Input tok/s/GPU"),
              ("p90_e2e_norm_intvty", "total_tput_per_gpu", "P90 E2E norm. interactivity", "Total tok/s/GPU")]
    if cost:
        charts.append(("p90_intvty", "total_tokens_per_dollar", "P90 interactivity (tok/s/user)", "Tokens per $"))
    color = series_colors(df)
    fig, axes = plt.subplots(1, len(charts), figsize=(4.6 * len(charts), 4.2))
    for a, letter, (x, y, xlabel, title) in zip(axes, "abcde", charts):
        for label, c in color.items():
            g = df[df["label"] == label].sort_values("conc")
            a.plot(g[x], g[y], color=c, lw=2.0, marker="o", ms=6)
            for _, r in g.iterrows():
                a.annotate(f"c{r['conc']}", (r[x], r[y]), fontsize=9, xytext=(4, 4), textcoords="offset points")
        a.set_xlabel(xlabel)
        a.set_xlim(0, df[x].max() * 1.25)
        a.set_ylim(0, df[y].max() * 1.2)
        panel(a, f"({letter}) {title}")
    label_legend(fig, color)
    finalize(fig, out, "pareto")


def concurrency(df: pd.DataFrame, out: Path):
    """Throughput, TTFT and interactivity against concurrency, one line per label."""
    apply_publication_style()
    charts = [(("total_tput_per_gpu",), "Total tok/s/GPU"),
              (("output_tput_per_gpu",), "Output tok/s/GPU"),
              (("p50_ttft_s", "p90_ttft_s"), "TTFT (s)"),
              (("p50_intvty", "p90_intvty"), "Interactivity (tok/s/user)")]
    color = series_colors(df)
    concs = sorted(df["conc"].unique())
    fig, axes = plt.subplots(1, len(charts), figsize=(4.6 * len(charts), 4.2))
    for a, letter, (cols, title) in zip(axes, "abcd", charts):
        for label, c in color.items():
            g = df[df["label"] == label].sort_values("conc")
            for col, ls in zip(cols, ("-", "--")):
                a.plot(g["conc"], g[col], color=c, lw=2.0, ls=ls, marker="o", ms=6)
        a.set_xscale("log", base=2)
        a.set_xticks(concs, [str(c) for c in concs])
        a.minorticks_off()
        a.set_xlim(concs[0] / 1.6, concs[-1] * 1.6)
        a.set_ylim(0, df[list(cols)].max().max() * 1.25)
        a.set_xlabel("concurrency")
        panel(a, f"({letter}) {title}")
        if len(cols) == 2:
            a.legend(handles=[Line2D([], [], color="black", lw=2, ls="-", label="p50"),
                              Line2D([], [], color="black", lw=2, ls="--", label="p90")], loc="upper left")
    label_legend(fig, color)
    finalize(fig, out, "concurrency")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("point", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="default: <label>/report/c<N>-<label>")
    args = ap.parse_args()
    meta = json.loads((args.point / "meta" / "point.json").read_text())
    out = args.out or args.point.parent / "report" / f"c{meta['concurrency']}-{meta['label']}"
    draw_point(args.point, out)
    print("wrote", out)


if __name__ == "__main__":
    main()
