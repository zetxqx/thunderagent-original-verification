"""Shared fixtures: a tiny synthetic point directory in the layout run-point.sh writes.

No parquet (the server-side columns are optional in analyze.py), so the tests run
without a vLLM scrape; the EPP scrape is a small hand-written gzip in the same
format epp_scrape.py produces.
"""

import gzip
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def analyze():
    return load_script("analyze")


@pytest.fixture(scope="session")
def router_metrics():
    return load_script("router_metrics")


T0_NS = 1_760_000_000_000_000_000  # an arbitrary start, nanoseconds since the epoch
MIN = 60_000_000_000


def record(phase, start_ns, end_ns, conv, root, ttft_ms, isl, osl, cached=None, error=None, cancelled=False):
    metrics = {
        "time_to_first_token": {"value": ttft_ms, "unit": "ms"},
        "request_latency": {"value": (end_ns - start_ns) / 1e6, "unit": "ms"},
        "input_sequence_length": {"value": isl, "unit": "tokens"},
        "output_sequence_length": {"value": osl, "unit": "tokens"},
    }
    if cached is not None:
        metrics["usage_prompt_cache_read_tokens"] = {"value": cached, "unit": "tokens"}
    r = {
        "metadata": {
            "benchmark_phase": phase,
            "request_start_ns": start_ns,
            "request_end_ns": end_ns,
            "conversation_id": conv,
            "root_correlation_id": root,
            "source_trace_id": f"trace-{root}",
            "agent_depth": 0,
            "was_cancelled": cancelled,
        },
        "metrics": metrics,
    }
    if error:
        r["error"] = error
    return r


def make_records():
    """2 warmup + 10 profiling requests over 12 minutes, two session trees.

    Minutes 0 to 4 (before the 5-minute steady-state cut): 4 fast requests.
    Minutes 6 to 11: 6 slower requests, one of them an error.
    """
    rows = [
        record("warmup", T0_NS - 3 * MIN, T0_NS - 2 * MIN, "w1", "w1", 100, 1000, 10),
        record("warmup", T0_NS - 2 * MIN, T0_NS - 1 * MIN, "w2", "w2", 100, 1000, 10),
    ]
    # ramp: 4 requests, 2 per tree, ttft 0.5 s, 20 s long, 100 output tokens
    for i in range(4):
        start = T0_NS + i * MIN
        rows.append(record("profiling", start, start + 20_000_000_000, f"c{i % 2}", f"r{i % 2}",
                           500, 10_000 * (i + 1), 100, cached=9_000 * i))
    # steady state: 6 requests, ttft 2 s, 60 s long, 200 output tokens; the last is an error
    for i in range(6):
        start = T0_NS + (6 + i) * MIN
        err = {"type": "HTTPError", "code": 500} if i == 5 else None
        rows.append(record("profiling", start, start + 60_000_000_000, f"c{i % 2}", f"r{i % 2}",
                           2000, 50_000, 200, cached=40_000, error=err))
    return rows


def write_epp_scrape(path: Path, prefix: str, t0_s: float):
    """Three snapshots: counters rise by 5 delayed dispatches and 2 pauses in the window."""
    base = ("http://10.0.0.9:9090/metrics", t0_s)
    snaps = []
    for k, (dd, pauses) in enumerate([(10, 1), (12, 2), (15, 3)]):
        ts = base[1] + k * 300
        body = "\n".join([
            f"{prefix}delayed_dispatches_total {dd}",
            f"{prefix}pauses_total {pauses}",
            f"{prefix}starvation_promotions_total 0",
            f'{prefix}endpoint_working_set_tokens{{endpoint="10.0.0.1:8000"}} {1_000_000 * (k + 1)}',
            f'{prefix}endpoint_capacity_tokens{{endpoint="10.0.0.1:8000"}} 2000000',
            f"llm_d_epp_flow_control_queue_size {k}",
            f'llm_d_epp_flow_control_request_queue_duration_seconds_bucket{{le="1"}} {10 * (k + 1)}',
            f'llm_d_epp_flow_control_request_queue_duration_seconds_bucket{{le="10"}} {12 * (k + 1)}',
            f'llm_d_epp_flow_control_request_queue_duration_seconds_bucket{{le="+Inf"}} {12 * (k + 1)}',
            f"llm_d_epp_flow_control_request_queue_duration_seconds_sum {6.0 * (k + 1)}",
            f"llm_d_epp_flow_control_request_queue_duration_seconds_count {12 * (k + 1)}",
            f"llm_d_epp_request_total {100 * (k + 1)}",
            f"llm_d_epp_request_error_total 0",
        ])
        snaps.append(f"# ts={ts:.3f} url={base[0]}\n{body}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as f:
        f.write("".join(snaps))


@pytest.fixture
def point(tmp_path) -> Path:
    """results/<label>/c8 with aiperf artifacts, meta and an EPP scrape (pool mode)."""
    d = tmp_path / "results" / "arm-r1" / "c8"
    art = d / "aiperf_artifacts"
    (art / "logs").mkdir(parents=True)
    (d / "meta").mkdir()
    with (art / "profile_export.jsonl").open("w") as f:
        for r in make_records():
            f.write(json.dumps(r) + "\n")
    (art / "profile_export_aiperf.json").write_text(json.dumps({
        "metadata": {"submission_valid": True, "submission_invalid_reasons": []},
        "theoretical_prefix_cache_hit": {"avg": 80.0},
        "context_overflow_count": {"avg": 0},
    }))
    # the line analyze.py reads the cancelled count from, with aiperf's thousands separators
    (art / "logs" / "aiperf.log").write_text(
        "2026-10-09 06:10:41.006 - PhaseRunner - NOTICE - Phase profiling (profiling) complete | "
        "completed=1,269, cancelled=30, errors=1 | duration=3600.0s\n")
    (d / "meta" / "point.json").write_text(json.dumps({
        "label": "arm-r1", "mode": "pool", "lane": "a", "concurrency": 8, "num_gpus": 4,
        "num_vllm_pods": 2, "server_metrics_urls": "http://10.0.0.1:8000/metrics http://10.0.0.2:8000/metrics",
    }))
    (d / "meta" / "finish.json").write_text(json.dumps({"job_status": "succeeded", "pod_changed": False}))
    (d / "meta" / "vllm-deployment.yaml").write_text(
        "spec:\n  template:\n    spec:\n      containers:\n      - name: modelserver\n        args:\n"
        "        - vllm serve Qwen/Qwen3-Coder-30B-A3B-Instruct-FP8 --max-num-batched-tokens=4096 "
        "--max-model-len=262144\n")
    write_epp_scrape(d / "epp" / "raw-epp-metrics.txt.gz", "llm_d_epp_thunder_agent_", T0_NS / 1e9)
    return d
