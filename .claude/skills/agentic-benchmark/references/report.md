# The benchmark report

Each step folder ends with one report: `<step>/README.md`, in English. A Chinese version `<step>/README.zh.md` is optional and is a translation of the same content, made after the English one is final (use the `shuorenhua` skill to keep it natural). The structure follows the repo's step READMEs and `summary-report/THUNDER-AGENT-SUMMARY.md`.

## Writing rules

- Lead with the answer. The takeaways must make sense to a reader who stops there.
- Simple, short sentences. No marketing words ("dramatically", "significant" without a test). Explain a term the first time it appears.
- Every number comes from `summary.csv`, `ratios.md` or a named artifact. State the window next to each claim: whole profiling window (AgentX, comparable with InferenceX) or steady state (`ss_*`, after minute 5, what the figures show), and the replicate count.
- Ratios: "1.31x (1.27 to 1.35, 3 replicates)". Under about 5% is a tie; say "tie", not "slightly better".
- Report what failed: invalid points, errors, cancels, forced admissions, points the job stopped early. Never drop a point silently.
- Write the expectations section before the run and do not edit it afterwards; the result section says which expectations held.
- No em dash. Do not wrap lines in markdown.

## Template

```markdown
# Step NN: <arm vs arm> on <topology>, AgentX workload

Status: <setup | running | done> (YYYY-MM-DD).

## Takeaways

- <the main result with its number, replicate count and range>
- <where it helps and where it does not (concurrency range, working set vs pool)>
- <the cost: TTFT tail, forced admissions, router wait>
- <validity caveat that limits the claim, if any>

## Question

<one paragraph: what decision this run informs, and the hypothesis>

## Setup

| | |
|---|---|
| Model server | vLLM v0.28.0, Qwen3-Coder-30B-A3B-Instruct-FP8, TP=2, <N> pods (<N x 2> H100), KV <tokens> per pod, CPU offload <off / 400 GiB> |
| Server flags | as in the skill's references/deployment.md section 2, plus <changes>; live copy in `results/<label>/c<N>/meta/vllm-deployment.yaml` |
| Router arms | <arm>: <plugin file, EPP image tag and digest>; ... |
| Client | agentx-harness agentx-v1.0.6, `--scenario agentx`, dataset `semianalysis_cc_traces_weka_062126_256k`, seed 42 |
| Grid | concurrency <list>, <R> replicates at <points>, 60 min profiling per point, fresh server per point |
| SLO | TTFT <= <X> s |
| Dates and nodes | <run dates>, <node names>; arms compared on the same day and nodes |

## Expectations (written before the run)

1. <expected direction and size, and the metric that decides it>
2. <what would falsify it>

## Results

### Throughput at equal interactivity

![](results/compare/report/fig1-pareto.png)

<two or three sentences: read the figure for the reader>

### Load: throughput, goodput and latency against concurrency

![](results/compare/report/fig2-load.png)

| arm | conc | output tok/s/GPU | goodput tok/s | P90 interactivity | TTFT p50 / p90 (s) | turn SLO share | completed | valid |
|---|---|---|---|---|---|---|---|---|

### Why: cache reuse, working set, engine step

![](results/compare/report/fig3-cache.png)
![](results/compare/report/fig4-engine.png)

| arm | conc | GPU hit / CPU hit / computed (%) | theoretical hit | working set / pool | ms per output token | vLLM queue wait (s) | vLLM waiting |
|---|---|---|---|---|---|---|---|

### The gate's behavior and cost

![](results/compare/report/fig5-gate.png)

| arm | conc | delayed dispatches | pauses | forced admissions | EPP queue wait mean / p99 (s) |
|---|---|---|---|---|---|

### Against the baseline

<paste ratios.md, or the rows that matter>

### Expectations: what held

1. <held / did not hold, with the number>

## Validity

<the "Validity checks" section of summary.md for every point, and what was done about each problem; points excluded and why>

## Caveats

- <closed loop: faster arms complete more requests and see a slightly different mix>
- <spot nodes, neighbors on the node, single day, etc.>

## Next steps

- <one or two runs this result calls for>

## Reproduce

- Run: `RESULTS=$PWD/results MODE=<lane|pool> <env> ../.claude/skills/agentic-benchmark/scripts/run-sweep.sh <label> <concurrency...>`
- Analyze: `uv run ../.claude/skills/agentic-benchmark/scripts/analyze.py --ttft-slo <X> --out results/compare results/<label>/c* ...`
- Figures: `uv run ../.claude/skills/agentic-benchmark/scripts/make_figures.py --baseline <label> --out results/compare/report results/compare/report/summary.csv`
- Raw per-request files (`profile_export.jsonl`) over 100 MB are not committed; say where they are kept.
```

## Before calling the report done

- [ ] Takeaways quote numbers that appear in a table or `ratios.md`.
- [ ] Every figure is embedded and read in the text; every figure was opened and checked.
- [ ] Every point's validity line is accounted for.
- [ ] Versions: EPP image tag and digest, router commit, agentx-harness commit, vLLM image, dataset slug.
- [ ] The repo `README.md` "Steps" section has a short entry for this step with the main result.
