"""Step 26 (Qwen3.5-397B-A17B-FP8, vLLM TP=4): the same metrics as step 25's report1h/collect.py, into
metrics-qwen.json, so the GLM-5.2 and Qwen3.5 numbers come from the same code."""
import csv, json, gzip, re, collections, statistics as st
from pathlib import Path

R = Path(__file__).resolve().parent.parent
C = (32, 48, 64)
ARMS = {
    "passthrough": {c: "qwen35-direct" for c in C},
    "thunder": {c: "qwen35-thunder-gpu-l10" for c in C},
}
summ = {}
for f in ("report/summary.csv",):
    for r in csv.DictReader(open(R / f)):
        summ[(r["label"], int(r["conc"]))] = r

def q(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))]

out = {}
for arm, pts in ARMS.items():
    for c, lab in pts.items():
        d = R / lab / f"c{c}"; s = summ[(lab, c)]
        a = json.load(open(d / "aiperf_artifacts/profile_export_aiperf.json"))
        isl, osl, zero, turns = [], [], 0, collections.Counter()
        n = 0
        for l in open(d / "aiperf_artifacts/profile_export.jsonl"):
            x = json.loads(l); m = x["metadata"]; mt = x["metrics"]
            if m.get("benchmark_phase") != "profiling" or m.get("was_cancelled"):
                continue
            g = lambda k: (mt.get(k) or {}).get("value")
            if g("input_sequence_length"): isl.append(g("input_sequence_length"))
            if g("output_sequence_length"): osl.append(g("output_sequence_length"))
            n += 1; zero += (g("usage_prompt_cache_read_tokens") or 0) == 0
            turns[m.get("source_trace_id")] += 1
        gate = {}
        epp = d / "epp/raw-epp-metrics.txt.gz"
        if epp.exists():
            run, idle, pau, ws, cap = [], [], [], [], []; last = {}
            for l in gzip.open(epp, "rt"):
                mm = re.match(r'llm_d_epp_thunder_agent_sessions\{state="(\w+)"\} (\S+)', l)
                if mm: {"running": run, "idle": idle, "paused": pau}[mm.group(1)].append(float(mm.group(2)))
                mm = re.match(r'llm_d_epp_thunder_agent_endpoint_working_set_tokens\S* (\S+)', l)
                if mm: ws.append(float(mm.group(1)))
                mm = re.match(r'llm_d_epp_thunder_agent_endpoint_capacity_tokens\S* (\S+)', l)
                if mm: cap.append(float(mm.group(1)))
                mm = re.match(r'llm_d_epp_thunder_agent_(starvation_promotions_total|pauses_total) (\S+)', l)
                if mm: last[mm.group(1)] = int(float(mm.group(2)))
            k = len(run) // 12  # skip the first 5 of about 65 minutes
            gate = {"admitted_mean": st.mean([r + i for r, i in zip(run[k:], idle[k:])]),
                    "ws_over_cap_mean": st.mean(ws[k:]) / cap[-1], "paused_peak": max(pau),
                    "forced": last.get("starvation_promotions_total", 0), "pauses": last.get("pauses_total", 0),
                    "capacity": cap[-1]}
        load, src = None, {}
        for row in csv.reader(l for l in open(d / "aiperf_artifacts/server_metrics_export.csv") if not l.startswith("#")):
            if len(row) > 4 and row[1] == "counter" and row[2] == "vllm:kv_offload_load_bytes" and load is None:
                load = float(row[4])
            if len(row) > 4 and row[1] == "counter" and row[2] == "vllm:prompt_tokens_by_source":
                k = next((x for x in row if x in ("external_kv_transfer", "local_cache_hit", "local_compute")), None)
                if k: src.setdefault(k, float(row[4]))
        src_total = sum(src.values()) or 1
        dur = float(s["duration_s"])
        out[f"{arm}/{c}"] = {
            "arm": arm, "conc": c, "label": lab, "mode": "formal" if lab == "r1" else "exploration",
            "completed": int(s["completed"]), "errors": int(float(s["errors"] or 0)), "cancelled": int(float(s["cancelled"] or 0)),
            "duration_s": dur, "req_per_s": int(s["completed"]) / dur,
            "out_tok_s": float(s["output_tput"]), "out_tok_s_gpu": float(s["output_tput_per_gpu"]),
            "ttft_p50": float(s["p50_ttft_s"]), "ttft_p90": float(s["p90_ttft_s"]),
            "ttft_p99": a["time_to_first_token"]["p99"] / 1000, "ttft_max": a["time_to_first_token"]["max"] / 1000,
            "itl_p50": a["inter_token_latency"]["p50"], "itl_p99": a["inter_token_latency"]["p99"],
            "intvty_p50": float(s["p50_intvty"]), "intvty_p90": float(s["p90_intvty"]),
            "e2e_norm_intvty_p50": float(s["p50_e2e_norm_intvty"]), "e2e_norm_intvty_p90": float(s["p90_e2e_norm_intvty"]),
            "e2el_p50": float(s["p50_e2el_s"]), "e2el_p90": float(s["p90_e2el_s"]), "e2el_p99": a["request_latency"]["p99"] / 1000,
            "gpu_hit": float(s["gpu_hit_pct"]), "cpu_hit": float(s["cpu_hit_pct"]), "overall_hit": float(s["overall_hit_pct"]),
            "ss_gpu_hit": float(s.get("ss_gpu_hit_pct") or "nan"), "ss_overall_hit": float(s.get("ss_overall_hit_pct") or "nan"),
            "kv_peak": float(s["kv_usage_max_pct"]), "running_mean": float(s["running_avg_sum"]), "waiting_mean": float(s["waiting_avg_sum"]),
            "zero_hit_pct": 100 * zero / n, "turns_over_60s_pct": None, "sessions_over_60s_pct": float(s["sessions_worst_ttft_over_slo_pct"]),
            "isl_p50": q(isl, .5), "isl_p90": q(isl, .9), "isl_max": max(isl), "osl_p50": q(osl, .5), "osl_mean": st.mean(osl),
            "turns_by_trace": dict(turns), "cpu_to_gpu_tb": (load or 0) / 1e12,
            # token sources in the steady state (analyze.py ss_*: from minute 5 of profiling, no warmup)
            "prompt_from_cpu_pct": float(s["ss_cpu_hit_pct"]),
            "prompt_from_gpu_pct": float(s["ss_gpu_hit_pct"]),
            "prompt_computed_pct": float(s["ss_recompute_pct"]),
            "working_set_mean": float(s["working_set_mean"]), "working_set_max": float(s["working_set_max"]), **{f"gate_{k}": v for k, v in gate.items()},
        }
        long_ = sum(1 for l in open(d / "aiperf_artifacts/profile_export.jsonl")
                    if (lambda x: x["metadata"].get("benchmark_phase") == "profiling" and not x["metadata"].get("was_cancelled")
                        and ((x["metrics"].get("time_to_first_token") or {}).get("value") or 0) > 60000)(json.loads(l)))
        out[f"{arm}/{c}"]["turns_over_60s_pct"] = 100 * long_ / n
# per-session progress on traces both arms worked on
for c in C:
    p, t = out[f"passthrough/{c}"]["turns_by_trace"], out[f"thunder/{c}"]["turns_by_trace"]
    shared = [k for k in p if k in t and p[k] and t[k]]
    ratios = [t[k] / p[k] for k in shared]
    out[f"thunder/{c}"]["shared_traces"] = len(shared)
    out[f"thunder/{c}"]["progress_ratio_mean"] = st.mean(ratios) if ratios else None
    out[f"thunder/{c}"]["progress_ratio_turns"] = sum(t[k] for k in shared) / max(1, sum(p[k] for k in shared))
for v in out.values():
    v.pop("turns_by_trace")
json.dump(out, open(Path(__file__).parent / "metrics-qwen.json", "w"), indent=1)
for k, v in out.items():
    print(k, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk not in ("arm", "conc", "label")})
