#!/usr/bin/env python3
"""Step 13 long-window cells: c=128 for 90 minutes, three arms, sliced into 30-minute
windows to see whether the scheduler gains change as sessions deepen.

Per slice and arm: output throughput (tokens of requests that ended in the slice),
prefix-cache hit rate (vLLM interval counters), TTFT p50 and p90, mean prompt tokens
(depth proxy), turns per second, session SLO attainment (strict and lenient, SLO =
TTFT <= 30 s, over sessions with at least one turn in the slice) and the share of
sessions active in the cell so far that completed nothing in the slice.
Usage: analyze_long.py <run_dir> [slice_seconds=1800] [cell_suffix=-c128-w90]
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ARMS = (("epp-baseline", "#B64342", "s", "llm-d default"), ("epp-thunder", "#0F4D92", "o", "most-room"), ("epp-thunder-origin", "#3E9B4F", "^", "origin-only"),
        ("epp-thunder-origin-u15", "#42949E", "D", "origin + urgent 15 s"), ("epp-thunder-origin-u15-f25", "#9A4D8E", "v", "origin + urgent 15 s + forced 25 s"),
        ("epp-thunder-origin-age", "#E9A6A1", "P", "origin + age-only 15 s"), ("epp-thunder-origin-age-reserve", "#FFD700", "X", "origin + age 15 s + reserve"))
SLO_S = 30.0


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))] if v else float("nan")


def vllm_rows(cell):
    """Pool-level vLLM samples with time relative to load onset (first sample with a running request).
    Per-request timestamps are a monotonic clock, not epoch, so slices are aligned on onset."""
    rows = list(csv.DictReader((cell / "results" / "vllm-metrics.csv").open()))
    onset = next((float(r["ts"]) for r in rows if float(r.get("num_requests_running") or 0) > 0), float(rows[0]["ts"]))
    return [(float(r["ts"]) - onset, float(r.get("interval_queries") or 0), float(r.get("interval_hits") or 0)) for r in rows]


def hit_rate(vrows, lo, hi):
    """Token-weighted prefix-cache hit rate over the pool for relative time [lo, hi)."""
    q = sum(x[1] for x in vrows if lo <= x[0] < hi); h = sum(x[2] for x in vrows if lo <= x[0] < hi)
    return h / q if q else float("nan")


def slices(cell, slice_s):
    recs = json.loads((cell / "results" / "report" / "per_request_lifecycle_metrics.json").read_text())
    ok = [r for r in recs if not r.get("error")]
    t0 = min(r["start_time"] for r in recs)
    window_s = float(json.loads((cell / "manifest.json").read_text()).get("window_s", 1800))
    has_sid = "session_id" in recs[0]
    vrows = vllm_rows(cell)
    out = []
    k = 0
    while (k + 1) * slice_s <= window_s + 1:  # only slices fully inside the load window; the drain tail is not a slice
        lo, hi = t0 + k * slice_s, t0 + (k + 1) * slice_s
        done = [r for r in ok if lo <= r["end_time"] < hi]
        if not done:
            break
        tt = [r["computed_metrics"]["time_to_first_token"] for r in done if r.get("computed_metrics")]
        out_tok = sum((r["computed_metrics"] or {}).get("output_tokens") or 0 for r in done)
        prompt = [(r["computed_metrics"] or {}).get("input_tokens") or 0 for r in done]
        row = {"slice": k + 1, "throughput": out_tok / slice_s, "turns_ps": len(done) / slice_s, "ttft_p50": pct(tt, .5), "ttft_p90": pct(tt, .9),
               "prompt_mean": sum(prompt) / len(prompt) if prompt else float("nan"), "hit": hit_rate(vrows, k * slice_s, (k + 1) * slice_s), "requests": len(done)}
        if has_sid:
            # sessions active in the slice: any request (completed or not) overlapping it; a session whose trace
            # finished before the slice is not in the population, a session held through the slice is
            seen = {r["session_id"] for r in recs if r.get("session_id") and r["start_time"] < hi and r["end_time"] >= lo}
            turns, good = {}, {}
            for r in done:
                sid = r.get("session_id"); t = (r.get("computed_metrics") or {}).get("time_to_first_token")
                if not sid or t is None:
                    continue
                turns[sid] = turns.get(sid, 0) + 1; good[sid] = good.get(sid, 0) + (1 if t <= SLO_S else 0)
            active = [s for s in seen if turns.get(s, 0) > 0]
            row.update({"sessions": len(seen), "attain_strict": sum(1 for s in active if good[s] == turns[s]) / len(seen) if seen else float("nan"),
                        "attain_lenient": sum(1 for s in active if good[s] >= 0.95 * turns[s]) / len(seen) if seen else float("nan"),
                        "zero_share": sum(1 for s in seen if turns.get(s, 0) == 0) / len(seen) if seen else float("nan"),
                        "goodput_slo": sum(good.values()) / slice_s})
        out.append(row)
        k += 1
    return out


def main():
    root = Path(sys.argv[1]); slice_s = float(sys.argv[2]) if len(sys.argv) > 2 else 1800.0; suffix = sys.argv[3] if len(sys.argv) > 3 else "-c128-w90"
    data = {}
    for arm, *_ in ARMS:
        cell = root / f"{arm}{suffix}"
        if (cell / "results" / "report").exists():
            data[arm] = slices(cell, slice_s)
    n = max((len(v) for v in data.values()), default=0)
    rows = [("throughput (tok/s)", "throughput", "{:.0f}"), ("prefix-cache hit rate", "hit", "{:.3f}"), ("TTFT p50 (s)", "ttft_p50", "{:.1f}"), ("TTFT p90 (s)", "ttft_p90", "{:.1f}"),
            ("mean prompt tokens", "prompt_mean", "{:.0f}"), ("turns per second", "turns_ps", "{:.2f}"), ("goodput within SLO (turns/s)", "goodput_slo", "{:.2f}"),
            ("session SLO attainment, strict", "attain_strict", "{:.2f}"), ("session SLO attainment, lenient", "attain_lenient", "{:.2f}"), ("sessions active in the slice", "sessions", "{:.0f}"), ("sessions with zero turns in the slice", "zero_share", "{:.2f}")]
    L = [f"# Long window: {suffix.strip('-')} sliced into {slice_s / 60:.0f}-minute windows\n", "Slice 1 is the warm-up-plus-first-half; later slices see deeper sessions (longer prompts). Ratios are of the arms' values within the same slice.\n"]
    for name, key, spec in rows:
        L.append(f"## {name}\n"); L.append("| slice | " + " | ".join(a[3] for a in ARMS if a[0] in data) + " | most-room / default | origin / most-room | u15 / origin | u15-f25 / origin |"); L.append("|---|" + "---|" * (len(data) + 4))
        for k in range(n):
            vals = {arm: data[arm][k].get(key, float("nan")) if k < len(data[arm]) else float("nan") for arm in data}
            def ratio(a, b):
                return f"{vals[a] / vals[b]:.2f}x" if a in vals and b in vals and vals[b] == vals[b] and vals[b] else "-"
            L.append(f"| {k + 1} | " + " | ".join(spec.format(vals[a]) if vals[a] == vals[a] else "-" for a in data) + f" | {ratio('epp-thunder', 'epp-baseline')} | {ratio('epp-thunder-origin', 'epp-thunder')} | {ratio('epp-thunder-origin-u15', 'epp-thunder-origin')} | {ratio('epp-thunder-origin-u15-f25', 'epp-thunder-origin')} |")
        L.append("")
    (root / "long.md").write_text("\n".join(L)); print("\n".join(L[:24]))

    plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"], "font.size": 14, "axes.linewidth": 2, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
    panels = [("throughput", "Throughput", "output tokens / s"), ("hit", "Prefix-cache hit rate", "token-weighted, per slice"), ("ttft_p50", "TTFT p50", "seconds"), ("attain_strict", "Session SLO attainment", f"strict, TTFT <= {SLO_S:.0f} s"), ("prompt_mean", "Mean prompt length", "tokens per request")]
    fig, axes = plt.subplots(1, len(panels) + 1, figsize=(4.3 * len(panels) + 3.2, 4.8), gridspec_kw={"width_ratios": [1] * len(panels) + [0.75]})
    for ax, (key, title, unit) in zip(axes, panels):
        for arm, col, marker, label in ARMS:
            if arm not in data:
                continue
            x = [r["slice"] * slice_s / 60 for r in data[arm]]; y = [r.get(key, float("nan")) for r in data[arm]]
            ax.plot(x, y, color=col, marker=marker, markersize=7, linewidth=2.2, label=label)
        ax.set_title(title, loc="left", fontweight="bold", fontsize=15, pad=20); ax.text(0, 1.02, unit, transform=ax.transAxes, fontsize=11.5, color="0.35", va="bottom")
        ax.set_xlabel("end of slice (min)"); ax.set_xticks([r["slice"] * slice_s / 60 for r in next(iter(data.values()))]); ax.set_ylim(bottom=0)
    h, l = axes[0].get_legend_handles_labels(); axes[-1].set_axis_off(); axes[-1].legend(h, l, loc="center left", fontsize=13)
    fig.text(0.005, 0.005, f"c=128 (32 sessions per pod), one 90-minute cell per arm, values per {slice_s / 60:.0f}-minute slice; session attainment over sessions active in the slice.", fontsize=11, color="0.35")
    fig.tight_layout(pad=1, rect=(0, 0.05, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"long.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig); print(f"figure: {root}/long.png")


if __name__ == "__main__":
    main()
