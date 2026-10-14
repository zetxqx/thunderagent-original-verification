# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "pyarrow", "matplotlib", "tabulate", "pyyaml"]
# ///
"""Recompute the summary of every point in dashboard bundles with the current analyze.py, and add
turns_by_trace, from the point's raw results. For bundles exported before analyze.py had p99 columns
and export_bundle.py wrote turns_by_trace (run after regroup_by_model.py).

  uv run dashboard/backfill_summary.py dashboard/data/glm52-nvfp4-8xb200.json=25-glm52-tp8-offload/b200/results \\
      dashboard/data/qwen3-coder-30b-fp8-2xh100.json=24-thunder-pr3-lanes/results

A point's raw folder is <results>/<id without " (shared)">. Series, distributions and config stay as they are.
"""
import importlib.util, json, sys
from pathlib import Path

import pandas as pd

SKILL = Path(__file__).resolve().parents[1] / ".claude/skills/agentic-benchmark/scripts"
spec = importlib.util.spec_from_file_location("export_bundle", SKILL / "export_bundle.py")
eb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eb)

for arg in sys.argv[1:]:
    bundle_path, results = (Path(x) for x in arg.split("=", 1))
    bundle = json.load(open(bundle_path))
    slo, skip = bundle["settings"]["ttft_slo_s"], bundle["settings"]["skip_minutes"]
    done = {}
    for p in bundle["points"]:
        point = results / p["id"].removesuffix(" (shared)")
        if point not in done:
            print(f"analyzing {point}", flush=True)
            row = eb.a23.analyze_point(point, point, None, slo, skip)
            recs = eb.a23.load_records(point / "aiperf_artifacts" / "profile_export.jsonl")
            ok = recs[(recs["phase"] == "profiling") & recs["err_type"].isna() & ~recs["cancelled"]
                      & recs["lat_s"].notna() & recs["trace"].notna()]
            done[point] = (
                {k: (eb.num(v, 6) if not isinstance(v, str) else v) for k, v in row.items()},
                eb.a23.checks(pd.Series(row)),
                {str(k): int(v) for k, v in ok["trace"].value_counts().items()},
            )
        p["summary"], p["checks"], p["turns_by_trace"] = done[point]
    json.dump(bundle, open(bundle_path, "w"), separators=(",", ":"))
    print(f"wrote {bundle_path}")
