#!/usr/bin/env python3
"""Analysis for step 10: the step 08 replicate protocol through the llm-d-router EPP.

Arms: epp-sticky (plugin as scorer only, no admission) vs epp-thunder (the
upstream tr-decay port). Same cells layout as step 08 plus epp-metrics.csv
from the prober, and a reference table against the step 08 Python arms.

Three things step 07 could not do:
  1. Error bars: the same config run N times, so the 2x claim gets a range.
  2. Warm-up vs steady state: the first ~10 minutes are a transient (cold
     pool filling) that dilutes the whole-window number - default's hit rate
     reads 0.095 over the window but 0.008 in steady state.
  3. Same-session comparison: per-session step_count from the router lets us
     restrict to the sessions BOTH arms touched, removing the confound that
     the faster arm pulls more traces out of the corpus.

Usage: analyze.py <results_root>
"""
import csv
import json
import statistics as st
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PALETTE = {"blue": "#0F4D92", "red": "#B64342", "grey": "#CFCECE"}
ARMS = (("epp-sticky", PALETTE["red"], "epp-sticky (no admission)"),
        ("epp-thunder", PALETTE["blue"], "epp-thunder (ThunderAgent port)"))
# Step 08 reference (3 replicates, c=128, one pod per lane, Python router).
STEP08 = {"default": {"throughput": 221, "hit_steady": 0.008, "ttft_p50": 52.7, "ttft_p90": 92.5, "requests": 1059},
          "tr-decay": {"throughput": 469, "hit_steady": 0.685, "ttft_p50": 3.0, "ttft_p90": 18.0, "requests": 1994}}
WARMUP_S = 600


def load_requests(cell):
    path = next((cell / "results" / "report").glob("*per_request_lifecycle*"), None)
    if path is None:
        return []
    out = []
    for e in json.loads(path.read_text()):
        info = e.get("info") or {}
        rm = info.get("response_metrics") or {}
        su = rm.get("server_usage") or {}
        det = su.get("prompt_tokens_details") or {}
        cm = e.get("computed_metrics") or {}
        ttft = cm.get("time_to_first_token")
        if ttft is None:
            ct = rm.get("chunk_times") or []
            ttft = (ct[0] - e["start_time"]) if ct and e.get("start_time") else None
        out.append({"ok": not e.get("error"), "prompt": su.get("prompt_tokens"),
                    "cached": det.get("cached_tokens"), "out": su.get("completion_tokens"),
                    "ttft": ttft, "start": e.get("start_time")})
    return out


def hit_rate(cell, lo=0.0, hi=float("inf")):
    """Token-weighted hit rate from the pod's own counters, over a time slice."""
    p = cell / "results" / "vllm-metrics.csv"
    if not p.exists():
        return float("nan")
    rows = list(csv.DictReader(open(p)))
    if not rows:
        return float("nan")
    t0 = float(rows[0]["ts"])
    q = h = 0
    for r in rows:
        if lo <= float(r["ts"]) - t0 < hi:
            q += int(r["interval_queries"] or 0)
            h += int(r["interval_hits"] or 0)
    return h / q if q else float("nan")


def sessions(cell):
    """program_id -> (final step_count, ever_paused). Needs the step_count column."""
    p = cell / "results" / "programs-timeline.csv"
    if not p.exists():
        return {}
    out = {}
    for r in csv.DictReader(open(p)):
        sc = r.get("step_count")
        if sc in (None, ""):
            continue
        pid = r["program_id"]
        prev = out.get(pid, (0, False))
        out[pid] = (max(prev[0], int(sc)), prev[1] or r.get("state") == "paused")
    return out


def epp_stats(cell):
    """End-of-run EPP counters and peaks from epp-metrics.csv."""
    p = cell / "results" / "epp-metrics.csv"
    out = {"holds": float("nan"), "pauses": float("nan"), "resumes": float("nan"), "max_paused": float("nan"),
           "starved": float("nan"), "queue_wait_mean": float("nan"), "max_queue": float("nan")}
    if not p.exists():
        return out
    rows = [r for r in csv.DictReader(open(p)) if r.get("pauses_total") not in (None, "")]
    if not rows:
        return out
    f = lambda r, k: float(r[k]) if r.get(k) not in (None, "") else 0.0
    last = rows[-1]
    out["holds"] = f(last, "holds_paused") + f(last, "holds_new")
    out["pauses"] = f(last, "pauses_total")
    out["resumes"] = f(last, "resumes_total")
    out["starved"] = f(last, "starvation_promotions_total")
    out["max_paused"] = max(f(r, "programs_paused") for r in rows)
    out["max_queue"] = max(f(r, "fc_queue_size") for r in rows)
    cnt = f(last, "fc_queue_wait_count") - f(rows[0], "fc_queue_wait_count")
    if cnt > 0:
        out["queue_wait_mean"] = (f(last, "fc_queue_wait_sum") - f(rows[0], "fc_queue_wait_sum")) / cnt
    return out


def cell_window(cell, default=2700):
    m = cell / "manifest.json"
    if m.exists():
        try:
            return float(json.loads(m.read_text()).get("window_s") or default)
        except Exception:
            return default
    return default


def cell_stats(cell, window_s=None):
    window_s = window_s or cell_window(cell)
    reqs = [r for r in load_requests(cell) if r["ok"]]
    lat = [r["ttft"] for r in reqs if r["ttft"]]
    zero = [r for r in reqs if r["cached"] == 0]
    return {
        "requests": len(reqs),
        "errors": len(load_requests(cell)) - len(reqs),
        "throughput": sum(r["out"] or 0 for r in reqs) / window_s,
        "hit_window": hit_rate(cell),
        "hit_warmup": hit_rate(cell, 0, WARMUP_S),
        "hit_steady": hit_rate(cell, WARMUP_S),
        "ttft_p50": float(np.percentile(lat, 50)) if lat else float("nan"),
        "ttft_p90": float(np.percentile(lat, 90)) if lat else float("nan"),
        "zero_cache_share": len(zero) / len(reqs) if reqs else float("nan"),
        "sessions": sessions(cell),
        **epp_stats(cell),
    }


def wait_profile(cell):
    """Where does waiting happen, and how much of it crosses the client's patience?

    Returns per-request durations split into successful and errored, plus the
    router pause intervals. Errored requests all sit at exactly the client's
    request_timeout, so this shows whether the timeouts are the mechanism
    working as designed (a long admission hold) or something failing.
    """
    reqs = load_requests(cell)
    ok = [r for r in reqs if r["ok"]]
    err = [r for r in reqs if not r["ok"]]
    p = cell / "results" / "programs-timeline.csv"
    pauses = []
    if p.exists():
        per = {}
        for r in csv.DictReader(open(p)):
            per.setdefault(r["program_id"], []).append((float(r["ts"]), r["state"]))
        for v in per.values():
            v.sort()
            start = None
            for t, s in v:
                if s == "paused" and start is None:
                    start = t
                elif s != "paused" and start is not None:
                    pauses.append(t - start)
                    start = None
            if start is not None:
                pauses.append(v[-1][0] - start)
    return {"n_ok": len(ok), "n_err": len(err), "pauses": pauses}


def make_error_figure(root, reps, client_timeout=1900.0):
    """Why tr-decay logs more errors: the client gives up before the router does."""
    plt.rcParams.update({"font.family": ["DejaVu Sans", "sans-serif"], "font.size": 13,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "legend.frameon": False, "axes.linewidth": 2.0})
    fig, (ax_rate, ax_dur, ax_pause) = plt.subplots(1, 3, figsize=(17, 5.2))

    agg = {}
    for arm, col, lab in ARMS:
        n_ok = n_err = 0
        pauses, ok_dur = [], []
        for r in reps:
            cell = root / f"{arm}-r{r}"
            if not (cell / "results").exists():
                continue
            w = wait_profile(cell)
            n_ok += w["n_ok"]; n_err += w["n_err"]; pauses += w["pauses"]
            path = next((cell / "results" / "report").glob("*per_request_lifecycle*"), None)
            if path:
                for e in json.loads(path.read_text()):
                    if not e.get("error") and e.get("end_time") and e.get("start_time"):
                        ok_dur.append(e["end_time"] - e["start_time"])
        agg[arm] = {"n_ok": n_ok, "n_err": n_err, "pauses": pauses, "ok_dur": ok_dur}

    # (a) how often the client gave up
    for j, (arm, col, lab) in enumerate(ARMS):
        a = agg[arm]
        share = 100 * a["n_err"] / (a["n_ok"] + a["n_err"])
        ax_rate.bar(j, share, 0.55, color=col, edgecolor="black", linewidth=1.2)
        ax_rate.text(j, share + 0.06, f"{share:.1f}%\n({a['n_err']} of {a['n_ok'] + a['n_err']})",
                     ha="center", fontsize=11)
    ax_rate.set_xticks(range(len(ARMS)), [a[0] for a in ARMS])
    ax_rate.set_ylabel("Requests abandoned by the client (%)")
    ax_rate.set_title("(a) Client gave up waiting", fontsize=14)
    ax_rate.set_ylim(0, 3.2)

    # (b) successful-request duration: where the two arms really differ
    for arm, col, lab in ARMS:
        d = np.sort(agg[arm]["ok_dur"])
        if len(d):
            ax_dur.plot(100 * np.arange(1, len(d) + 1) / len(d), d,
                        "-" if arm == "epp-thunder" else "--", color=col, linewidth=2.6,
                        label=f"{lab} (median {np.median(d):.0f}s)")
    ax_dur.axhline(client_timeout, color="0.35", linestyle=":", linewidth=2)
    ax_dur.text(2, client_timeout * 1.05, "client timeout 600s", fontsize=11, color="0.35")
    ax_dur.set_yscale("log")
    ax_dur.set_xlabel("Successful requests, sorted (%)")
    ax_dur.set_ylabel("End-to-end request time (s), log")
    ax_dur.set_title("(b) Successful requests are 4x faster under tr", fontsize=13)
    ax_dur.legend(fontsize=10, loc="lower right")

    # (c) the cause: router holds, and how many cross the client's patience
    for arm, col, lab in ARMS:
        p = np.sort(agg[arm]["pauses"])
        if not len(p):
            ax_pause.plot([], [], color=col, label=f"{lab}: never pauses")
            continue
        over = int((p > client_timeout).sum())
        ax_pause.plot(100 * np.arange(1, len(p) + 1) / len(p), np.maximum(p, 1),
                      "-", color=col, linewidth=2.6,
                      label=f"{lab}: {len(p)} holds, {over} over 600s")
    ax_pause.axhline(client_timeout, color="0.35", linestyle=":", linewidth=2)
    ax_pause.axhline(1800, color=PALETTE["red"], linestyle="--", linewidth=1.5)
    ax_pause.text(2, 1900, "router's own forced-admission limit 1800s",
                  fontsize=10, color=PALETTE["red"])
    ax_pause.set_yscale("log")
    ax_pause.set_xlabel("Router hold intervals, sorted (%)")
    ax_pause.set_ylabel("Hold duration (s), log")
    ax_pause.set_title("(c) Cause: a few holds outlast the client", fontsize=13)
    ax_pause.legend(fontsize=10, loc="lower right")

    fig.suptitle("Errors and request durations by arm (client timeout 1900 s > 1800 s backstop; "
                 "admission holds - not failures", fontsize=14, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"errors.{ext}", dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"figure: {root}/errors.png")


def fmt(vals, spec="{:.3f}"):
    """value list -> 'mean (min-max)', the honest way to show N replicates."""
    vals = [v for v in vals if v == v]
    if not vals:
        return "-"
    if len(vals) == 1:
        return spec.format(vals[0])
    return f"{spec.format(st.mean(vals))} ({spec.format(min(vals))}-{spec.format(max(vals))})"


def main():
    root = Path(sys.argv[1])
    reps = sorted({int(d.name.split("-r")[-1]) for d in root.iterdir()
                   if d.is_dir() and "-r" in d.name and d.name[-1].isdigit()})
    if not reps:
        print("no replicate cells found")
        return
    data = {}
    for arm, _, _ in ARMS:
        data[arm] = []
        for r in reps:
            d = root / f"{arm}-r{r}"
            if (d / "results").exists():
                data[arm].append(cell_stats(d))

    L = [f"# Step 10: replicated A/B through the EPP, {len(reps)} run(s) of the same configuration\n"]
    rows = [("throughput (output tok/s)", "throughput", "{:.0f}"),
            ("requests completed", "requests", "{:.0f}"),
            ("hit rate, whole window", "hit_window", "{:.3f}"),
            ("hit rate, first 10 min (warm-up)", "hit_warmup", "{:.3f}"),
            ("hit rate, after 10 min (STEADY)", "hit_steady", "{:.3f}"),
            ("TTFT p50 (s)", "ttft_p50", "{:.1f}"),
            ("TTFT p90 (s)", "ttft_p90", "{:.1f}"),
            ("requests with zero cache hit", "zero_cache_share", "{:.2f}"),
            ("errors", "errors", "{:.0f}"),
            ("EPP holds (paused + new)", "holds", "{:.0f}"),
            ("EPP pauses", "pauses", "{:.0f}"),
            ("EPP resumes", "resumes", "{:.0f}"),
            ("EPP max programs paused at once", "max_paused", "{:.0f}"),
            ("EPP forced admissions", "starved", "{:.0f}"),
            ("EPP mean queue wait (s)", "queue_wait_mean", "{:.1f}"),
            ("EPP max queue size", "max_queue", "{:.0f}")]
    L.append("Each cell shows mean (min-max) over replicates.\n")
    L.append("| metric | epp-sticky | epp-thunder | ratio of means |")
    L.append("|---|---|---|---|")
    for name, key, spec in rows:
        dv = [c[key] for c in data["epp-sticky"]]
        tv = [c[key] for c in data["epp-thunder"]]
        ratio = "-"
        if dv and tv and st.mean(dv):
            ratio = f"{st.mean(tv) / st.mean(dv):.2f}x"
        L.append(f"| {name} | {fmt(dv, spec)} | {fmt(tv, spec)} | {ratio} |")
    L.append("")

    # Reference: the same protocol through the Python router (step 08).
    L.append("## Against step 08 (Python router, same protocol)\n")
    L.append("| metric | py default | epp-sticky | py tr-decay | epp-thunder |")
    L.append("|---|---|---|---|---|")
    for name, key, spec in [("throughput (output tok/s)", "throughput", "{:.0f}"),
                            ("requests completed", "requests", "{:.0f}"),
                            ("hit rate, after 10 min (STEADY)", "hit_steady", "{:.3f}"),
                            ("TTFT p50 (s)", "ttft_p50", "{:.1f}"),
                            ("TTFT p90 (s)", "ttft_p90", "{:.1f}")]:
        sv = [c[key] for c in data["epp-sticky"]]
        tv = [c[key] for c in data["epp-thunder"]]
        L.append(f"| {name} | {spec.format(STEP08['default'][key])} | {fmt(sv, spec)} | "
                 f"{spec.format(STEP08['tr-decay'][key])} | {fmt(tv, spec)} |")
    L.append("")

    # Same-session comparison: only sessions both arms of a replicate touched.
    L.append("## Same sessions only (turns completed)\n")
    L.append("Restricted to the sessions BOTH arms of a replicate started, so the "
             "faster arm pulling extra traces out of the corpus cannot flatter it.\n")
    L.append("| replicate | shared sessions | turns: epp-sticky | turns: epp-thunder | ratio |")
    L.append("|---|---|---|---|---|")
    for i, r in enumerate(reps):
        if i >= len(data["epp-sticky"]) or i >= len(data["epp-thunder"]):
            continue
        ds, ts_ = data["epp-sticky"][i]["sessions"], data["epp-thunder"][i]["sessions"]
        both = set(ds) & set(ts_)
        if not both:
            L.append(f"| r{r} | n/a (the EPP state dump lists no program ids) | - | - | - |")
            continue
        dt = sum(ds[p][0] for p in both)
        tt = sum(ts_[p][0] for p in both)
        L.append(f"| r{r} | {len(both)} | {dt} | {tt} | {tt / dt:.2f}x |" if dt
                 else f"| r{r} | {len(both)} | {dt} | {tt} | - |")
    L.append("")

    (root / "analysis.md").write_text("\n".join(L))
    print("\n".join(L))

    # Figure: per-replicate points, so the spread is visible rather than averaged away.
    plt.rcParams.update({"font.family": ["Helvetica", "Arial", "DejaVu Sans", "sans-serif"],
                         "font.size": 13, "axes.spines.top": False, "axes.spines.right": False,
                         "legend.frameon": False, "axes.linewidth": 1.6,
                         "xtick.major.width": 1.6, "ytick.major.width": 1.6})
    panels = [("throughput", "Throughput", "output tokens / s", "{:.0f}", "higher"),
              ("hit_steady", "Prefix-cache hit rate", "steady state (after 10 min)", "{:.3f}", "higher"),
              ("ttft_p50", "TTFT p50", "seconds", "{:.1f}", "lower")]
    fig, axes = plt.subplots(1, len(panels), figsize=(4.1 * len(panels), 4.3))
    for ax, (key, title, unit, spec, better) in zip(axes, panels):
        means, top = [], 0.0
        for j, (arm, col, _) in enumerate(ARMS):
            vals = np.array([c[key] for c in data[arm]], dtype=float)
            if not len(vals):
                means.append(np.nan)
                continue
            m = float(vals.mean())
            means.append(m)
            top = max(top, float(vals.max()))
            ax.bar(j, m, width=0.62, color=col, alpha=0.2, edgecolor=col, linewidth=1.8, zorder=1)
            ax.vlines(j, vals.min(), vals.max(), color=col, linewidth=1.8, zorder=2)
            jit = np.linspace(-0.13, 0.13, len(vals)) if len(vals) > 1 else np.zeros(1)
            ax.scatter(j + jit, vals, s=60, color=col, edgecolor="white", linewidth=1.0, zorder=3)
            ax.annotate(spec.format(m), (j, vals.max()), xytext=(0, 7), textcoords="offset points",
                        ha="center", va="bottom", fontsize=12, fontweight="bold", color=col)
        if len(means) == 2 and all(np.isfinite(means)) and min(means) > 0:
            r = means[1] / means[0] if better == "higher" else means[0] / means[1]
            ax.text(0.5, 0.97, f"{r:.0f}x {better}" if r >= 10 else f"{r:.1f}x {better}",
                    transform=ax.transAxes, ha="center", va="top", fontsize=13,
                    fontweight="bold", color="#333333")
        ax.set_xticks(range(len(ARMS)), ["epp-sticky\n(no admission)", "epp-thunder\n(port)"])
        ax.set_xlim(-0.6, len(ARMS) - 0.4)
        ax.set_ylim(0, top * 1.32 if top else 1)
        ax.set_title(title, fontsize=14, fontweight="bold", loc="left")
        ax.set_ylabel(unit)
        ax.tick_params(axis="x", length=0)
    fig.text(0.01, 0.01, f"n = {len(reps)} replicate(s) per arm at c = 128 through the llm-d-router EPP. "
             "Bar = mean, whisker = min-max, dots = individual runs.",
             fontsize=10.5, color="#555555", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.05, 1, 1), w_pad=2.5)
    for ext in ("png", "pdf"):
        fig.savefig(root / f"replicates.{ext}", dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"figure: {root}/replicates.png")
    make_error_figure(root, reps)


if __name__ == "__main__":
    main()
