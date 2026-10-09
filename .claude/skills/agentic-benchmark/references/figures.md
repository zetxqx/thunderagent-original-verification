# Figures: which skill, which charts

Every figure is a report figure: one style, PNG only, and everything goes into the report folder next to `summary.md`.

| Kind | Made by | Goes into |
|---|---|---|
| Per point and per sweep | `scripts/analyze.py` calls `scripts/point_figures.py` | `results/<label>/report/` (or the `--out` of a multi-arm analysis) |
| Across arms (replicates, ratios) | `scripts/make_figures.py` | `results/compare/report/` |

## Style

- **`scientific-figure-making`** rules for every figure, kept in `scripts/figstyle.py`: palette, Arial/Helvetica sans-serif, font 15 and spine width 2 (compact analytic plots), no top and right spines, no legend frame, `tight_layout(pad=1)`, PNG at 300 dpi. No PDF.
- Keep figures plain: a short `(a) ...` panel title with the unit in it (`panel_title`), no figure-wide title, no explanation text inside the plot. Caveats (dropped bins, the idle-cap ramp, outliers) go into the report text.
- Legends sit in empty space above the data (`top_legend` in `point_figures.py`) or below the axes; never on top of a curve.
- Light horizontal grid (`GRID_COLOR`) only; 2 to 4 curves per panel; time series as 30 s rolling means.
- Line styles mean the same everywhere: the headline series (P90, all output, mean) solid with filled markers; the second series (P50, goodput, max, p99) dashed with hollow markers in the same color.
- Colors: the baseline arm is always red (`red_strong`); the proposed method is blue (`blue_main`), further variants teal, violet, green. Keep one color per arm across every figure of a report.
- Do not use `dataviz` (web and dashboard charts) or Plotly for these reports.

### Rules from the user's review of step 23 (keep them)

The step 23 figures were reviewed panel by panel; these choices are deliberate:

- **Units everywhere**: on every axis, and in legend values too (`median 92 k tokens`, `p50 26.1 tok/s/user`). A histogram's y axis is `% of requests`, not a count.
- **Plain words over engine jargon**: show "time to first token split into queue wait and prefill" and "ms per output token", not B, T and a step-time fit. B, T and the fit stay as `summary.csv` columns (`batch_B`, `step_time_T_ms`, `step_fit_*`), not as a figure.
- **Percentiles**: per-minute panels show p50 and p90 only (a minute has 10 to 60 requests, so a per-minute p99 is just the slowest request). Whole-run distributions mark p50, p90 and p99. For speed (tok/s/user) p90 and p99 mean the slow end, i.e. the 10th and 1st percentiles. No p75 in figures (it stays in `summary.csv` for the AgentX Pareto options).
- **Mark values on curves** instead of making the reader read them off: dots with labels on the TTFT CDF (p50/p90/p99), and a small table (white background, above the grid) of turns and goodput at TTFT targets 0.5, 1, 2, 5, 10 s.
- **No reference lines that need explaining** (the "summary SLO 60 s" line was removed). The only marker kept is the dotted 300 s idle-cap line on time axes.
- **Keep AgentX's names**: `tok/s/user`, `interactivity`, `goodput`; explain them in the report, not on the plot.
- **Long tails on log axes** (OSL, TTFT, the TTFT target), including the P90 TTFT axis of `pareto.png` and the TTFT panel of `concurrency.png` (TTFT jumps from about 1 s to 100 s once a pod saturates); drop the top 1% from a linear histogram rather than squashing it; all other Pareto and concurrency axes start at 0.
- **Sweep figures use the steady state** (`ss_*`, requests started after minute 5), so the low-load ramp does not make high-c points look fast; per-point figures show the whole window with the 5-minute marker.
- **P50 next to P90 on the Pareto**, dashed and hollow in the arm's color, never instead of P90 (AgentX's headline).
- **Simple and expert views in separate files**: `concurrency.png` (metric against concurrency) is separate from `pareto.png` (AgentX trade-off curves).
- Label the computed prefill share "computed", not "recompute": it includes first-time tokens; only the part above 100% minus the theoretical hit rate is recomputation.

## Per-point figures (`point_figures.py`, drawn by `analyze.py`)

Time axes are minutes since profiling started; the dotted vertical line is the 300 s per-tree idle cap (lanes that waited out recorded first-request gaps start there).

| File | Panels | Question |
|---|---|---|
| `report/pareto.png` | total tok/s/GPU vs interactivity; output tok/s/GPU vs interactivity; input tok/s/GPU vs TTFT (log); total tok/s/GPU vs E2E normalized interactivity (+ tokens per $ with a cost). P90 solid with filled markers, P50 dashed with hollow markers, same color per label; points labeled `c<N>` (on P90), alternating above and below. Steady-state (`ss_*`) values | AgentX's main view, one curve per label; the P50-P90 gap shows how unevenly users are served |
| `report/concurrency.png` | against concurrency (log2 axis, ticks at the run points): total tok/s/GPU; output tok/s/GPU; TTFT p50 (solid) and p90 (dashed), log scale; interactivity p50 and p90. Steady-state (`ss_*`) values | The simple view: how throughput and latency move as load grows |
| `c<N>-<label>/timeline.png` | (a) client requests and sessions in flight vs c (b) vLLM running and waiting (c) server input and output throughput (d) TTFT p50/p90 per minute (e) interactivity p50/p90 per minute (f) KV usage | Does load reach c? Does latency drift? Which pod fills first? |
| `c<N>-<label>/cache.png` | (a) working set, in-flight tokens and KV pool (b) prompt token source per minute (GPU hit, CPU tier, computed) with the theoretical hit rate | Does the working set fit? Is reuse kept or lost? |
| `c<N>-<label>/prefill.png` | (a) TTFT inside vLLM per minute, stacked: waiting in queue and prefill (vLLM `request_queue_time` and `request_prefill_time` histograms) (b) prefill tokens computed per second (bars) and ms per output token (line, the step time T over busy 10 s bins) | Is TTFT queueing or compute? Does prefill slow every user's output? |
| `c<N>-<label>/latency.png` | (a) TTFT CDF per turn (p50/p90/p99 marked) and per session's worst turn (b) % of turns and % of output tokens (goodput) meeting each TTFT target, with a table at 0.5/1/2/5/10 s (c) tok/s/user per request as % of requests, with p50, p90, p99 | What users see, and the SLO trade-off |
| `c<N>-<label>/isl-osl.png` | ISL and OSL histograms (y: number of requests; OSL on a log axis), medians with units | Workload mix of this point |
| `c<N>-<label>/gate.png` (pool mode, EPP scraped) | (a) gate events per minute (b) EPP queue size (c) gate ledger working set vs capacity per pod (d) EPP queue wait | Did the gate engage, and when? |
| `aiperf_artifacts/swim_lane.html` | per-session Gantt chart (from aiperf) | Which sessions stalled, how subagents fan out |

Engine-step bins with more prefill per step than `max_num_batched_tokens` (8192) cannot happen under chunked prefill; they are metrics-lag artifacts and are dropped (`step_bins_dropped`).

## Across-arm figures (`make_figures.py`)

`uv run scripts/make_figures.py --out results/compare/report --baseline <label> --name <label>="Display name" ... [--window steady|whole] results/compare/report/summary.csv [...]`

Labels that differ only by `-r<N>` are replicates of one arm: the figures show the mean with min-max bars, and `ratios.md` uses the means. `--window steady` (default) uses the `ss_*` columns like the sweep figures; `--window whole` uses the whole profiling window, for numbers to compare with InferenceX. `ratios.md` says which window it used. Same style as the per-point figures: P90 (or the headline series) solid with filled markers, the second series dashed with hollow markers in the same color, a small black style legend in the first panel that needs one, arm colors in one legend below the figure.

| File | Panels | Claim it supports |
|---|---|---|
| `fig1-pareto` | (a) total tok/s/GPU vs interactivity (b) output tok/s/GPU vs interactivity (c) input tok/s/GPU vs TTFT (log) (d) total tok/s/GPU vs E2E normalized interactivity; P90 solid, P50 dashed | Throughput at equal user experience. Compare at the same interactivity, not peak against peak |
| `fig2-load` | (a) output tok/s/GPU (solid) and goodput per GPU (dashed) (b) TTFT p90 and p50, log scale (c) turns with TTFT <= SLO (%), all vs concurrency | Where each arm saturates, and what users pay for it |
| `fig3-cache` | (a) prompt token source per arm and concurrency: GPU hit, CPU tier hit (only when non-zero), computed, with the theoretical max (b) working set / KV pool, mean and max, vs concurrency | Why: reuse kept or lost, and whether the working set fits |
| `fig4-engine` | (a) ms per output token (b) prompt tokens computed (%) (c) wait in the vLLM queue (s) (d) vLLM waiting requests, all vs concurrency | Mechanism in plain terms: prefill work slows every user's output and fills the queue (B, T and the step fit stay in `summary.csv`) |
| `fig5-gate` | (a) delayed dispatches (solid) and pauses (dashed) per hour (b) EPP queue wait mean and p99 (c) forced admissions per hour | Cost of the gate: who waits at the router, and whether the backstop fired |
| `ratios.md` | each arm / baseline at the same concurrency for throughput, goodput, interactivity, TTFT, SLO share, hit rate, completed | The numbers quoted in the takeaways |

A figure is skipped when its columns are missing (for example `fig5-gate` without EPP data).

## Adding a figure

- One figure answers one question; write that question as the panel title, `(a) ...` style, left aligned (`panel_title`).
- Put shared helpers in `figstyle.py`, per-point figures in `point_figures.py` and across-arm figures in `make_figures.py`, not in a step folder, so the next step reuses them.
- Read numbers only from `summary.csv` or the point artifacts, never typed by hand.
- After rendering, open the png and check it: labels readable, no overlapping text, units on every axis, legend not covering data.
