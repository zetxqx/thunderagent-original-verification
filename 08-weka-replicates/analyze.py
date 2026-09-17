#!/usr/bin/env python3
"""Analysis for the replicated A/B.

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
ARMS = (("default", PALETTE["red"], "default (pure proxy)"),
        ("tr-decay", PALETTE["blue"], "tr-decay (ThunderAgent)"))
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


def cell_stats(cell, window_s=2700):
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


def make_error_figure(root, reps, client_timeout=600.0):
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
                        "-" if arm == "tr-decay" else "--", color=col, linewidth=2.6,
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

    fig.suptitle("The extra 'errors' under ThunderAgent are client timeouts on a few long "
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

    L = [f"# Replicated A/B: {len(reps)} runs of the same configuration\n"]
    rows = [("throughput (output tok/s)", "throughput", "{:.0f}"),
            ("requests completed", "requests", "{:.0f}"),
            ("hit rate, whole window", "hit_window", "{:.3f}"),
            ("hit rate, first 10 min (warm-up)", "hit_warmup", "{:.3f}"),
            ("hit rate, after 10 min (STEADY)", "hit_steady", "{:.3f}"),
            ("TTFT p50 (s)", "ttft_p50", "{:.1f}"),
            ("TTFT p90 (s)", "ttft_p90", "{:.1f}"),
            ("requests with zero cache hit", "zero_cache_share", "{:.2f}"),
            ("errors", "errors", "{:.0f}")]
    L.append("Each cell shows mean (min-max) over replicates.\n")
    L.append("| metric | default | tr-decay | ratio of means |")
    L.append("|---|---|---|---|")
    for name, key, spec in rows:
        dv = [c[key] for c in data["default"]]
        tv = [c[key] for c in data["tr-decay"]]
        ratio = "-"
        if dv and tv and st.mean(dv):
            ratio = f"{st.mean(tv) / st.mean(dv):.2f}x"
        L.append(f"| {name} | {fmt(dv, spec)} | {fmt(tv, spec)} | {ratio} |")
    L.append("")

    # Same-session comparison: only sessions both arms of a replicate touched.
    L.append("## Same sessions only (turns completed)\n")
    L.append("Restricted to the sessions BOTH arms of a replicate started, so the "
             "faster arm pulling extra traces out of the corpus cannot flatter it.\n")
    L.append("| replicate | shared sessions | turns: default | turns: tr-decay | ratio |")
    L.append("|---|---|---|---|---|")
    for i, r in enumerate(reps):
        if i >= len(data["default"]) or i >= len(data["tr-decay"]):
            continue
        ds, ts_ = data["default"][i]["sessions"], data["tr-decay"][i]["sessions"]
        both = set(ds) & set(ts_)
        if not both:
            L.append(f"| r{r} | 0 (no step_count recorded) | - | - | - |")
            continue
        dt = sum(ds[p][0] for p in both)
        tt = sum(ts_[p][0] for p in both)
        L.append(f"| r{r} | {len(both)} | {dt} | {tt} | {tt / dt:.2f}x |" if dt
                 else f"| r{r} | {len(both)} | {dt} | {tt} | - |")
    L.append("")

    (root / "analysis.md").write_text("\n".join(L))
    print("\n".join(L))

    # Figure: per-replicate points, so the spread is visible rather than averaged away.
    plt.rcParams.update({"font.family": ["DejaVu Sans", "sans-serif"], "font.size": 13,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "legend.frameon": False, "axes.linewidth": 2.0})
    panels = [("throughput", "Throughput (output tok/s)", False),
              ("hit_steady", "Hit rate, steady state (after 10 min)", False),
              ("ttft_p50", "TTFT p50 (s)", True)]
    fig, axes = plt.subplots(1, len(panels), figsize=(5.6 * len(panels), 5))
    for ax, (key, title, logy) in zip(axes, panels):
        for j, (arm, col, lab) in enumerate(ARMS):
            vals = [c[key] for c in data[arm]]
            ax.scatter([j] * len(vals), vals, s=110, color=col, zorder=3, label=lab)
            if vals:
                ax.hlines(st.mean(vals), j - 0.25, j + 0.25, color=col, linewidth=3)
        ax.set_xticks(range(len(ARMS)), [a[0] for a in ARMS])
        ax.set_title(title, fontsize=14)
        if logy:
            ax.set_yscale("log")
        else:
            ax.set_ylim(bottom=0)
    axes[0].set_ylabel(f"one point per replicate (n={len(reps)}), bar = mean")
    fig.suptitle("Same configuration, repeated: how stable is the result?", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"replicates.{ext}", dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"figure: {root}/replicates.png")
    make_error_figure(root, reps)


if __name__ == "__main__":
    main()
