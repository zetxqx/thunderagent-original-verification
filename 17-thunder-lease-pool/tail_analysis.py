#!/usr/bin/env python3
"""Where the TTFT tail comes from: EPP hold versus engine time, per request.

For every cell, each client request (inference-perf per-request report) is
matched to its EPP log entry by start and end time (the two clocks differ by a
constant offset, estimated from the sorted arrival times). The EPP logs
"EPP received request" when the request arrives and "EPP sent request body
response(s)" when flow control dispatches it, so their gap is the request's
hold in the gate; the rest of its TTFT is scheduling, the vLLM queue and
prefill.

Each request is classed from the client side: the first request of a session
in the run is new; a later request held longer than HOLD_S was paused (turns
of admitted sessions always dispatch at once); otherwise admitted.

Writes tail.md next to this script. Usage: tail_analysis.py
"""
import bisect
import csv
import glob
import random
import json
import re
import statistics as st
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
S16 = HERE.parent / "16-thunder-minimal-pool" / "results" / "rep-20260927-195200-c128-t1900"
S17 = HERE / "results" / "rep-20260928-115246-c128-t1900"
ARMS = [
    ("minimal, half-life 10 s, sweep 1 s (step 16)", S16, "epp-thunder-min-hl10-s1-c128"),
    ("lease 30 s", S17, "epp-thunder-lease-c128"),
    ("lease 5 s", S17, "epp-thunder-lease5-c128"),
]
WARMUP_S = 600
HOLD_S = 1.0  # a hold longer than this means flow control kept the request waiting


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))] if v else float("nan")


def ts(s):
    return datetime.fromisoformat(s[:26].rstrip("Z") + "+00:00").timestamp()


def epp_events(cell):
    recv, sent, done = {}, {}, {}
    pat = re.compile(r'"timestamp":"([^"]+)".*?"body":"(EPP received request|EPP sent request body response\(s\) to proxy|EPP sent response body back to proxy)".*?"x-request-id":"([^"]+)"')
    for line in open(cell / "epp.log", errors="replace"):
        m = pat.search(line)
        if not m:
            continue
        t, what, rid = ts(m.group(1)), m.group(2), m.group(3)
        if what.startswith("EPP received"):
            recv.setdefault(rid, t)
        elif what.startswith("EPP sent request"):
            sent.setdefault(rid, t)
        else:
            done[rid] = t
    return [(recv[r], sent[r], done.get(r)) for r in recv if r in sent]


def client_requests(cell):
    p = next(iter(glob.glob(str(cell / "results" / "report" / "*per_request_lifecycle*"))), None)
    out = []
    for e in json.load(open(p)):
        if e.get("error"):
            continue
        su = ((e.get("info") or {}).get("response_metrics") or {}).get("server_usage") or {}
        prompt = su.get("prompt_tokens") or 0
        cached = (su.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        out.append({"start": e["start_time"], "end": e["end_time"], "sid": e.get("session_id"),
                    "event": (e.get("info") or {}).get("graph_event_id") or "",
                    "ttft": (e.get("computed_metrics") or {}).get("time_to_first_token"),
                    "prompt": prompt, "cached": cached})
    return [r for r in out if r["ttft"] is not None]


def match(reqs, events):
    """Attach hold (s) to each request; returns the matched share."""
    # The EPP sees a few requests the client report lacks (cancelled at stage
    # end), so pairing by sorted index drifts. Anchor on the first arrival
    # (every session starts at t0), then refine with each request's nearest
    # EPP arrival.
    events = sorted(events)
    keys = [e[0] for e in events]
    coarse = keys[0] - min(r["start"] for r in reqs)

    def nearest(t):
        i = bisect.bisect_left(keys, t)
        return min((abs(keys[j] - t), keys[j] - t) for j in (i - 1, i) if 0 <= j < len(keys))[1]
    offset = coarse + st.median(nearest(r["start"] + coarse) for r in reqs)
    used = set()
    matched = 0
    for r in reqs:
        t0, t1 = r["start"] + offset, r["end"] + offset
        i = bisect.bisect_left(keys, t0 - 0.5)
        best, cost = None, 1.0
        while i < len(keys) and keys[i] <= t0 + 0.5:
            if i not in used:
                recv, sent, done = events[i]
                c = abs(recv - t0) + (abs(done - t1) if done else 0.5)
                if c < cost:
                    best, cost = i, c
            i += 1
        if best is not None:
            used.add(best)
            r["hold"] = events[best][1] - events[best][0]
            matched += 1
    return matched / len(reqs), offset


def classify(reqs):
    t0 = min(r["start"] for r in reqs)
    seen, last_end = set(), {}
    for r in sorted(reqs, key=lambda r: r["start"]):
        r["t"] = r["start"] - t0
        r["gap"] = r["start"] - last_end[r["sid"]] if r["sid"] in last_end else None
        if r["sid"] not in seen:
            r["cls"] = "new"
        elif r.get("hold", 0) > HOLD_S:
            r["cls"] = "paused"
        else:
            r["cls"] = "admitted"
        seen.add(r["sid"])
        last_end[r["sid"]] = max(last_end.get(r["sid"], 0), r["end"])
        r["engine"] = r["ttft"] - r.get("hold", 0)
        r["cache"] = r["cached"] / r["prompt"] if r["prompt"] else 0


def cell_report(cell):
    reqs = client_requests(cell)
    share, _ = match(reqs, epp_events(cell))
    classify(reqs)
    ss = [r for r in reqs if r["t"] >= WARMUP_S and "hold" in r]
    p99 = pct([r["ttft"] for r in reqs], 99)
    tail = [r for r in reqs if r["ttft"] >= p99 and "hold" in r]
    return reqs, ss, tail, share, p99


def counters(cell):
    """Steady-window pauses and releases from the prober's 2 s EPP series: how often a
    release of a paused session shares a 2 s interval with a pause, the mean queue
    size, and the release rate (paused + new) for Little's law."""
    rows = list(csv.DictReader(open(cell / "results" / "epp-metrics.csv")))
    t0 = float(rows[0]["ts"])
    f = lambda r, k: float(r[k]) if r.get(k) not in (None, "") else 0.0
    ss = [r for r in rows if float(r["ts"]) - t0 >= WARMUP_S]
    end = max(float(r["ts"]) for r in ss if f(r, "fc_queue_size") > 0)  # the queue drains after the stage
    ss = [r for r in ss if float(r["ts"]) <= end]
    out = {"pauses": 0.0, "releases": 0.0, "releases_with_pause": 0.0,
           "queue": [f(r, "fc_queue_size") for r in ss], "span": float(ss[-1]["ts"]) - float(ss[0]["ts"]),
           "admits": (f(ss[-1], "releases_paused") + f(ss[-1], "releases_new")) - (f(ss[0], "releases_paused") + f(ss[0], "releases_new"))}
    for a, b in zip(ss, ss[1:]):
        dp, dr = f(b, "pauses_total") - f(a, "pauses_total"), f(b, "releases_paused") - f(a, "releases_paused")
        out["pauses"] += dp
        out["releases"] += dr
        if dp > 0:
            out["releases_with_pause"] += dr
    return out


def after_session_end(reqs, rng, lo=28, hi=32):
    """Share of long holds (> 60 s) released lo-hi s after some session's last response,
    and the same share for random times: the signature of waiting for a finished
    session to pass a 30 s lease."""
    tend = max(r["end"] for r in reqs)
    t0 = min(r["start"] for r in reqs)
    last = {}
    for r in reqs:
        last[r["sid"]] = max(last.get(r["sid"], 0), r["end"])
    fin = sorted(e for e in last.values() if e < tend - 300)

    def hit(x):
        i = bisect.bisect_left(fin, x - hi)
        return i < len(fin) and fin[i] <= x - lo
    held = [r for r in reqs if r["cls"] == "paused" and r["hold"] > 60]
    return sum(hit(r["start"] + r["hold"]) for r in held), sum(hit(rng.uniform(t0 + WARMUP_S, tend - 300)) for _ in held), len(held)


def summarize(label, cells):
    rows = {}
    allreq, allss, alltail, shares, p99s = [], [], [], [], []
    cnt = {"pauses": 0.0, "releases": 0.0, "releases_with_pause": 0.0, "queue": [], "span": 0.0, "admits": 0.0}
    sig, sig_null, sig_n = 0, 0, 0
    rng = random.Random(1)
    for c in cells:
        reqs, ss, tail, share, p99 = cell_report(c)
        allreq += reqs; allss += ss; alltail += tail; shares.append(share); p99s.append(p99)
        k = counters(c)
        for key in cnt:
            cnt[key] += k[key]
        a, b, n = after_session_end(reqs, rng)
        sig, sig_null, sig_n = sig + a, sig_null + b, sig_n + n
    held = [r for r in allreq if r["cls"] == "paused"]
    rows["cells"] = ", ".join(c.name for c in cells)
    rows["matched share of requests"] = f"{min(shares):.3f}-{max(shares):.3f}"
    rows["TTFT p99 per cell (s)"] = " / ".join(f"{p:.0f}" for p in p99s)
    rows["tail requests (TTFT >= its cell's p99), all cells"] = f"{len(alltail)}"
    n = len(alltail) or 1
    for cls in ("paused", "new", "admitted"):
        rows[f"tail share, class {cls}"] = f"{sum(r['cls'] == cls for r in alltail) / n:.2f}"
    rows["tail: hold share of TTFT, median"] = f"{st.median(r['hold'] / r['ttft'] for r in alltail if r['ttft'] > 0):.2f}"
    rows["tail: hold p50 / p90 (s)"] = f"{pct([r['hold'] for r in alltail], 50):.0f} / {pct([r['hold'] for r in alltail], 90):.0f}"
    rows["tail: engine time (TTFT - hold) p50 / p90 (s)"] = f"{pct([r['engine'] for r in alltail], 50):.1f} / {pct([r['engine'] for r in alltail], 90):.1f}"
    rows["tail: prompt tokens, median (k)"] = f"{st.median(r['prompt'] for r in alltail) / 1e3:.0f}"
    rows["tail: cache hit share of prompt, median"] = f"{st.median(r['cache'] for r in alltail):.2f}"
    rows["tail: idle gap before the request, median (s)"] = f"{st.median(r['gap'] for r in alltail if r['gap'] is not None):.1f}"
    rows["tail: start minute in the window, p10 / p50 / p90"] = " / ".join(f"{pct([r['t'] for r in alltail], p) / 60:.0f}" for p in (10, 50, 90))
    rows["paused requests (held > 1 s), per cell"] = f"{len(held) / len(cells):.0f}"
    rows["paused requests: hold p50 / p90 / p99 (s)"] = " / ".join(f"{pct([r['hold'] for r in held], p):.0f}" for p in (50, 90, 99))
    rows["paused requests: share held over 60 s / over 120 s"] = f"{sum(r['hold'] > 60 for r in held) / max(len(held), 1):.2f} / {sum(r['hold'] > 120 for r in held) / max(len(held), 1):.2f}"
    rows["paused requests: prompt tokens, median (k)"] = f"{st.median(r['prompt'] for r in held) / 1e3:.0f}" if held else "-"
    rows["paused requests: cache hit share, median"] = f"{st.median(r['cache'] for r in held):.2f}" if held else "-"
    held_ss = [r for r in held if r["t"] >= WARMUP_S]
    med = st.median(r["prompt"] for r in held_ss)
    small = [r["hold"] for r in held_ss if r["prompt"] <= med]
    big = [r["hold"] for r in held_ss if r["prompt"] > med]
    rows["paused (steady), prompt at or below the median: hold p50 / p90 (s)"] = f"{pct(small, 50):.0f} / {pct(small, 90):.0f}"
    rows["paused (steady), prompt above the median: hold p50 / p90 (s)"] = f"{pct(big, 50):.0f} / {pct(big, 90):.0f}"
    rows["steady pauses / releases of paused sessions, three cells"] = f"{cnt['pauses']:.0f} / {cnt['releases']:.0f}"
    rows["releases of paused sessions in a 2 s interval that also has a pause"] = f"{cnt['releases_with_pause'] / max(cnt['releases'], 1):.2f}"
    lq, lam = st.mean(cnt["queue"]), cnt["admits"] / cnt["span"]
    rows["EPP queue, mean steady / admission rate (paused + new, per s)"] = f"{lq:.1f} / {lam:.3f}"
    rows["Little's law mean wait, queue / rate (s)"] = f"{lq / lam:.0f}"
    rows["measured mean hold of paused requests, steady (s)"] = f"{st.mean(r['hold'] for r in held_ss):.0f}"
    rows["holds > 60 s released 28-32 s after a session's last response (random times)"] = f"{sig / max(sig_n, 1):.2f} ({sig_null / max(sig_n, 1):.2f})"
    rows["admitted requests (steady): engine time p99 (s)"] = f"{pct([r['engine'] for r in allss if r['cls'] == 'admitted'], 99):.1f}"
    rows["all requests (steady): hold p99 (s)"] = f"{pct([r['hold'] for r in allss], 99):.0f}"
    return rows


def main():
    table = []
    for label, run, prefix in ARMS:
        cells = sorted(d for d in run.glob(prefix + "*") if d.is_dir() and d.name.split("-c128")[-1] in ("", "-r2", "-r3"))
        table.append((label, summarize(label, cells)))
    keys = list(table[0][1].keys())
    L = ["# Where the TTFT tail comes from\n",
         "Per request: hold = EPP dispatch minus EPP arrival (flow control); engine = TTFT minus hold. "
         "Class from the client side: first request of a session = new; later request held > 1 s = paused; else admitted. "
         "Tail = requests at or above their cell's TTFT p99, pooled over three cells per arm.\n",
         "| | " + " | ".join(label for label, _ in table) + " |", "|---|" + "---|" * len(table)]
    for k in keys:
        L.append(f"| {k} | " + " | ".join(rows[k] for _, rows in table) + " |")
    (HERE / "tail.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
