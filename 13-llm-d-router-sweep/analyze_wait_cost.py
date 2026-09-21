#!/usr/bin/env python3
"""The wait-cost curve: how much of a session's prefix is still cached on its pod
when its next turn is prefilled, as a function of how long the prefix sat idle.

Per turn (after warm-up, turn index >= 1): prefix idle age = time of this turn's
first token minus the end of the session's previous turn (tool gap plus EPP hold
plus vLLM queue plus prefill), cached fraction = vLLM's cached_tokens /
prompt_tokens for this turn. Sessions are joined via session_id (session-id
bench image). Writes wait-cost.md and wait-cost.png in the run directory.
Usage: analyze_wait_cost.py <run_dir> [cell ...]
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ARMS = [("most-room", ["epp-thunder-c128-r2", "epp-thunder-c128-r3"], "#0F4D92", "o"),
        ("origin-only", ["epp-thunder-origin-c128-r2", "epp-thunder-origin-c128-r3"], "#3E9B4F", "^"),
        ("origin + age-only 15 s", ["epp-thunder-origin-age-c128-r2"], "#E9A6A1", "P"),
        ("origin + urgent 15 s (move)", ["epp-thunder-origin-u15-c128-r2", "epp-thunder-origin-u15-c128-r3"], "#42949E", "D"),
        ("origin + wait cap 8 s", ["epp-thunder-origin-w8-c128-r2", "epp-thunder-origin-w8-c128-r3", "epp-thunder-origin-w8-c128-r4"], "#3775BA", "X")]
BINS = [(0, 2), (2, 5), (5, 10), (10, 15), (15, 30), (30, 60), (60, 120), (120, 1e9)]
WARMUP_S = 600.0


def turns(cell):
    recs = json.loads((cell / "results" / "report" / "per_request_lifecycle_metrics.json").read_text())
    t0 = min(r["start_time"] for r in recs)
    by = {}
    for r in recs:
        if r.get("session_id"):
            by.setdefault(r["session_id"], []).append(r)
    out = []
    for sid, rs in by.items():
        rs.sort(key=lambda r: r["start_time"])
        for prev, cur in zip(rs, rs[1:]):
            cm = cur.get("computed_metrics") or {}
            su = ((cur.get("info") or {}).get("response_metrics") or {}).get("server_usage") or {}
            det = su.get("prompt_tokens_details") or {}
            if cur.get("error") or cur["start_time"] < t0 + WARMUP_S or "time_to_first_token" not in cm or not su.get("prompt_tokens"):
                continue
            age = cur["start_time"] + cm["time_to_first_token"] - prev["end_time"]
            out.append((age, det.get("cached_tokens", 0) / su["prompt_tokens"], cm["time_to_first_token"], su["prompt_tokens"]))
    return out


def main():
    root = Path(sys.argv[1])
    data = {}
    for label, cells, col, marker in ARMS:
        rows = []
        for c in cells:
            if (root / c / "results" / "report").exists():
                rows += turns(root / c)
        if rows:
            data[label] = (np.array(rows), col, marker)
    L = ["# Wait cost: cached prefix fraction at the next turn vs how long the prefix sat idle\n",
         "Per turn after warm-up, c=128. Idle age = this turn's first token minus the previous turn's end. Cached fraction = vLLM cached_tokens / prompt_tokens. Re-prefill = prompt tokens not cached.\n"]
    for label, (a, _, _) in data.items():
        L.append(f"## {label} ({len(a)} turns)\n"); L.append("| idle age (s) | turns | share of turns | cached fraction, median | cached fraction, mean | turns with < 50% cached | re-prefill tokens, median | TTFT median (s) |"); L.append("|---|---|---|---|---|---|---|---|")
        for lo, hi in BINS:
            m = (a[:, 0] >= lo) & (a[:, 0] < hi)
            if m.sum() == 0:
                continue
            s = a[m]
            L.append(f"| {lo}-{'' if hi > 1e8 else int(hi)} | {m.sum()} | {m.sum() / len(a):.2f} | {np.median(s[:, 1]):.2f} | {s[:, 1].mean():.2f} | {(s[:, 1] < 0.5).mean():.2f} | {np.median(s[:, 3] * (1 - s[:, 1])):.0f} | {np.median(s[:, 2]):.1f} |")
        L.append("")
    (root / "wait-cost.md").write_text("\n".join(L)); print("\n".join(L))

    plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"], "font.size": 14, "axes.linewidth": 2, "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False})
    fig, axes = plt.subplots(1, 4, figsize=(20, 5), gridspec_kw={"width_ratios": [1, 1, 1, 0.7]})
    centers = [np.sqrt(lo * max(hi if hi < 1e8 else 300, lo + 1)) if lo > 0 else 1.0 for lo, hi in BINS]
    for label, (a, col, marker) in data.items():
        med, share, refill = [], [], []
        for lo, hi in BINS:
            m = (a[:, 0] >= lo) & (a[:, 0] < hi); s = a[m]
            med.append(np.median(s[:, 1]) if m.sum() >= 5 else np.nan); share.append(m.sum() / len(a)); refill.append(np.median(s[:, 3] * (1 - s[:, 1])) / 1000 if m.sum() >= 5 else np.nan)
        axes[0].plot(centers, med, color=col, marker=marker, linewidth=2.2, markersize=7, label=label)
        axes[1].plot(centers, refill, color=col, marker=marker, linewidth=2.2, markersize=7)
        axes[2].plot(centers, share, color=col, marker=marker, linewidth=2.2, markersize=7)
    for ax, (title, unit) in zip(axes, [("Prefix still cached at the next turn", "median cached fraction"), ("Re-prefill at the next turn", "median thousand tokens"), ("Where the turns are", "share of turns per idle-age bin")]):
        ax.set_xscale("log"); ax.set_xticks([1, 3, 7, 12, 21, 42, 85, 190]); ax.set_xticklabels(["0-2", "2-5", "5-10", "10-15", "15-30", "30-60", "60-120", "120+"], fontsize=11)
        ax.set_xlabel("prefix idle age (s): previous turn end to this turn's first token"); ax.set_title(title, loc="left", fontweight="bold", fontsize=15, pad=20); ax.text(0, 1.02, unit, transform=ax.transAxes, fontsize=11.5, color="0.35", va="bottom"); ax.set_ylim(bottom=0)
    axes[0].set_ylim(0, 1.02)
    h, l = axes[0].get_legend_handles_labels(); axes[3].set_axis_off(); axes[3].legend(h, l, loc="center left", fontsize=12)
    fig.text(0.005, 0.005, "c=128 (32 sessions per pod), 30-minute cells with session ids, turns after warm-up. A moved turn under most-room shows up as a low cached fraction at short idle age.", fontsize=11, color="0.35")
    fig.tight_layout(pad=1, rect=(0, 0.05, 1, 1))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"wait-cost.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.06)
    print(f"figure: {root}/wait-cost.png")


if __name__ == "__main__":
    main()
