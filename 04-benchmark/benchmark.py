#!/usr/bin/env python3
"""Benchmark the original ThunderAgent router with an agentic multi-turn workload.

Drives N concurrent sessions (one program_id each) of T turns through the
router's OpenAI endpoint. Each session starts with a unique ~large preamble so
prefix-cache hits can only come from the session's own earlier turns, which is
exactly the reuse ThunderAgent's sticky placement is supposed to protect.

While the workload runs, a prober thread polls the router every
--probe-interval seconds and records time series to CSV:
  - per backend (from /metrics): kv_cache_usage_perc, cumulative
    prefix_cache_queries/hits plus the interval hit rate computed from their
    deltas, num_requests_running/waiting, active/reasoning/acting program
    tokens as seen by the scheduler
  - router-level (from /health): reasoning/acting/paused program counts
  - per program (from /programs): current backend, for the stickiness check

At the end the script validates the run and exits non-zero if a check fails:
  1. every request returned HTTP 200
  2. every program stayed on a single backend for the whole run (sticky)
  3. aggregate prefix-cache hit rate over the run window >= --min-hit-rate
  4. peak KV cache utilization > 0 (the workload actually touched the cache)
  5. all sessions were tracked as programs and released cleanly

Stdlib only; run it against a port-forward (see run-benchmark.sh).
"""
import argparse
import csv
import json
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

WORDS = (
    "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima "
    "mike november oscar papa quebec romeo sierra tango uniform victor whiskey "
    "xray yankee zulu ledger vector matrix kernel socket buffer packet thread"
).split()


def http_json(url, payload=None, timeout=300):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read())


def make_preamble(session_idx, n_words):
    rng = random.Random(1000 + session_idx)
    words = " ".join(rng.choice(WORDS) for _ in range(n_words))
    return (
        f"You are agent session {session_idx}. Here is your working context "
        f"(a log you must remember): {words}\n"
    )


class SessionResult:
    def __init__(self, program_id):
        self.program_id = program_id
        self.turns = []  # dicts: turn, status, latency_s, prompt_tokens, completion_tokens
        self.errors = []
        self.profile = None
        self.released = False


def finish_session(base_url, result, release=True):
    """Capture the program's profile, then (optionally) release it.

    Releasing per session matters under saturation: ThunderAgent only frees a
    program's tokens on release, so paused programs can only resume if
    finished sessions release promptly. --no-release models the realistic
    case where clients never signal completion; then capacity turnover relies
    on acting-token decay (if enabled) or the 1800s forced-resume timeout.
    """
    pid = result.program_id
    try:
        _, result.profile = http_json(f"{base_url}/profiles/{pid}", timeout=30)
    except Exception:
        pass
    if not release:
        return
    try:
        _, body = http_json(f"{base_url}/programs/release", {"program_id": pid}, timeout=30)
        result.released = bool(body.get("released"))
    except Exception as e:
        result.errors.append(f"release: {e}")


def run_session(base_url, model, session_idx, args, result, start_delay=0.0):
    if start_delay > 0:
        time.sleep(start_delay)
    pid = result.program_id
    messages = [
        {
            "role": "user",
            "content": make_preamble(session_idx, args.preamble_words)
            + "Summarize your context log in one sentence.",
        }
    ]
    for turn in range(args.turns):
        payload = {
            "model": model,
            "program_id": pid,
            "max_tokens": args.max_tokens,
            "temperature": 0,
            "messages": messages,
        }
        t0 = time.monotonic()
        try:
            status, body = http_json(
                f"{base_url}/v1/chat/completions", payload, timeout=args.request_timeout
            )
        except urllib.error.HTTPError as e:
            result.errors.append(f"turn {turn}: HTTP {e.code}")
            result.turns.append({"turn": turn, "status": e.code, "latency_s": None})
            finish_session(base_url, result, release=not args.no_release)
            return
        except Exception as e:
            result.errors.append(f"turn {turn}: {e}")
            result.turns.append({"turn": turn, "status": "error", "latency_s": None})
            finish_session(base_url, result, release=not args.no_release)
            return
        latency = time.monotonic() - t0
        usage = body.get("usage", {})
        result.turns.append(
            {
                "turn": turn,
                "status": status,
                "latency_s": round(latency, 3),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            }
        )
        reply = body["choices"][0]["message"]["content"]
        messages.append({"role": "assistant", "content": reply})
        messages.append(
            {
                "role": "user",
                "content": f"Turn {turn + 2}: add one more observation about item "
                f"{turn + 2} of your context log, one sentence.",
            }
        )
        time.sleep(args.think_time)  # tool-call / think gap between turns
    finish_session(base_url, result, release=not args.no_release)


class Prober(threading.Thread):
    def __init__(self, base_url, interval, out_dir):
        super().__init__(daemon=True)
        self.base_url = base_url
        self.interval = interval
        self.stop_event = threading.Event()
        self.backend_rows = []
        self.router_rows = []
        self.program_rows = []  # per-program status timeline (who is paused when)
        self.program_backends = {}  # program_id -> set of backends seen
        self.prev_counters = {}  # backend -> (queries, hits)
        self.out_dir = out_dir

    def sample(self):
        ts = round(time.time(), 1)
        _, m = http_json(f"{self.base_url}/metrics")
        for url, b in m["backends"].items():
            met = b.get("metrics", {})
            q, h = met.get("prefix_cache_queries", 0), met.get("prefix_cache_hits", 0)
            pq, ph = self.prev_counters.get(url, (q, h))
            dq, dh = q - pq, h - ph
            self.prev_counters[url] = (q, h)
            self.backend_rows.append(
                {
                    "ts": ts,
                    "backend": url,
                    "kv_cache_usage_perc": met.get("kv_cache_usage_perc"),
                    "interval_hit_rate": round(dh / dq, 4) if dq > 0 else "",
                    "interval_queries": dq,
                    "interval_hits": dh,
                    "cum_prefix_cache_queries": q,
                    "cum_prefix_cache_hits": h,
                    "num_requests_running": met.get("num_requests_running"),
                    "num_requests_waiting": met.get("num_requests_waiting"),
                    "num_preemptions": met.get("num_preemptions"),
                    "active_program_tokens": b.get("active_program_tokens"),
                    "reasoning_program_tokens": b.get("reasoning_program_tokens"),
                    "acting_program_tokens": b.get("acting_program_tokens"),
                    "capacity_overflow": b.get("capacity_overflow"),
                }
            )
        _, h = http_json(f"{self.base_url}/health")
        self.router_rows.append(
            {
                "ts": ts,
                "programs_count": h["programs_count"],
                "reasoning_count": h["reasoning_count"],
                "acting_count": h["acting_count"],
                "paused_count": h["paused_count"],
            }
        )
        _, progs = http_json(f"{self.base_url}/programs")
        for pid, st in progs.items():
            if st.get("backend"):
                self.program_backends.setdefault(pid, set()).add(st["backend"])
            self.program_rows.append(
                {"ts": ts, "program_id": pid, "status": st.get("status"),
                 "state": st.get("state"), "backend": st.get("backend")}
            )

    def run(self):
        while not self.stop_event.is_set():
            try:
                self.sample()
            except Exception as e:
                print(f"prober: sample failed: {e}", file=sys.stderr)
            self.stop_event.wait(self.interval)
        try:
            self.sample()  # final sample
        except Exception:
            pass

    def write_csvs(self):
        for name, rows in (
            ("metrics-backends.csv", self.backend_rows),
            ("metrics-router.csv", self.router_rows),
            ("programs-timeline.csv", self.program_rows),
        ):
            if not rows:
                continue
            with open(self.out_dir / name, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base-url", default="http://localhost:18300")
    p.add_argument("--model", default="Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8")
    p.add_argument("--sessions", type=int, default=12)
    p.add_argument("--turns", type=int, default=5)
    p.add_argument("--preamble-words", type=int, default=900)
    p.add_argument("--max-tokens", type=int, default=120)
    p.add_argument("--think-time", type=float, default=0.5)
    p.add_argument("--probe-interval", type=float, default=2.0)
    p.add_argument("--min-hit-rate", type=float, default=0.3)
    p.add_argument("--ramp-seconds", type=float, default=0.0,
                   help="Stagger session starts uniformly over this window")
    p.add_argument("--request-timeout", type=float, default=300.0)
    p.add_argument("--expect-pauses", action="store_true",
                   help="Add a check that the scheduler paused at least one program")
    p.add_argument("--allow-backend-moves", action="store_true",
                   help="Report backend moves without failing the sticky check "
                        "(paused programs may legitimately be re-placed at admission)")
    p.add_argument("--expect-mode", default="tr", choices=["tr", "default"],
                   help="Fail preflight unless the router runs in this mode")
    p.add_argument("--no-release", action="store_true",
                   help="Never send /programs/release during the run (realistic "
                        "clients don't signal completion); leftovers are still "
                        "swept after the final measurement for cleanup")
    p.add_argument("--run-id", default=time.strftime("run-%Y%m%d-%H%M%S"))
    p.add_argument("--out", default=None, help="Output dir (default results/<run-id>)")
    args = p.parse_args()

    out_dir = Path(args.out or Path(__file__).parent / "results" / args.run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"output dir: {out_dir}")

    # Preflight: router must be up, in the expected mode, with backends.
    # Retry: service endpoints may lag the deployment rollout by a few seconds.
    health = None
    for attempt in range(30):
        try:
            _, health = http_json(f"{args.base_url}/health", timeout=10)
            break
        except Exception as e:
            print(f"preflight: router not reachable ({e}), retry {attempt + 1}/30")
            time.sleep(2)
    if health is None:
        print("FAIL: router unreachable after retries", file=sys.stderr)
        return 1
    print(f"router: mode={health['router_mode']} backends={len(health['backends'])}")
    if health["router_mode"] != args.expect_mode or not health["backends"]:
        print(f"FAIL: expected mode {args.expect_mode} with backends", file=sys.stderr)
        return 1

    prober = Prober(args.base_url, args.probe_interval, out_dir)
    prober.start()
    time.sleep(args.probe_interval)  # one baseline sample before load

    run_id = args.run_id
    results = [SessionResult(f"bench-{run_id}-s{i:03d}") for i in range(args.sessions)]
    threads = [
        threading.Thread(
            target=run_session,
            args=(args.base_url, args.model, i, args, r,
                  args.ramp_seconds * i / max(1, args.sessions - 1)),
        )
        for i, r in enumerate(results)
    ]
    t_start = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    makespan = time.monotonic() - t_start

    time.sleep(max(6.0, args.probe_interval))  # let the 5s metrics poll catch up
    prober.stop_event.set()
    prober.join(timeout=30)
    prober.write_csvs()

    # Sessions release themselves on finish; snapshot and sweep any leftovers.
    _, progs = http_json(f"{args.base_url}/programs")
    with open(out_dir / "programs-final.json", "w") as f:
        json.dump(progs, f, indent=2)
    bench_pids = {r.program_id for r in results}
    for pid in bench_pids & set(progs):
        http_json(f"{args.base_url}/programs/release", {"program_id": pid})
    with open(out_dir / "profiles.json", "w") as f:
        json.dump({r.program_id: r.profile for r in results if r.profile}, f, indent=2)

    # Per-turn CSV.
    with open(out_dir / "requests.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["program_id", "turn", "status", "latency_s", "prompt_tokens", "completion_tokens"])
        for r in results:
            for t in r.turns:
                w.writerow([r.program_id, t["turn"], t["status"], t.get("latency_s"),
                            t.get("prompt_tokens"), t.get("completion_tokens")])

    # ---- Validation ----
    checks = []

    total_expected = args.sessions * args.turns
    ok_turns = [t for r in results for t in r.turns if t["status"] == 200]
    errors = [e for r in results for e in r.errors]
    checks.append(("all requests succeeded",
                   len(ok_turns) == total_expected,
                   f"{len(ok_turns)}/{total_expected} ok" + (f"; errors: {errors[:3]}" if errors else "")))

    observed = prober.program_backends.keys() & bench_pids
    moved = {pid: sorted(bs) for pid, bs in prober.program_backends.items()
             if pid in bench_pids and len(bs) > 1}
    checks.append(("sticky routing (one backend per program)",
                   args.allow_backend_moves or not moved,
                   f"{len(observed)}/{args.sessions} programs observed, {len(moved)} moved"
                   + (f" (informational): {dict(list(moved.items())[:3])}" if moved else "")))

    dq = sum(r["interval_queries"] for r in prober.backend_rows)
    dh = sum(r["interval_hits"] for r in prober.backend_rows)
    agg_hit = dh / dq if dq else 0.0
    checks.append((f"aggregate prefix-cache hit rate >= {args.min_hit_rate}",
                   agg_hit >= args.min_hit_rate,
                   f"hit rate {agg_hit:.3f} ({dh}/{dq} tokens over the run window)"))

    peak_kv = max((r["kv_cache_usage_perc"] or 0) for r in prober.backend_rows)
    checks.append(("KV cache utilization rose above 0", peak_kv > 0,
                   f"peak kv_cache_usage_perc {peak_kv:.4f}"))

    released_ok = sum(1 for r in results if r.released)
    tracked = observed | {r.program_id for r in results if r.released}
    if args.no_release:
        checks.append(("all sessions tracked as programs (no-release mode)",
                       len(tracked) == args.sessions,
                       f"{len(tracked)}/{args.sessions} tracked, releases intentionally skipped"))
    else:
        checks.append(("all sessions tracked as programs and released",
                       len(tracked) == args.sessions and released_ok == args.sessions,
                       f"{len(tracked)}/{args.sessions} tracked, {released_ok}/{args.sessions} released"))

    max_paused = max((int(r["paused_count"]) for r in prober.router_rows), default=0)
    pause_times = [r.profile.get("avg_pause_s", 0) or 0 for r in results if r.profile]
    held = sum(1 for pv in pause_times if pv > 0.05)
    if args.expect_pauses:
        checks.append(("scheduler paused at least one program (admission control engaged)",
                       max_paused > 0 or held > 0,
                       f"max concurrent paused {max_paused}; {held}/{len(pause_times)} programs "
                       f"with avg pause > 50ms"
                       + (f", max avg pause {max(pause_times):.2f}s" if pause_times else "")))

    latencies = [t["latency_s"] for t in ok_turns if t["latency_s"] is not None]
    summary = {
        "run_id": run_id,
        "config": vars(args),
        "makespan_s": round(makespan, 2),
        "turns_ok": len(ok_turns),
        "turns_expected": total_expected,
        "latency_s": {
            "p50": round(statistics.median(latencies), 3) if latencies else None,
            "mean": round(statistics.fmean(latencies), 3) if latencies else None,
            "max": round(max(latencies), 3) if latencies else None,
        },
        "aggregate_prefix_hit_rate": round(agg_hit, 4),
        "peak_kv_cache_usage_perc": peak_kv,
        "max_paused_count": max_paused,
        "programs_held": held,
        "max_avg_pause_s": round(max(pause_times), 3) if pause_times else 0,
        "backend_moves": {pid: bs for pid, bs in moved.items()},
        "program_backend_map": {pid: sorted(bs) for pid, bs in prober.program_backends.items()
                                if pid in bench_pids},
        "checks": [{"name": n, "pass": ok, "detail": d} for n, ok, d in checks],
    }
    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nmakespan: {makespan:.1f}s, turn latency p50/mean/max: "
          f"{summary['latency_s']['p50']}/{summary['latency_s']['mean']}/{summary['latency_s']['max']}s")
    print(f"aggregate prefix-cache hit rate: {agg_hit:.3f}, peak KV usage: {peak_kv:.4f}, "
          f"max paused programs: {summary['max_paused_count']}")
    all_ok = True
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        all_ok = all_ok and ok
    print(f"\nrun {'as expected' if all_ok else 'NOT as expected'}; artifacts in {out_dir}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
