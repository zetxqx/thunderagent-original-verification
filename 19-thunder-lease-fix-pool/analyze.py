#!/usr/bin/env python3
"""Step 19 analysis: the lease thunder-agent after the in-flight accounting fix.

One cell (pool, c=128, lease 30 s, image thunder-agent-lease-44544c04) against
the same arm before the fix (step 18, one cell), step 17's lease 30 s (the
build that summed per-turn estimates, three cells) and step 16's best minimal
arm (three cells).

Writes <run>/analysis.md, raw-metrics-<cell>.md and timeseries.png.
Usage: analyze.py <step19 run dir>
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
S16 = HERE.parent / "16-thunder-minimal-pool" / "results" / "rep-20260927-195200-c128-t1900"
S17 = HERE.parent / "17-thunder-lease-pool" / "results" / "rep-20260928-115246-c128-t1900"
S18 = HERE.parent / "18-thunder-lease-main-pool" / "results" / "rep-20260929-040322-c128-t1900"


def main():
    run = Path(sys.argv[1])
    arms = [("fix", "step 19 lease 30 s, fixed accounting", s16.cells_for(run, "epp-thunder-lease-main-c128*"), "#1BAF7A"),
            ("pre", "step 18 lease 30 s, before the fix", s16.cells_for(S18, "epp-thunder-lease-main-c128*"), "#B64342"),
            ("l30", "step 17 lease 30 s (3 cells)", s16.cells_for(S17, "epp-thunder-lease-c128*"), "#0F4D92"),
            ("m10s1", "step 16 half-life 10 s, sweep 1 s (3 cells)", s16.cells_for(S16, "epp-thunder-min-hl10-s1-c128*"), "#7B3FA0")]
    data = {k: [s16.stats(c) for c in cs] for k, _, cs, _ in arms}
    present = [a for a in arms if data[a[0]]]
    L = ["# Step 19: lease thunder-agent after the in-flight accounting fix, pool, c=128\n",
         "Step 19 and 18 columns are one cell each; step 16 and 17 columns are mean (min-max) over three cells.\n",
         "| metric | " + " | ".join(label for _, label, _, _ in present) + " |", "|" + "---|" * (1 + len(present))]
    for row in s15.ROWS + s16.EXTRA_ROWS:
        name, key, spec_ = row[:3]
        scale = row[3] if len(row) > 3 else 1
        L.append(f"| {name} | " + " | ".join(s15.cellfmt(data[k], key, spec_, scale) for k, *_ in present) + " |")
    L.append("")
    (run / "analysis.md").write_text("\n".join(L))
    print("\n".join(L))
    for c in arms[0][2]:
        (run / f"raw-metrics-{c.name}.md").write_text(s16.raw_report(c))
    s15.PALETTE = {k: col for k, _, _, col in present}
    s15.LABELS = {k: label for k, label, _, _ in present}
    s15.timeseries({k: cs for k, _, cs, _ in present}, run / "timeseries.png")
    print(f"wrote {run / 'analysis.md'}")


if __name__ == "__main__":
    main()
