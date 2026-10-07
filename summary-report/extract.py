#!/usr/bin/env python3
"""Data for the summary report (THUNDER-AGENT-SUMMARY.zh.md), from raw results already in this repo.

Writes data/ (delete a file to recompute it):

  engine-intervals.json  every 10 s scrape interval of the steady state of every
                         step 20 and step 21 cell (single vLLM replica): engine steps,
                         scheduled tokens, generated tokens, KV usage, running and
                         waiting requests, CPU tier loads
  engine-cells.json      the same, summed over each cell's steady state
  pool-sweep.json        step 13 (4-pod pool) per level and arm: output and prefill
                         tokens per second, ITL p50, from the per-request reports

Usage: uv run --with numpy --with orjson python extract.py
"""
import gzip
import json
from pathlib import Path

import numpy as np

try:
    import orjson
    loads = orjson.loads
except ImportError:
    loads = json.loads

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
GPU_KV_TOKENS = 2237040

# metric name -> key; labelled metrics keep one label value
KEEP = {
    "vllm:iteration_tokens_total_count": "steps", "vllm:iteration_tokens_total_sum": "sched",
    "vllm:generation_tokens_total": "gen",
    "vllm:inter_token_latency_seconds_sum": "itl_sum", "vllm:inter_token_latency_seconds_count": "itl_n",
    "vllm:num_requests_running": "running", "vllm:num_requests_waiting": "waiting",
    "vllm:kv_cache_usage_perc": "kv",
    "vllm:num_preemptions_total": "preempt",
    "vllm:kv_offload_load_bytes_total": "load_bytes", "vllm:kv_offload_load_time_total": "load_time",
    "vllm:kv_offload_store_bytes_total": "store_bytes",
    "vllm:request_queue_time_seconds_sum": "queue_sum", "vllm:request_queue_time_seconds_count": "queue_n",
    "vllm:request_prefill_time_seconds_sum": "prefill_time_sum",
    "vllm:request_decode_time_seconds_sum": "decode_time_sum",
    "vllm:request_prefill_time_seconds_count": "req_n",
}
BY_LABEL = {"vllm:prompt_tokens_by_source_total": ("source", "prompt_")}
GAUGES = ("running", "waiting", "kv")


def snapshots(path):
    """[(ts, {key: value})] from a gzip of '# ts=' Prometheus snapshots."""
    out, cur = [], None
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("# ts="):
                cur = {}
                out.append((float(line[5:].strip()), cur))
                continue
            if cur is None or line[0] == "#" or not line.strip():
                continue
            name = line.split("{", 1)[0].split(" ", 1)[0]
            if name in KEEP:
                k = KEEP[name]
            elif name in BY_LABEL:
                label, prefix = BY_LABEL[name]
                i = line.find(label + '="')
                if i < 0:
                    continue
                k = prefix + line[i + len(label) + 2:line.index('"', i + len(label) + 2)]
            else:
                continue
            cur[k] = cur.get(k, 0.0) + float(line.rsplit(" ", 1)[1])
    return out


def engine(cell, meta):
    snaps = snapshots(cell / "results" / "raw-vllm-metrics.txt.gz")
    t0 = snaps[0][0]
    steady = [(t, m) for t, m in snaps if t0 + meta["warmup_s"] <= t <= t0 + meta["window_s"]]
    rows = []
    for (ta, a), (tb, b) in zip(steady, steady[1:]):
        d = {k: b.get(k, 0.0) - a.get(k, 0.0) for k in b if k not in GAUGES}
        row = {"dt": tb - ta, **d}
        for g in GAUGES:
            row[g] = (a.get(g, 0.0) + b.get(g, 0.0)) / 2
        rows.append(row)
    tot = {k: sum(r[k] for r in rows) for k in rows[0] if k not in GAUGES}
    for g in GAUGES:
        tot[g] = float(np.mean([r[g] for r in rows]))
    return rows, tot


def step_cells():
    """(step, phase, arm, c, rep, lane, cell dir, meta) for every step 20 and 21 cell."""
    for step, results in (("20", ROOT / "20-cpu-offload-pool" / "results"), ("21", ROOT / "21-thunder-tier-budget" / "results")):
        for run in sorted(results.glob("rep-*")):
            mp = run / "step20.json"
            if not mp.exists():
                continue
            meta = json.loads(mp.read_text())
            for lane, arm in sorted(meta["lane_arms"].items()):
                cell = run / f"epp-{arm}-{lane}"
                if cell.is_dir():
                    yield step, meta["phase"], arm, meta["concurrency"], meta.get("replicate", 1), lane, cell, meta


def build_engine():
    ivals, cells = [], []
    for step, phase, arm, c, rep, lane, cell, meta in step_cells():
        print("engine", cell.relative_to(ROOT), flush=True)
        rows, tot = engine(cell, meta)
        tag = {"step": step, "phase": phase, "arm": arm, "c": c, "rep": rep, "lane": lane,
               "cell": str(cell.relative_to(ROOT))}
        cells.append({**tag, **tot})
        ivals += [{**tag, **r} for r in rows]
    (DATA / "engine-intervals.json").write_text(json.dumps(ivals))
    (DATA / "engine-cells.json").write_text(json.dumps(cells, indent=1))


def build_pool_sweep():
    run = ROOT / "13-llm-d-router-sweep" / "results" / "sweep-20260918-134248-t1900"
    rows = []
    for c in (16, 32, 48, 64, 96, 128, 192, 256, 338):
        for arm in ("baseline", "thunder", "thunder-origin"):
            cell = run / f"epp-{arm}-c{c}"
            if not cell.is_dir():
                continue
            print("pool", cell.name, flush=True)
            window = json.loads((cell / "manifest.json").read_text()).get("window_s") or 1800
            summ = json.loads((cell / "results" / "report" / "summary_lifecycle_metrics.json").read_text())
            recs = loads((cell / "results" / "report" / "per_request_lifecycle_metrics.json").read_bytes())
            out = prompt = cached = 0
            for r in recs:
                if r.get("error"):
                    continue
                rm = (r.get("info") or {}).get("response_metrics") or {}
                use = rm.get("server_usage") or {}
                out += rm.get("output_tokens") or 0
                prompt += use.get("prompt_tokens") or 0
                cached += ((use.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0
            lat = summ["successes"]["latency"]
            rows.append({"arm": arm, "c": c, "per_pod": c / 4, "window_s": window,
                         "output_tps": out / window, "prefill_tps": (prompt - cached) / window,
                         "prompt_tps": prompt / window, "hit_window": cached / prompt if prompt else None,
                         "itl_p50": lat["inter_token_latency"]["median"], "itl_mean": lat["inter_token_latency"]["mean"],
                         "requests": summ["successes"]["count"]})
            del recs
    (DATA / "pool-sweep.json").write_text(json.dumps(rows, indent=1))


def main():
    DATA.mkdir(exist_ok=True)
    if not (DATA / "engine-cells.json").exists():
        build_engine()
    if not (DATA / "pool-sweep.json").exists():
        build_pool_sweep()


if __name__ == "__main__":
    main()
