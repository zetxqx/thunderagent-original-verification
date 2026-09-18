#!/usr/bin/env python3
"""Analysis for step 12: three EPP policies on the whole pool.

Per arm, mean (min-max) over replicates of throughput, requests, hit rates
(pool-wide, from the pods' own counters), TTFT, zero-hit share, errors,
sessions that issued a first request, and (thunder) holds/pauses/resumes.
Ratios are relative to the baseline arm. Also a per-pod table (hit rate and
KV per pod) to show placement behaviour, and a three-bar figure.
Usage: analyze.py <run_dir>
"""
import csv
import glob
import json
import statistics as st
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PALETTE = {"grey": "#767676", "red": "#B64342", "blue": "#0F4D92"}
ARMS = (("epp-baseline", PALETTE["grey"], "baseline\n(llm-d default)"),
        ("epp-affinity", PALETTE["red"], "affinity\n(session pin)"),
        ("epp-thunder", PALETTE["blue"], "thunder\n(port)"))
WARMUP_S = 600


def f(r, k):
    v = r.get(k)
    return float(v) if v not in (None, "") else 0.0


def load_requests(cell):
    p = next((cell / "results" / "report").glob("*per_request_lifecycle*"), None)
    if p is None:
        return []
    out = []
    for e in json.loads(p.read_text()):
        info = e.get("info") or {}
        su = ((info.get("response_metrics") or {}).get("server_usage") or {})
        det = su.get("prompt_tokens_details") or {}
        cm = e.get("computed_metrics") or {}
        out.append({"ok": not e.get("error"), "cached": det.get("cached_tokens"), "out": su.get("completion_tokens"),
                    "ttft": cm.get("time_to_first_token"), "gid": info.get("graph_event_id") or ""})
    return out


def hit_rate(path, lo=0.0, hi=float("inf")):
    if not path.exists():
        return float("nan")
    rows = list(csv.DictReader(open(path)))
    if not rows:
        return float("nan")
    t0 = float(rows[0]["ts"]); q = h = 0
    for r in rows:
        if lo <= float(r["ts"]) - t0 < hi:
            q += int(f(r, "interval_queries")); h += int(f(r, "interval_hits"))
    return h / q if q else float("nan")


def series_mean(path, key, lo=60.0):
    if not path.exists():
        return float("nan")
    rows = list(csv.DictReader(open(path)))
    t0 = float(rows[0]["ts"])
    vals = [f(r, key) for r in rows if float(r["ts"]) - t0 >= lo]
    return st.mean(vals) if vals else float("nan")


def cell_window(cell):
    m = cell / "manifest.json"
    return float(json.loads(m.read_text()).get("window_s") or 2700) if m.exists() else 2700.0


def cell_stats(cell):
    w = cell_window(cell)
    reqs = load_requests(cell); ok = [r for r in reqs if r["ok"]]
    lat = [r["ttft"] for r in ok if r["ttft"]]
    res = cell / "results"
    out = {"requests": len(ok), "errors": len(reqs) - len(ok),
           "throughput": sum(r["out"] or 0 for r in ok) / w,
           "hit_window": hit_rate(res / "vllm-metrics.csv"), "hit_warmup": hit_rate(res / "vllm-metrics.csv", 0, WARMUP_S),
           "hit_steady": hit_rate(res / "vllm-metrics.csv", WARMUP_S),
           "ttft_p50": float(np.percentile(lat, 50)) if lat else float("nan"),
           "ttft_p90": float(np.percentile(lat, 90)) if lat else float("nan"),
           "zero_cache_share": sum(1 for r in ok if r["cached"] == 0) / len(ok) if ok else float("nan"),
           "sessions_started": sum(1 for r in reqs if r["gid"].startswith("event_000_")),
           "inflight": series_mean(res / "vllm-metrics.csv", "num_requests_running"),
           "kv": series_mean(res / "vllm-metrics.csv", "kv_cache_usage_perc"),
           "holds": float("nan"), "pauses": float("nan"), "resumes": float("nan"), "max_paused": float("nan"), "forced": float("nan")}
    e = res / "epp-metrics.csv"
    if e.exists():
        rows = [r for r in csv.DictReader(open(e)) if r.get("pauses_total") not in (None, "")]
        if rows:
            last = rows[-1]
            out.update({"holds": f(last, "holds_paused") + f(last, "holds_new"), "pauses": f(last, "pauses_total"),
                        "resumes": f(last, "resumes_total"), "max_paused": max(f(r, "programs_paused") for r in rows),
                        "forced": f(last, "starvation_promotions_total")})
    # per pod
    out["pods"] = {}
    for p in sorted(res.glob("vllm-metrics-*.csv")):
        pod = p.stem.replace("vllm-metrics-", "")
        out["pods"][pod] = {"hit_steady": hit_rate(p, WARMUP_S), "kv": series_mean(p, "kv_cache_usage_perc"),
                            "inflight": series_mean(p, "num_requests_running")}
    return out


def fmt(vals, spec):
    vals = [v for v in vals if v == v]
    if not vals:
        return "-"
    m = spec.format(st.mean(vals))
    return m if len(vals) == 1 else f"{m} ({spec.format(min(vals))}-{spec.format(max(vals))})"


def main():
    root = Path(sys.argv[1])
    reps = sorted({int(d.name.split("-r")[-1]) for d in root.iterdir() if d.is_dir() and "-r" in d.name and d.name[-1].isdigit()})
    data = {arm: [cell_stats(root / f"{arm}-r{r}") for r in reps if (root / f"{arm}-r{r}" / "results").exists()] for arm, _, _ in ARMS}
    rows = [("throughput (output tok/s)", "throughput", "{:.0f}"), ("requests completed", "requests", "{:.0f}"),
            ("sessions that issued a request", "sessions_started", "{:.0f}"),
            ("hit rate, whole window", "hit_window", "{:.3f}"), ("hit rate, first 10 min", "hit_warmup", "{:.3f}"),
            ("hit rate, after 10 min (STEADY)", "hit_steady", "{:.3f}"),
            ("TTFT p50 (s)", "ttft_p50", "{:.1f}"), ("TTFT p90 (s)", "ttft_p90", "{:.1f}"),
            ("requests with zero cache hit", "zero_cache_share", "{:.2f}"), ("errors", "errors", "{:.0f}"),
            ("pool in-flight requests (mean)", "inflight", "{:.1f}"), ("pool KV usage (mean)", "kv", "{:.2f}"),
            ("EPP holds", "holds", "{:.0f}"), ("EPP pauses", "pauses", "{:.0f}"), ("EPP resumes", "resumes", "{:.0f}"),
            ("EPP max programs paused", "max_paused", "{:.0f}"), ("EPP forced admissions", "forced", "{:.0f}")]
    L = [f"# Step 12: three EPP policies on the 4-pod pool, {len(reps)} replicate(s)\n", "Each cell shows mean (min-max) over replicates; ratios are against the baseline arm.\n",
         "| metric | epp-baseline | epp-affinity | epp-thunder | affinity / baseline | thunder / baseline |", "|---|---|---|---|---|---|"]
    for name, key, spec in rows:
        cols = [[c[key] for c in data[arm]] for arm, _, _ in ARMS]
        def ratio(a, b):
            a = [x for x in a if x == x]; b = [x for x in b if x == x]
            return f"{st.mean(a) / st.mean(b):.2f}x" if a and b and st.mean(b) else "-"
        L.append(f"| {name} | " + " | ".join(fmt(c, spec) for c in cols) + f" | {ratio(cols[1], cols[0])} | {ratio(cols[2], cols[0])} |")
    L.append("")
    L.append("## Per pod (steady-state hit rate / mean KV / mean in flight), first replicate of each arm\n")
    L.append("| pod | " + " | ".join(a for a, _, _ in ARMS) + " |"); L.append("|---|---|---|---|")
    pods = sorted({p for arm in data for c in data[arm][:1] for p in c["pods"]})
    for p in pods:
        cells = []
        for arm, _, _ in ARMS:
            c = data[arm][0]["pods"].get(p) if data[arm] else None
            cells.append(f"{c['hit_steady']:.2f} / {c['kv']:.2f} / {c['inflight']:.0f}" if c else "-")
        L.append(f"| {p} | " + " | ".join(cells) + " |")
    L.append("")
    (root / "analysis.md").write_text("\n".join(L)); print("\n".join(L))

    plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"], "font.size": 13,
                         "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "axes.linewidth": 1.6})
    panels = [("throughput", "Throughput", "output tokens / s", "{:.0f}"), ("hit_steady", "Prefix-cache hit rate", "steady state (after 10 min)", "{:.3f}"),
              ("ttft_p50", "TTFT p50", "seconds", "{:.1f}")]
    fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.4))
    for ax, (key, title, unit, spec) in zip(axes, panels):
        top = 0.0
        for j, (arm, col, _) in enumerate(ARMS):
            vals = np.array([c[key] for c in data[arm] if c[key] == c[key]], dtype=float)
            if not len(vals):
                continue
            m = vals.mean(); top = max(top, vals.max())
            ax.bar(j, m, width=0.62, color=col, alpha=0.2, edgecolor=col, linewidth=1.8, zorder=1)
            ax.vlines(j, vals.min(), vals.max(), color=col, linewidth=1.8, zorder=2)
            jit = np.linspace(-0.13, 0.13, len(vals)) if len(vals) > 1 else np.zeros(1)
            ax.scatter(j + jit, vals, s=55, color=col, edgecolor="white", linewidth=1.0, zorder=3)
            ax.annotate(spec.format(m), (j, vals.max()), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=12, fontweight="bold", color=col)
        ax.set_xticks(range(len(ARMS)), [a[2] for a in ARMS]); ax.set_xlim(-0.6, len(ARMS) - 0.4); ax.set_ylim(0, top * 1.28 if top else 1)
        ax.set_title(title, fontsize=14, fontweight="bold", loc="left"); ax.set_ylabel(unit); ax.tick_params(axis="x", length=0)
    fig.text(0.01, 0.01, f"n = {len(reps)} replicate(s) per arm, c = whole corpus on the 4-pod pool through one EPP. Bar = mean, whisker = min-max, dots = individual runs.", fontsize=10.5, color="#555555")
    fig.tight_layout(rect=(0, 0.05, 1, 1), w_pad=2.5)
    for ext in ("png", "pdf"):
        fig.savefig(root / f"pool.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight", pad_inches=0.06)
    print(f"figure: {root}/pool.png")


if __name__ == "__main__":
    main()
