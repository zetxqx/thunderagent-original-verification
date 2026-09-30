#!/usr/bin/env bash
# Recover a cell whose results copy failed (kubectl cp "unexpected EOF" on the
# large per-request report makes run_cell stop before manifest.json and before
# deleting the bench job, whose pod keeps /results for 8 h after the run).
# Copies /results again (tar stream, every file gzip-compressed in the pod),
# checks each file's md5 against the pod, writes manifest.json from what is
# known, and deletes the bench job. The partial copy is kept as results-partial-copy/.
# Usage: recover-cell.sh <run-dir> <cell>   e.g. results/rep-...-c256-t1900 epp-baseline-c
set -euo pipefail
source "$(dirname "$0")/lib.sh"
pin_kube
RUN=$(cd "$1" && pwd); CELL=$2; C="$RUN/$CELL"
LANE=${CELL##*-}; ARM=${CELL#epp-}; ARM=${ARM%-*}
P=$(kubectl get pods -n "$NS" -l "cell=$CELL" -o jsonpath='{.items[0].metadata.name}')
[ -n "$P" ] || { echo "FATAL: no bench pod for $CELL (job already deleted?)" >&2; exit 1; }
kubectl exec "$P" -n "$NS" -c bench -- test -f /results/DONE || { echo "FATAL: $CELL's bench has not finished" >&2; exit 1; }

[ -d "$C/results" ] && [ ! -d "$C/results-partial-copy" ] && mv "$C/results" "$C/results-partial-copy"
rm -rf "$C/results"; mkdir -p "$C/results"
REMOTE=$(kubectl exec "$P" -n "$NS" -c bench -- sh -c 'cd /results && find . -type f | sort | xargs md5sum')
while read -r SUM F; do
  mkdir -p "$C/results/$(dirname "$F")"
  for i in 1 2 3 4 5; do
    kubectl exec "$P" -n "$NS" -c bench -- gzip -c "/results/$F" 2>/dev/null | gunzip -c > "$C/results/$F" 2>/dev/null || true
    [ "$(md5 -q "$C/results/$F")" = "$SUM" ] && break
    echo "retry $i: $F"; sleep 5
  done
  [ "$(md5 -q "$C/results/$F")" = "$SUM" ] || { echo "FATAL: $F still differs from the pod after 5 tries" >&2; exit 1; }
done <<< "$REMOTE"
echo "$(wc -l <<< "$REMOTE" | tr -d ' ') files copied, all md5 match the pod"

META=$(python3 -c "import json; print(json.load(open('$RUN/step20.json'))['lanes']['$LANE']['pod'])")
VUID=$(kubectl get pod "$META" -n "$NS" -o jsonpath='{.metadata.uid}' 2>/dev/null || true)
VRS=$(kubectl get pod "$META" -n "$NS" -o jsonpath='{.status.containerStatuses[?(@.name=="modelserver")].restartCount}' 2>/dev/null || true)
T0=$(gzip -dc "$C/results/raw-vllm-metrics.txt.gz" | grep -m1 "^# ts=" | cut -d= -f2 | cut -d. -f1)
C_=$(python3 -c "import json; print(json.load(open('$RUN/step20.json'))['concurrency'])")
W=$(python3 -c "import json; print(json.load(open('$RUN/step20.json'))['window_s'])")
python3 - "$C/manifest.json" "$CELL" "$ARM" "$LANE" "$C_" "$W" "$META" "$VUID" "$VRS" "$P" "$T0" "$C/config.yml" "$C/plugins.yaml" <<'EOF'
import json, sys, hashlib
out, cell, arm, lane, c, w, vp, vuid, vrs, bp, t0, cfg, plug = sys.argv[1:]
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
json.dump({"cell": cell, "arm": arm, "lane": lane, "concurrency": int(c), "window_s": int(w), "client_timeout_s": 1900,
  "vllm_pod": vp, "vllm_pod_uid": vuid, "bench_pod": bp, "preempted": False, "started_epoch": int(t0),
  "vllm_restarts_start": "0", "vllm_restarts_end": vrs, "config_sha256": sha(cfg), "plugins_sha256": sha(plug),
  "recovered": "written by recover-cell.sh: the driver's results copy failed, so run_cell stopped before this file; "
               "results/ was re-copied from the bench pod and every file matches the pod's md5; the partial copy is in results-partial-copy/"},
  open(out, "w"), indent=1)
EOF
echo "vLLM pod $META restarts now: ${VRS:-unknown} (a non-zero count means the cell may be affected)"
kubectl delete job "weka-bench-$CELL" -n "$NS"
