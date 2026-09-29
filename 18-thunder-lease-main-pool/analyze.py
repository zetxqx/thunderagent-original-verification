#!/usr/bin/env python3
"""Step 18 analysis: the lease thunder-agent rebuilt on the minimal ledger.

Two tables, one cell per arm:

- single vLLM pod (lane run, c=32): lease 30 s against lease 10 s;
- 4-pod pool (c=128): lease 30 s and lease 10 s against step 17's lease 30 s
  and lease 5 s (the step 17 build, three cells each) and step 16's best
  minimal arm (half-life 10 s, sweep 1 s, three cells).

Writes analysis.md, raw-metrics-<cell>.md per step 18 cell, and
timeseries-single.png / timeseries-pool.png next to this script's results.

Usage: analyze.py   (finds the newest single-pod and pool runs in results/)
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


s16 = load("step16", HERE.parent / "16-thunder-minimal-pool" / "analyze.py")
s15 = s16.s15
STEP16_RUN = HERE.parent / "16-thunder-minimal-pool" / "results" / "rep-20260927-195200-c128-t1900"
STEP17_RUN = HERE.parent / "17-thunder-lease-pool" / "results" / "rep-20260928-115246-c128-t1900"


def newest(pattern):
    runs = sorted((HERE / "results").glob(pattern))
    return runs[-1] if runs else None


def cells(root, name):
    return [d for d in sorted(root.glob(name)) if d.is_dir() and (d / "results").exists()] if root else []


def table(title, note, arms, data):
    present = [a for a in arms if data[a[0]]]
    L = [f"## {title}\n", note + "\n",
         "| metric | " + " | ".join(label for _, label, *_ in present) + " |",
         "|" + "---|" * (1 + len(present))]
    for row in s15.ROWS + s16.EXTRA_ROWS:
        name, key, spec_ = row[:3]
        scale = row[3] if len(row) > 3 else 1
        L.append(f"| {name} | " + " | ".join(s15.cellfmt(data[k], key, spec_, scale) for k, *_ in present) + " |")
    return L + [""]


def main():
    single = newest("rep-*-c32-t1900")
    pool = newest("rep-*-c128-t1900")

    single_arms = [("s30", "single pod, lease 30 s", cells(single, "epp-thunder-lease-main-r1"), "#0F4D92"),
                   ("s10", "single pod, lease 10 s", cells(single, "epp-thunder-lease-main10-r1"), "#B64342")]
    pool_arms = [("p30", "step 18 pool, lease 30 s", cells(pool, "epp-thunder-lease-main-c128"), "#0F4D92"),
                 ("p10", "step 18 pool, lease 10 s", cells(pool, "epp-thunder-lease-main10-c128"), "#B64342"),
                 ("l30", "step 17 lease 30 s (3 cells)", s16.cells_for(STEP17_RUN, "epp-thunder-lease-c128*"), "#6DA7EC"),
                 ("l5", "step 17 lease 5 s (3 cells)", s16.cells_for(STEP17_RUN, "epp-thunder-lease5-c128*"), "#E08A00"),
                 ("m10s1", "step 16 half-life 10 s, sweep 1 s (3 cells)", s16.cells_for(STEP16_RUN, "epp-thunder-min-hl10-s1-c128*"), "#7B3FA0")]

    data = {k: [s16.stats(c) for c in cs] for k, _, cs, _ in single_arms + pool_arms}
    L = ["# Step 18: the lease thunder-agent rebuilt on the minimal ledger\n",
         f"Single-pod run: `{single.name if single else '-'}`. Pool run: `{pool.name if pool else '-'}`. "
         "Step 18 columns are one cell each; step 16 and 17 columns are mean (min-max) over three cells.\n"]
    L += table("Single vLLM pod, c=32", "One EPP pinned to one vLLM pod (lane a), 32 sessions, the pool's per-pod load.",
               [(k, label) for k, label, _, _ in single_arms], data)
    L += table("4-pod pool, c=128", "One EPP over the four vLLM pods, the step 16 and 17 protocol.",
               [(k, label) for k, label, _, _ in pool_arms], data)
    out = HERE / "results" / "analysis.md"
    out.write_text("\n".join(L))
    print("\n".join(L))

    for k, _, cs, _ in single_arms + pool_arms[:2]:
        for c in cs:
            (HERE / "results" / f"raw-metrics-{c.name}.md").write_text(s16.raw_report(c))
    for name, arms in (("single", single_arms), ("pool", pool_arms)):
        present = [a for a in arms if a[2]]
        if not present:
            continue
        s15.PALETTE = {k: col for k, _, _, col in present}
        s15.LABELS = {k: label for k, label, _, _ in present}
        s15.timeseries({k: cs for k, _, cs, _ in present}, HERE / "results" / f"timeseries-{name}.png")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
