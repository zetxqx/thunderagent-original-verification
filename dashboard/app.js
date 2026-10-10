'use strict';
// Benchmark dashboard: loads bundles (SCHEMA.md) and draws them with Plotly.
// Plain script, no build step and no modules, so index.html also works from file://.

const STORE_KEY = 'agentic-bench-dashboard/1';
const DASHES = ['solid', 'dash', 'dot', 'dashdot', 'longdash'];
const PLOT_CONFIG = {
  displaylogo: false, responsive: true,
  modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d', 'toggleSpikelines',
    'hoverClosestCartesian', 'hoverCompareCartesian'],
  toImageButtonOptions: { format: 'png', scale: 3 },
};

const clone = x => JSON.parse(JSON.stringify(x));
const DEFAULT_UI = {
  tab: 'compare', window: 'steady', legend: false, hidden: [], focus: [], colors: {}, concOff: [],
  baseline: null, compareCards: clone(DEFAULT_COMPARE_CARDS), pointCards: clone(DEFAULT_POINT_CARDS),
  selected: [], loaded: [], tableGroups: ['Key'], sort: null,
};

const state = { index: [], bundles: [], arms: [], points: [], otherKeys: [], ui: loadUi() };

function loadUi() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || 'null');
    return saved ? { ...clone(DEFAULT_UI), ...saved } : clone(DEFAULT_UI);
  } catch (e) {
    return clone(DEFAULT_UI);
  }
}

function saveUi() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(state.ui)); } catch (e) { /* private mode */ }
}

// ---------- small DOM helpers (textContent only: bundles may come from anyone) ----------

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'text') e.textContent = v;
    else if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'checked' || k === 'selected' || k === 'value') e[k] = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of [].concat(children)) if (c !== null && c !== undefined) e.append(c);
  return e;
}

const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));

function message(text) {
  const box = el('div', { class: 'msg', text });
  $('messages').append(box);
  setTimeout(() => box.remove(), 12000);
}

function fmt(v) {
  if (v === null || v === undefined || (typeof v === 'number' && !Number.isFinite(v))) return '';
  if (typeof v !== 'number') return String(v);
  if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString('en-US');
  return Number(v.toPrecision(3)).toString();
}

// ---------- loading ----------

async function init() {
  bindStatic();
  try {
    const r = await fetch('data/index.json', { cache: 'no-store' });
    if (r.ok) state.index = await r.json();
  } catch (e) { /* file:// or no index */ }
  const fromQuery = new URLSearchParams(location.search).getAll('bundle');
  const known = new Set(state.index.map(e => 'data/' + e.file));
  let urls = fromQuery.length ? fromQuery : state.ui.loaded.filter(u => known.has(u));
  if (!urls.length && state.index.length) {
    const newest = [...state.index].sort((a, b) => (a.created_utc || '').localeCompare(b.created_utc || '')).pop();
    urls = ['data/' + newest.file];
  }
  for (const u of urls) await loadUrl(u);
  render();
}

async function loadUrl(url) {
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    addBundle(await r.json(), url, true);
  } catch (e) {
    message(`Could not load ${url}: ${e.message}`);
  }
}

function loadFiles(files) {
  for (const f of files) {
    f.text().then(t => {
      addBundle(JSON.parse(t), f.name, false);
      render();
    }).catch(e => message(`${f.name}: ${e.message}`));
  }
}

function addBundle(data, source, persistent) {
  if (!data || typeof data.schema !== 'string' || !data.schema.startsWith('agentic-bench/')
      || !Array.isArray(data.arms) || !Array.isArray(data.points)) {
    throw new Error('not a benchmark bundle (expected "schema": "agentic-bench/1", see SCHEMA.md)');
  }
  removeBundle(source, false);
  const bundle = { uid: source, source, persistent, data };
  state.bundles.push(bundle);
  for (const a of data.arms) {
    state.arms.push({ uid: `${source}::${a.id}`, bundle, id: a.id, name: a.name || a.id, baseline: !!a.baseline, color: null });
  }
  for (const p of data.points) {
    const armUid = `${source}::${p.arm}`;
    if (!state.arms.some(a => a.uid === armUid)) {
      state.arms.push({ uid: armUid, bundle, id: p.arm, name: p.arm, baseline: false, color: null });
    }
    state.points.push({ uid: `${source}::${p.id}`, armUid, bundle, conc: p.conc, replicate: p.replicate, p });
  }
  if (persistent && !state.ui.loaded.includes(source)) state.ui.loaded.push(source);
  refreshDerived();
}

function removeBundle(source, rerender = true) {
  state.bundles = state.bundles.filter(b => b.source !== source);
  state.arms = state.arms.filter(a => a.bundle.source !== source);
  state.points = state.points.filter(p => p.bundle.source !== source);
  state.ui.loaded = state.ui.loaded.filter(u => u !== source);
  refreshDerived();
  if (rerender) render();
}

function refreshDerived() {
  let i = 0;
  for (const a of state.arms) {
    a.color = state.ui.colors[a.uid] || (a.baseline ? PALETTE.baseline : PALETTE.arms[i++ % PALETTE.arms.length]);
    if (state.bundles.length > 1) a.label = `${a.name} (${a.bundle.data.title || a.bundle.source})`;
    else a.label = a.name;
  }
  const known = new Set();
  for (const m of SUMMARY_METRICS) {
    known.add(m.key);
    if (m.pct) PCTS.forEach(p => known.add(`${p}_${m.key}`));
  }
  const other = new Set();
  for (const p of state.points) {
    for (const [k, v] of Object.entries(p.p.summary || {})) {
      const base = k.startsWith('ss_') ? k.slice(3) : k;
      if (typeof v === 'number' && !known.has(base)) other.add(base);
    }
  }
  state.otherKeys = [...other].sort();
}

// ---------- selection helpers ----------

const armOf = p => state.arms.find(a => a.uid === p.armUid);
const visibleArms = () => state.arms.filter(a => !state.ui.hidden.includes(a.uid));
const pointsOf = arm => state.points.filter(p => p.armUid === arm.uid && !state.ui.concOff.includes(p.conc));

function baselineArm() {
  return state.arms.find(a => a.uid === state.ui.baseline) || state.arms.find(a => a.baseline) || null;
}

function findSummary(key) {
  return SUMMARY_METRICS.find(m => m.key === key) || { group: 'Other', key, label: key };
}
const findSeries = key => SERIES_METRICS.find(m => m.key === key) || { group: 'Other', key, label: key };
const findDist = key => DIST_METRICS.find(m => m.key === key) || { key, label: key };

function getter(p, win) {
  const s = p.p.summary || {};
  return key => {
    if (win === 'steady') {
      const v = s['ss_' + key];
      if (v !== undefined && v !== null) return v;
    }
    return s[key];
  };
}

function metricValue(p, m, pct, win) {
  const get = getter(p, win);
  const v = m.derive ? m.derive(p.p.summary || {}, get) : get(m.pct ? `${pct}_${m.key}` : m.key);
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function metricLabel(m, pct) {
  return m.pct ? `${m.label}, ${pct}` : m.label;
}

// Mean, min and max over replicates, per concurrency.
function aggregate(arm, valueFn) {
  const by = new Map();
  for (const p of pointsOf(arm)) {
    const v = valueFn(p);
    if (v === null) continue;
    if (!by.has(p.conc)) by.set(p.conc, []);
    by.get(p.conc).push(v);
  }
  return [...by.entries()].sort((a, b) => a[0] - b[0]).map(([conc, vs]) => ({
    conc, n: vs.length, mean: vs.reduce((s, v) => s + v, 0) / vs.length, min: Math.min(...vs), max: Math.max(...vs),
  }));
}

function armStyle(arm) {
  const f = state.ui.focus;
  const dim = f.length > 0 && !f.includes(arm.uid);
  return { color: arm.color, opacity: dim ? 0.18 : 1, width: dim ? 1.2 : 2.4, dim };
}

// ---------- plotting helpers ----------

function axis(title, extra = {}) {
  return {
    title: { text: title, standoff: 6 }, showline: true, linewidth: 1.5, linecolor: '#333', ticks: 'outside',
    zeroline: false, gridcolor: '#ececec', automargin: true, ...extra,
  };
}

function layout(xTitle, yTitle, opts = {}) {
  return {
    margin: { l: 58, r: 14, t: opts.legend ? 34 : 10, b: 44 },
    font: { family: 'Arial, Helvetica, sans-serif', size: 13, color: '#1d1d1f' },
    xaxis: axis(xTitle, opts.x || {}),
    yaxis: axis(yTitle, opts.y || {}),
    showlegend: !!opts.legend,
    legend: { orientation: 'h', x: 0, y: 1.02, yanchor: 'bottom', font: { size: 11 } },
    hovermode: 'closest', plot_bgcolor: '#fff', paper_bgcolor: '#fff',
    shapes: opts.shapes || [], annotations: opts.annotations || [],
    barmode: opts.barmode, bargap: opts.bargap, bargroupgap: opts.bargroupgap,
  };
}

function concAxis(concs) {
  const cs = [...new Set(concs)].sort((a, b) => a - b);
  if (!cs.length) return {};
  return {
    type: 'log', tickvals: cs, ticktext: cs.map(String),
    range: [Math.log10(cs[0] / 1.35), Math.log10(cs[cs.length - 1] * 1.35)],
  };
}

// Log axis labeled at powers of ten only, unless the data spans less than two decades.
function logAxis(values, extra = {}) {
  const v = values.filter(x => typeof x === 'number' && x > 0);
  const span = v.length ? Math.log10(Math.max(...v) / Math.min(...v)) : 0;
  return { type: 'log', ...(span >= 2 ? { dtick: 1 } : {}), exponentformat: 'none', ...extra };
}

const hline = (y, color = '#888', dash = 'dot') => ({
  type: 'line', xref: 'paper', x0: 0, x1: 1, y0: y, y1: y, line: { color, width: 1.3, dash },
});
const vline = (x, color = '#999', dash = 'dot') => ({
  type: 'line', yref: 'paper', y0: 0, y1: 1, x0: x, x1: x, line: { color, width: 1.2, dash },
});

function draw(div, traces, lay) {
  Plotly.react(div, traces, lay, PLOT_CONFIG);
}

// ---------- card shell ----------

function metricSelect(value, catalog, otherKeys, onChange) {
  const sel = el('select', { onchange: e => onChange(e.target.value) });
  const groups = [...new Set(catalog.map(m => m.group))];
  for (const g of groups) {
    const og = el('optgroup', { label: g });
    for (const m of catalog.filter(m => m.group === g)) og.append(el('option', { value: m.key, text: m.label, selected: m.key === value }));
    sel.append(og);
  }
  if (otherKeys && otherKeys.length) {
    const og = el('optgroup', { label: 'Other' });
    for (const k of otherKeys) og.append(el('option', { value: k, text: k, selected: k === value }));
    sel.append(og);
  }
  return sel;
}

function pctSelect(value, onChange, withNone = false) {
  const sel = el('select', { onchange: e => onChange(e.target.value) });
  if (withNone) sel.append(el('option', { value: '', text: 'no 2nd line', selected: !value }));
  for (const p of PCTS) sel.append(el('option', { value: p, text: withNone ? `+ ${p} (dashed)` : p, selected: p === value }));
  return sel;
}

function check(label, value, onChange) {
  return el('label', {}, [el('input', { type: 'checkbox', checked: !!value, onchange: e => onChange(e.target.checked) }), label]);
}

function cardShell(list, card, controls) {
  const update = patch => { Object.assign(card, patch); saveUi(); render(); };
  const remove = () => { list.splice(list.indexOf(card), 1); saveUi(); render(); };
  const plotDiv = el('div', { class: 'plot' });
  const note = el('p', { class: 'card-note' });
  const head = el('div', { class: 'card-head' }, [
    ...controls(update),
    el('span', { class: 'spacer' }),
    check('wide', card.wide, v => update({ wide: v })),
    el('button', { class: 'close', type: 'button', title: 'remove chart', text: '×', onclick: remove }),
  ]);
  const box = el('div', { class: 'card' }, [head, plotDiv, note]);
  if (card.wide) box.style.gridColumn = 'span 2';
  return { box, plotDiv, note };
}

// ---------- compare tab ----------

function renderCompare() {
  const wrap = $('compare-cards');
  purge(wrap);
  const cards = state.ui.compareCards;
  for (const card of cards) {
    let shell;
    if (card.type === 'conc') shell = concCard(cards, card);
    else if (card.type === 'pareto') shell = paretoCard(cards, card);
    else if (card.type === 'source') shell = sourceCard(cards, card);
    else if (card.type === 'cache') shell = cacheCard(cards, card);
    else continue;
    wrap.append(shell.box);
    shell.draw();
  }
}

function concCard(list, card) {
  const m = findSummary(card.metric);
  const pct = card.pct || 'p90';
  const shell = cardShell(list, card, update => [
    metricSelect(card.metric, SUMMARY_METRICS, state.otherKeys, v => update({ metric: v, log: undefined })),
    m.pct ? pctSelect(pct, v => update({ pct: v })) : null,
    m.pct ? pctSelect(card.second, v => update({ second: v }), true) : null,
    check('log y', card.log ?? m.log, v => update({ log: v })),
    check('ratio to baseline', card.ratio, v => update({ ratio: v })),
  ]);
  shell.draw = () => {
    const win = state.ui.window;
    const base = baselineArm();
    const baseMap = base ? new Map(aggregate(base, p => metricValue(p, m, pct, win)).map(r => [r.conc, r.mean])) : new Map();
    const traces = [], concs = [], allY = [];
    let replicated = false;
    for (const arm of visibleArms()) {
      if (card.ratio && base && arm.uid === base.uid) continue;
      const st = armStyle(arm);
      const lines = [[pct, 'solid', 'circle']];
      if (m.pct && card.second && card.second !== pct && !card.ratio) lines.push([card.second, 'dash', 'circle-open']);
      for (const [q, dash, symbol] of lines) {
        const rows = aggregate(arm, p => metricValue(p, m, q, win));
        if (!rows.length) continue;
        rows.forEach(r => concs.push(r.conc));
        rows.forEach(r => allY.push(r.min, r.max));
        replicated = replicated || rows.some(r => r.n > 1);
        const ys = card.ratio ? rows.map(r => (baseMap.get(r.conc) ? r.mean / baseMap.get(r.conc) : null)) : rows.map(r => r.mean);
        const err = !card.ratio && rows.some(r => r.n > 1)
          ? { type: 'data', symmetric: false, array: rows.map(r => r.max - r.mean), arrayminus: rows.map(r => r.mean - r.min), color: st.color, thickness: 1.4, width: 4 }
          : undefined;
        traces.push({
          x: rows.map(r => r.conc), y: ys, name: lines.length > 1 ? `${arm.label} ${q}` : arm.label, type: 'scatter', mode: 'lines+markers',
          line: { color: st.color, width: st.width, dash }, marker: { color: st.color, size: 7, symbol, line: { width: 1.6, color: st.color } },
          opacity: st.opacity, error_y: err, customdata: rows.map(r => r.n),
          hovertemplate: `<b>${esc(arm.label)}</b>${lines.length > 1 ? ' ' + q : ''}<br>c=%{x}<br>%{y:.4~g}` +
            (card.ratio ? ' x baseline' : '') + (replicated ? '<br>n=%{customdata}' : '') + '<extra></extra>',
        });
      }
    }
    const log = card.log ?? m.log;
    const yTitle = metricLabel(m, pct) + (card.ratio ? ' / baseline' : '');
    draw(shell.plotDiv, traces, layout('concurrency', yTitle, {
      legend: state.ui.legend, x: concAxis(concs), y: log ? logAxis(card.ratio ? [] : allY) : { rangemode: 'tozero' },
      shapes: card.ratio ? [hline(1, '#B64342', 'dash')] : [],
    }));
    const notes = [];
    if (m.better) notes.push(`${m.better} is better`);
    if (card.ratio) notes.push(base ? `ratio to ${base.label} at the same concurrency` : 'no baseline selected');
    if (win === 'steady' && m.whole) notes.push('whole run (no steady-state value)');
    if (replicated) notes.push('mean of replicates, bars = min to max');
    if (m.note) notes.push(m.note);
    if (!traces.length) notes.push('no data for this metric in the visible arms');
    shell.note.textContent = notes.join(' · ');
  };
  return shell;
}

function paretoCard(list, card) {
  const xm = findSummary(card.x || 'intvty'), ym = findSummary(card.y || 'output_tput_per_gpu');
  const xpct = card.xpct || 'p90', ypct = card.ypct || 'p90';
  const shell = cardShell(list, card, update => [
    el('span', { class: 'hint', text: 'x' }),
    metricSelect(xm.key, SUMMARY_METRICS, state.otherKeys, v => update({ x: v, logx: undefined })),
    xm.pct ? pctSelect(xpct, v => update({ xpct: v })) : null,
    el('span', { class: 'hint', text: 'y' }),
    metricSelect(ym.key, SUMMARY_METRICS, state.otherKeys, v => update({ y: v })),
    ym.pct ? pctSelect(ypct, v => update({ ypct: v })) : null,
    check('log x', card.logx ?? xm.log, v => update({ logx: v })),
    check('c labels', card.labels, v => update({ labels: v })),
  ]);
  shell.draw = () => {
    const win = state.ui.window;
    const traces = [], allX = [];
    for (const arm of visibleArms()) {
      const st = armStyle(arm);
      const xs = new Map(aggregate(arm, p => metricValue(p, xm, xpct, win)).map(r => [r.conc, r.mean]));
      const rows = aggregate(arm, p => metricValue(p, ym, ypct, win)).filter(r => xs.has(r.conc));
      if (!rows.length) continue;
      rows.forEach(r => allX.push(xs.get(r.conc)));
      traces.push({
        x: rows.map(r => xs.get(r.conc)), y: rows.map(r => r.mean), customdata: rows.map(r => r.conc),
        text: rows.map(r => 'c' + r.conc), textposition: 'top right', textfont: { size: 10, color: st.color },
        name: arm.label, type: 'scatter', mode: card.labels ? 'lines+markers+text' : 'lines+markers',
        line: { color: st.color, width: st.width }, marker: { color: st.color, size: 7 }, opacity: st.opacity,
        hovertemplate: `<b>${esc(arm.label)}</b><br>c=%{customdata}<br>x %{x:.4~g}<br>y %{y:.4~g}<extra></extra>`,
      });
    }
    const logx = card.logx ?? xm.log;
    draw(shell.plotDiv, traces, layout(metricLabel(xm, xpct), metricLabel(ym, ypct), {
      legend: state.ui.legend, x: logx ? logAxis(allX) : { rangemode: 'tozero' }, y: { rangemode: 'tozero' },
    }));
    const notes = ['one line per arm, points ordered by concurrency (hover for c)'];
    if (xm.better && ym.better) notes.push(`better: ${xm.better} x, ${ym.better} y`);
    if (xm.note) notes.push(xm.note);
    shell.note.textContent = notes.join(' · ');
  };
  return shell;
}

// Stacked prompt token source bars, one bar per visible arm and concurrency, with the
// theoretical max hit as a black tick (fig3-cache panel a). x is numeric so the ticks can
// sit on their bars; xa and ya name the axes ('x', 'x2', ...).
function tokenSourceTraces(xa, ya) {
  const win = state.ui.window;
  const arms = visibleArms();
  const concs = [...new Set(arms.flatMap(a => pointsOf(a).map(p => p.conc)))].sort((a, b) => a - b);
  const parts = [['gpu_hit_pct', 'GPU hit', 1], ['cpu_hit_pct', 'CPU tier hit', 0.55], ['recompute_pct', 'computed', 0.2]];
  const width = 0.8 / Math.max(arms.length, 1);
  const traces = [];
  const used = new Set();
  arms.forEach((arm, j) => {
    const st = armStyle(arm);
    const xs = concs.map((_, i) => i + (j - (arms.length - 1) / 2) * width);
    const base = new Array(concs.length).fill(0);
    for (const [key, name, alpha] of parts) {
      const vals = new Map(aggregate(arm, p => metricValue(p, findSummary(key), null, win)).map(r => [r.conc, r.mean]));
      if (![...vals.values()].some(v => v > 0)) continue;
      used.add(name);
      const ys = concs.map(c => vals.get(c) ?? 0);
      traces.push({
        type: 'bar', x: xs, y: ys, base: [...base], width: width * 0.94, xaxis: xa, yaxis: ya, showlegend: false,
        marker: { color: st.color, opacity: alpha * (st.dim ? 0.35 : 1), line: { color: '#fff', width: 0.6 } },
        customdata: concs, hovertemplate: `<b>${esc(arm.label)}</b><br>c%{customdata} ${name}: %{y:.1f}%<extra></extra>`,
      });
      ys.forEach((v, i) => { base[i] += v; });
    }
    const theo = new Map(aggregate(arm, p => metricValue(p, findSummary('theoretical_hit_pct'), null, win)).map(r => [r.conc, r.mean]));
    const keep = concs.map((c, i) => [xs[i], theo.get(c), c]).filter(r => r[1] !== undefined);
    if (keep.length) {
      traces.push({
        type: 'scatter', mode: 'markers', x: keep.map(r => r[0]), y: keep.map(r => r[1]), customdata: keep.map(r => r[2]),
        xaxis: xa, yaxis: ya, showlegend: false, opacity: st.dim ? 0.35 : 1,
        marker: { symbol: 'line-ew', size: Math.max(8, 70 * width), line: { width: 3, color: '#111' } },
        hovertemplate: `<b>${esc(arm.label)}</b><br>c%{customdata} theoretical max hit: %{y:.1f}%<extra></extra>`,
      });
    }
  });
  // Legend for the shading only; the arm colors are in the sidebar.
  const key = [];
  for (const [, name, alpha] of parts) {
    if (used.has(name)) key.push({ type: 'bar', x: [null], y: [null], name, marker: { color: `rgba(17,17,17,${alpha})` }, xaxis: xa, yaxis: ya, hoverinfo: 'skip' });
  }
  key.push({ type: 'scatter', mode: 'markers', x: [null], y: [null], name: 'theoretical max hit', xaxis: xa, yaxis: ya,
    marker: { symbol: 'line-ew', size: 14, line: { width: 3, color: '#111' } }, hoverinfo: 'skip' });
  return { traces: [...traces, ...key], x: { tickvals: concs.map((_, i) => i), ticktext: concs.map(c => 'c' + c), range: [-0.6, concs.length - 0.4] } };
}

function sourceCard(list, card) {
  const shell = cardShell(list, card, () => [el('strong', { text: 'Prompt token source (%)' })]);
  shell.draw = () => {
    const src = tokenSourceTraces('x', 'y');
    draw(shell.plotDiv, src.traces, layout('concurrency', '% of prompt tokens', {
      legend: true, x: src.x, y: { range: [0, 103] },
    }));
    shell.note.textContent = 'one bar per arm, in sidebar order and color; hover for values';
  };
  return shell;
}

// fig3-cache: prompt token source (a) and working set over the GPU KV pool (b), mean solid, max dashed.
function cacheCard(list, card) {
  const shell = cardShell(list, card, () => [el('strong', { text: 'Cache: prompt token source and working set' })]);
  shell.draw = () => {
    const src = tokenSourceTraces('x', 'y');
    const traces = [...src.traces];
    const concs = [];
    for (const arm of visibleArms()) {
      const st = armStyle(arm);
      for (const [key, dash, symbol, q] of [['working_set_over_pool_mean', 'solid', 'circle', 'mean'],
        ['working_set_over_pool_max', 'dash', 'circle-open', 'max']]) {
        const rows = aggregate(arm, p => metricValue(p, findSummary(key), null, state.ui.window));
        if (!rows.length) continue;
        rows.forEach(r => concs.push(r.conc));
        traces.push({
          type: 'scatter', mode: 'lines+markers', x: rows.map(r => r.conc), y: rows.map(r => r.mean), xaxis: 'x2', yaxis: 'y2',
          showlegend: false, opacity: st.opacity, line: { color: st.color, width: st.width, dash },
          marker: { color: st.color, size: 7, symbol, line: { width: 1.6, color: st.color } },
          hovertemplate: `<b>${esc(arm.label)}</b><br>c=%{x}<br>working set / pool, ${q}: %{y:.3~g}<extra></extra>`,
        });
      }
    }
    for (const [name, dash, symbol] of [['mean', 'solid', 'circle'], ['max', 'dash', 'circle-open']]) {
      traces.push({ type: 'scatter', mode: 'lines+markers', x: [null], y: [null], name, xaxis: 'x2', yaxis: 'y2', hoverinfo: 'skip',
        line: { color: '#111', width: 2, dash }, marker: { color: '#111', size: 7, symbol } });
    }
    const lay = layout('concurrency', '% of prompt tokens', { legend: true, x: { ...src.x, domain: [0, 0.6] }, y: { range: [0, 103] } });
    lay.xaxis2 = axis('concurrency', { ...concAxis(concs), domain: [0.7, 1], anchor: 'y2' });
    lay.yaxis2 = axis('working set / GPU KV pool', { anchor: 'x2', rangemode: 'tozero' });
    lay.shapes = [{ type: 'line', xref: 'x2 domain', x0: 0, x1: 1, yref: 'y2', y0: 1, y1: 1, line: { color: '#B64342', width: 1.5, dash: 'dot' } }];
    lay.annotations = [
      { text: '<b>(a) Prompt token source (%)</b>', xref: 'paper', yref: 'paper', x: 0, y: 1, xanchor: 'left', yanchor: 'bottom', showarrow: false },
      { text: '<b>(b) Working set / GPU KV pool</b>', xref: 'paper', yref: 'paper', x: 0.7, y: 1, xanchor: 'left', yanchor: 'bottom', showarrow: false },
    ];
    lay.margin.t = 62;
    lay.legend = { orientation: 'h', x: 0, y: 1.1, yanchor: 'bottom', font: { size: 11 } };
    draw(shell.plotDiv, traces, lay);
    const win = state.ui.window === 'steady' ? 'token source: steady state; ' : '';
    shell.note.textContent = `one bar or line per arm, in sidebar order and color; ${win}working set: whole run; dotted red: the working set equals the GPU KV pool`;
  };
  return shell;
}

// ---------- points tab ----------

function selectedPoints() {
  const sel = state.ui.selected.map(uid => state.points.find(p => p.uid === uid)).filter(Boolean);
  return sel.filter(p => !state.ui.hidden.includes(p.armUid));
}

function ensureSelection() {
  if (selectedPoints().length || !state.points.length) return;
  const arms = visibleArms();
  const base = baselineArm();
  const other = arms.find(a => !base || a.uid !== base.uid);
  const pick = [];
  if (base && other) {
    const shared = pointsOf(other).map(p => p.conc).filter(c => pointsOf(base).some(p => p.conc === c));
    if (shared.length) {
      const c = Math.max(...shared);
      pick.push(pointsOf(base).find(p => p.conc === c).uid, pointsOf(other).find(p => p.conc === c).uid);
    }
  }
  if (!pick.length) pick.push(state.points[0].uid);
  state.ui.selected = pick;
}

function pointStyle(p, sel) {
  const arm = armOf(p);
  const same = sel.filter(q => q.armUid === p.armUid);
  return { color: arm.color, dash: DASHES[same.indexOf(p) % DASHES.length], name: pointName(p) };
}

function pointName(p) {
  return `${armOf(p).label} c${p.conc}${p.replicate !== null && p.replicate !== undefined ? ' r' + p.replicate : ''}`;
}

function renderPicker() {
  const box = $('point-picker');
  box.replaceChildren();
  const sel = new Set(state.ui.selected);
  box.append(el('div', { class: 'row' }, [
    el('strong', { text: 'Points' }),
    el('span', { class: 'hint', text: 'click to add or remove; same arm = same color, different dash' }),
    el('button', { type: 'button', text: 'clear', onclick: () => { state.ui.selected = []; saveUi(); render(); } }),
  ]));
  for (const arm of visibleArms()) {
    const chips = pointsOf(arm).sort((a, b) => a.conc - b.conc || (a.replicate || 0) - (b.replicate || 0)).map(p => el('span', {
      class: 'chip' + (sel.has(p.uid) ? ' on' : ''),
      text: `c${p.conc}${p.replicate !== null && p.replicate !== undefined ? ' r' + p.replicate : ''}`,
      title: (p.p.checks || []).join('\n') || 'no validity warnings',
      onclick: () => {
        state.ui.selected = sel.has(p.uid) ? state.ui.selected.filter(u => u !== p.uid) : [...state.ui.selected, p.uid];
        saveUi(); render();
      },
    }));
    box.append(el('div', { class: 'picker-row' }, [
      el('span', { class: 'arm-name' }, [el('span', { class: 'swatch', style: `background:${arm.color}` }), arm.label]),
      el('div', { class: 'chips' }, chips),
    ]));
  }
}

function renderPoints() {
  ensureSelection();
  renderPicker();
  const wrap = $('point-cards');
  purge(wrap);
  const cards = state.ui.pointCards;
  for (const card of cards) {
    let shell;
    if (card.type === 'ts') shell = tsCard(cards, card);
    else if (card.type === 'dist') shell = distCard(cards, card);
    else if (card.type === 'slo') shell = sloCard(cards, card);
    else continue;
    wrap.append(shell.box);
    shell.draw();
  }
}

function availableSeries() {
  const keys = new Set(state.points.flatMap(p => Object.keys(p.p.series || {})));
  const known = SERIES_METRICS.filter(m => keys.has(m.key));
  const other = [...keys].filter(k => !SERIES_METRICS.some(m => m.key === k)).sort();
  return { known, other };
}

function tsCard(list, card) {
  const m = findSeries(card.metric);
  const { known, other } = availableSeries();
  const shell = cardShell(list, card, update => [
    metricSelect(card.metric, known, other, v => update({ metric: v, log: undefined })),
    check('log y', card.log ?? m.log, v => update({ log: v })),
  ]);
  shell.draw = () => {
    const sel = selectedPoints();
    const traces = [], shapes = [], missing = [], allY = [];
    const scale = m.scale || 1;
    const refs = new Set();
    for (const p of sel) {
      const s = (p.p.series || {})[m.key];
      if (!s) { missing.push(pointName(p)); continue; }
      const st = pointStyle(p, sel);
      s.v.forEach(v => allY.push(v * scale));
      traces.push({
        x: s.t, y: s.v.map(v => (v === null ? null : v * scale)), name: st.name, type: 'scatter', mode: 'lines',
        line: { color: st.color, width: 2.2, dash: st.dash },
        hovertemplate: `<b>${esc(st.name)}</b><br>minute %{x:.1f}<br>%{y:.4~g}<extra></extra>`,
      });
      if (m.ref && p.p[m.ref]) refs.add(p.p[m.ref] * scale);
    }
    for (const r of refs) shapes.push(hline(r, '#B64342', 'dash'));
    const skip = sel.length ? sel[0].bundle.data.settings?.skip_minutes : null;
    if (skip) shapes.push(vline(skip));
    draw(shell.plotDiv, traces, layout('minutes since the first profiled request', m.label, {
      legend: true, shapes, y: (card.log ?? m.log) ? logAxis(allY) : { rangemode: 'tozero' },
    }));
    const notes = [];
    if (skip) notes.push(`dotted line: steady state starts (minute ${skip})`);
    if (refs.size) notes.push(`dashed red: ${m.refLabel || m.ref}`);
    if (missing.length) notes.push(`not recorded for ${missing.join(', ')}`);
    if (!sel.length) notes.push('pick points above');
    shell.note.textContent = notes.join(' · ');
  };
  return shell;
}

function distCard(list, card) {
  const m = findDist(card.metric);
  const keys = new Set(state.points.flatMap(p => Object.keys(p.p.dists?.whole || {})));
  const known = DIST_METRICS.filter(d => keys.has(d.key)).map(d => ({ ...d, group: 'Distribution' }));
  const shell = cardShell(list, card, update => [
    metricSelect(card.metric, known, [...keys].filter(k => !DIST_METRICS.some(d => d.key === k)), v => update({ metric: v, log: undefined })),
    check('log x', card.log ?? m.log, v => update({ log: v })),
  ]);
  shell.draw = () => {
    const sel = selectedPoints();
    const win = state.ui.window;
    const traces = [], allX = [];
    for (const p of sel) {
      const q = (p.p.dists?.[win] || p.p.dists?.whole || {})[m.key];
      if (!q) continue;
      const st = pointStyle(p, sel);
      const grid = q.map((_, i) => (100 * i) / (q.length - 1));
      allX.push(...q);
      traces.push({
        x: q, y: grid, name: st.name, type: 'scatter', mode: 'lines', line: { color: st.color, width: 2.2, dash: st.dash },
        hovertemplate: `<b>${esc(st.name)}</b><br>p%{y:.1f}: %{x:.4~g}<extra></extra>`,
      });
    }
    draw(shell.plotDiv, traces, layout(m.label + ((card.log ?? m.log) ? ' (log scale)' : ''), '% at or below', {
      legend: true, x: (card.log ?? m.log) ? logAxis(allX) : {}, y: { range: [0, 101] },
      shapes: [hline(50, '#ccc'), hline(90, '#ccc')],
    }));
    shell.note.textContent = `${win === 'steady' ? 'steady state' : 'whole run'}; gray lines at p50 and p90`;
  };
  return shell;
}

function sloCard(list, card) {
  const measure = card.measure || 'turns';
  const shell = cardShell(list, card, update => [
    el('select', { onchange: e => update({ measure: e.target.value }) }, [
      el('option', { value: 'turns', text: 'Share of turns meeting a TTFT target', selected: measure === 'turns' }),
      el('option', { value: 'goodput', text: 'Share of output tokens meeting a TTFT target', selected: measure === 'goodput' }),
    ]),
  ]);
  shell.draw = () => {
    const sel = selectedPoints();
    const win = state.ui.window;
    const traces = [];
    for (const p of sel) {
      const c = p.p.slo_curve?.[win] || p.p.slo_curve?.whole;
      if (!c) continue;
      const st = pointStyle(p, sel);
      traces.push({
        x: c.targets_s, y: measure === 'turns' ? c.turns_pct : c.goodput_pct, name: st.name, type: 'scatter', mode: 'lines',
        line: { color: st.color, width: 2.2, dash: st.dash },
        hovertemplate: `<b>${esc(st.name)}</b><br>TTFT <= %{x:.3~g} s: %{y:.1f}%<extra></extra>`,
      });
    }
    const slo = sel.length ? sel[0].bundle.data.settings?.ttft_slo_s : null;
    draw(shell.plotDiv, traces, layout('TTFT target (s, log scale)', measure === 'turns' ? '% of turns' : '% of output tokens', {
      legend: true, x: logAxis([0.1, 3600]), y: { range: [0, 101] }, shapes: slo ? [vline(slo, '#B64342', 'dash')] : [],
    }));
    shell.note.textContent = `${win === 'steady' ? 'steady state' : 'whole run'}${slo ? `; dashed red: the report SLO (${slo} s)` : ''}; errors and requests without a first token at the end count as misses`;
  };
  return shell;
}

// ---------- table tab ----------

function tableGroups() {
  const groups = { Key: [
    ['output_tput_per_gpu'], ['ttft_s', 'p50'], ['ttft_s', 'p90'], ['intvty', 'p90'], ['turn_slo_share_pct'],
    ['overall_hit_pct'], ['working_set_over_pool_mean'], ['gate_starvation_promotions_per_h'],
  ] };
  for (const m of SUMMARY_METRICS) {
    if (!groups[m.group]) groups[m.group] = [];
    if (m.pct) ['p50', 'p90'].forEach(p => groups[m.group].push([m.key, p]));
    else groups[m.group].push([m.key]);
  }
  if (state.otherKeys.length) groups.Other = state.otherKeys.map(k => [k]);
  return groups;
}

function renderTable() {
  const groups = tableGroups();
  const bar = $('table-groups');
  bar.replaceChildren(el('strong', { text: 'Columns' }));
  for (const g of Object.keys(groups)) {
    const on = state.ui.tableGroups.includes(g);
    bar.append(el('span', {
      class: 'chip' + (on ? ' on' : ''), text: g,
      onclick: () => {
        state.ui.tableGroups = on ? state.ui.tableGroups.filter(x => x !== g) : [...state.ui.tableGroups, g];
        saveUi(); render();
      },
    }));
  }
  const seen = new Set();
  const cols = [];
  for (const g of Object.keys(groups)) {
    if (!state.ui.tableGroups.includes(g)) continue;
    for (const [key, pct] of groups[g]) {
      const id = pct ? `${pct}_${key}` : key;
      if (seen.has(id)) continue;
      seen.add(id);
      const m = findSummary(key);
      cols.push({ id, m, pct, label: metricLabel(m, pct) });
    }
  }
  const win = state.ui.window;
  let rows = visibleArms().flatMap(arm => pointsOf(arm).map(p => ({
    p, arm, values: Object.fromEntries(cols.map(c => [c.id, metricValue(p, c.m, c.pct, win)])),
  })));
  const sort = state.ui.sort;
  if (sort) {
    const val = r => (sort.key === 'arm' ? r.arm.label : sort.key === 'conc' ? r.p.conc : r.values[sort.key]);
    rows.sort((a, b) => {
      const x = val(a), y = val(b);
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * sort.dir;
    });
  }
  const sortBy = key => () => {
    state.ui.sort = state.ui.sort && state.ui.sort.key === key ? { key, dir: -state.ui.sort.dir } : { key, dir: 1 };
    saveUi(); render();
  };
  const arrow = key => (sort && sort.key === key ? (sort.dir > 0 ? ' ▲' : ' ▼') : '');
  const table = $('summary-table');
  table.replaceChildren(
    el('thead', {}, el('tr', {}, [
      el('th', { class: 'text', text: 'arm' + arrow('arm'), onclick: sortBy('arm') }),
      el('th', { text: 'c' + arrow('conc'), onclick: sortBy('conc') }),
      el('th', { text: 'checks' }),
      ...cols.map(c => el('th', { text: c.label + arrow(c.id), title: c.m.note || c.id, onclick: sortBy(c.id) })),
    ])),
    el('tbody', {}, rows.map(r => el('tr', {
      class: 'point-row', title: 'click: show this point over time',
      onclick: () => {
        if (!state.ui.selected.includes(r.p.uid)) state.ui.selected.push(r.p.uid);
        state.ui.tab = 'points'; history.replaceState(null, '', '#points'); saveUi(); render();
      },
    }, [
      el('td', { class: 'text' }, [el('span', { class: 'swatch', style: `background:${r.arm.color}` }), ' ', r.arm.label]),
      el('td', { text: String(r.p.conc) + (r.p.replicate !== null && r.p.replicate !== undefined ? ` r${r.p.replicate}` : '') }),
      el('td', { class: (r.p.p.checks || []).length ? 'warn' : '', text: String((r.p.p.checks || []).length), title: (r.p.p.checks || []).join('\n') }),
      ...cols.map(c => el('td', { text: fmt(r.values[c.id]) })),
    ]))),
  );
  $('checks-list').replaceChildren(...rows.filter(r => (r.p.p.checks || []).length).map(r => el('li', {
    text: `${r.arm.label} c${r.p.conc}: ${r.p.p.checks.join('; ')}`,
  })));
}

// ---------- config tab ----------

function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj || {})) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v === null || v === undefined) out[key] = '';
    else if (Array.isArray(v)) out[key] = v.every(x => typeof x !== 'object' || x === null) ? v.join('\n') : JSON.stringify(v, null, 1);
    else if (typeof v === 'object') flatten(v, key, out);
    else out[key] = String(v);
  }
  return out;
}

// common: lines present in every arm's value; they are grayed so the differing lines stand out.
function valueCell(v, common = null) {
  if (!(v.includes('\n') || v.length > 80)) return el('td', { class: 'text' }, v);
  if (!common) return el('td', { class: 'text' }, el('pre', { text: v }));
  const lines = v.split('\n').map(line => el('span', { class: common.has(line) ? 'same' : 'changed', text: line + '\n' }));
  return el('td', { class: 'text' }, el('pre', {}, lines));
}

function renderConfig() {
  const arms = visibleArms();
  const flat = new Map(arms.map(a => [a.uid, pointsOf(a).map(p => flatten(p.p.config))]));
  const keys = [...new Set([...flat.values()].flat().flatMap(f => Object.keys(f)))].sort();
  const diff = [], same = [], varies = [];
  for (const k of keys) {
    const perArm = arms.map(a => [...new Set(flat.get(a.uid).map(f => f[k] ?? '(not set)'))]);
    const varying = arms.filter((a, i) => perArm[i].length > 1);
    if (varying.length) varies.push([k, varying, perArm]);
    else if (new Set(perArm.map(v => v[0])).size > 1) diff.push([k, perArm.map(v => v[0])]);
    else if (perArm.length) same.push([k, perArm[0][0]]);
  }
  const head = el('thead', {}, el('tr', {}, [el('th', { class: 'text', text: 'setting' }),
    ...arms.map(a => el('th', { class: 'text' }, [el('span', { class: 'swatch', style: `background:${a.color}` }), ' ', a.label]))]));
  $('config-diff').replaceChildren(head, el('tbody', {}, diff.length
    ? diff.map(([k, vals]) => {
      const sets = vals.map(v => new Set(v.split('\n')));
      const common = new Set([...sets[0]].filter(line => sets.every(x => x.has(line))));
      return el('tr', {}, [el('td', { class: 'text', text: k }), ...vals.map(v => valueCell(v, common))]);
    })
    : [el('tr', {}, el('td', { class: 'text', text: arms.length > 1 ? 'no differences' : 'show two or more arms to compare' }))]));
  $('config-same').replaceChildren(el('tbody', {}, same.map(([k, v]) => el('tr', {}, [el('td', { class: 'text', text: k }), valueCell(v)]))));
  $('config-varies').replaceChildren(el('tbody', {}, varies.flatMap(([k, varying, perArm]) => varying.map(a => {
    const vals = perArm[arms.indexOf(a)];
    const shown = vals.slice(0, 6).join('\n') + (vals.length > 6 ? `\n... ${vals.length - 6} more` : '');
    return el('tr', {}, [el('td', { class: 'text', text: k }), el('td', { class: 'text', text: a.label }), valueCell(shown)]);
  }))));

  const sel = $('config-point');
  const pts = arms.flatMap(a => pointsOf(a));
  const current = pts.some(p => p.uid === sel.value) ? sel.value : pts[0]?.uid;
  sel.replaceChildren(...pts.map(p => el('option', { value: p.uid, text: pointName(p), selected: p.uid === current })));
  const p = pts.find(x => x.uid === current);
  if (!p) { $('config-raw').textContent = ''; return; }
  const cfg = clone(p.p.config || {});
  const plugins = cfg.router?.config;
  if (plugins) cfg.router.config = '(below)';
  $('config-raw').textContent = JSON.stringify(cfg, null, 2) + (plugins ? `\n\n# router plugin config (${cfg.router.config_file || ''})\n${plugins}` : '');
}

// ---------- sidebar and top level ----------

function renderSidebar() {
  $('bundle-list').replaceChildren(...state.bundles.map(b => el('div', { class: 'bundle' }, [
    el('span', { text: b.data.title || b.source, title: `${b.source}\n${b.data.description || ''}\ncreated ${b.data.created_utc || '?'}` }),
    el('button', { type: 'button', text: 'remove', onclick: () => { removeBundle(b.source); saveUi(); } }),
  ])));
  const notLoaded = state.index.filter(e => !state.bundles.some(b => b.source === 'data/' + e.file));
  $('available-list').replaceChildren(...notLoaded.map(e => el('div', { class: 'bundle' }, [
    el('span', { text: e.title || e.file, title: `data/${e.file}, ${e.points} points, ${e.created_utc}` }),
    el('button', { type: 'button', text: 'load', onclick: async () => { await loadUrl('data/' + e.file); saveUi(); render(); } }),
  ])));

  const has = state.points.length > 0;
  $('arms-section').hidden = !has;
  $('filters-section').hidden = !has;
  $('empty').hidden = has;
  if (!has) return;

  const focus = state.ui.focus;
  $('arm-list').replaceChildren(...state.arms.map(a => {
    const hidden = state.ui.hidden.includes(a.uid);
    return el('div', { class: 'arm' + (focus.includes(a.uid) ? ' focused' : '') + (focus.length && !focus.includes(a.uid) ? ' dimmed' : '') }, [
      el('input', { type: 'checkbox', checked: !hidden, title: 'show or hide',
        onchange: e => {
          state.ui.hidden = e.target.checked ? state.ui.hidden.filter(u => u !== a.uid) : [...state.ui.hidden, a.uid];
          saveUi(); render();
        } }),
      el('input', { type: 'color', value: a.color, title: 'color',
        onchange: e => { state.ui.colors[a.uid] = e.target.value; refreshDerived(); saveUi(); render(); } }),
      el('span', { class: 'name', text: a.label, title: 'click to focus (others fade)',
        onclick: () => {
          state.ui.focus = focus.includes(a.uid) ? focus.filter(u => u !== a.uid) : [...focus, a.uid];
          saveUi(); render();
        } }),
      a.uid === baselineArm()?.uid ? el('span', { class: 'tag', text: 'baseline' }) : null,
    ]);
  }));
  const base = baselineArm();
  $('baseline-select').replaceChildren(el('option', { value: '', text: '(none)', selected: !base }),
    ...state.arms.map(a => el('option', { value: a.uid, text: a.label, selected: base && a.uid === base.uid })));

  const concs = [...new Set(state.points.map(p => p.conc))].sort((a, b) => a - b);
  $('conc-list').replaceChildren(...concs.map(c => el('span', {
    class: 'chip' + (state.ui.concOff.includes(c) ? '' : ' on'), text: String(c),
    onclick: () => {
      state.ui.concOff = state.ui.concOff.includes(c) ? state.ui.concOff.filter(x => x !== c) : [...state.ui.concOff, c];
      saveUi(); render();
    },
  })));
  document.querySelectorAll('input[name=window]').forEach(r => { r.checked = r.value === state.ui.window; });
  const skip = state.bundles[0]?.data.settings?.skip_minutes;
  $('window-hint').textContent = state.ui.window === 'steady'
    ? `Requests started after minute ${skip ?? '?'}. Columns without a steady value use the whole run.`
    : 'Whole profiling window (AgentX definition).';
  $('legend-toggle').checked = state.ui.legend;
}

function purge(container) {
  container.querySelectorAll('.plot').forEach(d => Plotly.purge(d));
  container.replaceChildren();
}

function render() {
  renderSidebar();
  const has = state.points.length > 0;
  $('title').textContent = state.bundles.map(b => b.data.title).filter(Boolean).join(' + ');
  document.querySelectorAll('#tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === state.ui.tab));
  for (const t of TABS) $('tab-' + t).hidden = !has || state.ui.tab !== t;
  if (!has) return;
  if (state.ui.tab === 'compare') renderCompare();
  else if (state.ui.tab === 'points') renderPoints();
  else if (state.ui.tab === 'table') renderTable();
  else renderConfig();
}

const TABS = ['compare', 'points', 'table', 'config'];

function bindStatic() {
  const fromHash = () => {
    const t = location.hash.slice(1);
    if (TABS.includes(t)) state.ui.tab = t;
  };
  fromHash();
  window.addEventListener('hashchange', () => { fromHash(); saveUi(); render(); });
  document.querySelectorAll('#tabs button').forEach(b => b.addEventListener('click', () => {
    state.ui.tab = b.dataset.tab; history.replaceState(null, '', '#' + b.dataset.tab); saveUi(); render();
  }));
  $('file-input').addEventListener('change', e => { loadFiles(e.target.files); e.target.value = ''; });
  document.addEventListener('dragover', e => e.preventDefault());
  document.addEventListener('drop', e => { e.preventDefault(); loadFiles(e.dataTransfer.files); });
  $('arms-all').addEventListener('click', () => { state.ui.hidden = []; saveUi(); render(); });
  $('arms-none').addEventListener('click', () => { state.ui.hidden = state.arms.map(a => a.uid); saveUi(); render(); });
  $('focus-clear').addEventListener('click', () => { state.ui.focus = []; saveUi(); render(); });
  $('baseline-select').addEventListener('change', e => { state.ui.baseline = e.target.value || null; saveUi(); render(); });
  document.querySelectorAll('input[name=window]').forEach(r => r.addEventListener('change', () => {
    state.ui.window = r.value; saveUi(); render();
  }));
  $('legend-toggle').addEventListener('change', e => { state.ui.legend = e.target.checked; saveUi(); render(); });
  $('reset-layout').addEventListener('click', () => {
    const loaded = state.ui.loaded;
    state.ui = { ...clone(DEFAULT_UI), loaded };
    refreshDerived(); saveUi(); render();
  });
  $('config-point').addEventListener('change', () => renderConfig());
  const add = (list, card) => () => { state.ui[list].push(card()); saveUi(); render(); };
  $('add-conc').addEventListener('click', add('compareCards', () => ({ type: 'conc', metric: 'total_tput_per_gpu' })));
  $('add-pareto').addEventListener('click', add('compareCards', () => ({ type: 'pareto', x: 'ttft_s', xpct: 'p90', y: 'output_tput_per_gpu' })));
  $('add-source').addEventListener('click', add('compareCards', () => ({ type: 'source' })));
  $('add-cache').addEventListener('click', add('compareCards', () => ({ type: 'cache', wide: true })));
  $('add-ts').addEventListener('click', add('pointCards', () => ({ type: 'ts', metric: 'kv_usage_pct' })));
  $('add-dist').addEventListener('click', add('pointCards', () => ({ type: 'dist', metric: 'ttft_s' })));
  $('add-slo').addEventListener('click', add('pointCards', () => ({ type: 'slo', measure: 'turns' })));
}

init();
