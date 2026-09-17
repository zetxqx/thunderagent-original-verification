#!/usr/bin/env python3
"""Cross-trial stability check for repeated A/B runs.

Usage: trials.py <ab_root_1> <ab_root_2> [more roots...]

For every arm present in all roots, prints each metric per trial plus the
relative spread (max-min)/mean, and compares it with the between-arm gaps.
Writes <last_root>/trials-summary.md.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

METRICS = [
    ("makespan_s", "makespan (s)", "{:.1f}"),
    ("hit_rate", "prefix-cache hit rate", "{:.3f}"),
    ("prefilled_mtok", "prefilled tokens (M)", "{:.2f}"),
    ("lat_p50", "latency p50 (s)", "{:.1f}"),
    ("lat_p95", "latency p95 (s)", "{:.1f}"),
    ("max_paused", "max concurrent paused", "{:.0f}"),
]


def stats(d):
    with open(d / "summary.json") as f:
        s = json.load(f)
    with open(d / "metrics-backends.csv") as f:
        b = list(csv.DictReader(f))
    with open(d / "requests.csv") as f:
        reqs = [r for r in csv.DictReader(f) if r["status"] == "200" and r["latency_s"]]
    lats = np.array([float(r["latency_s"]) for r in reqs])
    dq = sum(int(r["interval_queries"]) for r in b)
    dh = sum(int(r["interval_hits"]) for r in b)
    return {
        "makespan_s": s["makespan_s"],
        "hit_rate": dh / dq if dq else 0.0,
        "prefilled_mtok": (dq - dh) / 1e6,
        "lat_p50": float(np.percentile(lats, 50)),
        "lat_p95": float(np.percentile(lats, 95)),
        "max_paused": s["max_paused_count"],
        "ok": f"{s['turns_ok']}/{s['turns_expected']}",
    }


def main():
    roots = [Path(p) for p in sys.argv[1:]]
    arms = sorted(
        set.intersection(*(({d.name for d in r.iterdir() if (d / "summary.json").exists()})
                           for r in roots))
    )
    lines = [f"# Trial stability across {len(roots)} runs\n",
             "Trials: " + ", ".join(r.name for r in roots) + "\n"]
    per_arm = {}
    for arm in arms:
        vals = [stats(r / arm) for r in roots]
        per_arm[arm] = vals
        lines.append(f"## {arm}\n")
        lines.append("| metric | " + " | ".join(f"trial {i+1}" for i in range(len(roots)))
                     + " | spread |")
        lines.append("|---" * (len(roots) + 2) + "|")
        lines.append("| requests ok | " + " | ".join(v["ok"] for v in vals) + " | |")
        for key, name, fmt in METRICS:
            xs = [v[key] for v in vals]
            mean = np.mean(xs)
            spread = (max(xs) - min(xs)) / mean if mean else 0.0
            lines.append(f"| {name} | " + " | ".join(fmt.format(x) for x in xs)
                         + f" | {spread:.1%} |")
        lines.append("")

    if "default" in per_arm:
        lines.append("## Gap vs run-to-run spread\n")
        for arm in arms:
            if arm == "default":
                continue
            for key, name, _ in METRICS[:1] + METRICS[3:5]:
                gaps = [per_arm[arm][i][key] / per_arm["default"][i][key]
                        for i in range(len(roots)) if per_arm["default"][i][key]]
                lines.append(f"- {arm} vs default, {name}: "
                             + ", ".join(f"{g:.2f}x" for g in gaps)
                             + f" (per-trial ratios; consistent = gap is real)")
        lines.append("")

    out = roots[-1] / "trials-summary.md"
    out.write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"written: {out}")


if __name__ == "__main__":
    main()
