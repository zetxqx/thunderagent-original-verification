# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pandas", "pyarrow", "matplotlib", "tabulate", "pyyaml"]
# ///
"""Export benchmark points to one JSON bundle for the dashboard (repo root dashboard/).

  uv run export_bundle.py --out ../dashboard/data/step24.json --title "Step 24: thunder PR3 lanes" \
      --baseline baseline-60m --name baseline-60m="no router" --name thunder-60m="thunder gate (PR3)" \
      <step>/results/<label>/c<N> [...]

Per point: the analyze.py summary row (same numbers as summary.csv) and its validity
checks, time series binned to 30 or 60 s, latency and length distributions as quantiles,
TTFT SLO curves, and the configuration read from meta/ (client command, vLLM image,
args and KV cache, router image and plugin config, envoy timeouts).
The format is in dashboard/SCHEMA.md. Points are read one at a time, so memory stays at
one point's peak. The bundle is added to index.json next to --out, which the dashboard
lists when it is served over HTTP.
"""

import argparse
import importlib.util
import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
SCHEMA = "agentic-bench/1"
QUANTILES = np.linspace(0, 100, 201)
SLO_TARGETS = np.geomspace(0.1, 3600, 121)
# aiperf flags that change with every point; the dashboard compares the rest across arms.
POINT_FLAGS = {"--url", "--concurrency", "--server-metrics", "--output-artifact-dir"}


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


a23 = _module("analyze")
pf = _module("point_figures")


def num(x, sig: int = 4):
    """JSON number with sig significant digits; None for missing or non-finite values."""
    if x is None or isinstance(x, (bool, np.bool_)):
        return None if x is None else bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return float(f"{x:.{sig}g}") if np.isfinite(x) else None


def ser(t, v) -> dict | None:
    t, v = np.asarray(t, float), np.asarray(v, float)
    keep = np.isfinite(t) & np.isfinite(v)
    if not keep.any():
        return None
    return {"t": [num(x) for x in t[keep]], "v": [num(x) for x in v[keep]]}


def bin_mean(t_min, v, bin_s: int) -> dict | None:
    s = pd.Series(np.asarray(v, float))
    g = s.groupby((np.asarray(t_min, float) * 60 // bin_s).astype(int)).mean()
    return ser((g.index + 0.5) * bin_s / 60, g.values)


def gauge(pq: pd.DataFrame, name: str, how: str = "sum", scale: float = 1.0, bin_s: int = 30) -> dict | None:
    """A vLLM gauge per bin: mean per pod, then summed (or averaged) over pods."""
    s, _ = a23.series(pq, name)
    if s.empty:
        return None
    per_pod = s.assign(b=(s["t"] * 60 // bin_s).astype(int)).groupby(["pod", "b"])["value"].mean()
    g = per_pod.groupby(level="b").sum() if how == "sum" else per_pod.groupby(level="b").mean()
    return ser((g.index + 0.5) * bin_s / 60, scale * g.values)


def client_series(ok: pd.DataFrame, t0: int) -> dict:
    """Per minute of request end: TTFT p50/p90 and tok/s/user p50 and p90 (slowest 10%)."""
    g = ok.groupby((((ok["end_ns"] - t0) / 60e9) // 1).astype(int))
    x = g.size().index + 0.5
    return {
        "ttft_p50_s": ser(x, g["ttft_s"].quantile(0.5)),
        "ttft_p90_s": ser(x, g["ttft_s"].quantile(0.9)),
        "intvty_p50": ser(x, g["intv"].quantile(0.5)),
        "intvty_p90": ser(x, g["intv"].quantile(0.1)),
        "completed_per_min": ser(x, g.size()),
    }


def server_series(d: dict) -> dict:
    pq, out = d["pq"], {}
    out["vllm_running"] = gauge(pq, "vllm:num_requests_running")
    out["vllm_waiting"] = gauge(pq, "vllm:num_requests_waiting")
    out["kv_usage_pct"] = gauge(pq, "vllm:kv_cache_usage_perc", how="mean", scale=100)
    for key, name in (("input_tps", "vllm:prompt_tokens"), ("output_tps", "vllm:generation_tokens")):
        r = pf.counter_rate(pq, name, bin_s=60)
        out[key] = ser(r.index + 0.5, r["value"] / 60) if not r.empty else None
    src = pf.counter_rate(pq, "vllm:prompt_tokens_by_source", bin_s=60, by="source").fillna(0)
    if not src.empty:
        share = 100 * src.div(src.sum(axis=1).replace(0, np.nan), axis=0)
        for key, col in (("src_gpu_hit_pct", "local_cache_hit"), ("src_cpu_hit_pct", "external_kv_transfer"),
                         ("src_computed_pct", "local_compute")):
            if col in share and share[col].sum() > 0:
                out[key] = ser(share.index + 0.5, share[col])
        if "local_compute" in src:
            out["prefill_computed_tps"] = ser(src.index + 0.5, src["local_compute"] / 60)
    for key, name in (("vllm_queue_time_s", "vllm:request_queue_time_seconds"),
                      ("vllm_prefill_time_s", "vllm:request_prefill_time_seconds")):
        m = pf.hist_mean_per_bin(pq, name, 60)
        out[key] = ser(m.index + 0.5, m.values) if len(m) else None
    st = d["steps"]
    if not st.empty:
        st = st[~st["impossible"]].copy()
        st["m"] = (st["t"] // 1).astype(int)
        per_min = st.groupby("m").agg(n=("steps", "size"), steps=("steps", "sum"))
        out["ms_per_output_token"] = ser(per_min.index + 0.5, 10_000 * per_min["n"] / per_min["steps"])
    return out


def gate_series(d: dict, epp: pd.DataFrame, bin_s: int = 60) -> dict:
    """EPP gate counters per minute, flow-control queue, gate ledger, mean router wait (as fig_gate)."""
    t0 = d["t0"] / 1e9
    e = epp[epp["ts"] >= t0 - bin_s].copy()
    if e.empty:
        return {}
    e["t"] = (e["ts"] - t0) / 60
    out = {}
    for col, names in a23.GATE_COUNTERS.items():
        x = next((e[e["metric"] == n] for n in names if (e["metric"] == n).any()), None)
        if x is None:
            continue
        x = x.sort_values("ts")
        inc = x.groupby(["url", "labels"])["value"].diff().clip(lower=0)
        r = inc.groupby((x["t"] * 60 // bin_s).astype(int)).sum().iloc[1:]
        out[f"{col}_per_min"] = ser((r.index + 0.5) * bin_s / 60, r.values * 60 / bin_s)
    qs = e[e["metric"] == "llm_d_epp_flow_control_queue_size"].groupby("t")["value"].sum()
    out["epp_queue_size"] = bin_mean(qs.index, qs.values, 30) if len(qs) else None
    for key, metric in (("gate_working_set_tokens", a23.GATE + "endpoint_working_set_tokens"),
                        ("gate_capacity_tokens", a23.GATE + "endpoint_capacity_tokens")):
        s = e[e["metric"] == metric].groupby("t")["value"].sum()
        out[key] = bin_mean(s.index, s.values, 30) if len(s) else None
    s = e[e["metric"] == a23.EPP_QUEUE + "_sum"].groupby("ts")["value"].sum()
    c = e[e["metric"] == a23.EPP_QUEUE + "_count"].groupby("ts")["value"].sum()
    if len(s) and len(c):
        b = ((s.index - t0) // bin_s).astype(int)
        ds, dc = s.groupby(b).last().diff().clip(lower=0), c.groupby(b).last().diff().clip(lower=0)
        w = (ds / dc.where(dc > 0)).dropna()
        out["epp_wait_mean_s"] = ser((w.index + 0.5) * bin_s / 60, w.values)
    return out


def quantiles(v) -> list | None:
    v = pd.Series(v, dtype=float).dropna()
    return [num(x) for x in np.percentile(v, QUANTILES)] if len(v) else None


def distributions(ok: pd.DataFrame, errors: int) -> tuple[dict, dict]:
    dists = {
        "ttft_s": quantiles(ok["ttft_s"]),
        "worst_ttft_s": quantiles(ok.groupby("root")["ttft_s"].max()),
        "intvty": quantiles(ok["intv"]),
        "isl": quantiles(ok["isl"]),
        "osl": quantiles(ok["osl"]),
    }
    n, tokens = max(len(ok) + errors, 1), ok["osl"].sum()
    ttft = np.sort(ok["ttft_s"].to_numpy(float))
    slo = {
        "targets_s": [num(x) for x in SLO_TARGETS],
        "turns_pct": [num(100 * np.searchsorted(ttft, x, side="right") / n) for x in SLO_TARGETS],  # n includes misses without a record
        "goodput_pct": [num(100 * ok.loc[ok["ttft_s"] <= x, "osl"].sum() / tokens) if tokens else None
                        for x in SLO_TARGETS],
    }
    return dists, slo


def read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def container(doc: dict, pick) -> dict:
    for c in (doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers") or []):
        if pick(c):
            return c
    return {}


def aiperf_command(job: dict) -> tuple[str | None, dict]:
    c = container(job, lambda c: c.get("name") == "aiperf")
    text = " ".join(c.get("args") or [])
    m = re.search(r"aiperf profile .*?(?=\n\s*rc=|\Z)", text.replace("\\\n", " "), re.S)
    if not m:
        return None, {}
    cmd = " ".join(m.group(0).split())
    flags, key = {}, None
    for tok in shlex.split(cmd)[2:]:
        if tok.startswith("--"):
            key = tok
            flags[key] = ""
        elif key:
            flags[key] = (flags[key] + " " + tok).strip()
    return cmd, {k: v for k, v in flags.items() if k not in POINT_FLAGS}


def point_config(point: Path) -> dict:
    meta = point / "meta"
    cfg = {"point": json.loads((meta / "point.json").read_text()) if (meta / "point.json").exists() else {}}
    if (meta / "finish.json").exists():
        cfg["finish"] = json.loads((meta / "finish.json").read_text())

    job = read_yaml(meta / "job.yaml")
    cmd, flags = aiperf_command(job)
    client = container(job, lambda c: c.get("name") == "aiperf")
    cfg["client"] = {"image": client.get("image"), "command": cmd, "flags": flags,
                     "env": {e["name"]: e.get("value") for e in client.get("env") or [] if "name" in e}}

    vllm = read_yaml(meta / "vllm-deployment.yaml")
    c = container(vllm, lambda c: True)
    ms = {"image": c.get("image"), "command": (c.get("command") or []) + (c.get("args") or []),
          "resources": c.get("resources"), "replicas": vllm.get("spec", {}).get("replicas")}
    cache = next(iter(sorted(meta.glob("cache-config-*.txt"))), None)
    if cache:
        labels = dict(re.findall(r'(\w+)="([^"]*)"', cache.read_text()))
        ms["kv_cache"] = {k: labels[k] for k in ("kv_cache_size_tokens", "num_gpu_blocks", "block_size", "cache_dtype",
                                                 "gpu_memory_utilization", "kv_offloading_size",
                                                 "kv_offloading_backend", "num_cpu_blocks") if k in labels}
    cfg["model_server"] = ms

    epp = read_yaml(meta / "epp-deployment.yaml")
    if epp:
        c = container(epp, lambda c: "--config-file" in (c.get("args") or []))
        args = c.get("args") or []
        file = Path(args[args.index("--config-file") + 1]).name if "--config-file" in args else None
        cm = next(iter(sorted(meta.glob("epp-configmap-*-epp.yaml"))), None)
        plugins = (read_yaml(cm).get("data") or {}).get(file) if cm and file else None
        router = {"image": c.get("image"), "args": args, "config_file": file, "config": plugins}
        envoy_cm = next(iter(sorted(meta.glob("epp-configmap-*-envoy.yaml"))), None)
        if envoy_cm:
            text = envoy_cm.read_text()
            router["envoy"] = {
                "image": container(epp, lambda c: "envoy" in str(c.get("image"))).get("image"),
                "ext_proc_message_timeout": sorted(set(re.findall(r"message_timeout:\s*\"?([0-9.]+[a-z]*)", text))),
                "idle_timeouts": sorted(set(re.findall(r"idle_timeout:\s*\"?([0-9.]+[a-z]*)", text))),
            }
        cfg["router"] = router
    return cfg


def cpu_tier_tokens(config: dict, kv_bytes_per_token: int | None) -> int | None:
    """Tokens the CPU offload tier holds: --kv-offloading-size (GiB, summed over TP ranks)
    over the KV bytes per token. vLLM's offloading connector copies every computed block to
    CPU, so this is also about the most KV a pod can keep (not GPU plus CPU)."""
    size = (config.get("model_server", {}).get("kv_cache") or {}).get("kv_offloading_size")
    try:
        gib = float(size)
    except (TypeError, ValueError):
        return None
    return int(gib * 2**30 / kv_bytes_per_token) if kv_bytes_per_token and gib > 0 else None


def export_point(point: Path, slo: float, skip_minutes: float, replicate_suffix: str,
                 kv_bytes_per_token: int | None = None, arm_map: dict | None = None) -> dict:
    row = a23.analyze_point(point, point, None, slo, skip_minutes)
    checks = a23.checks(pd.Series(row))
    d = pf.load(point)
    ok, t0 = d["ok"], d["t0"]
    fl = d["fl"]
    series = {
        "client_requests": bin_mean(fl["t"] / 60, fl["requests"], 30),
        "client_sessions": bin_mean(fl["t"] / 60, fl["sessions"], 30),
        "inflight_tokens": bin_mean(fl["t"] / 60, fl["unique_tokens"], 30),
        "working_set_tokens": bin_mean(fl["t"] / 60, fl["working_set"], 30),
        **client_series(ok, t0),
        **server_series(d),
    }
    epp_path = point / "epp" / "raw-epp-metrics.txt.gz"
    if epp_path.exists():
        series.update(gate_series(d, a23.load_epp(epp_path)))

    recs = a23.load_records(point / "aiperf_artifacts" / "profile_export.jsonl")
    prof = recs[recs["phase"] == "profiling"]
    ss_from = t0 + int(skip_minutes * 60e9)
    errors_ss = int((prof["err_type"].notna() & (prof["start_ns"] >= ss_from)).sum())
    unserved = int(row.get("unserved") or 0)  # no first token by the end: SLO misses, as in analyze.py
    done = prof[prof["err_type"].isna() & ~prof["cancelled"] & prof["lat_s"].notna() & prof["trace"].notna()]
    whole, slo_whole = distributions(ok, d["errors"] + unserved)
    steady, slo_steady = distributions(ok[ok["start_ns"] >= ss_from], errors_ss + unserved)

    label = str(row["label"])
    m = re.search(replicate_suffix, label)
    arm = re.sub(replicate_suffix, "", label)
    arm = (arm_map or {}).get(arm, arm)
    summary = {k: (num(v, 6) if not isinstance(v, str) else v) for k, v in row.items()}
    config = point_config(point)
    return {
        "id": f"{label}/c{row['conc']}",
        "arm": arm,
        "conc": int(row["conc"]),
        "replicate": int(re.sub(r"\D", "", m.group(0))) if m and re.sub(r"\D", "", m.group(0)) else None,
        "duration_min": num(d["duration"] / 60),
        "kv_pool_tokens": d["pool"],
        "cpu_tier_tokens": cpu_tier_tokens(config, kv_bytes_per_token),
        "summary": summary,
        "turns_by_trace": {str(k): int(v) for k, v in done["trace"].value_counts().items()},
        "checks": checks,
        "config": config,
        "series": {k: v for k, v in series.items() if v},
        "dists": {"whole": whole, "steady": steady},
        "slo_curve": {"whole": slo_whole, "steady": slo_steady},
    }


def update_index(out: Path, title: str, created: str, n_points: int) -> None:
    index = out.parent / "index.json"
    entries = json.loads(index.read_text()) if index.exists() else []
    entries = [e for e in entries if e.get("file") != out.name]
    entries.append({"file": out.name, "title": title, "created_utc": created, "points": n_points})
    index.write_text(json.dumps(sorted(entries, key=lambda e: e["file"]), indent=1) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("points", nargs="+", type=Path, help="point directories <results>/<label>/c<N>")
    ap.add_argument("--out", type=Path, required=True, help="bundle file, e.g. dashboard/data/step24.json")
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", default="")
    ap.add_argument("--baseline", help="arm drawn in red and used for ratios")
    ap.add_argument("--name", action="append", default=[], help="ARM=TEXT display name")
    ap.add_argument("--arm", action="append", default=[],
                    help="LABEL=ARM: put a label's points into another arm, e.g. to join points of one setup "
                         "that ran under two labels into one curve (say why in --description)")
    ap.add_argument("--ttft-slo", type=float, default=60.0)
    ap.add_argument("--skip-minutes", type=float, default=5.0, help="steady state start, as in analyze.py")
    ap.add_argument("--replicate-suffix", default=r"-r\d+$", help="regex stripped from labels to group replicates")
    ap.add_argument("--kv-bytes-per-token", type=int, default=None,
                    help="KV cache bytes per token over all TP ranks, for the CPU tier size of offload points; "
                         "layers x 2 (K, V) x KV heads x head dim x dtype bytes, e.g. 49152 for "
                         "Qwen3-Coder-30B-A3B with an FP8 KV cache (48 x 2 x 4 x 128 x 1)")
    args = ap.parse_args()

    names = dict(n.split("=", 1) for n in args.name)
    arm_map = dict(a.split("=", 1) for a in args.arm)
    points = []
    for p in args.points:
        if not (p / "aiperf_artifacts" / "profile_export_aiperf.json").exists():
            print(f"skip {p}: no profile_export_aiperf.json")
            continue
        print(f"exporting {p}", flush=True)
        points.append(export_point(p, args.ttft_slo, args.skip_minutes, args.replicate_suffix, args.kv_bytes_per_token,
                                   arm_map))
    if not points:
        raise SystemExit("no exportable points")

    arm_ids = list(dict.fromkeys(p["arm"] for p in points))
    if args.baseline and args.baseline not in arm_ids:
        raise SystemExit(f"--baseline {args.baseline} is not one of the arms: {', '.join(arm_ids)}")
    arm_ids.sort(key=lambda a: a != args.baseline)
    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle = {
        "schema": SCHEMA,
        "title": args.title,
        "description": args.description,
        "created_utc": created,
        "settings": {"ttft_slo_s": args.ttft_slo, "skip_minutes": args.skip_minutes,
                     "kv_bytes_per_token": args.kv_bytes_per_token},
        "arms": [{"id": a, "name": names.get(a, a), "baseline": a == args.baseline} for a in arm_ids],
        "points": sorted(points, key=lambda p: (arm_ids.index(p["arm"]), p["conc"], p["replicate"] or 0)),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(bundle, separators=(",", ":"), allow_nan=False))
    update_index(args.out, args.title, created, len(points))
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB, {len(points)} points)")


if __name__ == "__main__":
    main()
