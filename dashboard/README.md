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

One bundle per model and GPU, built from the per-step bundles by `regroup_by_model.py` (see its docstring): `glm52-nvfp4-8xb200.json` (step 25) and `qwen3-coder-30b-fp8-2xh100.json` (step 24). Points are one hour; short exploration runs are left out, except one 900 s check of the upstream main EPP image, whose arm name says "15 min". A point whose run did not use the CPU tier is equivalent with and without offload and appears in both arms, with "(shared)" in its id.

## Use it

- **Sidebar**: show or hide arms, click an arm name to focus it (the others fade), change colors, pick the baseline, filter concurrencies, switch between the steady state and the whole run.
- **Compare arms**: one metric against concurrency per card. Each card picks its metric, percentile, an optional second percentile (dashed), log scale and ratio to the baseline. Also x-vs-y (Pareto) cards, the prompt token source bars, and the cache card (token source with the theoretical max hit, and working set / GPU KV pool, as in make_figures.py fig3). Hover for exact values; drag to zoom, double-click to reset; the camera icon saves a PNG.
- **Points over time**: pick points (chips per arm), then time series, distributions (CDF) and the share of turns meeting a TTFT target.
- **Table**: all points with selectable column groups, sortable; click a row to open the point over time. Validity checks below.
- **Configuration**: settings that differ between the visible arms (lines that differ are highlighted), settings shared by all, settings that change per point, and the full configuration of one point.

The layout (cards, hidden arms, colors) is saved in the browser; "reset layout" restores the defaults. Labels for known metrics are in `metrics.js`.

## Files

| File | Content |
|---|---|
| `index.html`, `style.css`, `app.js` | the page |
| `metrics.js` | metric labels, groups, default cards |
| `vendor/plotly-basic.min.js` | Plotly 2.30.1 basic bundle (MIT, `vendor/plotly-LICENSE`) |
| `data/` | bundles and `index.json` |
| `SCHEMA.md` | the bundle format |
