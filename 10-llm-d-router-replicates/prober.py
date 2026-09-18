#!/usr/bin/env python3
"""Sidecar prober for step 10: pod-side and EPP-side time series.

Every INTERVAL seconds, appends (with flush):

1. vllm-metrics.csv - scraped directly from the lane's vLLM pod /metrics
   (same columns as step 08: KV usage, running/waiting, preemptions,
   cumulative and interval prefix-cache queries/hits).
2. epp-metrics.csv  - the lane EPP's metrics port (kube-rbac; the pod's
   projected service-account token is sent as a bearer): thunder_agent
   programs by state, holds/releases by class, pauses/resumes/rebinds/
   starvation promotions, pod utilization, and the flow-control queue size
   and queue-wait histogram sum/count.

There is no per-program timeline: the EPP's state dump is sanitized and does
not list program ids, so the step 08 "same sessions" comparison is not
available here.

Env: VLLM_URL, EPP_METRICS_URL, TOKEN_FILE, OUT_DIR, INTERVAL, MAX_SECONDS.
"""
import csv
import os
import re
import time
import urllib.request

VLLM_URL = os.environ["VLLM_URL"]
EPP_URL = os.environ["EPP_METRICS_URL"]
TOKEN_FILE = os.environ.get("TOKEN_FILE", "/var/run/secrets/kubernetes.io/serviceaccount/token")
OUT_DIR = os.environ.get("OUT_DIR", "/results")
INTERVAL = float(os.environ.get("INTERVAL", "2"))
MAX_SECONDS = float(os.environ.get("MAX_SECONDS", "0") or 0)

VLLM_FIELDS = ["ts", "kv_cache_usage_perc", "num_requests_running",
               "num_requests_waiting", "num_preemptions_total",
               "cum_prefix_cache_queries", "cum_prefix_cache_hits",
               "interval_queries", "interval_hits", "interval_hit_rate"]
EPP_FIELDS = ["ts", "programs_running", "programs_idle", "programs_marked", "programs_paused",
              "holds_reasoning", "holds_paused", "holds_new",
              "releases_reasoning", "releases_paused", "releases_new",
              "pauses_total", "resumes_total", "rebinds_total", "starvation_promotions_total",
              "pod_utilization", "fc_queue_size", "fc_queue_wait_sum", "fc_queue_wait_count"]


def prom_value(text, name, labels=""):
    m = re.search(rf"^\S*{re.escape(name)}(?:\{{[^}}]*{re.escape(labels)}[^}}]*\}})?\s+([\d.eE+-]+)", text, re.M)
    return float(m.group(1)) if m else None


def prom_sum(text, name):
    return sum(float(v) for v in re.findall(rf"^\S*{re.escape(name)}(?:\{{[^}}]*\}})?\s+([\d.eE+-]+)", text, re.M)) or None


def get(url, timeout=10, token=None):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
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
    epp_csv = Csv(os.path.join(OUT_DIR, "epp-metrics.csv"), EPP_FIELDS)
    token = open(TOKEN_FILE).read().strip() if os.path.exists(TOKEN_FILE) else None
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
            m = get(EPP_URL, token=token)
            g = lambda name, labels="": prom_value(m, name, labels)
            epp_csv.row({
                "ts": ts,
                "programs_running": g("thunder_agent_programs", 'state="running"'),
                "programs_idle": g("thunder_agent_programs", 'state="idle"'),
                "programs_marked": g("thunder_agent_programs", 'state="marked"'),
                "programs_paused": g("thunder_agent_programs", 'state="paused"'),
                "holds_reasoning": g("thunder_agent_holds_total", 'class="reasoning"'),
                "holds_paused": g("thunder_agent_holds_total", 'class="paused"'),
                "holds_new": g("thunder_agent_holds_total", 'class="new"'),
                "releases_reasoning": g("thunder_agent_releases_total", 'class="reasoning"'),
                "releases_paused": g("thunder_agent_releases_total", 'class="paused"'),
                "releases_new": g("thunder_agent_releases_total", 'class="new"'),
                "pauses_total": g("thunder_agent_pauses_total"),
                "resumes_total": g("thunder_agent_resumes_total"),
                "rebinds_total": g("thunder_agent_rebinds_total"),
                "starvation_promotions_total": g("thunder_agent_starvation_promotions_total"),
                "pod_utilization": g("thunder_agent_pod_utilization"),
                "fc_queue_size": prom_sum(m, "flow_control_queue_size"),
                "fc_queue_wait_sum": prom_sum(m, "flow_control_request_queue_duration_seconds_sum"),
                "fc_queue_wait_count": prom_sum(m, "flow_control_request_queue_duration_seconds_count"),
            })
        except Exception as e:
            print(f"epp probe failed: {e}", flush=True)
        if final:
            break
        if os.path.exists(done_path):
            print("prober: DONE seen", flush=True)
            final = True
            continue
        if MAX_SECONDS and (time.time() - started) >= MAX_SECONDS:
            print(f"prober: deadline {MAX_SECONDS:.0f}s reached without DONE", flush=True)
            final = True
            continue
        time.sleep(INTERVAL)
    print("prober: done", flush=True)


if __name__ == "__main__":
    main()
