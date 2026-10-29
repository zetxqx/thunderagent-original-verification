# Benchmark dashboard

An interactive view of benchmark results: every arm and point of a step, one metric per chart, arms you can hide or focus, and the configuration of each arm side by side. It is a static page (HTML, JS and a vendored Plotly), with no server code and no build step.

## Open it

Online: https://zetxqx.github.io/thunderagent-original-verification/ (GitHub Pages, published from `main` by `.github/workflows/pages.yml` whenever `dashboard/` changes).

Locally:

```bash
python3 -m http.server -d dashboard 8000
# open http://localhost:8000
```

Served this way, it lists the bundles in `data/` (from `data/index.json`) and loads the newest. You can also open `index.html` directly from disk and load bundle files with "Open bundle files" or by dropping them on the page.

## Add a step

Export the step's points to one bundle with the agentic-benchmark skill, from the step folder:

```bash
uv run ../.claude/skills/agentic-benchmark/scripts/export_bundle.py \
  --out ../dashboard/data/<step>.json --title "Step N: ..." \
  --baseline <baseline label> --name <label>="display name" ... \
  results/<label>/c* [...]
```

It reuses `analyze.py` (same numbers as `summary.csv`) and reads one point at a time. The format is in [SCHEMA.md](SCHEMA.md); other tools can write it too.

## Current bundles

One bundle per model and GPU, built from the per-step bundles by `regroup_by_model.py` (see its docstring): `glm52-nvfp4-8xb200.json` (step 25) and `qwen3-coder-30b-fp8-2xh100.json` (step 24). Points are one hour; short exploration runs and a few variant arms (listed in the script's docstring) are left out. A point whose run did not use the CPU tier is equivalent with and without offload and appears in both arms, with "(shared)" in its id. `backfill_summary.py` then recomputed every summary with the current analyze.py (p99 columns) and added `turns_by_trace` from the raw results. `merge_bundle.py` added the step 27 DEP=8 points (12, three arms) to the GLM bundle and prefixed the step 25 arm names with "TP=8" (the command is in its docstring). It also added the step 28 llm-d-router v1.0.0 turn-priority points (4, arm `tp8-turn-priority`), exported with `--arm turn-priority-v1=tp8-turn-priority --kv-bytes-per-token 48408` and merged with `--cpu-tier-tokens 18173440`, and the step 29 points (4, arm `dep8-turn-priority`: v1.0.0 turn-priority on top of session affinity on DEP=8), exported with `--kv-bytes-per-token 48408` and merged with `--cpu-tier-tokens 18173440`. The Qwen3.5 bundle `qwen35-397b-fp8-4xb200.json` (step 26) got the step 30 turn-priority points the same way (3, arm `qwen35-turn-priority`, `--kv-bytes-per-token 32770`, `--cpu-tier-tokens 12680442`). Step 26 part 2 (TP=4 without the CPU tier, 10 points, arms `qwen35-nooff-direct` and `qwen35-nooff-thunder-l10`) was exported with `--kv-bytes-per-token 32770` and merged without `--cpu-tier-tokens` (no CPU tier). Its third arm `qwen35-nooff-thunder-u08` (utilThreshold 0.8, 5 points) was added the same way. The knee points (c = 28, 36, 40, 44, all three CPU-off arms, 12 points) were added the same way. The gate capacity sweep (arms `qwen35-nooff-thunder-u07` and `-u06`, c = 24 to 40, 10 points) was added the same way. It also holds the step 33 1P1D disaggregated points (5, arm `qwen35-1p1d-baseline`, one prefill + one decode server on 8 GPUs, exported with `--kv-bytes-per-token 32770` and merged with `--cpu-tier-tokens 25360884`, the CPU tiers of both servers); the file name keeps "4xb200" so saved layouts still load. The 1P1D arm has a fixed amber color (`--color qwen35-1p1d-baseline=#E0A33A`, `arms[].color` in SCHEMA.md), so it does not take the palette blue next to the thunder arm. The step 34 thunder-on-1P1D points (3, arm `qwen35-1p1d-thunder-l10`, exported with `--kv-bytes-per-token 32770`, merged with `--cpu-tier-tokens 25360884 --color qwen35-1p1d-thunder-l10=#1F1F1F`) are near-black so they stand apart from the amber no-thunder 1P1D arm. The GLM-5.2 bundle holds the step 35 two-node 1P1D points (5, arm `glm52-1p1d-baseline`, dark green `#1B7837`) and the step 36 thunder-on-1P1D points (4, arm `glm52-1p1d-thunder-l10`, near-black `#1F1F1F`), exported with `--kv-bytes-per-token 48408` and merged with `--cpu-tier-tokens 36346880` (both servers' CPU tiers); amber is already taken by an existing GLM arm there.

## Use it

- **Sidebar**: show or hide arms, click an arm name to focus it (the others fade), change colors, pick the baseline, filter concurrencies, switch between the steady state and the whole run.
- **Compare arms**: one metric against concurrency per card. Each card picks its metric, percentile, an optional second percentile (dashed), log scale and ratio to the baseline. Also x-vs-y (Pareto) cards, the prompt token source bars, and the cache card (token source with the theoretical max hit, and working set / GPU KV pool, as in make_figures.py fig3). Hover for exact values; drag to zoom, double-click to reset; the camera icon saves a PNG.
- **Points over time**: pick points (chips per arm), then time series, distributions (CDF) and the share of turns meeting a TTFT target. A time-series card can add a second series (for example vLLM running and waiting requests), drawn in the same colors with open markers, on the same axis or on a right axis for other units.
- **Table**: all points with selectable column groups, sortable; click a row to open the point over time. Validity checks below.
- **Configuration**: settings that differ between the visible arms (lines that differ are highlighted), settings shared by all, settings that change per point, and the full configuration of one point.

The layout (cards, hidden arms, colors) is saved in the browser; "reset layout" restores the defaults. The default compare view starts with the agent metrics: output throughput, E2E normalized interactivity p90 and p50, request latency p99 and p90, and session progress against the baseline. Labels for known metrics are in `metrics.js`.

## Files

| File | Content |
|---|---|
| `index.html`, `style.css`, `app.js` | the page |
| `metrics.js` | metric labels, groups, default cards |
| `vendor/plotly-basic.min.js` | Plotly 2.30.1 basic bundle (MIT, `vendor/plotly-LICENSE`) |
| `data/` | bundles and `index.json` |
| `SCHEMA.md` | the bundle format |
