"""verify-point.sh on the synthetic point and on a real lane point of step 23."""

import gzip
import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify-point.sh"
REPO = Path(__file__).resolve().parents[4]
REAL_POINT = REPO / "23-aiperf-thunder-pr3" / "results" / "lane-20m" / "c12"


def run(*points):
    return subprocess.run(["bash", str(SCRIPT), *map(str, points)], capture_output=True, text=True)


def test_synthetic_point_without_parquet_fails_on_parquet_only(point):
    (point / "epp-pod.log").write_text("all good\n")
    r = run(point)
    fails = [line for line in r.stdout.splitlines() if line.startswith("FAIL")]
    assert r.returncode == 1
    assert len(fails) == 1 and "server_metrics_export.parquet" in fails[0], r.stdout


def test_synthetic_point_passes_with_parquet_and_epp(point):
    (point / "aiperf_artifacts" / "server_metrics_export.parquet").write_bytes(b"PAR1")
    (point / "epp-pod.log").write_text("all good\n")
    r = run(point)
    assert r.returncode == 0, r.stdout
    assert "FAIL" not in r.stdout


def test_detects_pod_change_gate_warning_and_missing_cached(point):
    (point / "aiperf_artifacts" / "server_metrics_export.parquet").write_bytes(b"PAR1")
    (point / "meta" / "finish.json").write_text(json.dumps({"job_status": "succeeded", "pod_changed": True}))
    (point / "epp-pod.log").write_text("WARNING setups that defeat the gate: ...\n")
    (point / "epp" / "raw-epp-metrics.txt.gz").unlink()
    # strip the cached-token counts
    jl = point / "aiperf_artifacts" / "profile_export.jsonl"
    rows = [json.loads(l) for l in jl.read_text().splitlines()]
    for r in rows:
        r["metrics"].pop("usage_prompt_cache_read_tokens", None)
    jl.write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = run(point).stdout
    assert "pod_changed = succeeded True" in out
    assert "defeat the gate" in out
    assert "no epp/raw-epp-metrics.txt.gz" in out
    assert "usage_prompt_cache_read_tokens" in out


def test_real_lane_point():
    """The committed step 23 point is a direct lane run: no EPP checks apply."""
    if not (REAL_POINT / "aiperf_artifacts" / "profile_export.jsonl").exists():
        import pytest
        pytest.skip("step 23 artifacts not checked out")
    r = run(REAL_POINT)
    assert r.returncode == 0, r.stdout
    assert "EPP" not in r.stdout
