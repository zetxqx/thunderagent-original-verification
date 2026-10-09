# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "pyarrow", "matplotlib", "tabulate"]
# ///
"""Build an AgentX-style report from AIPerf (agentx-v1.0.6) artifacts.

Usage: uv run analyze.py [--out DIR] [--cost-per-gpu-hour X] [--ttft-slo S] POINT_DIR [POINT_DIR ...]

A POINT_DIR is results/<label>/c<N> as written by run-point.sh. Points with
different labels are drawn as separate curves, so two configurations can be
compared by passing both label directories.

Every column is defined in ../references/metrics.md. Formulas follow
InferenceX; the engine, session, SLO and gate columns follow the repo's
BENCHMARK-METRICS.md:
  duration       = max(request_end) - min(request_start), profiling, no error
  throughput     = sum(tokens) / duration, per GPU = / num_gpus
  full ITL       = (request_latency - TTFT) / (OSL - 1), per request
  interactivity  = 1 / pXX(full ITL)
  e2e norm intv. = 1 / pXX(request_latency / OSL)
"""

import argparse
import gzip
import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import pandas as pd

PCTS = {"mean": None, "p50": 50, "p75": 75, "p90": 90, "p95": 95}
# vLLM v0.28 default for this server (../model-server/README.md): a step cannot
# carry more prefill than this, so a bin above it is a metrics artifact.
MAX_BATCHED_TOKENS = 8192
UNIT_TO_S = {"ns": 1e-9, "us": 1e-6, "ms": 1e-3, "s": 1.0, "sec": 1.0}


def pct(values: pd.Series, p: float | None) -> float:
    values = values.dropna()
    if values.empty:
        return float("nan")
    return float(values.mean() if p is None else np.percentile(values, p))


def netloc(url: str) -> str:
    return urlparse(url if "://" in url else f"http://{url}").netloc


def seconds(entry: dict | None) -> float | None:
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    return float(entry["value"]) * UNIT_TO_S.get(str(entry.get("unit", "ms")).lower(), 1e-3)


def number(entry: dict | None) -> float | None:
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    return float(entry["value"])


def load_records(path: Path) -> pd.DataFrame:
    rows = []
    with path.open() as f:
        for line in f:
            r = json.loads(line)
            m, x, err = r.get("metadata", {}), r.get("metrics") or {}, r.get("error") or {}
            rows.append({
                "phase": m.get("benchmark_phase"),
                "start_ns": m.get("request_start_ns"),
                "end_ns": m.get("request_end_ns"),
                "conv": m.get("conversation_id"),
                "root": m.get("root_correlation_id"),
                "depth": m.get("agent_depth"),
                "cancelled": bool(m.get("was_cancelled")),
                "overflow_skip": bool(m.get("context_overflow_skip")),
                "err_type": err.get("type"),
                "err_code": err.get("code"),
                "ttft_s": seconds(x.get("time_to_first_token")),
                "lat_s": seconds(x.get("request_latency")),
                "isl": number(x.get("input_sequence_length")),
                "osl": number(x.get("output_sequence_length")),
                "cached": number(x.get("usage_prompt_cache_read_tokens")),
            })
    return pd.DataFrame(rows)


def phase_counts(art: Path) -> dict:
    """Completed/cancelled/errors of the profiling phase from the aiperf log.

    Requests cancelled when the grace period ends appear in no export file,
    only in this log line.
    """
    log = art / "logs" / "aiperf.log"
    if not log.exists():
        return {}
    pat = re.compile(r"Phase profiling \(profiling\) complete \| completed=(\d+), cancelled=(\d+), errors=(\d+)")
    for line in reversed(log.read_text(errors="replace").splitlines()):
        if m := pat.search(line):
            return {"phase_completed": int(m[1]), "cancelled": int(m[2]), "phase_errors": int(m[3])}
    return {}


def metric(pj: dict, tag: str, stat: str = "avg") -> float | None:
    v = pj.get(tag)
    if isinstance(v, dict):
        v = v.get(stat)
    return None if v is None else float(v)


PQ_FIXED = {"endpoint_url", "metric_name", "metric_type", "unit", "description", "timestamp_ns",
            "value", "sum", "count", "bucket_le", "bucket_count", "pod", "m"}


def read_server(path: Path, columns: list[str] | None = None, metrics: list[str] | None = None) -> pd.DataFrame:
    """Read the parquet without histogram bucket rows: every analysis uses only a
    histogram's sum and count, which the '+Inf' row of each scrape carries. A c=192
    point has 3.3M rows, 81% of them buckets; loading them all took about 5 GB."""
    import pyarrow.dataset as pads

    le = pads.field("bucket_le")
    flt = le.is_null() | (le == "+Inf")
    if metrics:
        flt = flt & pads.field("metric_name").isin(metrics)
    return pads.dataset(path).to_table(columns=columns, filter=flt).to_pandas()


def load_server(path: Path, pods: set[str]) -> pd.DataFrame:
    """server_metrics_export.parquet rows of the target pods, profiling window only.

    Counters, histogram sums and counts are cumulative deltas from the start of
    profiling. The CSV and JSON summaries are not used: their counter totals
    include the warmup phase (checked on lane-20m/c16, run as try-lane-c16-20m: CSV prompt tokens =
    parquet profiling delta + warmup ISL).
    """
    pq = read_server(path)
    pq = pq[pq["endpoint_url"].map(netloc).isin(pods)].copy()
    pq["pod"] = pq["endpoint_url"].map(netloc)
    pq["m"] = pq["metric_name"].str.removesuffix("_total")
    return pq


def series(pq: pd.DataFrame, name: str) -> tuple[pd.DataFrame, list[str]]:
    """Rows of one metric (one row per scrape and series) and its label columns."""
    d = pq[pq["m"] == name.removesuffix("_total")]
    labels = [c for c in d.columns if c not in PQ_FIXED and d[c].notna().any()]
    if d["bucket_le"].notna().any():
        d = d.groupby(["pod", *labels, "timestamp_ns"], dropna=False)[["sum", "count"]].first().reset_index()
    return d, labels


def counter_total(pq: pd.DataFrame, name: str, by: str | None = None, col: str = "value",
                  since_ns: int | None = None) -> dict | float:
    """Increase of a counter over the profiling window, or from since_ns to its end."""
    d, labels = series(pq, name)
    if d.empty:
        return {} if by else float("nan")
    d = d.sort_values("timestamp_ns")
    keys = ["pod", *labels]
    last = d.groupby(keys, dropna=False)[col].last()
    if since_ns is not None:
        base = d[d["timestamp_ns"] <= since_ns].groupby(keys, dropna=False)[col].last()
        last = (last - base.reindex(last.index).fillna(0)).clip(lower=0)
    last = last.reset_index()
    return last.groupby(by)[col].sum().to_dict() if by else float(last[col].sum())


def counter_by_pod(pq: pd.DataFrame, name: str) -> dict[str, float]:
    return counter_total(pq, name, by="pod")


def gauge_stats(pq: pd.DataFrame, name: str, by: str = "pod", since_ns: int | None = None) -> pd.DataFrame:
    d, _ = series(pq, name)
    if since_ns is not None:
        d = d[d["timestamp_ns"] >= since_ns]
    if d.empty:
        return pd.DataFrame()
    return d.groupby(by)["value"].agg(avg="mean", max="max").reset_index()


def inflight(ok: pd.DataFrame, t0: int, step_s: float = 5.0) -> pd.DataFrame:
    """In-flight requests and in-flight unique input tokens over time.

    Each conversation runs at most one request at a time, so summing the ISL of
    running requests per conversation (max within a conversation) gives the
    deduplicated working set the KV pool must hold right now (AgentX definition).

    working_set also counts conversations between turns (waiting on a tool call
    or think time): the latest ISL of every conversation whose first profiled
    request has started and whose last one has not ended. Same definition as
    working_set() in the repo's 20-cpu-offload-pool/analyze.py: the prefix set
    a cache would need to keep every session's next turn a hit.
    """
    ok = ok.sort_values("start_ns")
    start, end = ok["start_ns"].to_numpy(), ok["end_ns"].to_numpy()
    span = ok.groupby("conv").agg(first=("start_ns", "min"), last=("end_ns", "max"))
    grid = np.arange(t0, end.max(), int(step_s * 1e9))
    rows = []
    for t in grid:
        active = ok[(start <= t) & (end > t)]
        live = span.index[(span["first"] <= t) & (span["last"] >= t)]
        latest = ok[start <= t].groupby("conv")["isl"].last()
        rows.append({
            "t": (t - t0) / 1e9,
            "requests": len(active),
            "sessions": active["root"].nunique(),
            "unique_tokens": float(active.groupby("conv")["isl"].max().sum()) if len(active) else 0.0,
            "working_set": float(latest.reindex(live).sum()),
        })
    return pd.DataFrame(rows)


GATE = "llm_d_epp_thunder_agent_"
EPP_QUEUE = "llm_d_epp_flow_control_request_queue_duration_seconds"
SAMPLE = re.compile(r"^([a-zA-Z_:][\w:]*)(?:\{([^}]*)\})?\s+(\S+)")
# Summary column -> EPP counter. The first name that exists wins: PR3 renamed
# holds_total to delayed_dispatches_total.
GATE_COUNTERS = {
    "gate_delayed_dispatches": [GATE + "delayed_dispatches_total", GATE + "holds_total"],
    "gate_pauses": [GATE + "pauses_total"],
    "gate_resumes": [GATE + "resumes_total"],
    "gate_releases": [GATE + "releases_total"],
    "gate_starvation_promotions": [GATE + "starvation_promotions_total"],
    "epp_requests": ["llm_d_epp_request_total"],
    "epp_request_errors": ["llm_d_epp_request_error_total"],
}


EPP_KEEP = (GATE, EPP_QUEUE, "llm_d_epp_flow_control_queue_size",
            "llm_d_epp_request_total", "llm_d_epp_request_error_total")


def load_epp(path: Path) -> pd.DataFrame:
    """Parse raw-epp-metrics.txt.gz written by epp_scrape.py into long form:
    one row per snapshot and series (ts in seconds, url, metric, labels, value).
    Only the metrics in EPP_KEEP are kept: a snapshot can have 200k series, mostly
    llm_d_epp_request_* histogram buckets per model name, which this report does not use."""
    rows, ts, url = [], None, None
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("# ts="):
                head = dict(kv.split("=", 1) for kv in line[2:].split())
                ts, url = float(head["ts"]), head.get("url", "")
                continue
            if line.startswith("#") or ts is None or not line.startswith(EPP_KEEP):
                continue
            m = SAMPLE.match(line)
            if m:
                rows.append((ts, url, m.group(1), m.group(2) or "", float(m.group(3))))
    return pd.DataFrame(rows, columns=["ts", "url", "metric", "labels", "value"])


def epp_window(epp: pd.DataFrame, metric: str, t0: float, t1: float) -> pd.DataFrame:
    """Snapshots of one metric inside [t0, t1], starting from the last snapshot
    at or before t0 so a counter delta covers the whole window."""
    d = epp[epp["metric"] == metric]
    before = d.loc[d["ts"] <= t0, "ts"]
    lo = before.max() if len(before) else t0
    return d[(d["ts"] >= lo) & (d["ts"] <= t1)]


def epp_delta(epp: pd.DataFrame, metric: str, t0: float, t1: float) -> float:
    d = epp_window(epp, metric, t0, t1)
    if d.empty:
        return float("nan")
    g = d.sort_values("ts").groupby(["url", "labels"])["value"]
    return float((g.last() - g.first()).clip(lower=0).sum())


def epp_gauge(epp: pd.DataFrame, metric: str, t0: float, t1: float) -> pd.Series:
    """A gauge summed over its series (pods, flows) per snapshot."""
    d = epp_window(epp, metric, t0, t1)
    return d.groupby("ts")["value"].sum()


def epp_hist_quantile(epp: pd.DataFrame, base: str, q: float, t0: float, t1: float) -> float | None:
    """Quantile of a Prometheus histogram over the window, from bucket deltas
    summed across series, interpolated linearly inside the bucket."""
    d = epp_window(epp, base + "_bucket", t0, t1)
    if d.empty:
        return None
    d = d.assign(le=d["labels"].str.extract(r'le="([^"]+)"')[0].astype(float))
    g = d.sort_values("ts").groupby(["url", "labels", "le"])["value"]
    cum = (g.last() - g.first()).clip(lower=0).groupby(level="le").sum().sort_index()
    total = cum.iloc[-1]
    if not total:
        return None
    rank, prev_le, prev_c = q * total, 0.0, 0.0
    for le, c in cum.items():
        if c >= rank:
            if np.isinf(le):
                return prev_le
            return prev_le + (le - prev_le) * (rank - prev_c) / (c - prev_c) if c > prev_c else le
        prev_le, prev_c = le, c
    return None


def epp_columns(epp: pd.DataFrame, t0: float, t1: float) -> dict:
    out: dict = {}
    for col, names in GATE_COUNTERS.items():
        for name in names:
            v = epp_delta(epp, name, t0, t1)
            if not np.isnan(v):
                out[col] = v
                break
    s, c = epp_delta(epp, EPP_QUEUE + "_sum", t0, t1), epp_delta(epp, EPP_QUEUE + "_count", t0, t1)
    out["epp_queue_wait_mean_s"] = s / c if c else None
    # Most turns of admitted sessions pass the gate at once, so the p90 is often
    # near zero while the held minority sets the mean and the p99.
    out["epp_queue_wait_p90_s"] = epp_hist_quantile(epp, EPP_QUEUE, 0.9, t0, t1)
    out["epp_queue_wait_p99_s"] = epp_hist_quantile(epp, EPP_QUEUE, 0.99, t0, t1)
    qs = epp_gauge(epp, "llm_d_epp_flow_control_queue_size", t0, t1)
    out["epp_queue_size_mean"], out["epp_queue_size_max"] = (qs.mean(), qs.max()) if len(qs) else (None, None)
    ws = epp_gauge(epp, GATE + "endpoint_working_set_tokens", t0, t1)
    cap = epp_gauge(epp, GATE + "endpoint_capacity_tokens", t0, t1)
    if len(ws) and len(cap) and cap.mean():
        out["gate_working_set_over_capacity_mean"] = ws.mean() / cap.mean()
        out["gate_working_set_over_capacity_max"] = (ws / cap.reindex(ws.index)).max()
    return out


def client_columns(ok: pd.DataFrame, errors: int, num_gpus: int, cost: float | None, slo: float,
                   prefix: str = "") -> dict:
    """Throughput, latency percentiles and goodput (InferenceX formulas) over the given requests."""
    if ok.empty:
        return {}
    duration = (ok["end_ns"].max() - ok["start_ns"].min()) / 1e9
    in_tok, out_tok = ok["isl"].sum(), ok["osl"].sum()
    dec = ok[ok["osl"] > 1]
    itl = (dec["lat_s"] - dec["ttft_s"]) / (dec["osl"] - 1)
    norm = ok["lat_s"] / ok["osl"].where(ok["osl"] > 0)
    good = ok["ttft_s"] <= slo
    col = {
        "completed": len(ok),
        "duration_s": duration,
        "input_tput": in_tok / duration,
        "output_tput": out_tok / duration,
        "total_tput": (in_tok + out_tok) / duration,
        "goodput_output_tput": ok.loc[good, "osl"].sum() / duration,
        "turn_slo_share_pct": 100 * good.sum() / max(len(ok) + errors, 1),
    }
    for k in ("input", "output", "total"):
        col[f"{k}_tput_per_gpu"] = col[f"{k}_tput"] / num_gpus
        if cost:
            col[f"{k}_tokens_per_dollar"] = col[f"{k}_tput_per_gpu"] * 3600 / cost
            col[f"{k}_cost_per_mtok"] = cost * 1e6 / (3600 * col[f"{k}_tput_per_gpu"])
    for name, p in PCTS.items():
        col[f"{name}_intvty"] = 1 / pct(itl, p)
        col[f"{name}_ttft_s"] = pct(ok["ttft_s"], p)
        col[f"{name}_e2el_s"] = pct(ok["lat_s"], p)
        col[f"{name}_e2e_norm_intvty"] = 1 / pct(norm, p)
    return {prefix + k: v for k, v in col.items()}


def analyze_point(d: Path, out: Path, cost: float | None, slo: float, skip_minutes: float = 5.0) -> dict:
    meta_path = d / "meta" / "point.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    finish_path = d / "meta" / "finish.json"
    finish = json.loads(finish_path.read_text()) if finish_path.exists() else {}
    art = d / "aiperf_artifacts"
    pj = json.loads((art / "profile_export_aiperf.json").read_text())
    df = load_records(art / "profile_export.jsonl")
    conc = int(meta.get("concurrency") or d.name.lstrip("c"))
    num_gpus = int(meta.get("num_gpus") or 1)
    pods = {netloc(u) for u in str(meta.get("server_metrics_urls", "")).split()}

    prof = df[df["phase"] == "profiling"]
    ok = prof[prof["err_type"].isna() & ~prof["cancelled"] & prof["start_ns"].notna() & prof["end_ns"].notna()]
    ok = ok[ok["lat_s"].notna() & ok["osl"].notna()]
    t0 = int(ok["start_ns"].min())
    duration = (ok["end_ns"].max() - t0) / 1e9
    in_tok = ok["isl"].sum()
    # Steady state: requests started after the ramp. The 300 s per-tree idle cap
    # releases lanes still waiting out recorded first-request gaps at minute 5, so
    # the first minutes run far below c and their fast requests bias whole-run
    # percentiles at high c (lane-20m c=32: p50 tok/s/user 43.7 whole run, 7.7 after).
    ss_from = t0 + int(skip_minutes * 60e9)
    ok_ss = ok[ok["start_ns"] >= ss_from]
    errors_ss = int((prof["err_type"].notna() & (prof["start_ns"] >= ss_from)).sum())

    md = pj.get("metadata", {}) or {}
    reasons = list(md.get("submission_invalid_reasons") or []) + list(pj.get("runtime_submission_invalid_reasons") or [])
    overflow = metric(pj, "context_overflow_count") or 0.0
    skipped = metric(pj, "skipped_context_overflow_count") or 0.0
    errors = prof["err_type"].notna().sum()

    row = {
        "label": meta.get("label", d.parent.name),
        "conc": conc,
        "num_gpus": num_gpus,
        "mode": meta.get("mode"),
        "job_status": finish.get("job_status"),
        "pod_changed": finish.get("pod_changed"),
        "submission_valid": md.get("submission_valid"),
        "invalid_reasons": ";".join(sorted(set(reasons))),
        "errors": int(errors),
        "error_types": ";".join(f"{k}:{v}" for k, v in prof["err_type"].value_counts().items()),
        "cancelled": int(prof["cancelled"].sum()),
        **phase_counts(art),
        "context_overflow": overflow,
        "overflow_rate_pct": 100 * overflow / max(len(ok) + errors + skipped, 1),
        "warmup_requests": int((df["phase"] == "warmup").sum()),
        "lanes_seen": int(ok["root"].nunique()),
        **client_columns(ok, int(errors), num_gpus, cost, slo),
        "skip_minutes": skip_minutes,
        **client_columns(ok_ss, errors_ss, num_gpus, cost, slo, prefix="ss_"),
        "isl_median": ok["isl"].median(),
        "osl_median": ok["osl"].median(),
        "effective_conc_requests": ok["lat_s"].sum() / duration,
    }
    # Sessions = AgentX session trees (root + subagents). An error counts as an SLO miss.
    per_tree = ok.groupby("root")
    worst = per_tree["ttft_s"].max()
    turns = per_tree.size()
    row["session_worst_ttft_p90_s"] = pct(worst, 90)
    row["sessions_worst_ttft_over_slo_pct"] = 100 * (worst > slo).mean() if len(worst) else None
    row["turns_per_session_p10"], row["turns_per_session_p50"], row["turns_per_session_p90"] = (
        pct(turns, q) for q in (10, 50, 90))
    row["ttft_slo_s"] = slo
    row["theoretical_hit_pct"] = metric(pj, "theoretical_prefix_cache_hit")
    row["usage_cache_read_pct"] = 100 * ok["cached"].sum() / in_tok if ok["cached"].notna().any() else None

    parquet = art / "server_metrics_export.parquet"
    pool = None
    if parquet.exists():
        pq = load_server(parquet, pods)
        src = counter_total(pq, "vllm:prompt_tokens_by_source", by="source")
        denom = sum(src.values())
        if denom:
            row["gpu_hit_pct"] = 100 * src.get("local_cache_hit", 0) / denom
            row["cpu_hit_pct"] = 100 * src.get("external_kv_transfer", 0) / denom
            row["recompute_pct"] = 100 * src.get("local_compute", 0) / denom
            row["overall_hit_pct"] = row["gpu_hit_pct"] + row["cpu_hit_pct"]
        hits, queries = (counter_total(pq, f"vllm:prefix_cache_{k}") for k in ("hits", "queries"))
        row["prefix_hits_over_queries_pct"] = 100 * hits / queries if queries else None
        row["preemptions"] = counter_total(pq, "vllm:num_preemptions")
        row["srv_prompt_tput"] = counter_total(pq, "vllm:prompt_tokens") / duration
        row["srv_generation_tput"] = counter_total(pq, "vllm:generation_tokens") / duration
        kv = gauge_stats(pq, "vllm:kv_cache_usage_perc")
        if not kv.empty:
            row["kv_usage_avg_pct"] = 100 * kv["avg"].mean()
            row["kv_usage_max_pct"] = 100 * kv["max"].max()
            row["kv_usage_skew_pct"] = 100 * (kv["avg"].max() - kv["avg"].min())
        for g in ("running", "waiting"):
            d = gauge_stats(pq, f"vllm:num_requests_{g}")
            if not d.empty:
                row[f"{g}_avg_sum"] = d["avg"].sum()
                row[f"{g}_max_pod"] = d["max"].max()
        gen_by_pod = counter_by_pod(pq, "vllm:generation_tokens")
        for h in ("request_queue_time_seconds", "request_prefill_time_seconds", "request_decode_time_seconds"):
            tot = counter_total(pq, f"vllm:{h}", col="sum")
            cnt = counter_total(pq, f"vllm:{h}", col="count")
            row[f"engine_{h.removesuffix('_seconds')}_avg_s"] = tot / cnt if cnt else None
        wr = gauge_stats(pq, "vllm:num_requests_waiting_by_reason", by="reason")
        if not wr.empty:
            for _, w in wr.iterrows():
                row[f"waiting_{w['reason']}_share_pct"] = 100 * w["avg"] / wr["avg"].sum() if wr["avg"].sum() else None
        if denom and gen_by_pod:
            row["prefill_compute_per_output_token"] = src.get("local_compute", 0) / sum(gen_by_pod.values())
        src_ss = counter_total(pq, "vllm:prompt_tokens_by_source", by="source", since_ns=ss_from)
        if sum(src_ss.values()):
            row["ss_gpu_hit_pct"] = 100 * src_ss.get("local_cache_hit", 0) / sum(src_ss.values())
            row["ss_cpu_hit_pct"] = 100 * src_ss.get("external_kv_transfer", 0) / sum(src_ss.values())
            row["ss_overall_hit_pct"] = 100 * (src_ss.get("local_cache_hit", 0) + src_ss.get("external_kv_transfer", 0)) / sum(src_ss.values())
            row["ss_recompute_pct"] = 100 * src_ss.get("local_compute", 0) / sum(src_ss.values())
        kv_ss = gauge_stats(pq, "vllm:kv_cache_usage_perc", since_ns=ss_from)
        if not kv_ss.empty:
            row["ss_kv_usage_avg_pct"] = 100 * kv_ss["avg"].mean()
        for g in ("running", "waiting"):
            g_ss = gauge_stats(pq, f"vllm:num_requests_{g}", since_ns=ss_from)
            if not g_ss.empty:
                row[f"ss_{g}_avg_sum"] = g_ss["avg"].sum()
        cfg, _ = series(pq, "vllm:cache_config_info")
        if not cfg.empty and "kv_cache_size_tokens" in cfg:
            sizes = pd.to_numeric(cfg.groupby("pod")["kv_cache_size_tokens"].first(), errors="coerce")
            if len(sizes) and sizes.notna().all():
                pool = int(sizes.sum())
                row["kv_pool_tokens"] = pool

    fl = inflight(ok, t0)
    row["effective_sessions_inflight"] = fl["sessions"].mean()
    row["inflight_unique_tokens_max"] = fl["unique_tokens"].max()
    row["working_set_mean"] = fl["working_set"].mean()
    row["working_set_max"] = fl["working_set"].max()
    if pool:
        row["inflight_unique_over_pool_max"] = fl["unique_tokens"].max() / pool
        row["working_set_over_pool_mean"] = fl["working_set"].mean() / pool
        row["working_set_over_pool_max"] = fl["working_set"].max() / pool
    if parquet.exists():
        row.update(engine_steps(parquet, pods))
    epp_path = art.parent / "epp" / "raw-epp-metrics.txt.gz"  # d is reused for DataFrames above
    row["epp_scraped"] = epp_path.exists()
    if epp_path.exists():
        row.update(epp_columns(load_epp(epp_path), t0 / 1e9, ok["end_ns"].max() / 1e9))
    return row


def engine_step_bins(parquet: Path, pods: set[str], bin_s: int = 10) -> pd.DataFrame:
    """Per pod and bin: steps, iteration tokens, generated tokens, from counter deltas.

    Only bins where the pod had running requests at every scrape are kept, so idle
    time is not mistaken for slow steps. Columns T_ms and prefill_k (k prefill tokens
    per step), t_s (bin start, seconds since the first scrape), and impossible: more
    prefill per step than MAX_BATCHED_TOKENS. Seen once on lane-20m/c16 (run as try-lane-c16-20m) (10 steps,
    217k tokens after a 20 s stretch with almost no steps): the step histogram lagged
    and caught up in one bin, most likely while the vLLM frontend was busy.
    """
    pq = read_server(parquet, columns=["endpoint_url", "metric_name", "timestamp_ns", "value", "sum", "count"],
                     metrics=["vllm:iteration_tokens_total", "vllm:generation_tokens", "vllm:num_requests_running"])
    pq = pq[pq["endpoint_url"].map(netloc).isin(pods)].copy()
    pq["pod"] = pq["endpoint_url"].map(netloc)
    pq["b"] = (pq["timestamp_ns"] - pq["timestamp_ns"].min()) // int(bin_s * 1e9)

    def per_bin(name: str, col: str) -> pd.Series:
        d = pq[pq["metric_name"] == name].groupby(["pod", "timestamp_ns", "b"])[col].first().reset_index()
        last = d.sort_values("timestamp_ns").groupby(["pod", "b"])[col].last()
        return last.groupby(level="pod").diff()

    df = pd.DataFrame({
        "steps": per_bin("vllm:iteration_tokens_total", "count"),
        "tokens": per_bin("vllm:iteration_tokens_total", "sum"),
        "gen": per_bin("vllm:generation_tokens", "value"),
        "running_min": pq[pq["metric_name"] == "vllm:num_requests_running"].groupby(["pod", "b"])["value"].min(),
    }).dropna()
    df = df[(df["steps"] > 0) & (df["running_min"] > 0)].copy()
    df["T_ms"] = 1000 * bin_s / df["steps"]
    df["B"] = df["gen"] / df["steps"]
    df["prefill_k"] = (df["tokens"] - df["gen"]) / df["steps"] / 1000
    df["t_s"] = df.index.get_level_values("b") * bin_s
    df["impossible"] = df["prefill_k"] > MAX_BATCHED_TOKENS / 1000
    return df


def engine_steps(parquet: Path, pods: set[str], bin_s: int = 10) -> dict:
    """Engine step metrics (BENCHMARK-METRICS 2.3): output throughput = B / T,
    B decoding requests per step, T step time; fit T = a + b x (k prefill tokens per step)."""
    df = engine_step_bins(parquet, pods, bin_s)
    dropped = int(df["impossible"].sum()) if not df.empty else 0
    df = df[~df["impossible"]] if not df.empty else df
    if df.empty:
        return {}
    out = {
        "busy_bins": len(df),
        "step_bins_dropped": dropped,
        "batch_B": df["gen"].sum() / df["steps"].sum(),
        "prefill_tokens_per_step": 1000 * (df["prefill_k"] * df["steps"]).sum() / df["steps"].sum(),
        "step_time_T_ms": 1000 * bin_s * len(df) / df["steps"].sum(),
    }
    if len(df) >= 10 and df["prefill_k"].std() > 0:
        b, a = np.polyfit(df["prefill_k"], df["T_ms"], 1)
        pred = a + b * df["prefill_k"]
        ss = ((df["T_ms"] - df["T_ms"].mean()) ** 2).sum()
        out.update({"step_fit_a_ms": a, "step_fit_b_ms_per_k": b,
                    "step_fit_r2": 1 - ((df["T_ms"] - pred) ** 2).sum() / ss if ss else None})
    return out


def checks(r: pd.Series) -> list[str]:
    out = []
    if r.get("pod_changed") is True:
        out.append("a vLLM or EPP pod was replaced or restarted during the run: INVALID")
    if r.get("job_status") == "failed":
        out.append("the aiperf job failed (see bench-stdout.log)")
    if r.get("submission_valid") is False:
        out.append(f"submission_valid=false ({r.get('invalid_reasons')})")
    if r.get("errors", 0) > 0:
        out.append(f"{r['errors']} errors ({r.get('error_types')})")
    if r.get("overflow_rate_pct", 0) > 1:
        out.append(f"context overflow {r['overflow_rate_pct']:.2f}% > 1%")
    if r.get("cancelled", 0) > 0:
        out.append(f"{r['cancelled']} requests cancelled when the grace period ended (not in the exports)")
    th, hit = r.get("theoretical_hit_pct"), r.get("overall_hit_pct")
    if pd.notna(th) and pd.notna(hit) and th - hit > 10:
        out.append(f"server hit {hit:.1f}% is {th - hit:.1f} points below theoretical {th:.1f}%")
    if pd.notna(r.get("inflight_unique_over_pool_max")) and r["inflight_unique_over_pool_max"] > 1:
        out.append(f"in-flight working set peaked at {r['inflight_unique_over_pool_max']:.2f}x the KV pool")
    if pd.notna(r.get("working_set_over_pool_max")) and r["working_set_over_pool_max"] > 1:
        out.append(f"working set peaked at {r['working_set_over_pool_max']:.2f}x the KV pool (expect evictions)")
    if pd.notna(hit) and hit > 85 and pd.notna(r.get("kv_usage_max_pct")) and r["kv_usage_max_pct"] < 80:
        out.append("light load: hit rate above 85% and KV peak below 80% (BENCHMARK-METRICS calibration rule)")
    if r.get("conc", 0) > 393:
        out.append("concurrency above the 393 traces: traces are reused across lanes (cache-bust keeps them distinct)")
    if r.get("mode") == "pool" and not r.get("epp_scraped"):
        out.append("no EPP metrics: router and gate behavior unknown")
    if pd.notna(r.get("gate_pauses")) and r.get("gate_pauses", 0) == 0 and r.get("gate_delayed_dispatches", 0) == 0:
        out.append("thunder gate never delayed or paused a session: it did not engage")
    if pd.notna(r.get("gate_starvation_promotions")) and r["gate_starvation_promotions"] > 0:
        out.append(f"{r['gate_starvation_promotions']:.0f} forced admissions: demand is past the pool's capacity")
    if pd.notna(r.get("epp_request_errors")) and r["epp_request_errors"] > 0:
        out.append(f"{r['epp_request_errors']:.0f} EPP request errors (see epp-*.log)")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("points", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("report"))
    ap.add_argument("--cost-per-gpu-hour", type=float, default=None)
    ap.add_argument("--label", default=None,
                    help="report every given point under this label (one curve), e.g. to join points run under different labels")
    ap.add_argument("--ttft-slo", type=float, default=60.0, help="TTFT SLO in seconds for goodput and session columns")
    ap.add_argument("--skip-minutes", type=float, default=5.0,
                    help="steady state starts this many minutes into profiling (ss_* columns, sweep figures); "
                         "default 5 = the agentx per-tree idle cap")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows, points = [], []
    for d in args.points:
        if not (d / "aiperf_artifacts" / "profile_export_aiperf.json").exists():
            print(f"skip {d}: no profile_export_aiperf.json")
            continue
        print(f"analyzing {d}")
        rows.append(analyze_point(d, args.out, args.cost_per_gpu_hour, args.ttft_slo, args.skip_minutes))
        if args.label:
            rows[-1]["label"] = args.label
        points.append(d)
    if not rows:
        raise SystemExit("no analyzable points")
    df = pd.DataFrame(rows).sort_values(["label", "conc"])
    df.to_csv(args.out / "summary.csv", index=False)
    spec = importlib.util.spec_from_file_location("point_figures", Path(__file__).resolve().parent / "point_figures.py")
    figures = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(figures)
    for d, r in zip(points, rows):
        if (d / "aiperf_artifacts" / "server_metrics_export.parquet").exists() and (d / "meta" / "point.json").exists():
            figures.draw_point(d, args.out / f"c{r['conc']}-{r['label']}")
    figures.pareto(df, args.out, args.cost_per_gpu_hour)
    figures.concurrency(df, args.out)

    cols = ["label", "conc", "completed", "errors", "total_tput_per_gpu", "output_tput_per_gpu",
            "p90_intvty", "p90_ttft_s", "p90_e2el_s", "p90_e2e_norm_intvty", "overall_hit_pct",
            "theoretical_hit_pct", "kv_usage_avg_pct", "waiting_avg_sum", "preemptions",
            "goodput_output_tput", "working_set_over_pool_mean", "batch_B", "step_time_T_ms",
            "gate_delayed_dispatches", "gate_pauses", "gate_starvation_promotions", "epp_queue_wait_p90_s"]
    cols = [c for c in cols if c in df]
    lines = ["# AgentX sweep report", "", "## Whole profiling window (AgentX)", "",
             df[cols].to_markdown(index=False, floatfmt=".3g"), ""]
    ss_cols = ["label", "conc", "ss_completed", "ss_total_tput_per_gpu", "ss_output_tput_per_gpu", "ss_p50_intvty",
               "ss_p90_intvty", "ss_p50_ttft_s", "ss_p90_ttft_s", "ss_goodput_output_tput", "ss_overall_hit_pct",
               "ss_kv_usage_avg_pct", "ss_waiting_avg_sum"]
    ss_cols = [c for c in ss_cols if c in df]
    if len(ss_cols) > 2:
        lines += [f"## Steady state: requests started after minute {args.skip_minutes:g} (sweep figures use these)", "",
                  df[ss_cols].to_markdown(index=False, floatfmt=".3g"), ""]
    lines += ["## Validity checks", ""]
    for _, r in df.iterrows():
        problems = checks(r)
        lines.append(f"- {r['label']} c={r['conc']}: " + ("; ".join(problems) if problems else "ok"))
    (args.out / "summary.md").write_text("\n".join(lines) + "\n")
    print((args.out / "summary.md").read_text())


if __name__ == "__main__":
    main()
