#!/usr/bin/env bash
# Check one point directory after a smoke or calibration run: the checklist of
# SKILL.md step 4, as a script. Needs only bash and python3 (no uv).
#
# Usage: verify-point.sh <results/<label>/c<N>> [...]
# Exit 0 when every point passes; each failed check is printed as "FAIL <point>: ...".
#
# Checks, per point:
#   job      meta/finish.json says the job succeeded and no pod changed
#   records  profile_export.jsonl has profiling-phase requests without error
#   parquet  server_metrics_export.parquet exists (vLLM metrics for the figures)
#   cached   at least one response carries a cached-token count
#            (vLLM needs --enable-prompt-tokens-details)
#   epp      pool or lane-EPP mode: epp/raw-epp-metrics.txt.gz exists and no
#            epp-*.log line says the gate was defeated by the setup
#   log      logs/aiperf.log has the "Phase profiling ... complete" line
set -uo pipefail

[ $# -gt 0 ] || { echo "usage: verify-point.sh <point-dir> [...]" >&2; exit 2; }

rc=0
for d in "$@"; do
  d=${d%/}
  art="$d/aiperf_artifacts"
  fail() { echo "FAIL $d: $*"; rc=1; }
  ok() { echo "  ok $d: $*"; }

  # job
  if [ -f "$d/meta/finish.json" ]; then
    status=$(python3 -c "import json,sys; f=json.load(open(sys.argv[1])); print(f.get('job_status'), f.get('pod_changed'))" "$d/meta/finish.json")
    case "$status" in
      "succeeded False") ok "job succeeded, pods unchanged" ;;
      *) fail "finish.json: job_status/pod_changed = $status" ;;
    esac
  else
    fail "no meta/finish.json (run-point.sh did not finish)"
  fi

  # records and cached tokens
  if [ -s "$art/profile_export.jsonl" ]; then
    read -r n_prof n_ok n_cached <<<"$(python3 - "$art/profile_export.jsonl" <<'PY'
import json, sys
prof = ok = cached = 0
for line in open(sys.argv[1]):
    r = json.loads(line)
    m = r.get("metadata", {})
    if m.get("benchmark_phase") != "profiling":
        continue
    prof += 1
    if not r.get("error") and not m.get("was_cancelled"):
        ok += 1
    c = (r.get("metrics") or {}).get("usage_prompt_cache_read_tokens") or {}
    if (c.get("value") or 0) > 0:
        cached += 1
print(prof, ok, cached)
PY
)"
    if [ "$n_ok" -gt 0 ]; then ok "$n_ok of $n_prof profiling requests completed"; else fail "no completed profiling request ($n_prof profiling records)"; fi
    if [ "$n_cached" -gt 0 ]; then ok "$n_cached responses carry cached tokens"; else fail "no response carries usage_prompt_cache_read_tokens (vLLM --enable-prompt-tokens-details?)"; fi
  else
    fail "no $art/profile_export.jsonl"
  fi

  # parquet
  if [ -s "$art/server_metrics_export.parquet" ]; then ok "server metrics parquet present"; else fail "no server_metrics_export.parquet (were --server-metrics URLs reachable?)"; fi

  # aiperf log
  if [ -f "$art/logs/aiperf.log" ] && grep -q "Phase profiling (profiling) complete" "$art/logs/aiperf.log"; then
    ok "aiperf.log has the profiling complete line"
  else
    fail "aiperf.log missing or without 'Phase profiling (profiling) complete'"
  fi

  # EPP (pool mode or a lane EPP)
  if [ -f "$d/meta/point.json" ]; then
    epp=$(python3 -c "import json,sys; p=json.load(open(sys.argv[1])); print('1' if p.get('mode')=='pool' or str(p.get('lane_epp'))=='1' else '0')" "$d/meta/point.json")
    if [ "$epp" = 1 ]; then
      if [ -s "$d/epp/raw-epp-metrics.txt.gz" ]; then ok "EPP scrape present"; else fail "no epp/raw-epp-metrics.txt.gz (metrics-reader RBAC, EPP_SCRAPE=1?)"; fi
      if ls "$d"/epp-*.log >/dev/null 2>&1; then
        if grep -l "setups that defeat the gate" "$d"/epp-*.log >/dev/null 2>&1; then
          fail "an epp-*.log warns about setups that defeat the gate"
        else
          ok "no gate warnings in epp-*.log"
        fi
      else
        fail "no epp-*.log saved"
      fi
    fi
  fi
done
exit $rc
