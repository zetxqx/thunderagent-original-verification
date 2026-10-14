'use strict';
// How the dashboard labels and draws bundle fields (SCHEMA.md). Fields that are not
// listed here still appear in the pickers under "Other", with their raw key as label.
//
// Summary metric fields:
//   key     summary column; with pct, the column is `${pct}_${key}` (p50_ttft_s, ...)
//   better  'higher' or 'lower', shown in the card note
//   log     log y axis by default
//   derive  (s, get) => value, for metrics computed from other columns; s is the raw
//           summary, get(key) reads a column in the selected window
//   pair    (p, b) => value, for metrics of a point against the baseline point at the same
//           concurrency; p and b are bundle points (mean over baseline replicates)
//   whole   the column covers the whole run even in the steady window
//   note    shown under the chart
//   sloLine draw the bundle's TTFT SLO (settings.ttft_slo_s) on the chart
//   tierLine (working set / GPU KV pool) also draw the CPU offload tier, cpu_tier_tokens /
//           kv_pool_tokens, for arms whose points have one
// "{slo}" in a label is replaced by the bundle's TTFT SLO in seconds.

const PCTS = ['p50', 'p75', 'p90', 'p95', 'p99', 'mean'];

const SUMMARY_METRICS = [
  { group: 'Throughput', key: 'output_tput_per_gpu', label: 'Output tok/s per GPU', better: 'higher' },
  { group: 'Throughput', key: 'total_tput_per_gpu', label: 'Total (input + output) tok/s per GPU', better: 'higher' },
  { group: 'Throughput', key: 'input_tput_per_gpu', label: 'Input tok/s per GPU', better: 'higher' },
  { group: 'Throughput', key: 'goodput_per_gpu', label: 'Goodput tok/s per GPU (turns with TTFT <= {slo} s)', better: 'higher',
    derive: (s, get) => get('goodput_output_tput') / s.num_gpus },
  { group: 'Throughput', key: 'completed', label: 'Completed requests', better: 'higher' },

  { group: 'Latency', key: 'ttft_s', pct: true, label: 'TTFT (s)', better: 'lower', log: true, sloLine: true },
  { group: 'Latency', key: 'intvty', pct: true, label: 'Interactivity (tok/s per user)', better: 'higher',
    note: 'p90 is the slowest 10% of requests (AgentX convention).' },
  { group: 'Latency', key: 'e2el_s', pct: true, label: 'Request latency (s)', better: 'lower', log: true,
    note: 'Wait at the router and in vLLM + prefill + decode, per turn.' },
  { group: 'Latency', key: 'e2e_norm_intvty', pct: true, label: 'E2E normalized interactivity (tok/s per user)', better: 'higher',
    note: 'Output tokens / request latency, so the wait counts; p90 is the slowest 10%.' },
  { group: 'Latency', key: 'turn_slo_share_pct', label: 'Turns with TTFT <= {slo} s (%)', better: 'higher',
    note: 'Errors and requests without a first token at the end (gate or vLLM queue) count as misses.' },
  { group: 'Latency', key: 'session_worst_ttft_p90_s', label: 'Worst TTFT per session, p90 (s)', better: 'lower', log: true, whole: true, sloLine: true },
  { group: 'Latency', key: 'sessions_worst_ttft_over_slo_pct', label: 'Sessions with a turn over {slo} s TTFT (%)', better: 'lower', whole: true },
  { group: 'Latency', key: 'session_progress', label: 'Session progress (turns / baseline)', better: 'higher', whole: true,
    pair: (p, b) => {
      const t = p.turns_by_trace, u = b.turns_by_trace;
      if (!t || !u) return null;
      let mine = 0, base = 0;
      for (const [k, n] of Object.entries(t)) if (u[k]) { mine += n; base += u[k]; }
      return base ? mine / base : null;
    },
    note: 'Turns completed on the traces both this point and the baseline at the same concurrency ran, over the baseline\'s turns on them. 1 = the same progress per session.' },

  { group: 'Cache', key: 'overall_hit_pct', label: 'Prefix hit rate, GPU + CPU tier (%)', better: 'higher' },
  { group: 'Cache', key: 'gpu_hit_pct', label: 'GPU prefix hit (%)', better: 'higher' },
  { group: 'Cache', key: 'cpu_hit_pct', label: 'CPU tier hit (%)', better: 'higher' },
  { group: 'Cache', key: 'recompute_pct', label: 'Prompt tokens computed (%)', better: 'lower' },
  { group: 'Cache', key: 'theoretical_hit_pct', label: 'Theoretical max hit (%)', whole: true },
  { group: 'Cache', key: 'working_set_over_pool_mean', label: 'Working set / GPU KV pool, mean', whole: true, tierLine: true,
    note: 'Above 1 the sessions do not fit in GPU KV; above the CPU tier line they do not fit with offload either.' },
  { group: 'Cache', key: 'working_set_over_pool_max', label: 'Working set / GPU KV pool, max', whole: true, tierLine: true },
  { group: 'Cache', key: 'kv_usage_avg_pct', label: 'vLLM KV usage, mean (%)' },
  { group: 'Cache', key: 'preemptions', label: 'vLLM preemptions', better: 'lower', whole: true },

  { group: 'Engine', key: 'step_time_T_ms', label: 'ms per output token (engine step)', better: 'lower', whole: true },
  { group: 'Engine', key: 'batch_B', label: 'Decode batch size', whole: true },
  { group: 'Engine', key: 'prefill_tokens_per_step', label: 'Prefill tokens per step', whole: true },
  { group: 'Engine', key: 'engine_request_queue_time_avg_s', label: 'Wait in the vLLM queue, mean (s)', better: 'lower', whole: true },
  { group: 'Engine', key: 'engine_request_prefill_time_avg_s', label: 'vLLM prefill time, mean (s)', better: 'lower', whole: true },
  { group: 'Engine', key: 'waiting_avg_sum', label: 'vLLM waiting requests, mean', better: 'lower' },
  { group: 'Engine', key: 'running_avg_sum', label: 'vLLM running requests, mean' },
  { group: 'Engine', key: 'prefill_compute_per_output_token', label: 'Prompt tokens computed per output token', better: 'lower', whole: true },

  { group: 'Router gate', key: 'gate_delayed_dispatches_per_h', label: 'Gate delayed dispatches per hour', whole: true,
    derive: s => s.gate_delayed_dispatches / s.duration_s * 3600 },
  { group: 'Router gate', key: 'gate_pauses_per_h', label: 'Gate pauses per hour', whole: true,
    derive: s => s.gate_pauses / s.duration_s * 3600 },
  { group: 'Router gate', key: 'gate_starvation_promotions_per_h', label: 'Forced admissions per hour', better: 'lower', whole: true,
    derive: s => s.gate_starvation_promotions / s.duration_s * 3600 },
  { group: 'Router gate', key: 'epp_queue_wait_mean_s', label: 'Wait at the router, mean (s)', better: 'lower', whole: true },
  { group: 'Router gate', key: 'epp_queue_wait_p90_s', label: 'Wait at the router, p90 (s)', better: 'lower', whole: true },
  { group: 'Router gate', key: 'epp_queue_wait_p99_s', label: 'Wait at the router, p99 (s)', better: 'lower', whole: true,
    note: 'Empty when the p99 is above the histogram top bucket (60 s); see waits over the top bucket.' },
  { group: 'Router gate', key: 'epp_queue_wait_over_top_bucket_pct', label: 'Router waits over 60 s (%)', better: 'lower', whole: true,
    note: 'Share of requests that waited longer than the EPP histogram top bucket (60 s).' },
  { group: 'Router gate', key: 'epp_queue_size_mean', label: 'Router queue size, mean', whole: true },
  { group: 'Router gate', key: 'gate_working_set_over_capacity_mean', label: 'Gate working set / capacity, mean', whole: true },
  { group: 'Router gate', key: 'gate_working_set_over_capacity_max', label: 'Gate working set / capacity, max', whole: true },

  { group: 'Validity', key: 'errors', label: 'Errors', better: 'lower', whole: true },
  { group: 'Validity', key: 'cancelled', label: 'Cancelled at the end of the grace period', better: 'lower', whole: true },
  { group: 'Validity', key: 'unserved', label: 'Unserved at the end (no first token; SLO misses)', better: 'lower', whole: true },
  { group: 'Validity', key: 'overflow_rate_pct', label: 'Context overflow (%)', better: 'lower', whole: true },
];

// Point time series: x is minutes since the first profiled request.
const SERIES_METRICS = [
  { group: 'Load', key: 'client_requests', label: 'Requests in flight (client)' },
  { group: 'Load', key: 'client_sessions', label: 'Sessions in flight (client)' },
  { group: 'Load', key: 'vllm_running', label: 'vLLM running requests' },
  { group: 'Load', key: 'vllm_waiting', label: 'vLLM waiting requests' },
  { group: 'Load', key: 'completed_per_min', label: 'Completed requests per minute' },
  { group: 'Throughput', key: 'output_tps', label: 'Server output tok/s' },
  { group: 'Throughput', key: 'input_tps', label: 'Server input tok/s' },
  { group: 'Throughput', key: 'prefill_computed_tps', label: 'Prompt tokens computed per s' },
  { group: 'Latency', key: 'ttft_p50_s', label: 'TTFT p50 per minute (s)', log: true, sloLine: true },
  { group: 'Latency', key: 'ttft_p90_s', label: 'TTFT p90 per minute (s)', log: true, sloLine: true },
  { group: 'Latency', key: 'intvty_p50', label: 'tok/s per user, p50 per minute' },
  { group: 'Latency', key: 'intvty_p90', label: 'tok/s per user, p90 (slowest 10%) per minute' },
  { group: 'Latency', key: 'vllm_queue_time_s', label: 'Wait in the vLLM queue, mean per minute (s)' },
  { group: 'Latency', key: 'vllm_prefill_time_s', label: 'vLLM prefill time, mean per minute (s)' },
  { group: 'Latency', key: 'ms_per_output_token', label: 'ms per output token (engine step)' },
  { group: 'Cache', key: 'kv_usage_pct', label: 'vLLM KV cache usage (%)' },
  { group: 'Cache', key: 'working_set_tokens', label: 'Working set (M tokens)', scale: 1e-6, refs: [['kv_pool_tokens', 'GPU KV pool'], ['cpu_tier_tokens', 'CPU offload tier']] },
  { group: 'Cache', key: 'inflight_tokens', label: 'In-flight unique tokens (M)', scale: 1e-6, refs: [['kv_pool_tokens', 'GPU KV pool'], ['cpu_tier_tokens', 'CPU offload tier']] },
  { group: 'Cache', key: 'src_gpu_hit_pct', label: 'Prompt tokens from GPU cache (%)' },
  { group: 'Cache', key: 'src_cpu_hit_pct', label: 'Prompt tokens from CPU tier (%)' },
  { group: 'Cache', key: 'src_computed_pct', label: 'Prompt tokens computed (%)' },
  { group: 'Router gate', key: 'epp_queue_size', label: 'Router queue (requests)' },
  { group: 'Router gate', key: 'epp_wait_mean_s', label: 'Wait at the router, mean per minute (s)' },
  { group: 'Router gate', key: 'gate_working_set_tokens', label: 'Gate working set (M tokens)', scale: 1e-6, refs: [['kv_pool_tokens', 'GPU KV pool'], ['cpu_tier_tokens', 'CPU offload tier']] },
  { group: 'Router gate', key: 'gate_delayed_dispatches_per_min', label: 'Gate delayed dispatches per minute' },
  { group: 'Router gate', key: 'gate_pauses_per_min', label: 'Gate pauses per minute' },
  { group: 'Router gate', key: 'gate_resumes_per_min', label: 'Gate resumes per minute' },
  { group: 'Router gate', key: 'gate_releases_per_min', label: 'Gate releases per minute' },
  { group: 'Router gate', key: 'gate_starvation_promotions_per_min', label: 'Forced admissions per minute' },
  { group: 'Router gate', key: 'epp_requests_per_min', label: 'Router requests per minute' },
  { group: 'Router gate', key: 'epp_request_errors_per_min', label: 'Router request errors per minute' },
];

// Point distributions: quantiles evenly spaced from 0 to 100 (201 values).
const DIST_METRICS = [
  { key: 'ttft_s', label: 'TTFT per turn (s)', log: true, sloLine: true },
  { key: 'worst_ttft_s', label: 'Worst TTFT per session (s)', log: true, sloLine: true },
  { key: 'intvty', label: 'tok/s per user' },
  { key: 'isl', label: 'Input tokens per request' },
  { key: 'osl', label: 'Output tokens per request', log: true },
];

const PALETTE = {
  baseline: '#B64342',
  arms: ['#0F4D92', '#42949E', '#9A4D8E', '#8BCF8B', '#3775BA', '#E0A33A', '#5B5B5B', '#C76B98'],
};

// The first four are the agent view: throughput, speed per user with the wait included,
// the latency tail and how far each session gets.
const DEFAULT_COMPARE_CARDS = [
  { type: 'conc', metric: 'output_tput_per_gpu' },
  { type: 'conc', metric: 'e2e_norm_intvty', pct: 'p90', second: 'p50' },
  { type: 'conc', metric: 'e2el_s', pct: 'p99', second: 'p90' },
  { type: 'conc', metric: 'session_progress' },
  { type: 'conc', metric: 'ttft_s', pct: 'p90' },
  { type: 'conc', metric: 'turn_slo_share_pct' },
  { type: 'conc', metric: 'overall_hit_pct' },
  { type: 'conc', metric: 'working_set_over_pool_mean' },
  { type: 'conc', metric: 'gate_starvation_promotions_per_h' },
  { type: 'pareto', x: 'e2e_norm_intvty', xpct: 'p90', y: 'output_tput_per_gpu' },
  { type: 'cache', wide: true },
];

const DEFAULT_POINT_CARDS = [
  { type: 'ts', metric: 'client_requests' },
  { type: 'ts', metric: 'output_tps' },
  { type: 'ts', metric: 'ttft_p90_s' },
  { type: 'ts', metric: 'src_gpu_hit_pct' },
  { type: 'ts', metric: 'working_set_tokens' },
  { type: 'ts', metric: 'vllm_running', metric2: 'vllm_waiting' },
  { type: 'dist', metric: 'ttft_s' },
  { type: 'slo', measure: 'turns' },
];
