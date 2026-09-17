#!/usr/bin/env python3
"""Calibration verdict: is this regime saturated enough to test admission control?

Usage: verdict.py <calibration_out_root>

Gates (fixed before running):
  G1 baseline prefix-cache hit rate < 0.85   -> real eviction pressure exists
  G2 peak KV utilization > 0.80              -> corroborating signal
  G3 effective concurrency sustained         -> last-third mean >= 70% of peak
  G4 per-request cached_tokens present       -> primary metric now available
G1 is the decisive one; G2/G4 are corroborating; G3 says whether the window
measured what it claimed to measure.
"""
import csv
import json
import sys
from pathlib import Path

import statistics as st


def ts_col(path, col, cast=float):
    if not path.exists():
        return []
    out = []
    for r in csv.DictReader(open(path)):
        v = r.get(col)
        if v not in (None, ""):
            out.append(cast(v))
    return out


def cell_report(d):
    res = d / "results"
    rep = res / "report" / "per_request_lifecycle_metrics.json"
    m = json.loads((d / "manifest.json").read_text()) if (d / "manifest.json").exists() else {}
    row = {"cell": d.name, "c": m.get("concurrency"), "pod": m.get("pod", "")[-5:]}

    vm = res / "vllm-metrics.csv"
    dq = sum(int(x) for x in ts_col(vm, "interval_queries", int))
    dh = sum(int(x) for x in ts_col(vm, "interval_hits", int))
    kv = ts_col(vm, "kv_cache_usage_perc")
    wait = ts_col(vm, "num_requests_waiting")
    pre = ts_col(vm, "num_preemptions_total")
    row["hit_rate"] = dh / dq if dq else None
    row["kv_peak"] = max(kv) if kv else None
    row["wait_peak"] = max(wait) if wait else None
    row["preempt"] = (max(pre) - min(pre)) if pre else None

    rc = ts_col(res / "router-health.csv", "reasoning_count")
    if rc:
        peak = max(rc)
        third = rc[int(len(rc) * 2 / 3):]
        row["conc_peak"] = peak
        row["conc_mean"] = st.mean(rc)
        row["conc_last_third"] = st.mean(third) if third else 0
        row["conc_sustain"] = (row["conc_last_third"] / peak) if peak else 0

    row["cached_tokens"] = False
    row["requests"] = 0
    if rep.exists():
        entries = json.loads(rep.read_text())
        ok = [e for e in entries if not e.get("error")]
        row["requests"] = len(ok)
        row["errors"] = len(entries) - len(ok)
        for e in ok:
            su = ((e.get("info") or {}).get("response_metrics") or {}).get("server_usage") or {}
            det = su.get("prompt_tokens_details") or {}
            if det.get("cached_tokens") is not None:
                row["cached_tokens"] = True
                break
    tm = res / "trace-manifest.json"
    if tm.exists():
        t = json.loads(tm.read_text())
        row["corpus"] = t.get("kept")
        row["corpus_lines"] = t.get("complete_lines")
    return row


def main():
    root = Path(sys.argv[1])
    cells = sorted((d for d in root.iterdir() if d.is_dir()),
                   key=lambda d: json.loads((d / "manifest.json").read_text()).get("concurrency", 0)
                   if (d / "manifest.json").exists() else 0)
    rows = [cell_report(d) for d in cells]

    hdr = f"{'cell':<10}{'c':>5}{'corpus':>8}{'reqs':>7}{'hit':>8}{'KVpk':>7}{'waitpk':>8}{'preempt':>9}{'conc pk/mean/last⅓':>22}{'sustain':>9}{'cached':>8}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        conc = (f"{r.get('conc_peak', 0):.0f}/{r.get('conc_mean', 0):.0f}/"
                f"{r.get('conc_last_third', 0):.0f}")
        print(f"{r['cell']:<10}{r.get('c', 0) or 0:>5}{r.get('corpus', 0) or 0:>8}"
              f"{r['requests']:>7}"
              f"{(r['hit_rate'] if r['hit_rate'] is not None else float('nan')):>8.3f}"
              f"{(r['kv_peak'] or 0):>7.2f}{(r['wait_peak'] or 0):>8.0f}"
              f"{(r['preempt'] if r['preempt'] is not None else 0):>9.0f}"
              f"{conc:>22}{r.get('conc_sustain', 0):>9.0%}"
              f"{('yes' if r['cached_tokens'] else 'NO'):>8}")

    print()
    best = None
    for r in rows:
        g1 = r["hit_rate"] is not None and r["hit_rate"] < 0.85
        g2 = (r["kv_peak"] or 0) > 0.80
        g3 = r.get("conc_sustain", 0) >= 0.70
        g4 = r["cached_tokens"]
        verdict = "SATURATED" if g1 else "not saturated"
        print(f"{r['cell']}: {verdict} | G1 hit<0.85 {'PASS' if g1 else 'FAIL'} | "
              f"G2 KV>0.80 {'PASS' if g2 else 'fail'} | "
              f"G3 concurrency sustained {'PASS' if g3 else 'FAIL'} | "
              f"G4 cached_tokens {'PASS' if g4 else 'FAIL'}")
        if g1 and (best is None or (r.get("c") or 0) < (best.get("c") or 0)):
            best = r

    print()
    if best:
        print(f"=> lowest saturated concurrency: c={best['c']} (hit rate {best['hit_rate']:.3f}). "
              f"Run the long sweep centred there, e.g. c={best['c']}, "
              f"{int(best['c'] * 1.5)}, {best['c'] * 2}.")
    else:
        print("=> NO cell reached saturation. Do not run the long sweep as-is. "
              "Escalate: higher concurrency (needs corpus >= 3x c), or a "
              "dedicated vLLM with a smaller KV pool (--gpu-memory-utilization).")


if __name__ == "__main__":
    main()
