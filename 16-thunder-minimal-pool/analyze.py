#!/usr/bin/env python3
"""Step 16 analysis: the minimal thunder-agent on the 4-pod pool, against step 13.

Reference cells at c=128 from the step 13 run (same protocol: one EPP over the
four pods, 30 min, client timeout 1900 s, fixed load generator): llm-d default
(epp-baseline), the v3/v4 port with most-room resume (epp-thunder), and with
origin-only resume (epp-thunder-origin, the minimal plugin's only placement).

Writes <run>/analysis.md (step 15's metrics, the session-level metrics of
proposal Part 7 where the report has session ids, and pod balance), one
raw-metrics-<cell>.md per step 16 cell (every counter and histogram delta,
vLLM summed over the pods), and <run>/timeseries.png.

Usage: analyze.py <step16 run dir> [step13 run dir]
"""
import csv
import glob
import importlib.util
import statistics as st
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s15 = load("step15", HERE.parent / "15-thunder-minimal-single-pod" / "analyze.py")
s13 = load("step13", HERE.parent / "13-llm-d-router-sweep" / "analyze_replicates.py")
WARMUP_S = s15.WARMUP_S
ARMS = [("baseline", "step 13 llm-d default", "epp-baseline-c128*", "#999999"),
        ("mostroom", "step 13 v4 most-room", "epp-thunder-c128*", "#B64342"),
        ("origin", "step 13 v4 origin-only", "epp-thunder-origin-c128*", "#0F4D92"),
        ("min", "step 16 thunder-min (half-life 1 s)", "epp-thunder-min-c128*", "#2E8B57"),
        ("min10", "step 16 thunder-min (half-life 10 s)", "epp-thunder-min-hl10-c128*", "#E08A00"),
        ("min10s1", "step 16 thunder-min (half-life 10 s, sweep 1 s)", "epp-thunder-min-hl10-s1-c128*", "#7B3FA0")]


def cells_for(root, pattern):
    # Only valid cells: voided ones carry a suffix (-PREEMPTED, -SHORTCORPUS, -VOID-*) and 90-minute ones -w90.
    out = []
    for d in sorted(root.glob(pattern)):
        tail = d.name.split("-c128")[-1]
        if d.is_dir() and (d / "results").exists() and tail in ("", "-r2", "-r3"):
            out.append(d)
    return out


def balance(cell):
    """Spread across pods: per-pod steady means, reported as min-max over pods."""
    out = {}
    per = []
    for f in sorted((cell / "results").glob("vllm-metrics-*.csv")):
        rs = s15.rows(f)
        if not rs:
            continue
        t0 = float(rs[0]["ts"])
        ss = [r for r in rs if float(r["ts"]) - t0 >= WARMUP_S]
        kv = [float(r["kv_cache_usage_perc"]) for r in ss if r["kv_cache_usage_perc"]]
        run = [float(r["num_requests_running"]) for r in ss if r["num_requests_running"]]
        q = sum(int(r["interval_queries"] or 0) for r in ss)
        h = sum(int(r["interval_hits"] or 0) for r in ss)
        per.append((st.mean(kv) if kv else np.nan, st.mean(run) if run else np.nan, h / q if q else np.nan))
    if per:
        for i, k in enumerate(("pod_kv", "pod_running", "pod_hit")):
            vals = [p[i] for p in per]
            out[f"{k}_min"], out[f"{k}_max"] = min(vals), max(vals)
    pr = s15.rows(cell / "results" / "epp-pods.csv")
    if pr:
        t0 = float(pr[0]["ts"])
        by = {}
        for r in pr:
            if float(r["ts"]) - t0 >= WARMUP_S and r["working_set_undecayed"] and r["capacity_tokens"]:
                by.setdefault(r["pod"], []).append(float(r["working_set_undecayed"]) / float(r["capacity_tokens"]))
        if by:
            m = [st.mean(v) for v in by.values()]
            out["pod_ws_min"], out["pod_ws_max"] = min(m), max(m)
    return out


def stats(cell):
    s = s15.all_stats(cell)
    s.update(balance(cell))
    try:
        sm = s13.session_metrics(cell)
    except Exception:
        sm = None
    if sm:
        s.update(sm)
    return s


EXTRA_ROWS = [
    ("pod KV usage, steady mean, min-max over pods", ("pod_kv_min", "pod_kv_max"), "{:.2f}"),
    ("pod running requests, steady mean, min-max over pods", ("pod_running_min", "pod_running_max"), "{:.1f}"),
    ("pod steady hit rate, min-max over pods", ("pod_hit_min", "pod_hit_max"), "{:.3f}"),
    ("pod undecayed working set / capacity, min-max over pods", ("pod_ws_min", "pod_ws_max"), "{:.2f}"),
    ("sessions in the steady-state population", "sessions", "{:.0f}"),
    ("goodput within SLO, TTFT <= 30 s (turns/s)", "goodput_slo", "{:.2f}"),
    ("session SLO attainment, strict / lenient", ("attain_strict", "attain_lenient"), "{:.2f}"),
    ("turns per session after warm-up, p10 / p50 / p90", ("prog_p10", "prog_p50", "prog_p90"), "{:.0f}"),
    ("share of turns over the SLO", "slow_turn_share", "{:.3f}"),
    ("per-session worst TTFT, p90 (s)", "worst_ttft_p90", "{:.0f}"),
    ("sessions whose worst turn exceeded 60 s", "worst_over_60", "{:.2f}"),
]


def raw_report(cell):
    """Step 15's raw delta table, vLLM summed over the pool's pods."""
    L = [f"# Raw metric deltas, {cell.name}\n",
         "Every `_total`, `_sum` and `_count` series, summed over labels (and, for vLLM, over the four pods), "
         "last snapshot minus first. Histogram means are sum delta / count delta.\n"]
    vl, span = {}, 0.0
    files = sorted(glob.glob(str(cell / "results" / "raw-vllm-*.txt.gz")))
    for f in files:
        d, sp = s15.raw_counter_deltas(f)
        span = max(span, sp)
        for k, v in d.items():
            vl[k] = vl.get(k, 0.0) + v
    ep, esp = ({}, 0.0)
    if (cell / "results" / "raw-epp-metrics.txt.gz").exists():
        ep, esp = s15.raw_counter_deltas(cell / "results" / "raw-epp-metrics.txt.gz")
    for title, d, sp in ((f"vLLM, {len(files)} pods", vl, span), ("EPP", ep, esp)):
        L.append(f"## {title} ({sp:.0f} s between first and last snapshot)\n")
        L.append("| metric | delta | histogram mean |")
        L.append("|---|---|---|")
        for k, v in sorted(d.items()):
            if v == 0:
                continue
            mean = ""
            if k.endswith("_sum"):
                c = d.get(k[:-4] + "_count", 0)
                mean = f"{v / c:.4g}" if c else ""
            L.append(f"| `{k}` | {v:.6g} | {mean} |")
        L.append("")
    return "\n".join(L)


def main():
    run = Path(sys.argv[1])
    ref = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent / "13-llm-d-router-sweep" / "results" / "sweep-20260918-134248-t1900"
    cells = {}
    for key, _, pattern, _ in ARMS:
        root = run if key.startswith("min") else ref
        cells[key] = cells_for(root, pattern)
    data = {k: [stats(c) for c in cs] for k, cs in cells.items()}
    present = [a for a in ARMS if data[a[0]]]

    L = ["# Step 16: minimal thunder-agent on the 4-pod pool, c=128, against step 13\n",
         f"Step 13 reference: `{ref.name}`. Cells: " +
         "; ".join(f"{label}: {', '.join(c.name for c in cells[k])}" for k, label, _, _ in present) +
         ". Multi-cell columns are mean (min-max). The ratio columns compare each step 16 arm with step 13 origin-only "
         "(same placement policy) and say whether the value lies inside the origin-only min-max range.\n"]
    head = "| metric | " + " | ".join(label for _, label, _, _ in present)
    mins = [k for k, *_ in present if k.startswith("min")]
    head += "".join(f" | {k} / origin" for k in mins) + " |"
    L += [head, "|" + "---|" * (1 + len(present) + len(mins))]
    for row in s15.ROWS + EXTRA_ROWS:
        name, key, spec_ = row[:3]
        scale = row[3] if len(row) > 3 else 1
        line = f"| {name} | " + " | ".join(s15.cellfmt(data[k], key, spec_, scale) for k, *_ in present)
        line += "".join(f" | {s15.ratio(data[k], data['origin'], key)}" for k in mins) + " |"
        L.append(line)
    L.append("")
    (run / "analysis.md").write_text("\n".join(L))
    print("\n".join(L))
    for k in mins:
        for c in cells[k]:
            (run / f"raw-metrics-{c.name}.md").write_text(raw_report(c))
    s15.PALETTE = {k: col for k, _, _, col in ARMS}
    s15.LABELS = {k: label for k, label, _, _ in ARMS}
    s15.timeseries({k: cells[k] for k, *_ in present}, run / "timeseries.png")
    print(f"wrote {run / 'analysis.md'}, raw-metrics-*.md, timeseries.png")


if __name__ == "__main__":
    main()
