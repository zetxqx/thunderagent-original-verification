#!/usr/bin/env python3
"""Sidecar prober for step 12: every vLLM pod of the pool plus the EPP.

Every INTERVAL seconds, appends (with flush):

1. vllm-metrics.csv - pool aggregate over all pods (KV usage averaged, counts
   summed, interval hit rate from the summed counter deltas), plus
   vllm-metrics-<pod>.csv per pod with the same columns.
2. epp-metrics.csv  - the lane EPP's metrics port (kube-rbac; the pod's
   projected service-account token is sent as a bearer): thunder_agent
   programs by state, holds/releases by class, pauses/resumes/rebinds/
   starvation promotions, pod utilization, and the flow-control queue size
   and queue-wait histogram sum/count.

3. epp-pods.csv - per pod: undecayed and decayed working set and capacity
   (the minimal thunder-agent's pod_working_set_tokens / pod_capacity_tokens),
   so pod balance can be read; epp-metrics.csv carries their pool sums.
4. raw-epp-metrics.txt.gz, raw-vllm-<pod-ip>.txt.gz - every RAW_INTERVAL
   seconds (0 disables) the full text of each scrape, one gzip member per
   snapshot preceded by a "# ts=<epoch>" line (step 16).

There is no per-program timeline: the EPP's state dump is sanitized and does
not list program ids, so the step 08 "same sessions" comparison is not
available here.

Env: VLLM_URLS (comma-separated), EPP_METRICS_URL, TOKEN_FILE, OUT_DIR, INTERVAL,
RAW_INTERVAL, MAX_SECONDS.
"""
import csv
import gzip
import os
import re
import time
import urllib.request

VLLM_URLS = [u for u in os.environ["VLLM_URLS"].split(",") if u]  # one per pod in the pool
EPP_URL = os.environ["EPP_METRICS_URL"]
TOKEN_FILE = os.environ.get("TOKEN_FILE", "/var/run/secrets/kubernetes.io/serviceaccount/token")
OUT_DIR = os.environ.get("OUT_DIR", "/results")
INTERVAL = float(os.environ.get("INTERVAL", "2"))
RAW_INTERVAL = float(os.environ.get("RAW_INTERVAL", "10") or 0)
MAX_SECONDS = float(os.environ.get("MAX_SECONDS", "0") or 0)

VLLM_FIELDS = ["ts", "kv_cache_usage_perc", "num_requests_running",
               "num_requests_waiting", "num_preemptions_total",
               "cum_prefix_cache_queries", "cum_prefix_cache_hits",
               "interval_queries", "interval_hits", "interval_hit_rate"]
EPP_FIELDS = ["ts", "programs_running", "programs_idle", "programs_marked", "programs_paused",
              "holds_reasoning", "holds_paused", "holds_new",
              "releases_reasoning", "releases_paused", "releases_new",
              "pauses_total", "resumes_total", "rebinds_total", "starvation_promotions_total", "origin_waits_total", "urgent_promotions_total", "origin_wait_moves_total",
              "pod_utilization", "fc_queue_size", "fc_queue_wait_sum", "fc_queue_wait_count",
              # step 16: minimal plugin, pool sums of the per-pod gauges
              "working_set_undecayed", "working_set_decayed", "capacity_tokens"]
POD_FIELDS = ["ts", "pod", "working_set_undecayed", "working_set_decayed", "capacity_tokens"]


def prom_value(text, name, labels=""):
    m = re.search(rf"^\S*{re.escape(name)}(?:\{{[^}}]*{re.escape(labels)}[^}}]*\}})?\s+([\d.eE+-]+)", text, re.M)
    return float(m.group(1)) if m else None


def prom_sum(text, name):
    return sum(float(v) for v in re.findall(rf"^\S*{re.escape(name)}(?:\{{[^}}]*\}})?\s+([\d.eE+-]+)", text, re.M)) or None


def prom_by_pod(text, name):
    """{(pod, view or source): value} over every series of a per-pod gauge."""
    out = {}
    for labels, v in re.findall(rf"^\S*{re.escape(name)}\{{([^}}]*)\}}\s+([\d.eE+-]+)", text, re.M):
        d = dict(re.findall(r'(\w+)="([^"]*)"', labels))
        out[(d.get("pod", ""), d.get("view", d.get("source", "")))] = float(v)
    return out


def save_raw(name, ts, text):
    # One complete gzip member per snapshot: a killed pod loses at most one.
    with gzip.open(os.path.join(OUT_DIR, name), "at") as f:
        f.write(f"# ts={ts}\n{text}")


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
    pod_csv = {u: Csv(os.path.join(OUT_DIR, f"vllm-metrics-{u.split('//')[-1].split(':')[0].replace('.', '-')}.csv"), VLLM_FIELDS) for u in VLLM_URLS}
    epp_csv = Csv(os.path.join(OUT_DIR, "epp-metrics.csv"), EPP_FIELDS)
    pods_csv = Csv(os.path.join(OUT_DIR, "epp-pods.csv"), POD_FIELDS)
    last_raw = 0.0
    token = open(TOKEN_FILE).read().strip() if os.path.exists(TOKEN_FILE) else None
    prev = {u: (None, None) for u in VLLM_URLS}
    prev_pool = (None, None)
    done_path = os.path.join(OUT_DIR, "DONE")
    started = time.time()
    final = False
    while True:
        ts = round(time.time(), 1)
        raw = RAW_INTERVAL > 0 and (final or ts - last_raw >= RAW_INTERVAL)
        if raw:
            last_raw = ts
        agg = {"kv": [], "run": 0.0, "wait": 0.0, "pre": 0.0, "q": 0.0, "h": 0.0, "n": 0}
        for u in VLLM_URLS:
            try:
                text = get(f"{u}/metrics")
                if raw:
                    save_raw(f"raw-vllm-{u.split('//')[-1].split(':')[0].replace('.', '-')}.txt.gz", ts, text)
                q = prom_value(text, "vllm:prefix_cache_queries_total") or 0
                h = prom_value(text, "vllm:prefix_cache_hits_total") or 0
                pq, ph = prev[u]
                dq = q - pq if pq is not None else 0
                dh = h - ph if ph is not None else 0
                prev[u] = (q, h)
                kv = prom_value(text, "vllm:kv_cache_usage_perc") or 0.0
                run = prom_value(text, "vllm:num_requests_running") or 0.0
                wait = prom_value(text, "vllm:num_requests_waiting") or 0.0
                pre = prom_value(text, "vllm:num_preemptions_total") or 0.0
                pod_csv[u].row({"ts": ts, "kv_cache_usage_perc": kv, "num_requests_running": run,
                                "num_requests_waiting": wait, "num_preemptions_total": pre,
                                "cum_prefix_cache_queries": int(q), "cum_prefix_cache_hits": int(h),
                                "interval_queries": int(dq), "interval_hits": int(dh),
                                "interval_hit_rate": round(dh / dq, 4) if dq > 0 else ""})
                agg["kv"].append(kv); agg["run"] += run; agg["wait"] += wait; agg["pre"] += pre
                agg["q"] += q; agg["h"] += h; agg["n"] += 1
            except Exception as e:
                print(f"vllm probe failed for {u}: {e}", flush=True)
        if agg["n"]:
            pq, ph = prev_pool
            dq = agg["q"] - pq if pq is not None else 0
            dh = agg["h"] - ph if ph is not None else 0
            prev_pool = (agg["q"], agg["h"])
            vllm_csv.row({"ts": ts, "kv_cache_usage_perc": round(sum(agg["kv"]) / len(agg["kv"]), 4),
                          "num_requests_running": agg["run"], "num_requests_waiting": agg["wait"],
                          "num_preemptions_total": agg["pre"],
                          "cum_prefix_cache_queries": int(agg["q"]), "cum_prefix_cache_hits": int(agg["h"]),
                          "interval_queries": int(dq), "interval_hits": int(dh),
                          "interval_hit_rate": round(dh / dq, 4) if dq > 0 else ""})
        try:
            m = get(EPP_URL, token=token)
            if raw:
                save_raw("raw-epp-metrics.txt.gz", ts, m)
            g = lambda name, labels="": prom_value(m, name, labels)
            ws = prom_by_pod(m, "thunder_agent_pod_working_set_tokens")
            # The lease build exports one full-footprint series with no view
            # label: the minimal build's undecayed view.
            ws = {(p, k or "undecayed"): v for (p, k), v in ws.items()}
            cap = {pod: v for (pod, _), v in prom_by_pod(m, "thunder_agent_pod_capacity_tokens").items()}
            for pod in sorted({p for p, _ in ws} | set(cap)):
                pods_csv.row({"ts": ts, "pod": pod, "working_set_undecayed": ws.get((pod, "undecayed")),
                              "working_set_decayed": ws.get((pod, "decayed")), "capacity_tokens": cap.get(pod)})
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
                "origin_waits_total": g("thunder_agent_origin_waits_total"),
                "urgent_promotions_total": g("thunder_agent_urgent_promotions_total"),
                "origin_wait_moves_total": g("thunder_agent_origin_wait_moves_total"),
                "pod_utilization": g("thunder_agent_pod_utilization"),
                "fc_queue_size": prom_sum(m, "flow_control_queue_size"),
                "fc_queue_wait_sum": prom_sum(m, "flow_control_request_queue_duration_seconds_sum"),
                "fc_queue_wait_count": prom_sum(m, "flow_control_request_queue_duration_seconds_count"),
                "working_set_undecayed": sum(v for (_, k), v in ws.items() if k == "undecayed") if ws else None,
                "working_set_decayed": sum(v for (_, k), v in ws.items() if k == "decayed") if ws else None,
                "capacity_tokens": sum(cap.values()) if cap else None,
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
