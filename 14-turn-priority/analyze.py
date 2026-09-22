#!/usr/bin/env python3
"""Step 14: llm-d's turn-priority fairness (PR 2116, upstream defaults) on a single
pod, against step 10's epp-sticky and epp-thunder lanes (same protocol, same
v0.7.0 generator with the permit bug, so all three arms saw the same effective
load). Per cell: throughput, requests, steady-state hit rate, TTFT, errors split
into 429 sheds and the rest, plus vLLM queue. Writes analysis.md.
Usage: analyze.py <turnprio_run_dir> [step10_run_dir]
"""
import importlib.util
import json
import statistics as st
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("pool_analyze", Path(__file__).resolve().parent.parent / "12-llm-d-router-pool" / "analyze.py")
pa = importlib.util.module_from_spec(spec); spec.loader.exec_module(pa)

STEP10 = Path(__file__).resolve().parent.parent / "10-llm-d-router-replicates" / "results" / "rep-20260917-173839-c128-t1900"


def failures(cell):
    f = cell / "results" / "report" / "summary_lifecycle_metrics.json"
    if not f.exists():
        return 0, 0, {}
    j = json.loads(f.read_text()).get("failures") or {}
    by = {k: (v.get("count") if isinstance(v, dict) else v) for k, v in (j.get("by_label") or {}).items()}
    shed = sum(c for k, c in by.items() if str(k).startswith("429"))
    return int(j.get("count") or 0), int(shed), by


def stats(cell):
    s = pa.cell_stats(cell)
    s["waiting"] = pa.series_mean(cell / "results" / "vllm-metrics.csv", "num_requests_waiting", 600.0)
    s["fail_total"], s["shed_429"], s["fail_labels"] = failures(cell)
    return s


def fmt(v, spec):
    v = [x for x in v if x == x]
    if not v:
        return "-"
    return spec.format(st.mean(v)) + (f" ({spec.format(min(v))}-{spec.format(max(v))})" if len(v) > 1 else "")


def main():
    run = Path(sys.argv[1]); step10 = Path(sys.argv[2]) if len(sys.argv) > 2 else STEP10
    arms = [("epp-sticky", step10), ("epp-thunder", step10), ("epp-turnprio-005-ttl60", run)]
    data = {}
    for arm, root in arms:
        cells = sorted(d for d in root.glob(f"{arm}-r*") if (d / "results" / "report").exists())
        data[arm] = [stats(c) for c in cells]
    rows = [("throughput (output tok/s)", "throughput", "{:.0f}"), ("requests completed", "requests", "{:.0f}"), ("hit rate, steady state (after 10 min)", "hit_steady", "{:.3f}"),
            ("TTFT p50 (s)", "ttft_p50", "{:.1f}"), ("TTFT p90 (s)", "ttft_p90", "{:.1f}"), ("in flight, mean", "inflight", "{:.0f}"), ("waiting inside vLLM, mean after 10 min", "waiting", "{:.0f}"),
            ("KV usage, mean", "kv", "{:.2f}"), ("failed requests", "fail_total", "{:.0f}"), ("of which 429 (shed by the flow controller)", "shed_429", "{:.0f}")]
    L = ["# Step 14: turn-priority (PR 2116, upstream defaults) vs step 10's sticky and thunder lanes\n",
         f"Single pod per lane, c=128, 45-minute window, client timeout 1900 s, inference-perf v0.7.0 (permit bug: about half of the sessions active, the same for every arm). Cells: mean (min-max) over replicates. sticky and thunder from `{STEP10.name}`; turn-priority from `{run.name}`.\n",
         "| metric | epp-sticky | epp-thunder | epp-turnprio-005-ttl60 | turnprio / sticky | turnprio / thunder |", "|---|---|---|---|---|---|"]
    for name, key, spec in rows:
        vals = {a: [c[key] for c in data[a]] for a, _ in arms}
        def ratio(n, d):
            return f"{st.mean(vals[n]) / st.mean(vals[d]):.2f}x" if vals[n] and vals[d] and st.mean(vals[d]) else "-"
        L.append(f"| {name} | {fmt(vals['epp-sticky'], spec)} | {fmt(vals['epp-thunder'], spec)} | {fmt(vals['epp-turnprio-005-ttl60'], spec)} | {ratio('epp-turnprio-005-ttl60', 'epp-sticky')} | {ratio('epp-turnprio-005-ttl60', 'epp-thunder')} |")
    L.append("")
    labels = {}
    for c in data["epp-turnprio-005-ttl60"]:
        for k, v in c["fail_labels"].items():
            labels[k] = labels.get(k, 0) + v
    if labels:
        L.append("Turn-priority failure labels summed over its cells: " + ", ".join(f"`{k}`: {v}" for k, v in sorted(labels.items())) + "\n")
    (run / "step14-analysis.md").write_text("\n".join(L)); print("\n".join(L))


if __name__ == "__main__":
    main()
