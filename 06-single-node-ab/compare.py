#!/usr/bin/env python3
"""Compare the arms of a single-node A/B run.

Usage: compare.py <ab_out_root> [arm ...]   # arm dirs inside the root
Default arms: default tr  (first arm is the baseline for ratios)

Writes <ab_out_root>/comparison.md and comparison.png/.pdf.
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PALETTE = {"blue_main": "#0F4D92", "red_strong": "#B64342", "neutral": "#CFCECE",
           "teal": "#42949E", "green_3": "#8BCF8B", "violet": "#9A4D8E"}
ARM_META = {  # known arm names -> (label, color)
    "default": ("default (pure proxy)", PALETTE["red_strong"]),
    "tr": ("tr (ThunderAgent)", PALETTE["blue_main"]),
    "tr-decay": ("tr + acting decay (no release)", PALETTE["blue_main"]),
    "tr-nodecay": ("tr, no decay (no release)", PALETTE["teal"]),
}
FALLBACK_COLORS = [PALETTE["red_strong"], PALETTE["blue_main"], PALETTE["teal"],
                   PALETTE["violet"], PALETTE["green_3"]]


def arm_meta(name, idx):
    if name in ARM_META:
        return ARM_META[name]
    return name, FALLBACK_COLORS[idx % len(FALLBACK_COLORS)]


def apply_publication_style():
    plt.rcParams.update({
        "font.family": ["DejaVu Sans", "Helvetica", "Arial", "sans-serif"],
        "font.size": 15, "axes.linewidth": 2.0,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "pdf.fonttype": 42, "ps.fonttype": 42,
    })


def load_arm(d):
    with open(d / "summary.json") as f:
        summary = json.load(f)
    with open(d / "metrics-backends.csv") as f:
        backend = list(csv.DictReader(f))
    with open(d / "requests.csv") as f:
        requests = [r for r in csv.DictReader(f) if r["status"] == "200" and r["latency_s"]]
    return {"summary": summary, "backend": backend, "requests": requests}


def stats(arm):
    s, b, reqs = arm["summary"], arm["backend"], arm["requests"]
    lats = np.array([float(r["latency_s"]) for r in reqs])
    lat0 = np.array([float(r["latency_s"]) for r in reqs if r["turn"] == "0"])
    dq = sum(int(r["interval_queries"]) for r in b)
    dh = sum(int(r["interval_hits"]) for r in b)
    return {
        "makespan_s": s["makespan_s"],
        "hit_rate": dh / dq if dq else 0.0,
        "prefilled_mtok": (dq - dh) / 1e6,  # cache-miss tokens = real prefill compute
        "lat_p50": float(np.percentile(lats, 50)),
        "lat_p95": float(np.percentile(lats, 95)),
        "lat_max": float(lats.max()),
        "turn0_p50": float(np.percentile(lat0, 50)),
        "max_paused": s["max_paused_count"],
        "peak_kv": s["peak_kv_cache_usage_perc"],
        "peak_waiting": max(int(r["num_requests_waiting"] or 0) for r in b),
        "ok": f"{s['turns_ok']}/{s['turns_expected']}",
    }


def ts(arm, col):
    rows = arm["backend"]
    t0 = min(float(r["ts"]) for r in rows)
    t, y = [], []
    for r in rows:
        v = r.get(col)
        if v not in (None, ""):
            t.append(float(r["ts"]) - t0)
            y.append(float(v))
    return np.array(t), np.array(y)


def main():
    root = Path(sys.argv[1])
    arm_names = sys.argv[2:] or ["default", "tr"]
    base = arm_names[0]
    arms = {m: load_arm(root / m) for m in arm_names}
    st = {m: stats(a) for m, a in arms.items()}
    labels = {m: arm_meta(m, i)[0] for i, m in enumerate(arm_names)}
    colors = {m: arm_meta(m, i)[1] for i, m in enumerate(arm_names)}

    rows = [
        ("requests ok", "ok", "{}"),
        ("makespan (s)", "makespan_s", "{:.1f}"),
        ("prefix-cache hit rate", "hit_rate", "{:.3f}"),
        ("prefilled (miss) tokens (M)", "prefilled_mtok", "{:.2f}"),
        ("turn latency p50 (s)", "lat_p50", "{:.1f}"),
        ("turn latency p95 (s)", "lat_p95", "{:.1f}"),
        ("turn latency max (s)", "lat_max", "{:.1f}"),
        ("turn-0 latency p50 (s)", "turn0_p50", "{:.1f}"),
        ("max concurrent paused", "max_paused", "{}"),
        ("peak vLLM waiting queue", "peak_waiting", "{}"),
        ("peak KV utilization", "peak_kv", "{:.2f}"),
    ]
    lines = ["# Single-node A/B comparison\n",
             "| metric | " + " | ".join(labels[m] for m in arm_names) + " |",
             "|---" * (len(arm_names) + 1) + "|"]
    for name, key, fmt in rows:
        lines.append(f"| {name} | " + " | ".join(fmt.format(st[m][key]) for m in arm_names) + " |")
    for m in arm_names[1:]:
        r = {k: (st[m][k] / st[base][k] if st[base][k] else float("nan"))
             for k in ("prefilled_mtok", "makespan_s", "lat_p50", "lat_p95")}
        lines.append(f"\n{labels[m]} vs {labels[base]}: prefill {r['prefilled_mtok']:.2f}x, "
                     f"makespan {r['makespan_s']:.2f}x, p50 {r['lat_p50']:.2f}x, "
                     f"p95 {r['lat_p95']:.2f}x (lower is better)")
    lines.append("")
    (root / "comparison.md").write_text("\n".join(lines))
    print("\n".join(lines))

    # ---- figure ----
    apply_publication_style()
    fig, ((ax_hit, ax_q), (ax_lat, ax_bar)) = plt.subplots(2, 2, figsize=(14, 9))

    for m in arm_names:
        t, y = ts(arms[m], "interval_hit_rate")
        ax_hit.plot(t, y, "-o", color=colors[m], linewidth=2.2, markersize=4,
                    alpha=0.85, label=labels[m])
    ax_hit.set_xlabel("Time since first sample (s)")
    ax_hit.set_ylabel("Prefix-cache hit rate\n(per probe interval)")
    ax_hit.set_ylim(-0.03, 1.05)
    ax_hit.set_title("(a) Prefix-cache hit rate", fontsize=15)
    ax_hit.legend(fontsize=10)

    for m in arm_names:
        t, y = ts(arms[m], "num_requests_waiting")
        ax_q.plot(t, y, "-o", color=colors[m], linewidth=2.2, markersize=4,
                  alpha=0.85, label=labels[m])
    ax_q.set_xlabel("Time since first sample (s)")
    ax_q.set_ylabel("vLLM waiting queue depth")
    ax_q.set_title("(b) Engine queue depth", fontsize=15)
    ax_q.legend(fontsize=10)

    turns = sorted({int(r["turn"]) for r in arms[base]["requests"]})
    for m in arm_names:
        med, lo, hi = [], [], []
        for k in turns:
            v = [float(r["latency_s"]) for r in arms[m]["requests"] if int(r["turn"]) == k]
            med.append(np.percentile(v, 50)); lo.append(np.percentile(v, 25)); hi.append(np.percentile(v, 75))
        ax_lat.plot(turns, med, "-o", color=colors[m], linewidth=2.2, markersize=6,
                    label=labels[m])
        ax_lat.fill_between(turns, lo, hi, color=colors[m], alpha=0.13, linewidth=0)
    ax_lat.set_xticks(turns)
    ax_lat.set_xlabel("Turn index")
    ax_lat.set_ylabel("Turn latency (s)\nmedian, IQR band")
    ax_lat.set_title("(c) Per-turn latency", fontsize=15)
    ax_lat.legend(fontsize=10)

    cats = ["prefilled\ntokens", "makespan", "latency\np50", "latency\np95"]
    keys = ["prefilled_mtok", "makespan_s", "lat_p50", "lat_p95"]
    fmts = ["{:.1f}M", "{:.0f}s", "{:.0f}s", "{:.0f}s"]
    x = np.arange(len(cats))
    n = len(arm_names)
    w = 0.8 / n
    for i, m in enumerate(arm_names):
        vals = [st[m][k] / st[base][k] for k in keys]
        bars = ax_bar.bar(x + (i - (n - 1) / 2) * w, vals, w, color=colors[m],
                          edgecolor="black", linewidth=1.2, label=labels[m])
        for rect, k, f in zip(bars, keys, fmts):
            ax_bar.text(rect.get_x() + rect.get_width() / 2, rect.get_height() + 0.02,
                        f.format(st[m][k]), ha="center", va="bottom", fontsize=9)
    ax_bar.axhline(1.0, color="0.5", linestyle=":", linewidth=1.5)
    ax_bar.set_xticks(x, cats, fontsize=12)
    ax_bar.set_ylabel(f"Relative to {arm_names[0]}\n(lower is better)")
    ax_bar.set_title("(d) Summary (absolute values annotated)", fontsize=14)
    ax_bar.legend(fontsize=10)

    n_sess = arms[base]["summary"]["config"]["sessions"]
    fig.suptitle(f"Single vLLM pod, {n_sess} sessions x 3 turns (2.2x KV over-subscription), "
                 f"no program release", fontsize=15, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {})):
        fig.savefig(root / f"comparison.{ext}", bbox_inches="tight", pad_inches=0.06, **kw)
    plt.close(fig)
    print(f"figure: {root}/comparison.png")


if __name__ == "__main__":
    main()
