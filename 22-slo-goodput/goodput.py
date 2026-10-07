#!/usr/bin/env python3
"""Step 22: goodput under a TTFT SLO, from the per-request reports of steps 20 and 21.

No new runs. For every cell, the turns that start in the steady state (after the
warm-up, before the window ends) are scored against TTFT SLOs of 2 to 120 s:

  goodput_<X>     output tokens per second generated in the steady state by
                  the turns with TTFT <= X s (counted by token timestamps)
  turn_ok_<X>     share of the steady turns that meet X
  session_ok_<X>  share of the sessions live in the steady state whose every
                  steady turn meets X (a session with no steady turn fails)

A turn with an error counts as a miss. The report keeps a turn only if it ends
within about 120 s after the window, so a turn still waiting then is missing:
it is neither a hit nor a miss. Goodput is not affected (its tokens would come
after the window anyway); the turn and session shares and the TTFT percentiles
are optimistic for arms with long waits.

Writes results/goodput-data.json (cache; delete it to recompute), results/goodput.md
and figures/ (PNG and PDF).
Usage: uv run --with matplotlib --with numpy python goodput.py
"""
import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
STEP20 = HERE.parent / "20-cpu-offload-pool"
STEP21 = HERE.parent / "21-thunder-tier-budget"
CACHE = HERE / "results" / "goodput-data.json"
SLOS = [2, 5, 10, 30, 60, 120]
CDF_X = np.logspace(-1, np.log10(2000), 61)
PCTS = [50, 90, 95, 99]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m20 = load("figs20", STEP20 / "make_figures.py")
m20.OUT = HERE / "figures"
P = m20.PALETTE
# (phase, arm, label, color, line style, marker)
ARMS = [("B", "baseline", "llm-d default (no gate)", P["red_strong"], "-", "o"),
        ("B", "thunder-lease-main", "llm-d-thunder-simplified (GPU tier)", P["blue_main"], "-", "o"),
        ("B", "thunder-lease-main-tier", "llm-d-thunder-simplified (CPU tier)", P["teal"], "-", "o"),
        ("A", "baseline", "llm-d default, offloading off", P["red_strong"], "--", "o"),
        ("A", "thunder-lease-main", "llm-d-thunder-simplified, offloading off", P["blue_main"], "--", "o")]


def cell_goodput(cell, meta):
    recs = json.loads((cell / "results" / "report" / "per_request_lifecycle_metrics.json").read_text())
    t0 = min(r["start_time"] for r in recs)
    warm, end = t0 + meta["warmup_s"], t0 + meta["window_s"]
    steady_s = meta["window_s"] - meta["warmup_s"]
    ttft, steady_toks, live, turns = [], [], set(), {}
    for r in recs:
        sid = r.get("session_id")
        if r["end_time"] >= warm and sid:
            live.add(sid)
        t = None if r.get("error") else (r.get("computed_metrics") or {}).get("time_to_first_token")
        t = float("inf") if t is None else t
        times = ((r.get("info") or {}).get("response_metrics") or {}).get("output_token_times") or []
        # tokens generated in the steady state, by turn: this keeps the turns that started before
        # the steady state, and does not depend on the turns that never finished
        steady_toks.append((t, sum(1 for x in times if warm <= x < end)))
        if warm <= r["start_time"] < end:
            ttft.append(t)
            turns.setdefault(sid, []).append(t)
    ttft = np.array(ttft)
    tt = np.array([t for t, _ in steady_toks])
    tk = np.array([n for _, n in steady_toks], dtype=float)
    s = {"turns": len(ttft), "sessions": len(live), "steady_s": steady_s,
         "throughput_steady": float(tk.sum() / steady_s),
         "cdf": [float(np.mean(ttft <= x)) for x in CDF_X]}
    for p in PCTS:
        s[f"ttft_p{p}"] = float(np.percentile(ttft, p))
    for x in SLOS:
        ok = ttft <= x
        s[f"goodput_{x}"] = float(tk[tt <= x].sum() / steady_s)
        s[f"turn_ok_{x}"] = float(ok.mean())
        s[f"session_ok_{x}"] = sum(1 for sid in live if turns.get(sid) and max(turns[sid]) <= x) / len(live)
    return s


def collect():
    """[{"phase", "arm", "c", "rep", "cell", stats...}] for every cell of steps 20 and 21."""
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    rows = []
    for results in (STEP20 / "results", STEP21 / "results"):
        for run in sorted(results.glob("rep-*")):
            mp = run / "step20.json"
            if not mp.exists():
                continue
            meta = json.loads(mp.read_text())
            for lane, arm in sorted(meta["lane_arms"].items()):
                cell = run / f"epp-{arm}-{lane}"
                if not cell.is_dir():
                    continue
                print("cell", cell.relative_to(HERE.parent), flush=True)
                rows.append({"phase": meta["phase"], "arm": arm, "c": meta["concurrency"], "lane": lane,
                             "rep": meta.get("replicate", 1), "cell": str(cell.relative_to(HERE.parent)),
                             **cell_goodput(cell, meta)})
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(rows, indent=1))
    return rows


def group(rows):
    """{(phase, arm): {c: [rows]}}"""
    g = {}
    for r in rows:
        g.setdefault((r["phase"], r["arm"]), {}).setdefault(r["c"], []).append(r)
    return g


def mean_range(vals, spec):
    if len(vals) == 1:
        return spec.format(vals[0])
    return f"{spec.format(np.mean(vals))} ({spec.format(min(vals))}-{spec.format(max(vals))})"


def capacity(g, key, limit, above):
    """Largest tested c such that the mean meets the limit there and at every smaller tested c."""
    out = {}
    for k, by_c in g.items():
        out[k] = None
        for c in sorted(by_c):
            if (np.mean([r[key] for r in by_c[c]]) >= limit) != above:
                break
            out[k] = c
    return out


def tables(rows):
    g = group(rows)
    order = [(p, a) for p, a, *_ in ARMS] + sorted(k for k in g if k[0] == "T")
    md = ["# Step 22: goodput under a TTFT SLO (generated by goodput.py)", "",
          "Mean (min-max) over the cells of each point. Phase B: 400 GiB CPU tier, 3 runs. "
          "Phase A: offloading off, one run. Phase T: step 21, one run.", ""]
    for title, key, spec in (("Output throughput, steady state (tok/s)", "throughput_steady", "{:.0f}"),
                             ("Goodput, TTFT <= 10 s (tok/s)", "goodput_10", "{:.0f}"),
                             ("Goodput, TTFT <= 30 s (tok/s)", "goodput_30", "{:.0f}"),
                             ("Goodput, TTFT <= 120 s (tok/s)", "goodput_120", "{:.0f}"),
                             ("Turns meeting TTFT <= 30 s", "turn_ok_30", "{:.2f}"),
                             ("Sessions whose every steady turn meets TTFT <= 30 s", "session_ok_30", "{:.2f}"),
                             ("TTFT p90 (s)", "ttft_p90", "{:.1f}"),
                             ("TTFT p99 (s)", "ttft_p99", "{:.0f}")):
        cs = sorted({r["c"] for r in rows})
        md += [f"## {title}", "", "| phase | arm | " + " | ".join(f"c={c}" for c in cs) + " |",
               "|---|---|" + "---|" * len(cs)]
        for k in order:
            if k not in g:
                continue
            md.append(f"| {k[0]} | {k[1]} | " + " | ".join(
                mean_range([r[key] for r in g[k][c]], spec) if c in g[k] else "-" for c in cs) + " |")
        md.append("")
    md += ["## Capacity: largest tested c per replica that meets the target (mean over cells)", "",
           "Tested points: 32, 64, 128, 192, 256 (phase A: 32, 128, 256; phase T: 64 to 256). "
           "\"<\" means even the smallest tested point fails.", "",
           "| phase | arm | " + " | ".join(f"p{p} TTFT <= {x} s" for p, x in ((50, 10), (90, 10), (90, 30), (99, 30), (99, 120)))
           + " | 90% of turns <= 30 s |", "|---|---|---|---|---|---|---|---|"]
    caps = [capacity(g, f"ttft_p{p}", x, False) for p, x in ((50, 10), (90, 10), (90, 30), (99, 30), (99, 120))]
    caps.append(capacity(g, "turn_ok_30", 0.9, True))
    for k in order:
        if k in g:
            md.append(f"| {k[0]} | {k[1]} | " + " | ".join(str(c[k]) if c[k] else "<" for c in caps) + " |")
    (HERE / "results" / "goodput.md").write_text("\n".join(md) + "\n")
    print("wrote", HERE / "results" / "goodput.md")


def lines(ax, g, key, arms=ARMS):
    for phase, arm, _, color, ls, marker in arms:
        if (phase, arm) not in g:
            continue
        c, m, lo, hi = m20.series(g[(phase, arm)], key)
        ax.plot(c, m, color=color, lw=2.4, ls=ls, marker=marker, ms=7, zorder=3,
                mfc="white" if phase == "A" else color)
        ax.vlines(c, lo, hi, color=color, lw=1.8, zorder=2)


def legend(fig, arms=ARMS, ncol=3, y=-0.02):
    h = [Line2D([], [], color=c, lw=2.4, ls=ls, marker=mk, ms=7, mfc="white" if p == "A" else c, label=lab)
         for p, _, lab, c, ls, mk in arms]
    fig.legend(handles=h, loc="lower center", ncol=ncol, fontsize=11.5, bbox_to_anchor=(0.5, y))


def axis(ax):
    m20.c_axis(ax)
    ax.grid(axis="y", color="#E5E5E5", lw=1)
    ax.set_axisbelow(True)


def fig1_goodput(g):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), sharey=True)
    for ax, x, tag in zip(axes, (10, 30, 120), "abc"):
        lines(ax, g, f"goodput_{x}")
        ax.set_title(f"({tag}) TTFT SLO {x} s", loc="left", fontweight="bold", fontsize=14)
        ax.set_ylim(0, 700)
        axis(ax)
    axes[0].set_ylabel("goodput: output tokens/s\nof turns within the SLO")
    legend(fig)
    fig.tight_layout(rect=(0, 0.12, 1, 1))
    m20.finalize_figure(fig, "fig1-goodput")


def fig2_ttft_cdf(g):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), sharey=True)
    arms = [a for a in ARMS if a[0] == "B"]
    for ax, c, tag in zip(axes, (64, 128, 256), "abc"):
        for phase, arm, _, color, ls, _ in arms:
            cells = g.get((phase, arm), {}).get(c, [])
            if cells:
                ax.plot(CDF_X, np.mean([r["cdf"] for r in cells], axis=0), color=color, lw=2.4, ls=ls)
        for x in (10, 30):
            ax.axvline(x, color="#9a9a9a", lw=1, ls=":")
            ax.text(x * 1.08, 0.03, f"{x} s", fontsize=10.5, color="#555555")
        ax.set_xscale("log")
        ax.set_xticks([0.1, 1, 10, 100, 1000], ["0.1 s", "1 s", "10 s", "100 s", "1000 s"])
        ax.minorticks_off()
        ax.set_xlim(0.1, 2000)
        ax.set_ylim(0, 1.02)
        ax.set_xlabel("time to first token")
        ax.set_title(f"({tag}) c = {c} per replica", loc="left", fontweight="bold", fontsize=14)
        ax.grid(color="#E5E5E5", lw=1)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("share of steady-state turns\nwith TTFT <= x")
    legend(fig, arms)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    m20.finalize_figure(fig, "fig2-ttft-cdf")


def fig3_sessions(g):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharey=True)
    for ax, x, tag in zip(axes, (10, 30), "ab"):
        lines(ax, g, f"session_ok_{x}")
        ax.set_title(f"({tag}) every turn of the session within {x} s", loc="left", fontweight="bold", fontsize=14)
        ax.set_ylim(0, 1)
        axis(ax)
    axes[0].set_ylabel("share of sessions live\nin the steady state")
    legend(fig, ncol=2, y=-0.06)
    fig.tight_layout(rect=(0, 0.15, 1, 1))
    m20.finalize_figure(fig, "fig3-sessions")


def main():
    rows = collect()
    tables(rows)
    m20.apply_publication_style()
    g = group(rows)
    fig1_goodput(g)
    fig2_ttft_cdf(g)
    fig3_sessions(g)


if __name__ == "__main__":
    main()
