#!/usr/bin/env python3
"""Sidecar prober: pod-side and router-side time series during a bench cell.

Every INTERVAL seconds, appends (with flush, so partial data survives kills):

1. vllm-metrics.csv  - scraped DIRECTLY from the vLLM pod's /metrics
   (authoritative, not router-mediated): kv_cache_usage_perc,
   num_requests_running, num_requests_waiting, num_preemptions_total,
   cumulative prefix_cache queries/hits plus the interval hit rate from
   counter deltas.
2. router-health.csv - ThunderAgent /health: programs / reasoning / acting /
   paused counts (aggregate pause signal).
3. programs-timeline.csv - ThunderAgent /programs: one row per program per
   sample with status (reasoning/acting), state (active/PAUSED - the pause
   lives in `state`), and backend. Per-program pause intervals come from
   this file.

Exits after one final sample once OUT_DIR/DONE appears, or once MAX_SECONDS
has elapsed. The deadline matters: if the benchmark hangs without writing
DONE, sampling an idle system would pad the tail of every series and fake a
collapse in effective concurrency (that artifact appeared in calibration
round 2 - see HANG-INVESTIGATION.md).

Env: VLLM_URL, ROUTER_URL, OUT_DIR (/results), INTERVAL (2),
MAX_SECONDS (0 = no deadline).
"""
import csv
import json
import os
import re
import time
import urllib.request

VLLM_URL = os.environ["VLLM_URL"]
ROUTER_URL = os.environ.get("ROUTER_URL", "http://thunderagent-ab:8300")
OUT_DIR = os.environ.get("OUT_DIR", "/results")
INTERVAL = float(os.environ.get("INTERVAL", "2"))
MAX_SECONDS = float(os.environ.get("MAX_SECONDS", "0") or 0)

VLLM_FIELDS = ["ts", "kv_cache_usage_perc", "num_requests_running",
               "num_requests_waiting", "num_preemptions_total",
               "cum_prefix_cache_queries", "cum_prefix_cache_hits",
               "interval_queries", "interval_hits", "interval_hit_rate"]
HEALTH_FIELDS = ["ts", "programs_count", "reasoning_count", "acting_count", "paused_count"]
PROG_FIELDS = ["ts", "program_id", "status", "state", "backend"]


def prom_value(text, name):
    m = re.search(rf"^{re.escape(name)}(?:\{{[^}}]*\}})?\s+([\d.eE+-]+)", text, re.M)
    return float(m.group(1)) if m else None


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode()


class Csv:
    def __init__(self, path, fields):
        new = not os.path.exists(path)
        self.f = open(path, "a", newline="")
        self.w = csv.DictWriter(self.f, fieldnames=fields)
        if new:
            self.w.writeheader()

    def row(self, d):
        self.w.writerow(d)
        self.f.flush()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    vllm_csv = Csv(os.path.join(OUT_DIR, "vllm-metrics.csv"), VLLM_FIELDS)
    health_csv = Csv(os.path.join(OUT_DIR, "router-health.csv"), HEALTH_FIELDS)
    prog_csv = Csv(os.path.join(OUT_DIR, "programs-timeline.csv"), PROG_FIELDS)
    prev_q = prev_h = None
    done_path = os.path.join(OUT_DIR, "DONE")
    started = time.time()
    final = False
    while True:
        ts = round(time.time(), 1)
        try:
            text = get(f"{VLLM_URL}/metrics")
            q = prom_value(text, "vllm:prefix_cache_queries_total") or 0
            h = prom_value(text, "vllm:prefix_cache_hits_total") or 0
            dq = q - prev_q if prev_q is not None else 0
            dh = h - prev_h if prev_h is not None else 0
            prev_q, prev_h = q, h
            vllm_csv.row({
                "ts": ts,
                "kv_cache_usage_perc": prom_value(text, "vllm:kv_cache_usage_perc"),
                "num_requests_running": prom_value(text, "vllm:num_requests_running"),
                "num_requests_waiting": prom_value(text, "vllm:num_requests_waiting"),
                "num_preemptions_total": prom_value(text, "vllm:num_preemptions_total"),
                "cum_prefix_cache_queries": int(q), "cum_prefix_cache_hits": int(h),
                "interval_queries": int(dq), "interval_hits": int(dh),
                "interval_hit_rate": round(dh / dq, 4) if dq > 0 else "",
            })
        except Exception as e:
            print(f"vllm probe failed: {e}", flush=True)
        try:
            hd = json.loads(get(f"{ROUTER_URL}/health"))
            health_csv.row({"ts": ts, "programs_count": hd["programs_count"],
                            "reasoning_count": hd["reasoning_count"],
                            "acting_count": hd["acting_count"],
                            "paused_count": hd["paused_count"]})
            progs = json.loads(get(f"{ROUTER_URL}/programs"))
            for pid, st in progs.items():
                prog_csv.row({"ts": ts, "program_id": pid, "status": st.get("status"),
                              "state": st.get("state"), "backend": st.get("backend")})
        except Exception as e:
            print(f"router probe failed: {e}", flush=True)
        if final:
            break
        if os.path.exists(done_path):
            print("prober: DONE seen", flush=True)
            final = True  # one more sample, then exit
            continue
        if MAX_SECONDS and (time.time() - started) >= MAX_SECONDS:
            print(f"prober: deadline {MAX_SECONDS:.0f}s reached without DONE", flush=True)
            final = True
            continue
        time.sleep(INTERVAL)
    print("prober: done", flush=True)


if __name__ == "__main__":
    main()
