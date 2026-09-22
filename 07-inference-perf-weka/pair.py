#!/usr/bin/env python3
"""Paired analysis for the weka A/B sweep.

Usage: pair.py <ab_out_root>   # containing default-cN/ and tr-decay-cN/ cells

Methodology (mandatory for timeout-truncated arms): aggregate metrics across
truncated arms are unreliable because arms progress at different speeds and
capture different request populations. We pair per-request entries across the
two arms of each concurrency on (graph_event_id, prompt_tokens within 1%) -
replay is deterministic, so this pairs cleanly - and judge PAIRED deltas.
Unpaired tails are reported as window-progress differences.

Writes <root>/analysis.md and <root>/comparison-weka.png/.pdf.
"""
import csv
import json
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PALETTE = {"blue": "#0F4D92", "red": "#B64342", "teal": "#42949E",
           "green": "#8BCF8B", "violet": "#9A4D8E", "neutral": "#CFCECE"}
_CYCLE = [PALETTE["green"], PALETTE["teal"], PALETTE["violet"], PALETTE["blue"]]
C_COLORS: dict = {}  # concurrency -> colour, assigned in run order so any sweep works


def apply_style():
    plt.rcParams.update({
        "font.family": ["DejaVu Sans", "Helvetica", "Arial", "sans-serif"],
        "font.size": 14, "axes.linewidth": 2.0,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "pdf.fonttype": 42})


def load_requests(cell_dir):
    """Return list of dicts: event_id, prompt, cached, out_tokens, ttft, ok."""
    path = next((cell_dir / "results" / "report").glob("*per_request_lifecycle*"), None)
    if path is None:
        return []
    entries = json.loads(path.read_text())
    rows = []
    for e in entries:
        info = e.get("info") or {}
        rm = info.get("response_metrics") or {}
        su = rm.get("server_usage") or {}
        details = su.get("prompt_tokens_details") or {}
        cm = e.get("computed_metrics") or {}
        ttft = cm.get("time_to_first_token")
        if ttft is None:
            ct = rm.get("chunk_times") or []
            ttft = (ct[0] - e["start_time"]) if ct and e.get("start_time") else None
        rows.append({
            "event_id": info.get("graph_event_id"),
            "prompt": su.get("prompt_tokens"),
            "cached": details.get("cached_tokens"),
            "out": su.get("completion_tokens"),
            "ttft": ttft,
            "ok": not e.get("error"),
        })
    return rows


def pair(a_rows, b_rows):
    """Pair on (event_id, prompt within 1%)."""
    b_by_id = {}
    for r in b_rows:
        if r["ok"] and r["event_id"] and r["prompt"]:
            b_by_id.setdefault(r["event_id"], []).append(r)
    pairs = []
    for a in a_rows:
        if not (a["ok"] and a["event_id"] and a["prompt"]):
            continue
        for b in b_by_id.get(a["event_id"], []):
            if abs(b["prompt"] - a["prompt"]) <= 0.01 * a["prompt"]:
                pairs.append((a, b))
                break
    return pairs


def hit_ratio(r):
    # None (not 0) when the server did not report cached_tokens - vLLM needs
    # --enable-prompt-tokens-details for per-request cache counts.
    if r["cached"] is None or not r["prompt"]:
        return None
    return r["cached"] / r["prompt"]


def load_ts(cell_dir, fname, col):
    p = cell_dir / "results" / fname
    if not p.exists():
        return np.array([]), np.array([])
    rows = list(csv.DictReader(open(p)))
    if not rows:
        return np.array([]), np.array([])
    t0 = float(rows[0]["ts"])
    t, y = [], []
    for r in rows:
        v = r.get(col)
        if v not in (None, ""):
            t.append(float(r["ts"]) - t0)
            y.append(float(v))
    return np.array(t), np.array(y)


def rolling_hit_rate(cell_dir, win=30):
    """Hit rate as sum(hits)/sum(queries) over a sliding window of samples.

    Averaging the per-interval ratios would be wrong: 2s buckets carry very
    different token counts and empty buckets have no defined ratio. Ratio of
    sums weights every token equally, and turns an unreadable 0/1 sawtooth
    into the actual trend.
    """
    p = cell_dir / "results" / "vllm-metrics.csv"
    if not p.exists():
        return np.array([]), np.array([])
    rows = list(csv.DictReader(open(p)))
    if not rows:
        return np.array([]), np.array([])
    t0 = float(rows[0]["ts"])
    t = np.array([float(r["ts"]) - t0 for r in rows])
    q = np.array([float(r["interval_queries"] or 0) for r in rows])
    h = np.array([float(r["interval_hits"] or 0) for r in rows])
    k = np.ones(win)
    qs, hs = np.convolve(q, k, "same"), np.convolve(h, k, "same")
    with np.errstate(invalid="ignore", divide="ignore"):
        y = np.where(qs > 0, hs / qs, np.nan)
    return t, y


def make_summary_lines(root, concs, window_s=2700):
    """The plain-language summary: concurrency on x, one line per arm.

    Throughput is output tokens produced inside the fixed measurement window
    divided by that window - sessions are truncated, so "time to finish" does
    not exist and work-done-per-second is the throughput that matters.
    """
    apply_style()
    fig, (ax_tp, ax_tt, ax_hr) = plt.subplots(1, 3, figsize=(17, 5.2))
    ARMS = {"default": (PALETTE["red"], "passthrough"),
            "tr-decay": (PALETTE["blue"], "ThunderAgent")}
    # p50 / p90 / mean share a colour per arm and differ by line style.
    STATS = (("p50", "-", "o", lambda v: np.percentile(v, 50)),
             ("p90", "--", "s", lambda v: np.percentile(v, 90)),
             ("mean", ":", "^", np.mean))
    table = {}

    for arm, (col, lab) in ARMS.items():
        tp, hr = [], []
        ttft = {s: [] for s, _, _, _ in STATS}
        hit = {s: [] for s, _, _, _ in STATS}
        for c in concs:
            d = root / f"{arm}-c{c}"
            rows = [r for r in load_requests(d) if r["ok"]]
            tp.append(sum(r["out"] or 0 for r in rows) / window_s)
            lat = [r["ttft"] for r in rows if r["ttft"]]
            ratios = [hit_ratio(r) for r in rows]
            ratios = [x for x in ratios if x is not None]
            for s, _, _, f in STATS:
                ttft[s].append(float(f(lat)) if lat else np.nan)
                hit[s].append(float(f(ratios)) if ratios else np.nan)
            _, q = ts_sum(d, "interval_queries")
            _, h = ts_sum(d, "interval_hits")
            hr.append(h / q if q else np.nan)
        table[arm] = (tp, ttft, hr)

        ax_tp.plot(concs, tp, "-o" if arm == "tr-decay" else "--o", color=col,
                   linewidth=2.5, markersize=8, label=lab)
        for s, ls, mk, _ in STATS:
            ax_tt.plot(concs, ttft[s], ls, marker=mk, color=col, linewidth=2.0,
                       markersize=7, label=f"{lab} {s}")
            ax_hr.plot(concs, hit[s], ls, marker=mk, color=col, linewidth=2.0,
                       markersize=7, label=f"{lab} {s}")

    ax_tp.set_ylabel("Output tokens per second")
    ax_tp.set_title("Throughput (whole-window aggregate)", fontsize=14)
    ax_tp.set_ylim(bottom=0)
    ax_tp.legend(fontsize=11)

    ax_tt.set_ylabel("TTFT (s), log scale")
    ax_tt.set_title("Time to first token (per request)", fontsize=14)
    ax_tt.set_yscale("log")   # arms differ by ~10x; linear hides the tr curve

    ax_hr.set_ylabel("Per-request cached / prompt tokens")
    ax_hr.set_title("Cache hit ratio (per request)", fontsize=14)
    ax_hr.set_ylim(-0.03, 1.05)

    # One shared legend under the figure: per-axes legends covered the data.
    handles, labels = ax_tt.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=6, fontsize=11,
               bbox_to_anchor=(0.5, -0.04))

    for ax in (ax_tp, ax_tt, ax_hr):
        ax.set_xlabel("Concurrent sessions offered")
        ax.set_xticks(concs)

    # Annotate the ratio at each point: the number readers actually want.
    for i, c in enumerate(concs):
        d_tp, t_tp = table["default"][0][i], table["tr-decay"][0][i]
        if d_tp:
            ax_tp.annotate(f"{t_tp / d_tp:.1f}x", (c, t_tp), textcoords="offset points",
                           xytext=(0, 10), ha="center", fontsize=11,
                           color=PALETTE["blue"])

    fig.suptitle("Weka replay, single vLLM pod: ThunderAgent vs passthrough",
                 fontsize=15, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"summary-weka.{ext}", dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"figure: {root}/summary-weka.png")


def ts_sum(cell_dir, col):
    _, y = load_ts(cell_dir, "vllm-metrics.csv", col)
    return None, float(y.sum()) if len(y) else 0.0


def session_stalls(cell_dir):
    """Longest continuous stretch, per session, with a request outstanding.

    Uses the router's real program ids (the per-request report carries no
    session identity). `status == reasoning` means a request is in flight and
    unanswered, so for the pure proxy this is engine queueing and for
    ThunderAgent it is router hold plus engine queueing - the same quantity
    from the session's point of view: time spent unable to make progress.
    """
    p = cell_dir / "results" / "programs-timeline.csv"
    if not p.exists():
        return []
    per = {}
    for r in csv.DictReader(open(p)):
        per.setdefault(r["program_id"], []).append((float(r["ts"]), r["status"]))
    out = []
    for v in per.values():
        v.sort()
        best, start = 0.0, None
        for t, s in v:
            if s == "reasoning":
                if start is None:
                    start = t
                best = max(best, t - start)
            else:
                start = None
        out.append(best)
    return sorted(out)


def make_fairness_figure(root, concs):
    """Who benefits, and does anyone get left behind?

    Row 1: distribution of per-request cache hits, each arm on its own (NO
    cross-arm matching - graph_event_id repeats once per session, so matched
    pairs are not reliably the same session; see RESULTS.md).
    Row 2: per-session worst stall - the long-tail / fairness question.
    """
    apply_style()
    fig, axes = plt.subplots(2, len(concs), figsize=(5.6 * len(concs), 9), squeeze=False)
    styles = {"default": ("--", PALETTE["red"], "passthrough"),
              "tr-decay": ("-", PALETTE["blue"], "ThunderAgent")}

    for col, c in enumerate(concs):
        ax_hit, ax_tail = axes[0][col], axes[1][col]
        for arm in ("default", "tr-decay"):
            d = root / f"{arm}-c{c}"
            ls, colr, lab = styles[arm]

            ratios = sorted(x for x in (hit_ratio(r) for r in load_requests(d)
                                        if r["ok"]) if x is not None)
            if ratios:
                pct = 100 * np.arange(1, len(ratios) + 1) / len(ratios)
                ax_hit.plot(pct, ratios, ls, color=colr, linewidth=2.4,
                            label=f"{lab}  (n={len(ratios)})")

            stalls = session_stalls(d)
            if stalls:
                pct = 100 * np.arange(1, len(stalls) + 1) / len(stalls)
                ax_tail.plot(pct, np.array(stalls) / 60, ls, color=colr, linewidth=2.4,
                             label=f"{lab}  ({len(stalls)} sessions)")
                bad = 100 * np.mean(np.array(stalls) > 300)
                ax_tail.annotate(f"{bad:.0f}% of sessions stalled >5 min",
                                 xy=(0.42, 0.16 if arm == "default" else 0.07),
                                 xycoords="axes fraction", color=colr, fontsize=11)

        ax_hit.set_title(f"{c} sessions offered", fontsize=14)
        ax_hit.set_xlabel("Requests, sorted worst to best (%)")
        ax_hit.set_ylim(-0.03, 1.05)
        ax_tail.set_xlabel("Sessions, sorted best to worst (%)")
        ax_tail.axhline(30, color="0.45", linestyle=":", linewidth=1.5)
        if col == 0:
            ax_hit.set_ylabel("Fraction of the prompt\nserved from cache")
            ax_tail.set_ylabel("Worst stall for that session\n(minutes with a request pending)")
            ax_hit.legend(fontsize=10, loc="upper left")
            ax_tail.legend(fontsize=10, loc="upper left")
            ax_tail.text(2, 31.5, "30 min = ThunderAgent's forced-admission limit",
                         fontsize=9, color="0.45")

    fig.suptitle("Per-request cache hits (top) and per-session worst stall (bottom). "
                 "Each arm measured on its own - no cross-arm request matching.",
                 fontsize=13, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"fairness-weka.{ext}", dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"figure: {root}/fairness-weka.png")


def make_timeseries_figure(root, concs, arms=("default", "tr-decay")):
    """One ROW per concurrency, so arms are compared without cross-concurrency
    overlap (six lines in one axes was unreadable)."""
    apply_style()
    n = len(concs)
    fig, axes = plt.subplots(n, 4, figsize=(20, 4.2 * n), squeeze=False)
    styles = {"default": ("--", PALETTE["red"], "passthrough"),
              "tr-decay": ("-", PALETTE["blue"], "ThunderAgent")}

    for row, c in enumerate(concs):
        ax_hr, ax_kv, ax_q, ax_p = axes[row]
        for arm in arms:
            d = root / f"{arm}-c{c}"
            ls, col, lab = styles[arm]

            t, y = rolling_hit_rate(d)
            if len(t):
                ax_hr.plot(t / 60, y, ls, color=col, linewidth=2.0, label=lab)

            t, y = load_ts(d, "vllm-metrics.csv", "kv_cache_usage_perc")
            if len(t):
                ax_kv.plot(t / 60, y * 100, ls, color=col, linewidth=1.2,
                           alpha=0.8, label=lab)

            t, y = load_ts(d, "vllm-metrics.csv", "num_requests_waiting")
            if len(t):
                ax_q.plot(t / 60, y, ls, color=col, linewidth=1.2, alpha=0.8, label=lab)

            t, y = load_ts(d, "router-health.csv", "paused_count")
            if len(t):
                ax_p.plot(t / 60, y, ls, color=col, linewidth=2.0, label=lab)

        ax_hr.set_ylim(-0.03, 1.05)
        ax_hr.set_ylabel(f"c={c}\n\nprefix-cache hit rate", fontsize=13)
        ax_kv.set_ylabel("KV utilization (%)")
        ax_q.set_ylabel("vLLM waiting queue")
        ax_p.set_ylabel("paused programs")
        if row == 0:
            ax_hr.set_title("Prefix-cache hit rate (60s rolling)", fontsize=14)
            ax_kv.set_title("KV cache utilization", fontsize=14)
            ax_q.set_title("Engine queue depth", fontsize=14)
            ax_p.set_title("Programs paused by the router", fontsize=14)
            ax_hr.legend(fontsize=10, loc="lower right")
        if row == n - 1:
            for ax in axes[row]:
                ax.set_xlabel("Time (min)")

    fig.suptitle("Weka replay, per-concurrency time series: "
                 "dashed = passthrough, solid = ThunderAgent",
                 fontsize=15, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"timeseries-weka.{ext}",
                    dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"figure: {root}/timeseries-weka.png")


def main():
    root = Path(sys.argv[1])
    concs = sorted({int(m.group(1)) for d in root.iterdir()
                    for m in [re.match(r"default-c(\d+)$", d.name)] if m})
    for i, c in enumerate(concs):
        C_COLORS[c] = _CYCLE[i % len(_CYCLE)]
    lines = ["# Weka replay A/B: paired analysis\n"]
    fig_rows, progress = {}, {}
    apply_style()
    # Request-by-request comparison. Deliberately plain-language: this is the
    # same curve as before but without the jargon, and without the throughput
    # bars that duplicated summary-weka.png.
    fig, ax_d = plt.subplots(1, 1, figsize=(10, 6.5))

    for c in concs:
        d_dir, t_dir = root / f"default-c{c}", root / f"tr-decay-c{c}"
        d_rows, t_rows = load_requests(d_dir), load_requests(t_dir)
        pairs = pair(d_rows, t_rows)
        d_ok = [r for r in d_rows if r["ok"]]
        t_ok = [r for r in t_rows if r["ok"]]
        lines.append(f"## c={c}\n")
        progress[c] = {"default": sum(r["out"] or 0 for r in d_ok),
                       "tr-decay": sum(r["out"] or 0 for r in t_ok)}
        lines.append(f"- window progress: default {len(d_ok)} requests "
                     f"/ {progress[c]['default']} output tokens; "
                     f"tr-decay {len(t_ok)} / {progress[c]['tr-decay']}")
        lines.append(f"- errors: default {sum(1 for r in d_rows if not r['ok'])}, "
                     f"tr-decay {sum(1 for r in t_rows if not r['ok'])}")
        lines.append(f"- paired requests: {len(pairs)} "
                     f"(of {len(d_ok)} / {len(t_ok)} successful)")
        if pairs:
            dh = np.array([hit_ratio(b) - hit_ratio(a) for a, b in pairs
                           if hit_ratio(a) is not None and hit_ratio(b) is not None])
            dt = np.array([(b["ttft"] - a["ttft"]) for a, b in pairs
                           if a["ttft"] and b["ttft"]])
            if len(dh):
                lines.append(f"- paired hit-ratio delta (tr - default): "
                             f"median {np.median(dh):+.3f}, mean {np.mean(dh):+.3f}, "
                             f">0 in {np.mean(dh > 0):.0%} of pairs")
            else:
                lines.append("- per-request cached_tokens unavailable (vLLM lacks "
                             "--enable-prompt-tokens-details); use the pod-counter "
                             "hit-rate time series + paired TTFT instead")
            if len(dt):
                lines.append(f"- paired TTFT delta (tr - default): "
                             f"median {np.median(dt):+.2f}s, p90 {np.percentile(dt, 90):+.2f}s")
            if len(dh):
                fig_rows[c] = dh
        lines.append("")

    ax_d.axvspan(-1.05, 0, color=PALETTE["red"], alpha=0.05)
    ax_d.axvspan(0, 1.05, color=PALETTE["blue"], alpha=0.05)
    summary = []
    for c, dh in sorted(fig_rows.items()):
        xs = np.sort(dh)
        ax_d.plot(xs, 100 * np.arange(1, len(xs) + 1) / len(xs), color=C_COLORS.get(c),
                  linewidth=2.4, label=f"{c} sessions offered (n={len(xs)})")
        w = 100 * float(np.mean(dh > 0.001))
        l = 100 * float(np.mean(dh < -0.001))
        gain = dh[dh > 0.001]
        summary.append(f"{c:>4} sessions:  ThunderAgent served more of the prompt from "
                       f"cache on {w:.0f}% of requests (by {np.mean(gain):.0%} of the "
                       f"prompt on average), tied on {100 - w - l:.0f}%, lost on {l:.0f}%")
    ax_d.axvline(0, color="0.4", linestyle=":", linewidth=1.5)
    ax_d.set_xlim(-1.05, 1.05)
    ax_d.set_ylim(0, 100)
    ax_d.set_xlabel("Fraction of the prompt ThunderAgent served from cache,\n"
                    "minus what the passthrough served for the SAME request")
    ax_d.set_ylabel("Share of matched requests at or below this value (%)")
    ax_d.set_title("Request by request: who got more cache hits?\n"
                   "same trace replayed twice, each request matched to its twin "
                   "in the other run", fontsize=14)
    ax_d.text(-0.52, 95, "passthrough better", ha="center", fontsize=13,
              color=PALETTE["red"])
    ax_d.text(0.52, 95, "ThunderAgent better", ha="center", fontsize=13,
              color=PALETTE["blue"])
    ax_d.text(0.03, 4, "vertical jump at 0 = requests where both were equal\n"
                       "(usually both got nothing from cache)",
              ha="left", fontsize=10, color="0.35")
    ax_d.legend(fontsize=11, loc="center left")
    fig.text(0.5, -0.02, "\n".join(summary), ha="center", fontsize=11, family="monospace")
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    for ext in ("png", "pdf"):
        fig.savefig(root / f"per-request-cache-comparison.{ext}",
                    dpi=300 if ext == "png" else None,
                    bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    (root / "analysis.md").write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"figure: {root}/per-request-cache-comparison.png")
    make_summary_lines(root, concs)
    make_fairness_figure(root, concs)
    make_timeseries_figure(root, concs)


if __name__ == "__main__":
    main()
