#!/usr/bin/env bash
# Run one step 20 phase: every point of its table as one run of step 10's lane
# driver, the three lanes in parallel with one arm each (LANE_ARMS), the
# per-cell reset clearing the CPU tier too (RESET_EXTERNAL=1), client timeout
# 1900 s. Each run directory gets step20.json (phase, c, window, warm-up, lane
# arms and nodes). Before each point the deployment is checked against the
# phase and the lanes are re-labeled (a spot replacement brings a new pod).
# REP=<n> (default 1) is the replicate number: replicate n moves every arm n-1
# lanes over (a <- b <- c <- a), so over replicates 1 to 3 each arm runs once on
# each pod at each point.
# Phase T is step 21 (offload tier budget arms, same offloading as phase B).
# Usage: [REP=n] run-cells.sh A|B|T [c ...]    (default: every point of the phase)
set -uo pipefail
source "$(dirname "$0")/lib.sh"
pin_kube
PHASE="${1:?usage: run-cells.sh A|B|T [c ...]}"; shift
ONLY=" $* "
REP="${REP:-1}"

# rotate "a:X b:Y c:Z" by k lanes: k=1 gives "a:Y b:Z c:X"
rotate() {
  python3 - "$1" "$2" <<'PY'
import sys
pairs = [p.split(":", 1) for p in sys.argv[1].split()]
k = int(sys.argv[2]) % len(pairs)
arms = [a for _, a in pairs]
arms = arms[k:] + arms[:k]
print(" ".join(f"{l}:{a}" for (l, _), a in zip(pairs, arms)))
PY
}

# c  window_s  warmup_s  lane arms (lane a on trwg, b on 91qy, c on zhnf)
case "$PHASE" in
  A) WANT="none 3"; POINTS="
32  1800 600 a:baseline b:thunder-lease-main c:thunder-lease-main
128 1800 600 a:thunder-lease-main b:baseline c:thunder-lease-main
256 2700 900 a:thunder-lease-main b:thunder-lease-main c:baseline" ;;
  B) WANT="400 3"; POINTS="
32  1800 600 a:baseline b:thunder-lease-main c:thunder-lease-main-tier
64  1800 600 a:thunder-lease-main-tier b:baseline c:thunder-lease-main
128 1800 600 a:thunder-lease-main b:thunder-lease-main-tier c:baseline
192 2700 900 a:baseline b:thunder-lease-main c:thunder-lease-main-tier
256 2700 900 a:thunder-lease-main-tier b:baseline c:thunder-lease-main" ;;
  T) WANT="400 3"; POINTS="
64  1800 600 a:thunder-lease-budget30 b:thunder-lease-budget5 c:thunder-lease-main5
128 1800 600 a:thunder-lease-main5 b:thunder-lease-budget30 c:thunder-lease-budget5
192 2700 900 a:thunder-lease-budget5 b:thunder-lease-main5 c:thunder-lease-budget30
256 2700 900 a:thunder-lease-budget30 b:thunder-lease-budget5 c:thunder-lease-main5" ;;
  *) echo "usage: run-cells.sh A|B|T [c ...]" >&2; exit 2 ;;
esac

# memory <phase> <c> <when>: each lane pod's cgroup memory, OOM kills and /dev/shm use, to results/vllm-memory.csv
memory() {
  [ -f "$RESULTS/vllm-memory.csv" ] || echo "ts,phase,c,when,lane,pod,memory_current_bytes,memory_max,oom_kill,shm_used_bytes" > "$RESULTS/vllm-memory.csv"
  source "$RESULTS/lanes.env"
  for L in $LANES; do
    local PV="LANE_${L}_POD"
    local V; V=$(kubectl exec "${!PV}" -n "$NS" -c modelserver -- sh -c \
      'echo "$(cat /sys/fs/cgroup/memory.current),$(cat /sys/fs/cgroup/memory.max),$(grep -E "^oom_kill " /sys/fs/cgroup/memory.events | cut -d" " -f2),$(df -B1 /dev/shm | tail -1 | tr -s " " | cut -d" " -f3)"' 2>/dev/null || echo ",,,")
    echo "$(date +%s),$1,$2,$3,$L,${!PV},$V" >> "$RESULTS/vllm-memory.csv"
  done
}

FAIL=0
while read -r C WINDOW WARMUP ARMS; do
  [ -n "$C" ] || continue
  [ "$ONLY" = "  " ] || [[ "$ONLY" == *" $C "* ]] || continue
  ARMS=$(rotate "$ARMS" $((REP - 1)))
  echo; echo "##### phase $PHASE replicate $REP c=$C window ${WINDOW}s warm-up ${WARMUP}s: $ARMS  ($(date))"
  GOT=$(deploy_offload_size)
  [ "$GOT" = "$WANT" ] || { echo "FATAL: deployment is (offloading, replicas) = ($GOT), phase $PHASE needs ($WANT)" >&2; exit 1; }
  "$STEP20/lanes.sh" label || { echo "FATAL: lanes could not be labeled" >&2; exit 1; }
  memory "$PHASE" "$C" before
  LOG="$RESULTS/run-$PHASE-r$REP-c$C-$(date +%Y%m%d-%H%M%S).log"
  LANE_ARMS="$ARMS" RESET_EXTERNAL=1 SKIP_ANALYSIS=1 \
    "$STEP10/run-replicates.sh" "$C" 1 "$WINDOW" baseline 1900 2>&1 | tee "$LOG"
  RC=${PIPESTATUS[0]}
  memory "$PHASE" "$C" after
  RUN=$(grep -oE '^artifacts: .*' "$LOG" | tail -1 | cut -d' ' -f2)
  if [ -n "$RUN" ] && [ -d "$RUN" ]; then
    mv "$LOG" "$RUN/driver.log"
    python3 - "$RUN/step20.json" "$PHASE" "$C" "$WINDOW" "$WARMUP" "$ARMS" "$RESULTS/lanes.env" "$EPP_IMAGE_TAG" "$BENCH_IMAGE" "$REP" <<'PY'
import json, sys
out, phase, c, window, warmup, arms, lanes_env, epp, bench, rep = sys.argv[1:]
lanes = dict(l.strip().split("=", 1) for l in open(lanes_env) if "=" in l)
json.dump({"phase": phase, "replicate": int(rep), "offload_gib": 400 if phase in ("B", "T") else 0, "concurrency": int(c),
           "window_s": int(window), "warmup_s": int(warmup), "client_timeout_s": 1900,
           "lane_arms": dict(a.split(":", 1) for a in arms.split()),
           "lanes": {l: {"pod": lanes.get(f"LANE_{l}_POD"), "ip": lanes.get(f"LANE_{l}_IP"), "node": lanes.get(f"LANE_{l}_NODE")} for l in "abc"},
           "epp_image_tag": epp, "bench_image": bench}, open(out, "w"), indent=1)
PY
    echo "phase $PHASE replicate $REP c=$C done: $RUN (exit $RC)"
  else
    echo "WARNING: phase $PHASE c=$C left no run directory; log in $LOG"
  fi
  # run-replicates.sh exits 0 when a lane fails and says so in its output instead.
  if [ "$RC" != 0 ] || grep -q "at least one lane failed" "${RUN:-.}/driver.log" "$LOG" 2>/dev/null; then
    echo "WARNING: phase $PHASE c=$C: at least one lane failed (see the log)"; FAIL=1
  fi
done <<< "$POINTS"
exit $FAIL
