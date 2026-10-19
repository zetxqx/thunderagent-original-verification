# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas"]
# ///
"""Router (EPP) metrics: the gate's counters and ledger, the flow-control queue.

Parses the raw-epp-metrics.txt.gz scrape written by epp_scrape.py and turns it into
summary columns (gate_*, epp_*) and validity checks. analyze.py, point_figures.py and
export_bundle.py all read the metric names from here.

The gate's metric prefix is the only router-specific name. It defaults to the
thunder-agent plugin of llm-d (llm_d_epp_thunder_agent_) and can be set with the
environment variable GATE_METRIC_PREFIX for another admission-control plugin that
exports the same counters (delayed_dispatches, pauses, resumes, releases,
starvation_promotions, endpoint_working_set_tokens, endpoint_capacity_tokens).
Columns whose counters are absent are simply left out.
"""

import gzip
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

GATE = os.environ.get("GATE_METRIC_PREFIX", "llm_d_epp_thunder_agent_")
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
    try:
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
    except EOFError:
        # A copy cut short (run-point.sh warns "did not copy completely") ends mid-stream;
        # keep the snapshots read so far instead of failing the whole report.
        print(f"WARNING: {path} is truncated; using the snapshots before the cut")
    return pd.DataFrame(rows, columns=["ts", "url", "metric", "labels", "value"])


def epp_window(epp: pd.DataFrame, metric: str, t0: float, t1: float) -> pd.DataFrame:
    """Snapshots of one metric inside [t0, t1], starting from the last snapshot
    at or before t0 so a counter delta covers the whole window."""
    d = epp[epp["metric"] == metric]
    before = d.loc[d["ts"] <= t0, "ts"]
    lo = before.max() if len(before) else t0
    return d[(d["ts"] >= lo) & (d["ts"] <= t1)]


def epp_increase(epp: pd.DataFrame, metric: str, t0: float, t1: float) -> pd.Series:
    """Increase of every series of a counter from t0 to t1. Per-flow series (one per
    session) appear with their first request, so a series first seen after t0 starts
    from 0; taking its first value in the window as the base dropped that request
    (thunder c32: 1132 of 1298 queue waits counted, non-monotonic histogram buckets)."""
    d = epp[(epp["metric"] == metric) & (epp["ts"] <= t1)].sort_values("ts")
    if d.empty:
        return pd.Series(dtype=float)
    last = d.groupby(["url", "labels"])["value"].last()
    base = d[d["ts"] <= t0].groupby(["url", "labels"])["value"].last()
    return (last - base.reindex(last.index).fillna(0)).clip(lower=0)


def epp_delta(epp: pd.DataFrame, metric: str, t0: float, t1: float) -> float:
    inc = epp_increase(epp, metric, t0, t1)
    return float(inc.sum()) if len(inc) else float("nan")


def epp_gauge(epp: pd.DataFrame, metric: str, t0: float, t1: float) -> pd.Series:
    """A gauge summed over its series (pods, flows) per snapshot."""
    d = epp_window(epp, metric, t0, t1)
    return d.groupby("ts")["value"].sum()


def epp_hist_buckets(epp: pd.DataFrame, base: str, t0: float, t1: float) -> pd.Series:
    """Cumulative count at or below each bucket bound (le) over the window, summed across series."""
    inc = epp_increase(epp, base + "_bucket", t0, t1)
    if inc.empty:
        return pd.Series(dtype=float)
    le = inc.index.get_level_values("labels").str.extract(r'le="([^"]+)"')[0].astype(float).to_numpy()
    return inc.groupby(le).sum().sort_index()


def epp_hist_quantile(cum: pd.Series, q: float) -> float | None:
    """Quantile from cumulative bucket counts, interpolated linearly inside the bucket.
    None when it lies above the largest finite bound: the histogram cannot tell how far
    (the EPP queue-duration histogram stops at 60 s, gate holds last up to 1800 s)."""
    if cum.empty or not cum.iloc[-1]:
        return None
    rank, prev_le, prev_c = q * cum.iloc[-1], 0.0, 0.0
    for le, c in cum.items():
        if c >= rank:
            if np.isinf(le):
                return None
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
    cum = epp_hist_buckets(epp, EPP_QUEUE, t0, t1)
    out["epp_queue_wait_p90_s"] = epp_hist_quantile(cum, 0.9)
    out["epp_queue_wait_p99_s"] = epp_hist_quantile(cum, 0.99)
    finite = cum[~np.isinf(cum.index)] if len(cum) else cum
    if len(finite) and cum.iloc[-1]:
        out["epp_queue_wait_top_bucket_s"] = float(finite.index[-1])
        out["epp_queue_wait_over_top_bucket_pct"] = 100 * (1 - finite.iloc[-1] / cum.iloc[-1])
    qs = epp_gauge(epp, "llm_d_epp_flow_control_queue_size", t0, t1)
    out["epp_queue_size_mean"], out["epp_queue_size_max"] = (qs.mean(), qs.max()) if len(qs) else (None, None)
    ws = epp_gauge(epp, GATE + "endpoint_working_set_tokens", t0, t1)
    cap = epp_gauge(epp, GATE + "endpoint_capacity_tokens", t0, t1)
    if len(ws) and len(cap) and cap.mean():
        out["gate_working_set_over_capacity_mean"] = ws.mean() / cap.mean()
        out["gate_working_set_over_capacity_max"] = (ws / cap.reindex(ws.index)).max()
    return out


def checks(r: pd.Series) -> list[str]:
    """Validity lines about the router and gate for one summary row."""
    out = []
    if r.get("mode") == "pool" and not r.get("epp_scraped"):
        out.append("no EPP metrics: router and gate behavior unknown")
    if pd.notna(r.get("gate_pauses")) and r.get("gate_pauses", 0) == 0 and r.get("gate_delayed_dispatches", 0) == 0:
        out.append("the gate never delayed or paused a session: it did not engage")
    if pd.notna(r.get("gate_starvation_promotions")) and r["gate_starvation_promotions"] > 0:
        out.append(f"{r['gate_starvation_promotions']:.0f} forced admissions: demand is past the pool's capacity")
    if pd.notna(r.get("epp_request_errors")) and r["epp_request_errors"] > 0:
        out.append(f"{r['epp_request_errors']:.0f} EPP request errors (see epp-*.log)")
    return out
