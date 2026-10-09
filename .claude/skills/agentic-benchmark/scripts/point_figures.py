# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "pyarrow", "matplotlib", "tabulate"]
# ///
"""Per-point and sweep figures for the report, in the house style (figstyle.py).

analyze.py calls draw_point() for every point, and pareto() and concurrency() for the sweep; this
file can also redraw one point on its own:

  uv run point_figures.py <step>/results/<label>/c<N> [--out DIR]

Per point (<results>/<label>/report/c<N>-<label>/), PNG at 300 dpi:
  timeline     client load, vLLM queues, server throughput, TTFT and interactivity
               per minute, KV usage
  cache        working set against the KV pool, prompt token source
  prefill      TTFT in vLLM split into queue wait and prefill; prefill work against
               time per output token
  latency      TTFT CDF with p50/p90/p99, share meeting each TTFT target with a
               table, tok/s/user distribution
  isl-osl      input and output length distributions
  gate         EPP gate events, flow-control queue, gate ledger, queue wait
               (only when the EPP was scraped, MODE=pool)
Sweep (<results>/<label>/report/): pareto, concurrency.
See ../references/figures.md for what each panel is for.
"""

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.patches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("analyze", HERE / "analyze.py")
a23 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(a23)

sys.path.insert(0, str(HERE))
from figstyle import GRID_COLOR, PALETTE, apply_publication_style, finalize_figure, panel_title  # noqa: E402

SERIES_COLORS = [PALETTE["blue_main"], PALETTE["red_strong"], PALETTE["teal"], PALETTE["violet"], PALETTE["green_3"]]
BLUE, RED, TEAL = PALETTE["blue_main"], PALETTE["red_strong"], PALETTE["teal"]
MARK = "#7a7a7a"
IDLE_CAP_S = 300  # agentx preset --trace-idle-gap-cap-seconds


def finalize(fig, out: Path, name: str):
    finalize_figure(fig, out, name)


def panel(ax, title):
    panel_title(ax, title)
    ax.grid(axis="y", color=GRID_COLOR, lw=1)
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


def fig_gate(d, epp, out, bin_s=60):
    t0 = d["t0"] / 1e9
    e = epp[epp["ts"] >= t0 - bin_s].copy()
    if e.empty:
        return
    e["t"] = (e["ts"] - t0) / 60
    gate = a23.GATE

    def rate(metric):
        x = e[e["metric"] == metric].sort_values("ts")
        if x.empty:
            return pd.Series(dtype=float)
        inc = x.groupby(["url", "labels"])["value"].diff().clip(lower=0)
        return inc.groupby((x["t"] * 60 // bin_s).astype(int)).sum().iloc[1:]

    fig, ax = plt.subplots(1, 4, figsize=(21, 4.4))
    a = ax[0]
    colors = iter(SERIES_COLORS)
    for col, names in a23.GATE_COUNTERS.items():
        if not col.startswith("gate_"):
            continue
        r = next((rate(n) for n in names if (e["metric"] == n).any()), pd.Series(dtype=float))
        if len(r):
            a.plot(r.index * bin_s / 60, r.values, color=next(colors), lw=2.0, label=col.removeprefix("gate_").replace("_", " "))
    panel(a, f"(a) Gate events per {bin_s} s")
    minutes(a, d)
    if a.get_legend_handles_labels()[0]:
        top_legend(a, ncol=2)

    a = ax[1]
    qs = e[e["metric"] == "llm_d_epp_flow_control_queue_size"].groupby("t")["value"].sum()
    a.plot(qs.index, qs.values, color=BLUE, lw=2.0)
    panel(a, "(b) EPP queue (requests)")
    minutes(a, d)

    a = ax[2]
    for metric, ls, lab in ((gate + "endpoint_working_set_tokens", "-", "working set"),
                            (gate + "endpoint_capacity_tokens", "--", "capacity")):
        x = e[e["metric"] == metric]
        for i, (labels, s) in enumerate(x.groupby("labels")):
            ep = re.search(r'endpoint="([^"]+)"', labels)
            a.plot(s["t"], s["value"] / 1e6, ls, color=SERIES_COLORS[i % len(SERIES_COLORS)], lw=1.8,
                   label=f"{lab} {ep.group(1).rsplit('/', 1)[-1] if ep else i}")
    panel(a, "(c) Gate ledger per pod (M tokens)")
    minutes(a, d)
    if a.get_legend_handles_labels()[0]:
        top_legend(a, ncol=2, headroom=1.6)

    a = ax[3]
    s = e[e["metric"] == a23.EPP_QUEUE + "_sum"].groupby("ts")["value"].sum().diff()
    c = e[e["metric"] == a23.EPP_QUEUE + "_count"].groupby("ts")["value"].sum().diff()
    w = (s / c.where(c > 0)).dropna()
    a.plot((w.index - t0) / 60, w.values, color=RED, lw=2.0)
    panel(a, "(d) EPP queue wait, mean (s)")
    minutes(a, d)
    finalize(fig, out, "gate")


def draw_point(point: Path, out: Path):
    apply_publication_style()
    d = load(point)
    fig_timeline(d, out)
    fig_cache(d, out)
    fig_prefill(d, out)
    fig_latency(d, out)
    fig_isl_osl(d, out)
    epp_path = point / "epp" / "raw-epp-metrics.txt.gz"
    if epp_path.exists():
        fig_gate(d, a23.load_epp(epp_path), out)


def series_colors(df: pd.DataFrame) -> dict[str, str]:
    """Baseline labels red, the others from the blue family, as in make_figures.py."""
    others = [c for c in SERIES_COLORS if c != PALETTE["red_strong"]]
    colors, i = {}, 0
    for label in dict.fromkeys(df["label"]):
        if "baseline" in label:
            colors[label] = PALETTE["red_strong"]
        else:
            colors[label] = others[i % len(others)]
            i += 1
    return colors


def label_legend(fig, color: dict[str, str]):
    if len(color) > 1:
        fig.legend(handles=[Line2D([], [], color=c, lw=2, marker="o", label=l) for l, c in color.items()],
                   loc="lower center", ncol=len(color), bbox_to_anchor=(0.5, -0.08))


def steady(df: pd.DataFrame) -> pd.DataFrame:
    """Use the steady-state (ss_*) value of every column that has one: the first
    minutes run below c and bias whole-run percentiles (see analyze.py)."""
    df = df.copy()
    for c in [c for c in df.columns if c.startswith("ss_")]:
        base = c.removeprefix("ss_")
        df[base] = df[c].where(df[c].notna(), df.get(base))
    return df


def pareto(df: pd.DataFrame, out: Path, cost: float | None = None):
    """Throughput against latency, one curve per label (AgentX axes): P90 solid
    with filled markers, P50 dashed with hollow markers, same color per label."""
    apply_publication_style()
    df = steady(df)
    charts = [("intvty", "total_tput_per_gpu", "interactivity (tok/s/user)", "Total tok/s/GPU"),
              ("intvty", "output_tput_per_gpu", "interactivity (tok/s/user)", "Output tok/s/GPU"),
              ("ttft_s", "input_tput_per_gpu", "TTFT (s)", "Input tok/s/GPU"),
              ("e2e_norm_intvty", "total_tput_per_gpu", "E2E norm. interactivity", "Total tok/s/GPU")]
    if cost:
        charts.append(("intvty", "total_tokens_per_dollar", "interactivity (tok/s/user)", "Tokens per $"))
    color = series_colors(df)
    fig, axes = plt.subplots(1, len(charts), figsize=(4.6 * len(charts), 4.2))
    for a, letter, (x, y, xlabel, title) in zip(axes, "abcde", charts):
        xs = [f"p50_{x}", f"p90_{x}"]
        for label, c in color.items():
            g = df[df["label"] == label].sort_values("conc")
            a.plot(g[f"p50_{x}"], g[y], color=c, lw=1.6, ls="--", marker="o", ms=6, mfc="white", mew=1.6)
            a.plot(g[f"p90_{x}"], g[y], color=c, lw=2.0, marker="o", ms=6)
            for i, (_, r) in enumerate(g.iterrows()):  # alternate above and below so close points stay readable
                a.annotate(f"c{r['conc']}", (r[f"p90_{x}"], r[y]), fontsize=9, xytext=(5, 5 if i % 2 == 0 else -13),
                           textcoords="offset points")
        a.set_xlabel(xlabel)
        lo, hi = df[xs].min().min(), df[xs].max().max()
        if "ttft" in x:  # spans orders of magnitude once the server saturates
            a.set_xscale("log")
            a.set_xlim(lo / 1.6, hi * 1.6)
        else:
            a.set_xlim(0, hi * 1.25)
        a.set_ylim(0, df[y].max() * 1.25)
        panel(a, f"({letter}) {title}")
    axes[0].legend(handles=[Line2D([], [], color="black", lw=2, marker="o", ms=6, label="P90"),
                            Line2D([], [], color="black", lw=1.6, ls="--", marker="o", ms=6, mfc="white", label="P50")],
                   loc="upper left")
    label_legend(fig, color)
    finalize(fig, out, "pareto")


def concurrency(df: pd.DataFrame, out: Path):
    """Throughput, TTFT and interactivity against concurrency, one line per label."""
    apply_publication_style()
    df = steady(df)
    charts = [(("total_tput_per_gpu",), "Total tok/s/GPU"),
              (("output_tput_per_gpu",), "Output tok/s/GPU"),
              (("p90_ttft_s", "p50_ttft_s"), "TTFT (s)"),
              (("p90_intvty", "p50_intvty"), "Interactivity (tok/s/user)")]
    color = series_colors(df)
    concs = sorted(df["conc"].unique())
    fig, axes = plt.subplots(1, len(charts), figsize=(4.6 * len(charts), 4.2))
    for a, letter, (cols, title) in zip(axes, "abcd", charts):
        for label, c in color.items():
            g = df[df["label"] == label].sort_values("conc")
            for col, ls, mfc in zip(cols, ("-", "--"), (c, "white")):  # p90 solid filled, p50 dashed hollow
                a.plot(g["conc"], g[col], color=c, lw=2.0, ls=ls, marker="o", ms=6, mfc=mfc, mew=1.6)
        a.set_xscale("log", base=2)
        a.set_xticks(concs, [str(c) for c in concs])
        a.minorticks_off()
        a.set_xlim(concs[0] / 1.6, concs[-1] * 1.6)
        if any("ttft" in c for c in cols):
            a.set_yscale("log")
            a.set_ylim(df[list(cols)].min().min() / 2, df[list(cols)].max().max() * 6)
        else:
            a.set_ylim(0, df[list(cols)].max().max() * 1.25)
        a.set_xlabel("concurrency")
        panel(a, f"({letter}) {title}" + (", log scale" if any("ttft" in c for c in cols) else ""))
        if len(cols) == 2:
            a.legend(handles=[Line2D([], [], color="black", lw=2, marker="o", label="p90"),
                              Line2D([], [], color="black", lw=2, ls="--", marker="o", mfc="white", label="p50")],
                     loc="upper left")
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
