#!/usr/bin/env python3
"""Step 16 long window: the minimal thunder-agent at c=128 for 90 minutes,
sliced into 30-minute windows, next to step 13's 90-minute cells (llm-d
default, most-room, origin-only; same protocol).

The question is the minimal design's riskiest simplification: sessions are
released only by the idle TTL (3600 s, longer than the cell), with no
session-final signal. Finished sessions therefore stay on the books; if that
makes admission more conservative over time, later slices lose throughput
against origin-only (whose v4 build released on x-session-final, which the
replay never sent either, so both keep finished sessions; what differs is
markedForPause and the buffer). Per slice: step 13's request and session
metrics, plus EPP means of sessions by state, the undecayed working set over
capacity, and pauses and holds in the slice.

Writes <run>/long.md. Usage: analyze_long.py <step16 run> [step13 run]
"""
import csv
import importlib.util
import statistics as st
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("long13", HERE.parent / "13-llm-d-router-sweep" / "analyze_long.py")
long13 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(long13)
SLICE_S = 1800.0
ARMS = [("step 13 llm-d default", "ref", "epp-baseline-c128-w90"),
        ("step 13 v4 most-room", "ref", "epp-thunder-c128-w90"),
        ("step 13 v4 origin-only", "ref", "epp-thunder-origin-c128-w90"),
        ("step 16 thunder-min", "run", "epp-thunder-min-c128-w90")]


def epp_slices(cell, n):
    """Per-slice EPP means and counter deltas, aligned on load onset like long13.vllm_rows."""
    vr = list(csv.DictReader((cell / "results" / "vllm-metrics.csv").open()))
    onset = next((float(r["ts"]) for r in vr if float(r.get("num_requests_running") or 0) > 0), float(vr[0]["ts"]))
    er = list(csv.DictReader((cell / "results" / "epp-metrics.csv").open()))
    f = lambda r, k: float(r[k]) if r.get(k) not in (None, "") else None
    out = []
    for k in range(n):
        rows = [r for r in er if k * SLICE_S <= float(r["ts"]) - onset < (k + 1) * SLICE_S]
        if not rows:
            out.append({})
            continue
        d = {}
        for state in ("running", "idle", "paused"):
            v = [f(r, f"programs_{state}") for r in rows if f(r, f"programs_{state}") is not None]
            d[f"programs_{state}"] = st.mean(v) if v else float("nan")
        ws = [(f(r, "working_set_undecayed"), f(r, "capacity_tokens")) for r in rows]
        ws = [a / b for a, b in ws if a is not None and b]
        if not ws:  # v4: one pod's undecayed utilization
            ws = [f(r, "pod_utilization") for r in rows if f(r, "pod_utilization") is not None]
        d["ws"] = st.mean(ws) if ws else float("nan")
        for key in ("pauses_total", "resumes_total"):
            a, b = f(rows[0], key), f(rows[-1], key)
            d[key] = b - a if a is not None and b is not None else float("nan")
        hold = lambda r: (f(r, "holds_paused") or 0) + (f(r, "holds_new") or 0)
        d["holds"] = hold(rows[-1]) - hold(rows[0])
        out.append(d)
    return out


def main():
    run = Path(sys.argv[1])
    ref = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent / "13-llm-d-router-sweep" / "results" / "sweep-20260918-134248-t1900"
    data = {}
    for label, where, name in ARMS:
        cell = (run if where == "run" else ref) / name
        if (cell / "results" / "report").exists():
            sl = long13.slices(cell, SLICE_S)
            for row, e in zip(sl, epp_slices(cell, len(sl))):
                row.update(e)
            data[label] = sl
    n = max((len(v) for v in data.values()), default=0)
    rows = [("throughput (tok/s)", "throughput", "{:.0f}"), ("prefix-cache hit rate", "hit", "{:.3f}"),
            ("TTFT p50 (s)", "ttft_p50", "{:.1f}"), ("TTFT p90 (s)", "ttft_p90", "{:.1f}"),
            ("mean prompt tokens", "prompt_mean", "{:.0f}"), ("goodput within SLO (turns/s)", "goodput_slo", "{:.2f}"),
            ("session SLO attainment, strict", "attain_strict", "{:.2f}"), ("session SLO attainment, lenient", "attain_lenient", "{:.2f}"),
            ("sessions active in the slice", "sessions", "{:.0f}"),
            ("EPP sessions on the books: running, mean", "programs_running", "{:.0f}"),
            ("EPP sessions on the books: idle, mean (includes finished, kept until the TTL)", "programs_idle", "{:.0f}"),
            ("EPP sessions on the books: paused, mean", "programs_paused", "{:.0f}"),
            ("EPP undecayed working set / capacity (v4: first pod only)", "ws", "{:.2f}"),
            ("EPP pauses in the slice", "pauses_total", "{:.0f}"), ("EPP holds in the slice", "holds", "{:.0f}")]
    labels = list(data)
    L = ["# Step 16 long window: c=128 for 90 minutes, 30-minute slices\n",
         "Slice 1 includes the 10-minute warm-up. The last column is thunder-min / origin-only within the slice.\n"]
    for name, key, spec_ in rows:
        L.append(f"## {name}\n")
        L.append("| slice | " + " | ".join(labels) + " | min / origin |")
        L.append("|---|" + "---|" * (len(labels) + 1))
        for k in range(n):
            vals = {a: data[a][k].get(key, float("nan")) if k < len(data[a]) else float("nan") for a in labels}
            m, o = vals.get("step 16 thunder-min"), vals.get("step 13 v4 origin-only")
            r = f"{m / o:.2f}x" if m is not None and o and m == m and o == o else "-"
            L.append(f"| {k + 1} | " + " | ".join(spec_.format(vals[a]) if vals[a] == vals[a] else "-" for a in labels) + f" | {r} |")
        L.append("")
    (run / "long.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
