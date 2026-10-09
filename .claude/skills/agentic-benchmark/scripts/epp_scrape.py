"""Scrape the EPP metrics port into one gzip file, one gzip member per snapshot.

Runs as a native sidecar of the aiperf Job (MODE=pool), so it starts before
aiperf and stops when aiperf exits. The port enforces kube-rbac, so the pod
runs as service account thunderagent-metrics-reader and sends its token.
A killed pod loses at most the snapshot being written.

Env: EPP_METRICS_URLS (space-separated), OUT_DIR, INTERVAL (seconds, default 10).
"""

import gzip
import os
import time
import urllib.request

TOKEN_FILE = "/var/run/secrets/kubernetes.io/serviceaccount/token"


def main() -> None:
    urls = os.environ["EPP_METRICS_URLS"].split()
    out = os.environ["OUT_DIR"]
    interval = float(os.environ.get("INTERVAL", "10"))
    os.makedirs(out, exist_ok=True)
    while True:
        ts = time.time()
        token = open(TOKEN_FILE).read().strip()  # the kubelet rotates it
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
                text = urllib.request.urlopen(req, timeout=10).read().decode()
                with gzip.open(os.path.join(out, "raw-epp-metrics.txt.gz"), "at") as f:
                    f.write(f"# ts={ts:.3f} url={url}\n{text}")
            except Exception as e:
                print(f"{ts:.0f} scrape {url} failed: {e}", flush=True)
        time.sleep(max(0.0, interval - (time.time() - ts)))


if __name__ == "__main__":
    main()
