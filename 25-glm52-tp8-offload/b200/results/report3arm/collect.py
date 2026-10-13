"""Collect every number of the three-arm report (passthrough, thunder lease 10 s, thunder
lease 30 s; plus the no-offload points) into metrics.json."""
import csv, json, gzip, re, collections, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parent
C = (12, 16, 20, 24, 32)
ARMS = {
    "passthrough": {12: "r1", 16: "r1", 20: "explore1h-direct", 24: "explore1h-direct", 32: "explore1h-direct"},
    "thunder-l10": {c: "explore1h-thunder-gpu-l10" for c in C},
    "thunder-l30": {12: "thunder-r1", 16: "thunder-r1", 20: "explore1h-thunder-gpu-l30",
                    24: "explore1h-thunder-gpu-l30", 32: "explore1h-thunder-gpu-l30"},
    "passthrough-nooff": {c: "explore1h-direct-nooff" for c in (16, 24, 32)},
    "thunder-l10-nooff": {c: "explore1h-thunder-gpu-l10-nooff" for c in (16, 24, 32)},
}
summ = {}
for f in ("r1/report", "explore1h/report", "report3arm/summaries/thunder-r1", "report3arm/summaries/l30", "report3arm/summaries/nooff", "explore1h-r2/report"):
    p = R / f / "summary.csv"
    if p.exists():
        for r in csv.DictReader(open(p)):
            summ[(r["label"], int(r["conc"]))] = r

def q(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(p * len(v)))]

def counters(d):
    """Run totals of the vLLM counters (the export includes the warmup)."""
    out = {}
    for row in csv.reader(l for l in open(d / "aiperf_artifacts/server_metrics_export.csv") if not l.startswith("#")):
        if len(row) < 5 or row[1] != "counter":
            continue
        key = row[2]
        if key == "vllm:prompt_tokens_by_source":
            key += "/" + next((x for x in row if x in ("external_kv_transfer", "local_cache_hit", "local_compute")), "?")
        out.setdefault(key, float(row[4]))
    return out

out = {}
for arm, pts in ARMS.items():
    for c, lab in pts.items():
        d = R / lab / f"c{c}"
        if (lab, c) not in summ:
            print("missing", arm, c, lab); continue
        s = summ[(lab, c)]
        a = json.load(open(d / "aiperf_artifacts/profile_export_aiperf.json"))
        isl, osl, zero, long_, n, turns = [], [], 0, 0, 0, collections.Counter()
        for l in open(d / "aiperf_artifacts/profile_export.jsonl"):
            x = json.loads(l); m = x["metadata"]; mt = x["metrics"]
            if m.get("benchmark_phase") != "profiling" or m.get("was_cancelled"):
                continue
            g = lambda k: (mt.get(k) or {}).get("value")
            if g("input_sequence_length"): isl.append(g("input_sequence_length"))
            if g("output_sequence_length"): osl.append(g("output_sequence_length"))
            n += 1; zero += (g("usage_prompt_cache_read_tokens") or 0) == 0
            long_ += (g("time_to_first_token") or 0) > 60000
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
        ctr = counters(d)
        src = {k.split("/")[1]: v for k, v in ctr.items() if k.startswith("vllm:prompt_tokens_by_source/")}
        src_total = sum(src.values()) or 1
        dur = float(s["duration_s"])
        out[f"{arm}/{c}"] = {
            "arm": arm, "conc": c, "label": lab, "mode": "formal" if lab in ("r1", "thunder-r1") else "exploration",
            "completed": int(s["completed"]), "errors": int(float(s["errors"] or 0)), "cancelled": int(float(s["cancelled"] or 0)),
            "duration_s": dur, "req_per_s": int(s["completed"]) / dur,
            "out_tok_s": float(s["output_tput"]), "out_tok_s_gpu": float(s["output_tput_per_gpu"]),
            "ttft_p50": float(s["p50_ttft_s"]), "ttft_p90": float(s["p90_ttft_s"]),
            "ttft_p99": a["time_to_first_token"]["p99"] / 1000, "ttft_max": a["time_to_first_token"]["max"] / 1000,
            "itl_p50": a["inter_token_latency"]["p50"], "itl_p99": a["inter_token_latency"]["p99"],
            "intvty_p50": float(s["p50_intvty"]), "intvty_p90": float(s["p90_intvty"]),
            "gpu_hit": float(s["gpu_hit_pct"]), "cpu_hit": float(s["cpu_hit_pct"] or 0), "overall_hit": float(s["overall_hit_pct"]),
            "ss_gpu_hit": float(s.get("ss_gpu_hit_pct") or "nan"), "ss_overall_hit": float(s.get("ss_overall_hit_pct") or "nan"),
            "kv_peak": float(s["kv_usage_max_pct"]), "running_mean": float(s["running_avg_sum"]), "waiting_mean": float(s["waiting_avg_sum"]),
            "queue_time_avg_s": float(s["engine_request_queue_time_avg_s"] or "nan"),
            "zero_hit_pct": 100 * zero / n, "turns_over_60s_pct": 100 * long_ / n,
            "sessions_over_60s_pct": float(s["sessions_worst_ttft_over_slo_pct"]),
            "isl_p50": q(isl, .5), "isl_p90": q(isl, .9), "isl_max": max(isl), "osl_p50": q(osl, .5), "osl_mean": st.mean(osl),
            "prompt_from_cpu_pct": 100 * src.get("external_kv_transfer", 0) / src_total,
            "prompt_from_gpu_pct": 100 * src.get("local_cache_hit", 0) / src_total,
            "prompt_computed_pct": 100 * src.get("local_compute", 0) / src_total,
            "prompt_tokens_total": src_total, "prompt_computed_tok_s": src.get("local_compute", 0) / dur,
            "preemptions": int(ctr.get("vllm:num_preemptions", 0)),
            "cpu_to_gpu_tb": ctr.get("vllm:kv_offload_load_bytes", 0) / 1e12,
            "gpu_to_cpu_tb": ctr.get("vllm:kv_offload_store_bytes", 0) / 1e12,
            "turns_by_trace": dict(turns), **{f"gate_{k}": v for k, v in gate.items()},
        }
# per-session progress against passthrough on the traces both arms worked on
for key, v in out.items():
    base = out.get(f"passthrough/{v['conc']}")
    if v["arm"] == "passthrough" or base is None:
        continue
    p, t = base["turns_by_trace"], v["turns_by_trace"]
    shared = [k for k in p if k in t and p[k] and t[k]]
    v["shared_traces"] = len(shared)
    v["progress_ratio_turns"] = sum(t[k] for k in shared) / max(1, sum(p[k] for k in shared))
for v in out.values():
    v.pop("turns_by_trace")
json.dump(out, open(HERE / "metrics.json", "w"), indent=1)
for k, v in out.items():
    print(k, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk not in ("arm", "conc", "label")})
