#!/usr/bin/env python3
"""Step 15 analysis: the minimal thunder-agent (one lane) against step 10.

Puts the step 15 cell(s) next to step 10's three epp-thunder cells (the
benchmarked v3 port) and three epp-sticky cells (no admission control), all
at the same protocol: one EPP on one vLLM pod, c=128, 45 min, client timeout
1900 s, inference-perf v0.7.0, base seed 20260915.

Writes <run>/analysis.md (all metrics the cells share, mean (min-max) for the
step 10 arms), <run>/raw-metrics.md (every counter and histogram delta in the
raw vLLM and EPP scrapes of the step 15 cell, which only this step records),
and <run>/timeseries.png.

Usage: analyze.py <step15 run dir> [step10 run dir]
"""
import csv
import gzip
import importlib.util
import json
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
STEP10 = HERE.parent / "10-llm-d-router-replicates"
spec = importlib.util.spec_from_file_location("step10", STEP10 / "analyze.py")
step10 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step10)
WARMUP_S = step10.WARMUP_S
PALETTE = {"sticky": "#B64342", "v3": "#0F4D92", "min": "#2E8B57"}


def rows(path):
    return list(csv.DictReader(open(path))) if path.exists() else []


def num(r, k):
    v = r.get(k)
    return float(v) if v not in (None, "") else None


def pct(vals, q):
    return float(np.percentile(vals, q)) if vals else float("nan")


def series_stats(cell):
    """Means and peaks of the prober series, whole window and steady state."""
    out = {}
    vr = rows(cell / "results" / "vllm-metrics.csv")
    if vr:
        t0 = float(vr[0]["ts"])
        for key, col in (("kv", "kv_cache_usage_perc"), ("running", "num_requests_running"),
                         ("waiting", "num_requests_waiting")):
            allv = [num(r, col) for r in vr if num(r, col) is not None]
            ssv = [num(r, col) for r in vr if num(r, col) is not None and float(r["ts"]) - t0 >= WARMUP_S]
            out[f"{key}_mean"] = st.mean(allv) if allv else float("nan")
            out[f"{key}_mean_steady"] = st.mean(ssv) if ssv else float("nan")
            out[f"{key}_max"] = max(allv) if allv else float("nan")
        pre = [num(r, "num_preemptions_total") for r in vr if num(r, "num_preemptions_total") is not None]
        out["preemptions"] = pre[-1] - pre[0] if pre else float("nan")
    er = rows(cell / "results" / "epp-metrics.csv")
    if er:
        t0 = float(er[0]["ts"])
        last = er[-1]
        for st_ in ("running", "idle", "paused"):
            v = [num(r, f"programs_{st_}") for r in er if num(r, f"programs_{st_}") is not None]
            out[f"programs_{st_}_mean"] = st.mean(v) if v else float("nan")
        for cls in ("reasoning", "paused", "new"):
            out[f"holds_{cls}"] = num(last, f"holds_{cls}") or 0.0
            out[f"releases_{cls}"] = num(last, f"releases_{cls}") or 0.0
        ws = [(float(r["ts"]) - t0, num(r, "working_set_undecayed"), num(r, "working_set_decayed"), num(r, "capacity_tokens"))
              for r in er if num(r, "working_set_undecayed") is not None]
        if ws:
            cap = ws[-1][3] or float("nan")
            out["ws_undecayed_mean_steady"] = st.mean(w[1] for w in ws if w[0] >= WARMUP_S) / cap
            out["ws_decayed_mean_steady"] = st.mean(w[2] for w in ws if w[0] >= WARMUP_S) / cap
            out["ws_over_capacity_share"] = sum(1 for w in ws if w[1] > cap) / len(ws)
        else:  # v3 exported the undecayed utilization (plus 100-token buffers) as a ratio
            u = [(float(r["ts"]) - t0, num(r, "pod_utilization")) for r in er if num(r, "pod_utilization") is not None]
            if u:
                out["ws_undecayed_mean_steady"] = st.mean(x[1] for x in u if x[0] >= WARMUP_S)
                out["ws_over_capacity_share"] = sum(1 for x in u if x[1] > 1.0) / len(u)
    cpu = rows(cell / "cpu-usage.csv") if (cell / "cpu-usage.csv").exists() else []
    if cpu:
        text = (cell / "cpu-usage.csv").read_text().splitlines()
        epp = [int(l.split(",")[2].rstrip("m")) / 1000 for l in text if "-epp-" in l.split(",")[1]]
        out["epp_cpu_mean"] = st.mean(epp) if epp else float("nan")
        out["epp_cpu_max"] = max(epp) if epp else float("nan")
    return out


def request_stats(cell):
    """Latency percentiles and token totals from the per-request report."""
    path = next((cell / "results" / "report").glob("*per_request_lifecycle*"), None)
    out = {}
    if path is None:
        return out
    ok = [e for e in json.loads(path.read_text()) if not e.get("error")]
    cm = lambda k: [e["computed_metrics"][k] for e in ok if (e.get("computed_metrics") or {}).get(k) is not None]
    for key, name in (("request_latency", "e2e"), ("time_per_output_token", "tpot"), ("inter_token_latency", "itl")):
        v = cm(key)
        out[f"{name}_p50"], out[f"{name}_p90"], out[f"{name}_p99"] = pct(v, 50), pct(v, 90), pct(v, 99)
    prompt = cached = 0
    for e in ok:
        su = ((e.get("info") or {}).get("response_metrics") or {}).get("server_usage") or {}
        prompt += su.get("prompt_tokens") or 0
        cached += (su.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    out["prompt_tokens_mean"] = prompt / len(ok) if ok else float("nan")
    out["prefill_tokens_total"] = float(prompt - cached)
    out["cached_tokens_total"] = float(cached)
    return out


def session_stats(cell):
    p = next((cell / "results" / "report").glob("stage_0_session_lifecycle*"), None)
    if p is None:
        return {}
    s = json.loads(p.read_text())
    md = s.get("stage_metadata") or {}
    return {"sessions_ended": float(s.get("num_sessions") or 0),
            "sessions_failed": float(s.get("num_sessions_failed") or 0),
            "turns_dropped": float(md.get("dropped_requests") or 0),
            "events_completed": float(s.get("total_events_completed") or 0),
            "events_cancelled": float(s.get("total_events_cancelled") or 0)}


def all_stats(cell):
    s = step10.cell_stats(cell)
    s.pop("sessions", None)
    return {**s, **series_stats(cell), **request_stats(cell), **session_stats(cell)}


ROWS = [
    ("output throughput (tok/s)", "throughput", "{:.0f}"),
    ("requests completed", "requests", "{:.0f}"),
    ("request errors", "errors", "{:.0f}"),
    ("turns not issued at stage end (inference-perf dropped_requests)", "turns_dropped", "{:.0f}"),
    ("sessions ended in window / failed", ("sessions_ended", "sessions_failed"), "{:.0f}"),
    ("hit rate, whole window", "hit_window", "{:.3f}"),
    ("hit rate, warm-up (first 10 min)", "hit_warmup", "{:.3f}"),
    ("hit rate, steady state", "hit_steady", "{:.3f}"),
    ("requests with zero cache hit", "zero_cache_share", "{:.2f}"),
    ("prefill tokens computed (M)", "prefill_tokens_total", "{:.1f}", 1e-6),
    ("prompt tokens per request, mean (k)", "prompt_tokens_mean", "{:.1f}", 1e-3),
    ("TTFT p50 / p90 / p99 (s)", ("ttft_p50", "ttft_p90", "ttft_p99"), "{:.1f}"),
    ("E2E latency p50 / p90 / p99 (s)", ("e2e_p50", "e2e_p90", "e2e_p99"), "{:.1f}"),
    ("TPOT p50 / p90 (ms)", ("tpot_p50", "tpot_p90"), "{:.0f}", 1e3),
    ("ITL p50 / p90 (ms)", ("itl_p50", "itl_p90"), "{:.0f}", 1e3),
    ("vLLM KV usage, mean steady / max", ("kv_mean_steady", "kv_max"), "{:.2f}"),
    ("vLLM running, mean steady / max", ("running_mean_steady", "running_max"), "{:.0f}"),
    ("vLLM waiting, mean steady / max", ("waiting_mean_steady", "waiting_max"), "{:.1f}"),
    ("vLLM preemptions", "preemptions", "{:.0f}"),
    ("EPP undecayed working set / capacity, mean steady", "ws_undecayed_mean_steady", "{:.2f}"),
    ("EPP decayed working set / capacity, mean steady", "ws_decayed_mean_steady", "{:.2f}"),
    ("share of samples with working set over capacity", "ws_over_capacity_share", "{:.2f}"),
    ("EPP sessions running / idle / paused, mean", ("programs_running_mean", "programs_idle_mean", "programs_paused_mean"), "{:.0f}"),
    ("EPP max sessions paused at once", "max_paused", "{:.0f}"),
    ("EPP releases reasoning / paused / new", ("releases_reasoning", "releases_paused", "releases_new"), "{:.0f}"),
    ("EPP holds paused / new", ("holds_paused", "holds_new"), "{:.0f}"),
    ("EPP pauses / resumes", ("pauses", "resumes"), "{:.0f}"),
    ("EPP forced admissions", "starved", "{:.0f}"),
    ("EPP mean queue wait (s)", "queue_wait_mean", "{:.1f}"),
    ("EPP max queue size", "max_queue", "{:.0f}"),
    ("EPP CPU cores, mean / max", ("epp_cpu_mean", "epp_cpu_max"), "{:.2f}"),
]


def cellfmt(cells, keys, spec, scale):
    keys = keys if isinstance(keys, tuple) else (keys,)
    parts = []
    for k in keys:
        vals = [c[k] * scale for c in cells if isinstance(c.get(k), (int, float)) and np.isfinite(c[k])]
        if not vals:
            parts.append("-")
        elif len(vals) == 1:
            parts.append(spec.format(vals[0]))
        else:
            parts.append(f"{spec.format(st.mean(vals))} ({spec.format(min(vals))}-{spec.format(max(vals))})")
    return " / ".join(parts)


def ratio(new, ref, key):
    if isinstance(key, tuple):
        return ""
    a = [c[key] for c in new if np.isfinite(c.get(key, float("nan")))]
    b = [c[key] for c in ref if np.isfinite(c.get(key, float("nan")))]
    if not a or not b or not st.mean(b):
        return ""
    inside = "in" if min(b) <= st.mean(a) <= max(b) else "out"
    return f"{st.mean(a) / st.mean(b):.2f}x ({inside})"


def raw_counter_deltas(path):
    """Delta between the first and last snapshot of every counter-like series,
    summed over labels per metric name."""
    snaps = gzip.open(path, "rt").read().split("# ts=")[1:]
    if len(snaps) < 2:
        return {}, 0.0

    def parse(snap):
        head, _, body = snap.partition("\n")
        vals = defaultdict(float)
        for line in body.splitlines():
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^([A-Za-z_:][\w:]*)(\{[^}]*\})?\s+(\S+)", line)
            if not m:
                continue
            name = m.group(1)
            if name.endswith(("_total", "_sum", "_count")) and "_bucket" not in name:
                try:
                    vals[name] += float(m.group(3))
                except ValueError:
                    pass
        return float(head), vals

    t0, a = parse(snaps[0])
    t1, b = parse(snaps[-1])
    return {k: b.get(k, 0.0) - a.get(k, 0.0) for k in sorted(set(a) | set(b))}, t1 - t0


def raw_report(cell):
    L = [f"# Raw metric deltas, {cell.name}\n",
         "Every `_total`, `_sum` and `_count` series in the raw scrapes, summed over labels, "
         "last snapshot minus first. Histogram means are sum delta / count delta.\n"]
    for src, fname in (("vLLM", "raw-vllm-metrics.txt.gz"), ("EPP", "raw-epp-metrics.txt.gz")):
        p = cell / "results" / fname
        if not p.exists():
            continue
        d, span = raw_counter_deltas(p)
        L.append(f"## {src} ({span:.0f} s between first and last snapshot)\n")
        L.append("| metric | delta | histogram mean |")
        L.append("|---|---|---|")
        for k, v in d.items():
            if v == 0:
                continue
            mean = ""
            if k.endswith("_sum"):
                c = d.get(k[:-4] + "_count", 0)
                mean = f"{v / c:.4g}" if c else ""
            L.append(f"| `{k}` | {v:.6g} | {mean} |")
        L.append("")
    return "\n".join(L)


def smooth(ts, vs, w=30):
    if len(vs) < w:
        return ts, vs
    k = np.ones(w) / w
    return ts[w - 1:], np.convolve(vs, k, mode="valid")


def timeseries(cells_by_arm, out):
    panels = [("vllm-metrics.csv", "interval_hit_rate", "prefix-cache hit rate (1 min mean)", 1),
              ("vllm-metrics.csv", "kv_cache_usage_perc", "vLLM KV usage", 1),
              ("vllm-metrics.csv", "num_requests_running", "vLLM running", 1),
              ("vllm-metrics.csv", "num_requests_waiting", "vLLM waiting", 1),
              ("epp-metrics.csv", "programs_paused", "EPP sessions paused", 1),
              ("epp-metrics.csv", "fc_queue_size", "EPP queue size", 1)]
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                         "legend.frameon": False})
    fig, axes = plt.subplots(2, 3, figsize=(15, 7.5))
    for ax, (fname, col, title, _) in zip(axes.flat, panels):
        for arm, cells in cells_by_arm.items():
            for i, cell in enumerate(cells):
                rs = rows(cell / "results" / fname)
                pts = [(float(r["ts"]), num(r, col)) for r in rs if num(r, col) is not None]
                if not pts:
                    continue
                t0 = float(rs[0]["ts"])
                ts = np.array([(p[0] - t0) / 60 for p in pts])
                vs = np.array([p[1] for p in pts])
                ts, vs = smooth(ts, vs)
                ax.plot(ts, vs, color=PALETTE[arm], linewidth=2.2 if arm.startswith("min") else 1.0,
                        alpha=1.0 if arm.startswith("min") else 0.55, label=LABELS[arm] if i == 0 else None)
        ax.axvline(WARMUP_S / 60, color="#999999", linestyle=":", linewidth=1)
        ax.set_title(title)
        ax.set_xlabel("minutes")
    axes.flat[0].legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=150)


LABELS = {"sticky": "step 10 sticky (n=3)", "v3": "step 10 thunder v3 (n=3)", "min": "step 15 thunder-min"}


def main():
    run = Path(sys.argv[1])
    ref = Path(sys.argv[2]) if len(sys.argv) > 2 else STEP10 / "results" / "rep-20260917-173839-c128-t1900"
    new_cells = sorted(d for d in run.iterdir() if d.is_dir() and d.name.startswith("epp-thunder-min-r")
                       and (d / "results").exists())
    cells = {"sticky": sorted(ref.glob("epp-sticky-r[0-9]")), "v3": sorted(ref.glob("epp-thunder-r[0-9]")),
             "min": new_cells}
    data = {arm: [all_stats(c) for c in cs] for arm, cs in cells.items()}

    L = [f"# Step 15: minimal thunder-agent on one pod, against step 10\n",
         f"step 15 cells: {', '.join(c.name for c in new_cells)}; step 10 reference: `{ref.name}` "
         f"(sticky and thunder v3, three lanes each). Step 10 columns are mean (min-max). "
         f"The last column is thunder-min / thunder v3 of the means, and whether the thunder-min "
         f"value lies inside the v3 min-max range.\n",
         "| metric | step 10 sticky | step 10 thunder v3 | step 15 thunder-min | min / v3 |",
         "|---|---|---|---|---|"]
    for row in ROWS:
        name, key, spec_ = row[:3]
        scale = row[3] if len(row) > 3 else 1
        L.append(f"| {name} | {cellfmt(data['sticky'], key, spec_, scale)} | {cellfmt(data['v3'], key, spec_, scale)} | "
                 f"{cellfmt(data['min'], key, spec_, scale)} | {ratio(data['min'], data['v3'], key)} |")
    L.append("")
    (run / "analysis.md").write_text("\n".join(L))
    print("\n".join(L))
    for c in new_cells:
        (run / f"raw-metrics-{c.name}.md").write_text(raw_report(c))
    timeseries(cells, run / "timeseries.png")
    print(f"wrote {run / 'analysis.md'}, raw-metrics-*.md, timeseries.png")


if __name__ == "__main__":
    main()
