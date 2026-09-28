#!/usr/bin/env python3
"""Step 17 analysis: the lease thunder-agent on the 4-pod pool, against step 16.

Reference cells at c=128 from the step 16 run (same protocol: one EPP over the
four pods, 30 min, client timeout 1900 s, same load generator image): the
minimal thunder-agent with idle decay half-life 1 s, 10 s, and 10 s with a 1 s
pause sweep (step 16's best arm, the ratio reference here).

Writes <run>/analysis.md (step 16's metric set), one raw-metrics-<cell>.md
per step 17 cell and <run>/timeseries.png.

Usage: analyze.py <step17 run dir> [step16 run dir]
"""
import importlib.util
import sys
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
REF = "min10s1"
ARMS = [("min", "step 16 thunder-min (half-life 1 s)", "epp-thunder-min-c128*", "#2E8B57"),
        ("min10", "step 16 thunder-min (half-life 10 s)", "epp-thunder-min-hl10-c128*", "#E08A00"),
        (REF, "step 16 thunder-min (half-life 10 s, sweep 1 s)", "epp-thunder-min-hl10-s1-c128*", "#7B3FA0"),
        ("lease", "step 17 thunder-lease (lease 30 s)", "epp-thunder-lease-c128*", "#0F4D92"),
        ("lease5", "step 17 thunder-lease (lease 5 s)", "epp-thunder-lease5-c128*", "#B64342")]


def main():
    run = Path(sys.argv[1])
    ref = Path(sys.argv[2]) if len(sys.argv) > 2 else STEP16_RUN
    cells = {k: s16.cells_for(run if k.startswith("lease") else ref, pattern) for k, _, pattern, _ in ARMS}
    data = {k: [s16.stats(c) for c in cs] for k, cs in cells.items()}
    present = [a for a in ARMS if data[a[0]]]
    new = [k for k, *_ in present if k.startswith("lease")]

    L = ["# Step 17: lease thunder-agent on the 4-pod pool, c=128, against step 16\n",
         f"Step 16 reference: `{ref.name}`. Cells: " +
         "; ".join(f"{label}: {', '.join(c.name for c in cells[k])}" for k, label, _, _ in present) +
         ". Multi-cell columns are mean (min-max). The ratio columns compare each step 17 arm with step 16's "
         "half-life 10 s, sweep 1 s arm and say whether the value lies inside that arm's min-max range. "
         "For the lease build the undecayed working set row is its only working-set view.\n"]
    head = "| metric | " + " | ".join(label for _, label, _, _ in present)
    head += "".join(f" | {k} / {REF}" for k in new) + " |"
    L += [head, "|" + "---|" * (1 + len(present) + len(new))]
    for row in s15.ROWS + s16.EXTRA_ROWS:
        name, key, spec_ = row[:3]
        scale = row[3] if len(row) > 3 else 1
        line = f"| {name} | " + " | ".join(s15.cellfmt(data[k], key, spec_, scale) for k, *_ in present)
        line += "".join(f" | {s15.ratio(data[k], data[REF], key)}" for k in new) + " |"
        L.append(line)
    L.append("")
    (run / "analysis.md").write_text("\n".join(L))
    print("\n".join(L))
    for k in new:
        for c in cells[k]:
            (run / f"raw-metrics-{c.name}.md").write_text(s16.raw_report(c))
    s15.PALETTE = {k: col for k, _, _, col in ARMS}
    s15.LABELS = {k: label for k, label, _, _ in ARMS}
    s15.timeseries({k: cells[k] for k, *_ in present}, run / "timeseries.png")
    print(f"wrote {run / 'analysis.md'}, raw-metrics-*.md, timeseries.png")


if __name__ == "__main__":
    main()
