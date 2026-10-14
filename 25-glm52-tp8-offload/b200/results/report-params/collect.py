"""Collect the numbers of the llm-d-thunder-agent-simplified parameter report into metrics.json:
gate capacity (1.57M GPU pool, 3.15M, 3.91M, 6.29M) and idle lease (10 s, 30 s), against
no-router, one-hour points with CPU offload; plus 5-minute timelines of the c=32 and 48 points."""
import csv, gzip, json, re, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parent
ARMS = {
    "no-router": {12: "r1", 16: "r1", 20: "explore1h-direct", 24: "explore1h-direct", 32: "explore1h-direct",
                  48: "explore1h-direct"},
    "gpu-l10": {c: "explore1h-thunder-gpu-l10" for c in (12, 16, 20, 24, 32, 48)},
    "gpu-l30": {12: "thunder-r1", 16: "thunder-r1", 20: "explore1h-thunder-gpu-l30", 24: "explore1h-thunder-gpu-l30",
                32: "explore1h-thunder-gpu-l30"},
    "cap3m-l10": {32: "explore1h-thunder-cap3m-l10-retry", 48: "explore1h-thunder-cap3m-l10-retry"},
    "cap6m-l10": {32: "explore1h-thunder-cap6m-l10-retry", 48: "explore1h-thunder-cap6m-l10-retry"},
    "cap391-l10": {16: "thunder-cpu-l10-r1"},
}
SUMMARIES = ("r1/report", "explore1h/report", "explore1h-highc/report", "explore1h-cap/report",
             "report3arm/summaries/thunder-r1", "report3arm/summaries/l30", "report-params/summaries/cpu391")
summ = {}
for f in SUMMARIES:
    p = R / f / "summary.csv"
    if p.exists():
        for r in csv.DictReader(open(p)):
            summ[(r["label"], int(r["conc"]))] = r


def num(r, k):
    v = r.get(k)
    return float(v) if v not in (None, "") else None


def timeline(d, bin_s=300):
    """Per 5-minute bin: output tok/s, median TTFT, forced admissions, admitted ledger (M tokens)."""
    recs = []
    for l in open(d / "aiperf_artifacts/profile_export.jsonl"):
        x = json.loads(l); m = x["metadata"]; mt = x["metrics"]
        if m.get("benchmark_phase") != "profiling" or m.get("was_cancelled"):
            continue
        g = lambda k: (mt.get(k) or {}).get("value") or 0
        recs.append((m["request_start_ns"], m["request_end_ns"], g("output_sequence_length"), g("time_to_first_token") / 1000))
    t0 = min(r[0] for r in recs)
    epp, ts, cur = [], None, {}
    path = d / "epp/raw-epp-metrics.txt.gz"
    if path.exists():
        for l in gzip.open(path, "rt"):
            if l.startswith("# ts="):
                if ts and cur:
                    epp.append((ts, cur))
                ts, cur = float(l.split()[1][3:]), {}
                continue
            mm = re.match(r"llm_d_epp_thunder_agent_starvation_promotions_total (\S+)", l)
            if mm: cur["forced"] = float(mm.group(1))
            mm = re.match(r"llm_d_epp_thunder_agent_endpoint_working_set_tokens\S* (\S+)", l)
            if mm: cur["ledger"] = float(mm.group(1))
        if ts and cur:
            epp.append((ts, cur))
    out = []
    for b in range(0, 3600, bin_s):
        lo, hi = t0 + b * 1e9, t0 + (b + bin_s) * 1e9
        rr = [r for r in recs if lo <= r[1] < hi]
        e = [v for t, v in epp if lo / 1e9 <= t < hi / 1e9]
        out.append({"min": b // 60, "out_tok_s": sum(r[2] for r in rr) / bin_s,
                    "ttft_p50": st.median([r[3] for r in rr]) if rr else None,
                    "forced": (e[-1].get("forced", 0) - e[0].get("forced", 0)) if e else None,
                    "ledger_m": st.mean([v.get("ledger", 0) for v in e]) / 1e6 if e else None})
    return out


out = {}
for arm, pts in ARMS.items():
    for c, lab in pts.items():
        r = summ.get((lab, c))
        if r is None:
            print("missing", arm, c, lab); continue
        d = R / lab / f"c{c}"
        a = json.load(open(d / "aiperf_artifacts/profile_export_aiperf.json"))
        n = long_ = 0
        for l in open(d / "aiperf_artifacts/profile_export.jsonl"):
            x = json.loads(l)
            if x["metadata"].get("benchmark_phase") != "profiling" or x["metadata"].get("was_cancelled"):
                continue
            n += 1; long_ += ((x["metrics"].get("time_to_first_token") or {}).get("value") or 0) > 60000
        v = {"arm": arm, "conc": c, "label": lab, "mode": "formal" if lab in ("r1", "thunder-r1", "thunder-cpu-l10-r1") else "exploration",
             "completed": int(r["completed"]), "cancelled": int(float(r["cancelled"] or 0)),
             "out_tok_s": num(r, "output_tput"), "out_tok_s_gpu": num(r, "output_tput_per_gpu"),
             "ttft_p50": num(r, "p50_ttft_s"), "ttft_p90": num(r, "p90_ttft_s"),
             "ttft_p99": a["time_to_first_token"]["p99"] / 1000, "ttft_max": a["time_to_first_token"]["max"] / 1000,
             "intvty_p90": num(r, "p90_intvty"), "itl_p50": a["inter_token_latency"]["p50"],
             "ss_gpu_hit": num(r, "ss_gpu_hit_pct"), "cpu_hit": num(r, "cpu_hit_pct"), "recompute": num(r, "recompute_pct"),
             "running": num(r, "running_avg_sum"), "waiting": num(r, "waiting_avg_sum"),
             "turns_over_60s_pct": 100 * long_ / n, "sessions_over_60s_pct": num(r, "sessions_worst_ttft_over_slo_pct"),
             "forced": num(r, "gate_starvation_promotions"), "pauses": num(r, "gate_pauses"),
             "ledger_over_cap": num(r, "gate_working_set_over_capacity_mean"), "isl_median": num(r, "isl_median")}
        if c in (32, 48) and arm != "no-router":
            v["timeline"] = timeline(d)
        out[f"{arm}/{c}"] = v
json.dump(out, open(HERE / "metrics.json", "w"), indent=1)
for k, v in out.items():
    print(k, {kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk not in ("timeline", "arm", "conc")})
