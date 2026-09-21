#!/usr/bin/env python3
"""Step 13 replicates: most-room vs origin-only at c=96 and c=128, three cells each.

Replicate 1 of each arm and level is the sweep's own cell (<arm>-c<C>), replicates 2
and 3 are <arm>-c<C>-r2 and -r3 from run-origin-replicates.sh. Per-cell statistics
come from step 12's analyzer; on top of them this script adds the session-level
metrics of proposal Part 7 for the cells whose per-request report carries a
session_id (the session-id bench image, i.e. r2 and r3). Writes replicates.md and
replicates.png in the run directory.
Usage: analyze_replicates.py <run_dir>
"""
import csv
import importlib.util
import json
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

spec = importlib.util.spec_from_file_location("pool_analyze", Path(__file__).resolve().parent.parent / "12-llm-d-router-pool" / "analyze.py")
pa = importlib.util.module_from_spec(spec); spec.loader.exec_module(pa)

LEVELS = (96, 128)
PODS = 4
ARMS = (("epp-baseline", "llm-d default"), ("epp-thunder", "most-room"), ("epp-thunder-origin", "origin-only"), ("epp-thunder-origin-u15", "origin + urgent 15 s"), ("epp-thunder-origin-u15-f25", "origin + urgent 15 s + forced 25 s"), ("epp-thunder-origin-age", "origin + age-only 15 s"), ("epp-thunder-origin-age-reserve", "origin + age 15 s + reserve"), ("epp-thunder-origin-w8", "origin + wait cap 8 s"))
RATIOS = (("epp-thunder", "epp-baseline", "most-room / default"), ("epp-thunder-origin", "epp-thunder", "origin / most-room"), ("epp-thunder-origin-u15", "epp-thunder-origin", "u15 / origin"), ("epp-thunder-origin-u15-f25", "epp-thunder-origin", "u15-f25 / origin"), ("epp-thunder-origin-age", "epp-thunder-origin", "age / origin"), ("epp-thunder-origin-age-reserve", "epp-thunder-origin", "age-reserve / origin"), ("epp-thunder-origin-w8", "epp-thunder-origin", "w8 / origin"))
REPS = (1, 2, 3, 4)
WARMUP_S = 600.0
SLO_S = 30.0


def cell_dir(root, arm, c, r):
    return root / (f"{arm}-c{c}" if r == 1 else f"{arm}-c{c}-r{r}")


def epp_last(cell, field):
    f = cell / "results" / "epp-metrics.csv"
    if not f.exists():
        return 0.0
    rows = list(csv.DictReader(f.open()))
    v = rows[-1].get(field) if rows else None
    return float(v) if v not in (None, "") else 0.0


def session_metrics(cell):
    """Part 7 metrics after warm-up, or None when the report has no session ids.
    Population: every session with a request still open or issued after warm-up ended
    (a session held through the whole steady state counts as zero progress; a session
    whose trace finished during warm-up does not count)."""
    recs = json.loads((cell / "results" / "report" / "per_request_lifecycle_metrics.json").read_text())
    if not recs or "session_id" not in recs[0]:
        return None
    t0 = min(r["start_time"] for r in recs)
    warm = t0 + WARMUP_S
    window = max(r["end_time"] for r in recs) - warm
    seen = set(); turns = {}; ok_turns = {}
    for r in recs:
        sid = r.get("session_id")
        if not sid or r["end_time"] < warm:
            continue  # a session whose trace finished before warm-up ended is not in the population
        seen.add(sid)
        if r["start_time"] < warm or r.get("error"):
            continue
        ttft = (r.get("computed_metrics") or {}).get("time_to_first_token")
        if ttft is None:
            continue
        turns[sid] = turns.get(sid, 0) + 1
        ok_turns[sid] = ok_turns.get(sid, 0) + (1 if ttft <= SLO_S else 0)
    n = len(seen)
    total = sum(turns.values()); good = sum(ok_turns.values())
    # the minority view: how slow is a session's worst turn, and how many turns break the SLO at all
    worst = {}
    for r in recs:
        sid = r.get("session_id"); t = (r.get("computed_metrics") or {}).get("time_to_first_token")
        if sid in seen and r["start_time"] >= warm and not r.get("error") and t is not None:
            worst[sid] = max(worst.get(sid, 0.0), t)
    wv = sorted(worst.values())
    strict = sum(1 for s in seen if turns.get(s, 0) > 0 and ok_turns[s] == turns[s]) / n
    lenient = sum(1 for s in seen if turns.get(s, 0) > 0 and ok_turns[s] >= 0.95 * turns[s]) / n
    prog = sorted(turns.get(s, 0) for s in seen)
    q = lambda p: prog[min(len(prog) - 1, int(p * len(prog)))]
    return {"sessions": n, "goodput_slo": good / window if window > 0 else float("nan"), "turns_ps": total / window if window > 0 else float("nan"),
            "attain_strict": strict, "attain_lenient": lenient, "prog_p10": q(0.10), "prog_p50": q(0.50), "prog_p90": q(0.90),
            "zero_share": sum(1 for v in prog if v == 0) / n,
            "slow_turn_share": (total - good) / total if total else float("nan"),
            "worst_ttft_p90": wv[min(len(wv) - 1, int(0.9 * len(wv)))] if wv else float("nan"),
            "worst_over_60": sum(1 for v in wv if v > 60) / n if n else float("nan")}


def cell_stats(cell):
    s = pa.cell_stats(cell)
    s["waiting"] = pa.series_mean(cell / "results" / "vllm-metrics.csv", "num_requests_waiting", WARMUP_S)
    s["rebinds"] = epp_last(cell, "rebinds_total"); s["origin_waits"] = epp_last(cell, "origin_waits_total"); s["urgent"] = epp_last(cell, "urgent_promotions_total")
    sm = session_metrics(cell)
    if sm:
        s.update(sm)
    return s


def fmt(vals, spec):
    vals = [v for v in vals if v == v]
    if not vals:
        return "-"
    if len(vals) == 1:
        return spec.format(vals[0])
    return f"{spec.format(st.mean(vals))} ({spec.format(min(vals))}-{spec.format(max(vals))})"


def main():
    root = Path(sys.argv[1])
    data = {}  # (arm, c) -> {r: stats}
    for arm, _ in ARMS:
        for c in LEVELS:
            for r in REPS:
                d = cell_dir(root, arm, c, r)
                if (d / "results" / "report").exists():
                    data.setdefault((arm, c), {})[r] = cell_stats(d)
    rows = [("throughput (tok/s)", "throughput", "{:.0f}"), ("steady-state hit rate", "hit_steady", "{:.3f}"), ("TTFT p50 (s)", "ttft_p50", "{:.1f}"),
            ("TTFT p90 (s)", "ttft_p90", "{:.1f}"), ("requests completed", "requests", "{:.0f}"), ("waiting inside vLLM", "waiting", "{:.0f}"),
            ("errors", "errors", "{:.0f}"), ("EPP holds", "holds", "{:.0f}"), ("EPP forced admissions", "forced", "{:.0f}"),
            ("EPP rebinds", "rebinds", "{:.0f}"), ("EPP origin waits", "origin_waits", "{:.0f}"), ("EPP urgent promotions", "urgent", "{:.0f}")]
    srows = [("sessions seen", "sessions", "{:.0f}"), (f"goodput within SLO (turns/s with TTFT <= {SLO_S:.0f} s)", "goodput_slo", "{:.2f}"), ("turns/s, all", "turns_ps", "{:.2f}"),
             ("session SLO attainment, strict (all turns)", "attain_strict", "{:.2f}"), ("session SLO attainment, lenient (95% of turns)", "attain_lenient", "{:.2f}"),
             ("turns per session after warm-up, p10", "prog_p10", "{:.0f}"), ("turns per session after warm-up, p50", "prog_p50", "{:.0f}"), ("turns per session after warm-up, p90", "prog_p90", "{:.0f}"),
             ("sessions with zero turns after warm-up", "zero_share", "{:.2f}"),
             (f"share of turns with TTFT > {SLO_S:.0f} s", "slow_turn_share", "{:.3f}"), ("per-session worst TTFT, p90 (s)", "worst_ttft_p90", "{:.0f}"), ("sessions whose worst turn exceeded 60 s", "worst_over_60", "{:.2f}")]
    L = [f"# Step 13 replicates: most-room vs origin-only at c = {', '.join(map(str, LEVELS))}\n",
         "Replicate 1 is the sweep's own cell (thunder-agent-v3 for most-room, v4 for origin-only, old bench image); replicates 2 and 3 are v4 for both arms with the session-id bench image. The llm-d default (baseline) has the sweep cell plus one session-id cell per level. Cells show mean (min-max) over the replicates present; ratio columns are ratios of means, with the range of the per-replicate paired ratios in brackets when both arms share replicate indices.\n"]
    for title, table in (("Cell-level metrics", rows), (f"Session-level metrics (proposal Part 7; only cells with session ids, SLO = TTFT <= {SLO_S:.0f} s, after the 10-minute warm-up)", srows)):
        L.append(f"## {title}\n")
        for name, key, spec_ in table:
            L.append(f"### {name}\n")
            L.append("| c | sessions/pod | n (" + " / ".join(lbl for _, lbl in ARMS) + ") | " + " | ".join(lbl for _, lbl in ARMS) + " | " + " | ".join(lbl for _, _, lbl in RATIOS) + " |")
            L.append("|---|---|---|" + "---|" * (len(ARMS) + len(RATIOS)))
            for c in LEVELS:
                vals = {arm: {r: s_[key] for r, s_ in data.get((arm, c), {}).items() if key in s_} for arm, _ in ARMS}
                cells = [fmt(list(vals[arm].values()), spec_) for arm, _ in ARMS]
                ratios = []
                for num, den, _ in RATIOS:
                    nv, dv = vals[num], vals[den]
                    if nv and dv and st.mean(dv.values()):
                        r_ = f"{st.mean(nv.values()) / st.mean(dv.values()):.2f}x"
                        paired = [nv[r] / dv[r] for r in dv if r in nv and dv[r]]
                        if len(paired) > 1:
                            r_ += f" [{min(paired):.2f}-{max(paired):.2f}]"
                        ratios.append(r_)
                    else:
                        ratios.append("-")
                L.append(f"| {c} | {c // PODS} | " + " / ".join(str(len(vals[arm])) for arm, _ in ARMS) + " | " + " | ".join(cells) + " | " + " | ".join(ratios) + " |")
            L.append("")
    (root / "replicates.md").write_text("\n".join(L)); print("\n".join(L[:30]))

    # figure: grouped bars with min-max whiskers and replicate dots, house style
    plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"], "font.size": 14, "axes.linewidth": 2, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
    COL = {"epp-baseline": "#B64342", "epp-thunder": "#0F4D92", "epp-thunder-origin": "#3E9B4F", "epp-thunder-origin-u15": "#42949E", "epp-thunder-origin-u15-f25": "#9A4D8E", "epp-thunder-origin-age": "#E9A6A1", "epp-thunder-origin-age-reserve": "#FFD700", "epp-thunder-origin-w8": "#3775BA"}
    panels = [("throughput", "Throughput", "output tokens / s"), ("hit_steady", "Prefix-cache hit rate", "steady state"), ("ttft_p50", "TTFT p50", "seconds"), ("attain_strict", "Session SLO attainment", f"strict: every turn TTFT <= {SLO_S:.0f} s")]
    fig, axes = plt.subplots(1, 5, figsize=(23, 5), gridspec_kw={"width_ratios": [1, 1, 1, 1, 0.7]})
    present = [a for a in ARMS if any((a[0], c) in data for c in LEVELS)]
    x = np.arange(len(LEVELS)); w = 0.8 / max(1, len(present))
    for ax, (key, title, unit) in zip(axes, panels):
        for i, (arm, label) in enumerate(present):
            means, lo, hi = [], [], []
            for c in LEVELS:
                vals = [s[key] for s in data.get((arm, c), {}).values() if key in s and s[key] == s[key]]
                means.append(st.mean(vals) if vals else np.nan); lo.append(means[-1] - min(vals) if vals else 0); hi.append(max(vals) - means[-1] if vals else 0)
                for v in vals:
                    ax.plot(x[LEVELS.index(c)] + (i - (len(present) - 1) / 2) * w, v, "o", color="black", markersize=3.5, zorder=4)
            ax.bar(x + (i - (len(present) - 1) / 2) * w, means, w, color=COL[arm], edgecolor="black", linewidth=1.5, label=label, zorder=2)
            ax.errorbar(x + (i - (len(present) - 1) / 2) * w, means, yerr=[lo, hi], fmt="none", ecolor="black", elinewidth=1.5, capsize=4, zorder=3)
        ax.set_title(title, loc="left", fontweight="bold", fontsize=15, pad=20); ax.text(0, 1.02, unit, transform=ax.transAxes, fontsize=11.5, color="0.35", va="bottom")
        ax.set_xticks(x); ax.set_xticklabels([f"{c // PODS} / pod\n(c={c})" for c in LEVELS]); ax.set_ylim(bottom=0)
    h, l = axes[0].get_legend_handles_labels(); axes[4].set_axis_off(); axes[4].legend(h, l, loc="center left", fontsize=13)
    fig.text(0.005, 0.005, "Bars: mean over replicates; whiskers: min to max; dots: individual 30-minute cells. Session SLO attainment uses only the cells whose report carries session ids.", fontsize=11, color="0.35")
    fig.tight_layout(pad=1, rect=(0, 0.05, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"replicates.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig); print(f"figure: {root}/replicates.png")


if __name__ == "__main__":
    main()
