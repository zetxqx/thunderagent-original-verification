"""Step 26 utilThreshold test (Qwen3.5, 48 sessions): no-router, utilThreshold 1.0, 0.8 and 0.6, into
metrics-util.json for fig4 of the report. Summary values from report-util/summary.csv (analyze.py)."""
import collections, csv, gzip, json, re, statistics as st
from pathlib import Path

R = Path(__file__).resolve().parent.parent
ARMS = [("no-router", "qwen35-direct"), ("1.0", "qwen35-thunder-gpu-l10"),
        ("0.8", "qwen35-thunder-u08"), ("0.6", "qwen35-thunder-u06")]
summ = {r["label"]: r for r in csv.DictReader(open(R / "report-util/summary.csv"))}


def turns(d):
    t = collections.Counter()
    for l in open(d / "aiperf_artifacts/profile_export.jsonl"):
        x = json.loads(l); m = x["metadata"]
        if m.get("benchmark_phase") == "profiling" and not m.get("was_cancelled") and not x.get("error"):
            t[m.get("source_trace_id")] += 1
    return t


def admitted(d):
    epp = d / "epp/raw-epp-metrics.txt.gz"
    if not epp.exists():
        return None, None
    run, idle = [], []
    for l in gzip.open(epp, "rt"):
        mm = re.match(r'llm_d_epp_thunder_agent_sessions\{state="(running|idle)"\} (\S+)', l)
        if mm:
            (run if mm.group(1) == "running" else idle).append(float(mm.group(2)))
    k = len(run) // 12  # skip the first 5 of about 65 minutes
    return st.mean(run[k:]), st.mean(idle[k:])


out, base = {}, None
for name, lab in ARMS:
    d = R / lab / "c48"; s = summ[lab]
    f = lambda k: float(s[k])
    t = turns(d)
    base = base or t
    shared = [k for k in t if base.get(k)]
    run, idle = admitted(d)
    out[name] = {
        "label": lab, "out_tok_s_gpu": f("output_tput_per_gpu"),
        "gpu_pct": f("ss_gpu_hit_pct"), "cpu_pct": f("ss_cpu_hit_pct"), "computed_pct": f("ss_recompute_pct"),
        "running_mean": f("running_avg_sum"), "step_ms": f("step_time_T_ms"),
        "intvty_p50": f("p50_intvty"), "intvty_p90": f("p90_intvty"),
        "e2e_norm_intvty_p50": f("p50_e2e_norm_intvty"), "e2e_norm_intvty_p90": f("p90_e2e_norm_intvty"),
        "e2el_p90": f("p90_e2el_s"), "e2el_p99": f("p99_e2el_s"), "ttft_p99": f("p99_ttft_s"),
        "sessions_over_60s_pct": f("sessions_worst_ttft_over_slo_pct"),
        "progress_ratio_turns": sum(t[k] for k in shared) / sum(base[k] for k in shared),
        "admitted_running": run, "admitted_idle": idle,
    }
json.dump(out, open(Path(__file__).parent / "metrics-util.json", "w"), indent=1)
for k, v in out.items():
    print(k, {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items()})
