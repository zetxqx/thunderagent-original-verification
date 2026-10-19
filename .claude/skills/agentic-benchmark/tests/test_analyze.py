"""analyze.py on the synthetic point: the parsers that have bitten before, the
steady-state split, and the validity checks."""

import json
import os
import sys

import pandas as pd


def test_phase_counts_reads_thousands_separators(analyze, point):
    counts = analyze.phase_counts(point / "aiperf_artifacts")
    assert counts == {"phase_completed": 1269, "cancelled": 30, "phase_errors": 1}


def test_max_batched_tokens_from_recorded_deployment(analyze, point, tmp_path):
    assert analyze.max_batched_tokens(point) == 4096
    # no recorded deployment: vLLM's default
    assert analyze.max_batched_tokens(tmp_path) == analyze.DEFAULT_MAX_BATCHED_TOKENS
    # the flag and its value as two list items, as kubectl prints a container's args
    (point / "meta" / "vllm-deployment.yaml").write_text("args:\n- --max-num-batched-tokens\n- \"16384\"\n")
    assert analyze.max_batched_tokens(point) == 16384
    (point / "meta" / "vllm-deployment.yaml").write_text("args: ['--max-num-batched-tokens', '2048']\n")
    assert analyze.max_batched_tokens(point) == 2048


def test_analyze_point_whole_window_and_steady_state(analyze, point, tmp_path):
    row = analyze.analyze_point(point, tmp_path / "out", cost=None, slo=1.0)
    assert row["label"] == "arm-r1" and row["conc"] == 8 and row["num_gpus"] == 4
    assert row["max_batched_tokens"] == 4096
    # 10 profiling requests, 1 error, 2 warmup
    assert row["completed"] == 9 and row["errors"] == 1 and row["warmup_requests"] == 2
    assert row["error_types"] == "HTTPError:1"
    # steady state keeps only requests started at or after minute 5: 5 ok + 1 error
    assert row["ss_completed"] == 5
    # the ramp requests meet a 1 s TTFT SLO, the steady-state ones do not
    assert row["p50_ttft_s"] == 2.0 and row["ss_p90_ttft_s"] == 2.0
    good_turns = 4  # the four 0.5 s requests
    # SLO share counts errors and unserved (cancelled 30, no parquet: all count) as misses
    assert abs(row["turn_slo_share_pct"] - 100 * good_turns / (9 + 1 + 30)) < 1e-9
    assert row["unserved"] == 30
    assert row["lanes_seen"] == 2 and row["turns_per_session_p50"] == 4.5
    assert row["theoretical_hit_pct"] == 80.0
    assert abs(row["usage_cache_read_pct"] - 100 * (9_000 * 6 + 40_000 * 5) / row["isl_median"] / 1) > 0  # computed
    # no parquet: server-side columns absent, not zero
    assert "overall_hit_pct" not in row and "kv_pool_tokens" not in row


def test_analyze_point_gate_columns(analyze, point, tmp_path):
    row = analyze.analyze_point(point, tmp_path / "out", cost=None, slo=60.0)
    assert row["epp_scraped"] is True
    # counters rose from 10 to 15 and 1 to 3 across the window (deltas, not totals)
    assert row["gate_delayed_dispatches"] == 5 and row["gate_pauses"] == 2
    assert row["gate_starvation_promotions"] == 0
    assert row["epp_requests"] == 200 and row["epp_request_errors"] == 0
    # 24 queue waits summing to 12 s
    assert abs(row["epp_queue_wait_mean_s"] - 0.5) < 1e-9
    assert row["epp_queue_wait_p90_s"] is not None
    assert abs(row["gate_working_set_over_capacity_max"] - 1.5) < 1e-9


def test_gate_metric_prefix_env(point, tmp_path):
    """Another admission-control plugin exporting the same counters under its own prefix."""
    from conftest import T0_NS, load_script, write_epp_scrape

    write_epp_scrape(point / "epp" / "raw-epp-metrics.txt.gz", "llm_d_epp_other_gate_", T0_NS / 1e9)
    os.environ["GATE_METRIC_PREFIX"] = "llm_d_epp_other_gate_"
    sys.modules.pop("router_metrics", None)  # the prefix is read when router_metrics is imported
    try:
        a = load_script("analyze")
    finally:
        del os.environ["GATE_METRIC_PREFIX"]
        sys.modules.pop("router_metrics", None)
    assert a.GATE == "llm_d_epp_other_gate_"
    row = a.analyze_point(point, tmp_path / "out", cost=None, slo=60.0)
    assert row["gate_delayed_dispatches"] == 5


def test_checks(analyze):
    base = {"pod_changed": False, "job_status": "succeeded", "aiperf_summary_missing": False,
            "submission_valid": True, "errors": 0, "cancelled": 0, "unserved": 0, "overflow_rate_pct": 0.0,
            "conc": 8, "mode": "pool", "epp_scraped": True, "overall_hit_pct": 70.0,
            "theoretical_hit_pct": 72.0, "kv_usage_max_pct": 90.0}
    assert analyze.checks(pd.Series(base)) == []

    r = pd.Series({**base, "pod_changed": True, "gate_pauses": 0, "gate_delayed_dispatches": 0,
                   "gate_starvation_promotions": 3, "epp_request_errors": 2})
    out = analyze.checks(r)
    assert any("INVALID" in line for line in out)
    assert "the gate never delayed or paused a session: it did not engage" in out
    assert "3 forced admissions: demand is past the pool's capacity" in out
    assert "2 EPP request errors (see epp-*.log)" in out

    assert "no EPP metrics: router and gate behavior unknown" in analyze.checks(pd.Series({**base, "epp_scraped": False}))


def test_main_writes_summary(analyze, point, tmp_path, monkeypatch):
    """End to end through main(): summary.csv, summary.md and the sweep figures."""
    out = tmp_path / "report"
    monkeypatch.setattr("sys.argv", ["analyze.py", "--out", str(out), "--ttft-slo", "60", str(point)])
    analyze.main()
    df = pd.read_csv(out / "summary.csv")
    assert len(df) == 1 and df.loc[0, "completed"] == 9
    md = (out / "summary.md").read_text()
    assert "## Validity checks" in md and "arm-r1 c=8" in md
    assert (out / "pareto.png").exists() and (out / "concurrency.png").exists()
    assert json.loads((point / "meta" / "point.json").read_text())["concurrency"] == 8
