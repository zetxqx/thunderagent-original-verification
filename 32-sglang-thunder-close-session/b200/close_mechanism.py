# /// script
# dependencies = ["pandas", "pyarrow"]
# ///
"""Per-request cache analysis for the 1h points (usage: close_mechanism.py <results> <conc>).

- token-weighted hit from per-request usage (profiling, steady state after minute 5)
- per-pod server-side hit from parquet counters (profiling window, EPP-proxied series excluded)
- close arm: turns that follow a release_session of their own session vs all other turns
"""
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pyarrow.dataset as ds

R = Path(sys.argv[1])
C = sys.argv[2] if len(sys.argv) > 2 else "48"
ARMS = ["sglang-baseline-lru-1h", "sglang-thunder-close-1h"]


def load_records(arm):
    rows = []
    with open(R / arm / f"c{C}/aiperf_artifacts/profile_export.jsonl") as f:
        for line in f:
            d = json.loads(line)
            md, m = d["metadata"], d.get("metrics", {})
            if md.get("benchmark_phase") != "profiling" or md.get("was_cancelled"):
                continue
            g = lambda k: (m.get(k) or {}).get("value")
            rows.append(dict(
                corr=md["x_correlation_id"], conv=md["conversation_id"], root=md.get("root_correlation_id"),
                turn=md["turn_index"], start=md["request_start_ns"], end=md["request_end_ns"],
                isl=g("input_sequence_length"), cached=g("usage_prompt_cache_read_tokens"),
                ttft=g("time_to_first_token")))
    df = pd.DataFrame(rows)
    df["cached"] = df["cached"].fillna(0)
    t0 = df["start"].min()
    df["t"] = (df["start"] - t0) / 1e9
    return df


def server_hit(arm):
    p = R / arm / f"c{C}/aiperf_artifacts/server_metrics_export.parquet"
    t = ds.dataset(p).to_table(columns=["endpoint_url", "metric_name", "timestamp_ns", "value"],
                               filter=ds.field("metric_name").isin(["sglang:cached_tokens_total", "sglang:prompt_tokens_total",
                                                                    "sglang:cached_tokens", "sglang:prompt_tokens"])).to_pandas()
    t = t[~t["endpoint_url"].str.contains("epp")]
    out = {}
    for (ep, mname), g in t.groupby(["endpoint_url", "metric_name"]):
        s = g.groupby("timestamp_ns")["value"].sum().sort_index()
        out[(ep, mname.removesuffix("_total"))] = s.iloc[-1] - s.iloc[0]
    res = {}
    for ep in sorted({k[0] for k in out}):
        c, p_ = out.get((ep, "sglang:cached_tokens"), 0), out.get((ep, "sglang:prompt_tokens"), 0)
        res[ep] = (c, p_)
    return res


def releases(arm):
    ev = []
    for f in (R / "streams").glob(f"{arm}-c{C}-*.log"):
        for line in open(f):
            if "TP0]" in line and "release_session" in line:
                m = re.match(r"\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) TP0\] release_session (\S+): indexed (\d+)", line)
                if m:
                    ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
                    ev.append(dict(ts_ns=int(ts * 1e9), sid=m.group(2), indexed=int(m.group(3))))
    return pd.DataFrame(ev)


for arm in ARMS:
    df = load_records(arm)
    ss = df[df["t"] >= 300]
    print(f"\n=== {arm}")
    print(f"profiling requests {len(df)}, steady-state {len(ss)}; request-weighted hit (ss) "
          f"{100 * ss['cached'].sum() / ss['isl'].sum():.2f}%  uncached tokens/request (ss) {(ss['isl'] - ss['cached']).mean():,.0f}")
    for ep, (c, p) in server_hit(arm).items():
        print(f"  server {ep}: cached {c / 1e6:.1f}M / prompt {p / 1e6:.1f}M = {100 * c / p:.2f}%")
    # Turns that arrive with less than 50% of their prompt cached ("cold" turns)
    ss = ss.assign(hit=ss["cached"] / ss["isl"])
    print(f"  cold turns (hit<50%, turn>0): {((ss['hit'] < 0.5) & (ss['turn'] > 0)).sum()}  "
          f"uncached tokens in them {((ss['isl'] - ss['cached'])[(ss['hit'] < 0.5) & (ss['turn'] > 0)]).sum() / 1e6:.1f}M "
          f"of {(ss['isl'] - ss['cached']).sum() / 1e6:.1f}M")

    rel = releases(arm)
    if not rel.empty:  # stream files outlived their point; keep this arm's window only
        rel = rel[rel["ts_ns"].between(df["start"].min() - 600e9, df["end"].max())]
    print(f"  release_session events in window: {len(rel)}")
    if rel.empty:
        continue
    keys = {k: set(df[k].astype(str)) for k in ("corr", "conv", "root")}
    hits = {k: rel["sid"].isin(v).sum() for k, v in keys.items()}
    print(f"  release_session events {len(rel)} (indexed>0: {(rel['indexed'] > 0).sum()}); session id matches: {hits}")
    key = max(hits, key=hits.get)
    df = df.sort_values("start")
    nxt = []
    for _, e in rel.iterrows():
        g = df[(df[key].astype(str) == e["sid"]) & (df["start"] >= e["ts_ns"] - 1e9)]
        if len(g):
            r = g.iloc[0]
            nxt.append(dict(idx=r.name, gap_s=(r["start"] - e["ts_ns"]) / 1e9, indexed=e["indexed"]))
    nx = pd.DataFrame(nxt).drop_duplicates("idx")
    after = df.loc[nx["idx"]]
    after = after[after["t"] >= 300]
    rest = df[(df["t"] >= 300) & ~df.index.isin(nx["idx"]) & (df["turn"] > 0)]
    print(f"  first turn after a release (ss): n={len(after)}, hit {100 * after['cached'].sum() / after['isl'].sum():.1f}%, "
          f"uncached/turn {(after['isl'] - after['cached']).mean():,.0f}, TTFT p50 {after['ttft'].median() / 1e3:.2f}s p90 {after['ttft'].quantile(.9) / 1e3:.2f}s")
    print(f"  all other turns>0 (ss):      n={len(rest)}, hit {100 * rest['cached'].sum() / rest['isl'].sum():.1f}%, "
          f"uncached/turn {(rest['isl'] - rest['cached']).mean():,.0f}, TTFT p50 {rest['ttft'].median() / 1e3:.2f}s p90 {rest['ttft'].quantile(.9) / 1e3:.2f}s")
    print(f"  gap release->next turn: p50 {nx['gap_s'].median():.0f}s p90 {nx['gap_s'].quantile(.9):.0f}s; "
          f"extra uncached tokens from post-release turns ~{((after['isl'] - after['cached']).sum() - len(after) * (rest['isl'] - rest['cached']).mean()) / 1e6:.1f}M")

print("\n=== hit by idle gap since the same session's previous request ended (steady state, turn>0)")
bins = [-1e9, 5, 30, 60, 120, 300, 1e9]
labels = ["<5s", "5-30s", "30-60s", "60-120s", "120-300s", ">300s"]
tab = {}
for arm in ARMS:
    df = load_records(arm).sort_values("start")
    df["prev_end"] = df.groupby("corr")["end"].shift()
    df["gap"] = (df["start"] - df["prev_end"]) / 1e9
    d = df[(df["t"] >= 300) & df["gap"].notna()].copy()
    d["b"] = pd.cut(d["gap"], bins, labels=labels)
    g = d.groupby("b", observed=False).apply(lambda x: pd.Series({
        "n": len(x), "hit%": 100 * x["cached"].sum() / max(x["isl"].sum(), 1),
        "uncached_M": (x["isl"] - x["cached"]).sum() / 1e6}), include_groups=False)
    tab[arm] = g
print(pd.concat(tab, axis=1).round(1).to_string())
