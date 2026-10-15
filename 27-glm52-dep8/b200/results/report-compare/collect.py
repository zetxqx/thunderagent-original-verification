"""Step 27: TP=8 (step 25) against DEP=8 for GLM-5.2, c=24 to 64, into metrics.json. Summary values from
analyze.py (report-tp8/ and report/, the same analyze.py version for both). Session progress: turns
completed on the traces that the arm and TP=8 no-router at the same concurrency both ran, divided by the
TP=8 no-router turns on those traces."""
import collections, csv, json
from pathlib import Path

R = Path(__file__).resolve().parent.parent
T = R.parents[2] / "25-glm52-tp8-offload/b200/results"
C = (24, 32, 48, 64)
ARMS = {  # arm -> (summary label, point directory for a concurrency)
    "tp8-direct": ("explore1h-direct", lambda c: T / "explore1h-direct" / f"c{c}"),
    "tp8-thunder": ("explore1h-thunder-gpu-l10", lambda c: T / "explore1h-thunder-gpu-l10" / f"c{c}"),
    "dep8-direct": ("dep8-direct", lambda c: R / "dep8-direct" / f"c{c}"),
    # c=32: the second run (both tries in run-dep8.sh failed at the cache reset). c=64: the retry, because
    # the first try's client was OOMKilled before it wrote the server metrics (1,114 completed requests).
    "dep8-affinity": ("dep8-affinity", lambda c: R / {32: "dep8-affinity-r2", 64: "dep8-affinity-retry"}.get(c, "dep8-affinity") / f"c{c}"),
    "dep8-thunder": ("dep8-thunder-l10", lambda c: R / "dep8-thunder-l10" / f"c{c}"),
}
summ = {}
for f in ("report-tp8/summary.csv", "report/summary.csv"):
    for r in csv.DictReader(open(R / f)):
        if (r["label"], r["conc"]) == ("dep8-affinity", "64"):
            continue  # first try without server metrics; the retry below replaces it
        if r["label"] == "dep8-direct-retry":
            continue  # second try at c=64 (878 completed); the first try (834) is used
        summ[(r["label"].removesuffix("-r2").removesuffix("-retry"), int(r["conc"]))] = r


def turns(d):
    t = collections.Counter()
    for line in open(d / "aiperf_artifacts/profile_export.jsonl"):
        x = json.loads(line); m = x["metadata"]
        if m.get("benchmark_phase") == "profiling" and not m.get("was_cancelled") and not x.get("error"):
            t[m.get("source_trace_id")] += 1
    return t


f = lambda r, k: float(r[k]) if r.get(k) not in (None, "") else None
out = {}
for c in C:
    base = turns(ARMS["tp8-direct"][1](c))
    for arm, (label, path) in ARMS.items():
        r = summ.get((label, c))
        if r is None or not path(c).exists():
            continue
        t = turns(path(c))
        shared = [k for k in t if base.get(k)]
        out[f"{arm}/{c}"] = {
            "completed": int(r["completed"]), "out_tok_s_gpu": f(r, "output_tput_per_gpu"),
            "ttft_p50": f(r, "p50_ttft_s"), "ttft_p99": f(r, "p99_ttft_s"),
            "e2e_norm_intvty_p50": f(r, "p50_e2e_norm_intvty"), "e2e_norm_intvty_p90": f(r, "p90_e2e_norm_intvty"),
            "e2el_p90": f(r, "p90_e2el_s"), "e2el_p99": f(r, "p99_e2el_s"), "intvty_p90": f(r, "p90_intvty"),
            "gpu_pct": f(r, "ss_gpu_hit_pct"), "cpu_pct": f(r, "ss_cpu_hit_pct"), "computed_pct": f(r, "ss_recompute_pct"),
            "running": f(r, "running_avg_sum"), "waiting": f(r, "waiting_avg_sum"), "preemptions": f(r, "preemptions"),
            "progress": sum(t[k] for k in shared) / max(1, sum(base[k] for k in shared)),
            "summary_missing": r.get("aiperf_summary_missing") == "True",
        }
json.dump(out, open(Path(__file__).parent / "metrics.json", "w"), indent=1)
cols = ["completed", "out_tok_s_gpu", "intvty_p90", "e2e_norm_intvty_p50", "e2e_norm_intvty_p90", "e2el_p90", "e2el_p99", "ttft_p50", "ttft_p99",
        "gpu_pct", "computed_pct", "waiting", "progress"]
print("| point | " + " | ".join(cols) + " |")
for k, v in out.items():
    print(f"| {k} | " + " | ".join("-" if v[c] is None else f"{v[c]:.3g}" for c in cols) + " |")
