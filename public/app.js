/* Keystone UI. Every interactive element calls the real API; if the backend is slow, reads fall back to a cached snapshot. */
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const USER = (() => { try { let u = localStorage.ks_user; if (!u) { u = 'u' + Math.random().toString(36).slice(2, 9); localStorage.ks_user = u } return u } catch (e) { return 'demo' } })();
let tenant = 'falkordb', HIST = [], busy = false, EXAMPLE = null, EVAL = null, OV = null, cyEv = null, cyNet = null, lastEv = null, SNAP = null, CONFIG = {};
const ENT = { Person: '#1f5c57', PR: '#c8501e', Issue: '#c98a2b', Module: '#8a6d3b', File: '#8c948f', Decision: '#a63d6a', Topic: '#3a7ca5' };
const KIND_PLURAL = { Person: 'People', PR: 'Pull requests', Issue: 'Issues', Module: 'Modules', Decision: 'Decisions', Topic: 'Topic', File: 'Files' };
const PAL = ['#1f5c57', '#c8501e', '#c98a2b', '#a63d6a', '#3a7ca5', '#6b7a3a', '#7a5ea8', '#8a6d3b', '#2f6b4f', '#b13a17'];
const HOMES = []; const homeIdx = h => { let i = HOMES.indexOf(h); if (i < 0) { HOMES.push(h); i = HOMES.length - 1 } return i % PAL.length };
const DEFAULT_PR = { falkordb: 'FalkorDB/GraphRAG-SDK#328', pallets: 'pallets/click#3827' };
const HERO_Q = {
  falkordb: ['Who should review FalkorDB/GraphRAG-SDK#328?', 'Which modules are most at risk of losing knowledge?', 'Why did the team run redis-server as an unprivileged user in Docker?'],
  pallets: ['Who should review pallets/click#3827?', 'Which modules are most at risk of losing knowledge?', 'Why was Python 3.9 support dropped?']
};
const STARTERS = {
  falkordb: [['Who should review', ['Who should review FalkorDB/GraphRAG-SDK#328?']], ['Who knows', ['Who knows variable-length traversal best?', 'Who owns graph/src/runtime?']],
    ['Where is knowledge at risk', ['Which modules are most at risk of losing knowledge?']], ['Why was it decided', ['Why did the team run redis-server as an unprivileged user in Docker?']], ['How people connect', ['Who connects the different repositories?']]],
  pallets: [['Who should review', ['Who should review pallets/click#3827?']], ['Who knows', ['Who knows the shell completion code best?']],
    ['Where is knowledge at risk', ['Which modules are most at risk of losing knowledge?']], ['Why was it decided', ['Why was Python 3.9 support dropped?']], ['How people connect', ['Who connects click and flask?']]]
};

/* ---------- helpers ---------- */
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const REF = /([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)#(\d+)/g;
const link = t => t.replace(REF, '<a href="https://github.com/$1/pull/$2" target="_blank" rel="noopener">$1#$2</a>');
const fmt = t => link(esc(String(t || '').replace(/\*\*|__/g, '')));
const pct = v => Math.round(v * 100);
const ago = d => d < 1 ? 'today' : d === 1 ? '1 day ago' : d < 60 ? d + ' days ago' : Math.round(d / 30) + ' months ago';
const modPath = m => m.split(':').slice(1).join(':');
const repoShort = m => m.split(':')[0].split('/').pop();
const ghUrl = id => /^[^\s#]+\/[^\s#]+#\d+$/.test(id) ? `https://github.com/${id.split('#')[0]}/pull/${id.split('#')[1]}` : null;
const j = async (u, o) => { const r = await fetch(u, o); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText); return r.json() };
const post = (u, b) => j(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tenant, user: USER, ...b }) });
async function snapshot() { if (SNAP === null) { try { SNAP = await (await fetch('/snapshot.json')).json() } catch (e) { SNAP = {} } } return SNAP }
/* live first (8 s budget), cached snapshot if the backend is slow or down */
async function getJSON(url, pick) {
  try { const c = new AbortController(), t = setTimeout(() => c.abort(), 8000); const r = await fetch(url, { signal: c.signal }); clearTimeout(t); if (!r.ok) throw new Error(r.statusText); return await r.json() }
  catch (e) { const v = pick && pick(await snapshot()); if (v === undefined) throw e; $('#banner').hidden = false; return v }
}
const tsnap = k => s => s.t && s.t[tenant] && s.t[tenant][k];

/* ---------- reasoning trail: left-to-right layers, contributing edges thicker ---------- */
function trailLayout(ev, compact, Wfix) {
  const W = Wfix || (compact ? 148 : 204), H = compact ? 38 : 46, GX = compact ? 44 : 70, GY = compact ? 8 : 10, TOP = 22;
  const nodes = new Map(ev.nodes.map(n => [n.id, { ...n, layer: -1 }]));
  const edges = ev.edges.filter(e => nodes.has(e.source) && nodes.has(e.target) && e.source !== e.target);
  const adj = new Map([...nodes.keys()].map(k => [k, []]));
  edges.forEach(e => { adj.get(e.source).push(e.target); adj.get(e.target).push(e.source) });
  const suggested = new Set(edges.filter(e => e.type === 'SUGGESTED').map(e => e.target));
  const pri = n => ({ Topic: 6, Module: 4, Decision: 3, PR: 2, Issue: 2, Person: 1, File: 1 }[n.label] || 0) + (suggested.has(n.id) ? 4 : 0);
  const seen = new Set(), comps = [];
  for (const id of nodes.keys()) if (!seen.has(id)) { const c = [], st = [id]; seen.add(id); while (st.length) { const x = st.pop(); c.push(x); adj.get(x).forEach(y => { if (!seen.has(y)) { seen.add(y); st.push(y) } }) } comps.push(c) }
  comps.sort((a, b) => b.length - a.length);
  let y = TOP, maxLayer = 0; const colKinds = [];
  for (const comp of comps) {
    const root = comp.reduce((a, b) => { const na = nodes.get(a), nb = nodes.get(b); return pri(nb) > pri(na) || (pri(nb) === pri(na) && adj.get(b).length > adj.get(a).length) ? b : a });
    const layers = [[root]]; nodes.get(root).layer = 0; let fr = [root];
    while (fr.length) { const nx = []; fr.forEach(x => adj.get(x).forEach(yy => { const n = nodes.get(yy); if (n.layer < 0) { n.layer = nodes.get(x).layer + 1; nx.push(yy) } })); if (nx.length) layers.push(nx); fr = nx }
    const rows = Math.max(...layers.map(l => l.length));
    layers.forEach((l, li) => { maxLayer = Math.max(maxLayer, li); (colKinds[li] = colKinds[li] || []).push(...l.map(id => nodes.get(id).label)); l.forEach((id, ri) => { const n = nodes.get(id); n.x = li * (W + GX); n.y = y + ((rows - l.length) / 2 + ri) * (H + GY) }) });
    y += rows * (H + GY) + (compact ? 12 : 24)
  }
  const cols = colKinds.map(ks => { const c = {}; ks.forEach(k => c[k] = (c[k] || 0) + 1); const top = Object.entries(c).sort((a, b) => b[1] - a[1])[0]; return top ? (KIND_PLURAL[top[0]] || top[0]) : '' });
  return { nodes: [...nodes.values()], edges, W, H, GX, TOP, width: (maxLayer + 1) * W + maxLayer * GX, height: y, cols };
}
function drawTrail(el, ev, opt = {}) {
  const compact = !!opt.compact;
  if (!ev || !ev.nodes || !ev.nodes.length) { el.innerHTML = '<div class="label" style="padding:28px">No graph for this answer.</div>'; return }
  let L = trailLayout(ev, compact);
  { const n = L.cols.length, avail = (el.clientWidth || 560) - 44, w = Math.floor((avail - (n - 1) * L.GX) / n); if (n && w < L.W) L = trailLayout(ev, compact, Math.max(compact ? 92 : 116, w)) } // fit the container instead of clipping
  const byId = new Map(L.nodes.map(n => [n.id, n]));
  const wmax = Math.max(...L.edges.map(e => e.w || 0), 0.0001);
  const sugScore = {}; L.edges.forEach(e => { if (e.type === 'SUGGESTED') sugScore[e.source] = e.w });
  const paths = L.edges.map(e => { let a = byId.get(e.source), b = byId.get(e.target); if (a.layer > b.layer) [a, b] = [b, a];
    const x1 = a.x + L.W, y1 = a.y + L.H / 2, x2 = b.x, y2 = b.y + L.H / 2, mx = (x1 + x2) / 2;
    const sw = e.w ? 1.4 + (e.w / wmax) * 3.4 : 1.4, hot = e.type === 'SUGGESTED' || e.type === 'KNOWS' || e.w;
    const d = a.layer === b.layer ? `M${a.x + L.W / 2} ${Math.min(a.y, b.y) + L.H} V${Math.max(a.y, b.y)}` : `M${x1} ${y1} C${x1 + L.GX / 2} ${y1},${x2 - L.GX / 2} ${y2},${x2} ${y2}`;
    return `<path d="${d}" fill="none" stroke="${hot ? '#d34a1f' : '#a39c86'}" stroke-width="${sw.toFixed(1)}" opacity=".85" data-s="${esc(e.source)}" data-t="${esc(e.target)}"/>` + (compact ? '' : `<text x="${mx}" y="${(y1 + y2) / 2 - 3}" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="8.5" fill="#5a645f" style="paint-order:stroke;stroke:#f1ede3;stroke-width:3px">${esc(e.type.toLowerCase())}</text>`) }).join('');
  const heads = L.cols.map((c, i) => `<div class="col" style="position:absolute;left:${i * (L.W + L.GX)}px;top:0;width:${L.W}px">${esc(c)}</div>`).join('');
  const cards = L.nodes.map(n => { const sub = n.label === 'Person' && sugScore[n.id] != null ? 'score ' + sugScore[n.id] : n.label === 'PR' || n.label === 'Issue' || n.label === 'Decision' ? (n.title || '') : n.label === 'Module' ? n.id.split(':')[0].split('/').pop() : '';
    return `<div class="tn" data-id="${esc(n.id)}" style="left:${n.x}px;top:${n.y}px;width:${L.W}px;height:${L.H}px;--c:${ENT[n.label] || '#888'}" title="${esc((n.title || n.name || n.id) + ' (' + n.id + ')')}"><div class="k">${esc(n.label)}</div><div class="t">${esc(shortNode(n))}</div>${compact ? '' : `<div class="s">${esc(sub)}</div>`}</div>` }).join('');
  el.innerHTML = `<div class="trail ${compact ? 'compact' : ''}"><div style="position:relative;width:${L.width}px;height:${L.height}px">${heads}<svg width="${L.width}" height="${L.height}">${paths}</svg>${cards}</div></div>`;
  $$('.tn', el).forEach(c => {
    const id = c.dataset.id, n = byId.get(id);
    c.onclick = () => opt.onNode ? opt.onNode(n) : (ghUrl(id) || (n.label === 'Person' && 'https://github.com/' + id)) && window.open(ghUrl(id) || 'https://github.com/' + id, '_blank', 'noopener');
    c.onmouseenter = () => $$('svg path', el).forEach(p => p.style.opacity = (p.dataset.s === id || p.dataset.t === id) ? 1 : .12);
    c.onmouseleave = () => $$('svg path', el).forEach(p => p.style.opacity = '');
  })
}
const shortNode = n => { const id = n.id, k = n.label;
  if (/^[^\s#]+\/[^\s#]+#\d+$/.test(id)) return id.split('/').pop();
  if (k === 'Module') return id.split(':').pop().split('/').slice(-2).join('/') || id;
  const t = n.name || id; return t.length > 30 ? t.slice(0, 30) + '...' : t };
/* ---------- interactive graph layer: hover highlight, detail card, live expand, zoom controls ---------- */
const EXP = {};
const HINT = 'Hover to highlight. Click a node for facts and a follow-up question. Double-click to pull in its neighbours from FalkorDB. Ctrl+scroll to zoom.';
async function getExpand(d) { const k = d.label + '|' + d.id; if (!EXP[k]) EXP[k] = await j(`/api/expand?tenant=${tenant}&kind=${encodeURIComponent(d.label)}&id=${encodeURIComponent(d.id)}`); return EXP[k] }
const askFor = d => d.label === 'Module' ? 'Who knows ' + modPath(d.id) + ' best?' : d.label === 'PR' ? 'Who should review ' + d.id + '?' : d.label === 'Decision' ? 'Why was this decided: ' + (d.title || d.name) + '?' : null;
const openUrl = d => d.label === 'Person' ? 'https://github.com/' + d.id : ghUrl(d.id) ? ghUrl(d.id).replace('/pull/', d.label === 'Issue' ? '/issues/' : '/pull/') : null;
function showCard(card, d, onExpand) {
  card.hidden = false; const url = openUrl(d), q = askFor(d);
  card.innerHTML = `<button class="x" aria-label="Close">&times;</button><div class="label" style="color:${ENT[d.label] || '#888'}">${esc(d.label)}</div><div class="ttl">${esc(shortNode(d))}</div><div class="small muted" style="overflow-wrap:anywhere">${esc(d.title || d.name || d.id)}</div><div class="facts small">Loading facts from FalkorDB...</div><div class="acts">${onExpand ? '<button class="btn sm" data-a="exp">Expand neighbours</button>' : ''}${q ? '<button class="btn sm dark" data-a="ask">Ask about this</button>' : ''}${url ? `<a class="btn sm" href="${url}" target="_blank" rel="noopener">Open on GitHub</a>` : ''}</div>`;
  card.querySelector('.x').onclick = () => { card.hidden = true };
  getExpand(d).then(r => { const f = card.querySelector('.facts'); if (f) f.innerHTML = r.facts.map(x => `<div>${esc(x)}</div>`).join('') + `<div class="muted" style="margin-top:4px">${r.nodes.length} neighbours in the graph</div>` }).catch(() => { const f = card.querySelector('.facts'); if (f) f.textContent = 'Facts unavailable right now.' });
  const e = card.querySelector('[data-a=exp]'); if (e) e.onclick = () => onExpand(d);
  const a = card.querySelector('[data-a=ask]'); if (a) a.onclick = () => askQuestion(q)
}
const LAYOUT = (animate, fit) => ({ name: 'cose', animate: !!animate, animationDuration: 500, padding: 50, nodeRepulsion: 14000, idealEdgeLength: 105, nodeOverlap: 30, gravity: .5, numIter: animate ? 800 : 2500, nodeDimensionsIncludeLabels: true, randomize: !animate, fit: fit !== false });
async function expandNode(cy, d) {
  let r; try { r = await getExpand(d) } catch (e) { return }
  const have = new Set(cy.nodes().map(n => n.id())), at = cy.getElementById(d.id), pos = at.length ? at.position() : { x: 0, y: 0 }, add = [];
  r.nodes.forEach(n => { if (!have.has(n.id)) { have.add(n.id); add.push({ group: 'nodes', data: { id: n.id, label: shortNode(n), kind: n.label, name: n.name, title: n.title }, position: { x: pos.x + (Math.random() - .5) * 80, y: pos.y + (Math.random() - .5) * 80 } }) } });
  r.edges.forEach(e => { if (!have.has(e.source) || !have.has(e.target)) return; const id = 'x|' + e.source + '|' + e.target + '|' + e.type; if (!cy.getElementById(id).length) add.push({ group: 'edges', data: { id, source: e.source, target: e.target, label: e.type.toLowerCase() } }) });
  if (!add.length) return; cy.add(add); cy.layout(LAYOUT(true, false)).run(); setTimeout(() => cy.animate({ fit: { eles: cy.elements(), padding: 50 } }, { duration: 350 }), 600)
}
function wireCy(cy, el, card) {
  cy.userZoomingEnabled(false); // plain scroll keeps scrolling the page; ctrl/cmd+scroll or the buttons zoom
  el.addEventListener('wheel', e => { if (e.ctrlKey || e.metaKey) { e.preventDefault(); cy.zoom({ level: Math.min(2.5, Math.max(.25, cy.zoom() * (e.deltaY < 0 ? 1.12 : .89))), renderedPosition: { x: e.offsetX, y: e.offsetY } }) } }, { passive: false });
  const data = n => ({ id: n.id(), label: n.data('kind') || 'Person', name: n.data('name'), title: n.data('title') });
  cy.on('mouseover', 'node', e => { el.style.cursor = 'pointer'; cy.elements().addClass('faded'); e.target.closedNeighborhood().removeClass('faded') });
  cy.on('mouseout', 'node', () => { el.style.cursor = ''; cy.elements().removeClass('faded') });
  cy.on('tap', 'node', e => { cy.nodes().unselect(); e.target.select(); showCard(card, data(e.target), d => expandNode(cy, d)) });
  cy.on('dbltap', 'node', e => expandNode(cy, data(e.target)));
  cy.on('tap', e => { if (e.target === cy) card.hidden = true });
  const host = el.parentElement; host.querySelectorAll('.gtools').forEach(x => x.remove());
  const t = document.createElement('div'); t.className = 'gtools'; t.innerHTML = '<button title="Zoom in">+</button><button title="Zoom out">&minus;</button><button title="Fit to view">Fit</button><button title="Re-run the layout">&#8635;</button>'; host.append(t);
  const mid = () => ({ x: el.clientWidth / 2, y: el.clientHeight / 2 }), [zi, zo, fit, rl] = t.children;
  zi.onclick = () => cy.zoom({ level: Math.min(2.5, cy.zoom() * 1.25), renderedPosition: mid() }); zo.onclick = () => cy.zoom({ level: Math.max(.25, cy.zoom() * .8), renderedPosition: mid() });
  fit.onclick = () => cy.animate({ fit: { eles: cy.elements(), padding: 50 } }, { duration: 250 }); rl.onclick = () => { cy.layout(LAYOUT(true)).run() }
}
const CY_STYLE = bgNode => [
  { selector: 'node', style: { 'background-color': bgNode, label: 'data(label)', color: '#14211e', 'font-size': 11, 'font-family': 'Inter', 'text-valign': 'bottom', 'text-margin-y': 5, width: 20, height: 20, 'text-background-color': '#f1ede3', 'text-background-opacity': .9, 'text-background-padding': 2, 'text-wrap': 'ellipsis', 'text-max-width': 110, 'transition-property': 'opacity', 'transition-duration': '0.15s' } },
  { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#14211e' } },
  { selector: 'edge', style: { width: 1.3, 'line-color': '#a39c86', 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#a39c86', label: 'data(label)', 'font-size': 8, 'font-family': 'JetBrains Mono', color: '#5a645f', 'text-rotation': 'autorotate', 'text-background-color': '#f1ede3', 'text-background-opacity': .8, 'text-background-padding': 1 } },
  { selector: '.faded', style: { opacity: .14 } }];
function drawForce(el, ev) {
  if (cyEv) { cyEv.destroy(); cyEv = null }
  if (!ev || !ev.nodes.length) { el.innerHTML = '<div class="label" style="padding:28px">No graph for this answer.</div>'; return }
  el.innerHTML = ''; const ids = new Set(ev.nodes.map(n => n.id));
  const els = [...ev.nodes.map(n => ({ data: { id: n.id, label: shortNode(n), kind: n.label, name: n.name, title: n.title } })), ...ev.edges.filter(e => ids.has(e.source) && ids.has(e.target)).map((e, i) => ({ data: { id: 'e' + i, source: e.source, target: e.target, label: e.type.toLowerCase() } }))];
  cyEv = cytoscape({ container: el, elements: els, maxZoom: 2.5, minZoom: .25, layout: LAYOUT(false), style: CY_STYLE(n => ENT[n.data('kind')] || '#888') });
  cyEv.fit(undefined, 50); if (cyEv.zoom() > 1.15) { cyEv.zoom(1.15); cyEv.center() }
  wireCy(cyEv, el, $('#gcard'))
}
function exploreInGraph(d) {
  $$('.vtabs button')[1].click();
  setTimeout(() => { if (cyEv) { const n = cyEv.getElementById(d.id); if (n.length) { n.select(); cyEv.animate({ center: { eles: n } }, { duration: 250 }) } expandNode(cyEv, d) } }, 350)
}
function showEvidence(ev, trace) {
  lastEv = ev; drawTrail($('#pane-trail'), ev, { onNode: n => { $$('#pane-trail .tn').forEach(c => c.classList.toggle('hot', c.dataset.id === n.id)); showCard($('#gcard'), n, exploreInGraph) } });
  if (!$('#pane-graph').hidden) drawForce($('#gbox'), ev);
  $('#gcard').hidden = true; $('#nodeinfo').textContent = HINT;
  const used = [...new Set((ev.nodes || []).map(n => n.label))];
  $('#key').innerHTML = used.map(k => `<span><i style="background:${ENT[k] || '#888'}"></i>${esc(k)}</span>`).join('') + '<span>Thicker line = larger contribution to the score</span>';
  $('#trace').innerHTML = trace && trace.length ? trace.map(t => `<details class="q" open><summary><b>${esc(t.tool)}</b> <span class="muted">${esc(JSON.stringify(t.args))} &middot; ${t.ms} ms &middot; ${t.queries.length} quer${t.queries.length === 1 ? 'y' : 'ies'}</span></summary>` + t.queries.map(q => `<pre>${esc(q.cypher)}\n-- ${q.rows} rows, ${q.ms} ms</pre>`).join('') + '</details>').join('') : '<div class="label" style="padding:28px">No tools were needed for this answer.</div>'
}
$$('.vtabs button').forEach(b => b.onclick = () => {
  $$('.vtabs button').forEach(x => x.classList.toggle('on', x === b));
  ['trail', 'graph', 'cypher'].forEach(k => $('#pane-' + k).hidden = k !== b.dataset.t);
  if (b.dataset.t === 'graph' && lastEv) drawForce($('#gbox'), lastEv)
});
const tagsHtml = r => { const q = r.trace.reduce((a, t) => a + t.queries.length, 0), ms = r.trace.reduce((a, t) => a + t.ms, 0);
  return `<div class="tags">${r.trace.map(t => `<span class="tag">${esc(t.tool)}</span>`).join('')}<span class="tag">${q ? q + ' Cypher quer' + (q === 1 ? 'y' : 'ies') : 'cached result'}</span><span class="tag">${ms} ms in graph</span><span class="tag">${r.evidence.nodes.length} evidence nodes</span></div>` };

/* ---------- asking: real streaming progress ---------- */
class Steps {
  constructor(el) { this.el = el; el.innerHTML = '<ul class="steps"></ul>'; this.ul = el.firstChild }
  add(t) { this.done(); const li = document.createElement('li'); li.className = 'live'; li.innerHTML = `<i></i><span>${esc(t)}</span>`; this.ul.append(li); this.cur = li }
  done(t) { if (this.cur) { this.cur.className = 'done'; if (t) this.cur.lastChild.textContent = t; this.cur = null } }
}
function progress(steps) {
  return ev => {
    if (ev.e === 'llm') steps.add(ev.round === 0 ? 'Choosing a graph tool' : 'Writing the answer from the results');
    if (ev.e === 'tool') steps.add(`Running ${ev.name} on FalkorDB`);
    if (ev.e === 'tool_done') steps.done(ev.queries ? `${ev.name}: ${ev.queries} Cypher quer${ev.queries === 1 ? 'y' : 'ies'} in ${ev.ms} ms` : `${ev.name}: served from the 5-minute cache`)
  }
}
async function streamAsk(q, onEv) {
  const body = JSON.stringify({ tenant, question: q, user: USER, history: HIST.slice(-3) });
  let res = null; try { res = await fetch('/api/ask/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body }) } catch (e) { }
  if (res && !res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  if (!res || !res.body) { onEv({ e: 'llm', round: 0 }); return post('/api/ask', { question: q, history: HIST.slice(-3) }) } // no streaming support: plain request
  const rd = res.body.getReader(), dec = new TextDecoder(); let buf = '', final = null;
  for (; ;) { const { done, value } = await rd.read(); if (done) break; buf += dec.decode(value, { stream: true }); let i;
    while ((i = buf.indexOf('\n')) >= 0) { const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1); if (!line) continue; const ev = JSON.parse(line); if (ev.e === 'final') final = ev.result; else if (ev.e === 'error') throw new Error(ev.message); else onEv(ev) } }
  if (!final) throw new Error('The answer stream ended early.'); return final
}
function feedbackButtons(m, r) {
  const sr = r.structured && r.structured.suggest_reviewers; if (!sr || !sr.suggestions) return;
  m.append(...sr.suggestions.map(sg => { const d = document.createElement('div'); d.className = 'small muted'; d.style.marginTop = '8px';
    d.innerHTML = `${esc(sg.person)}: <button class="chip" data-v="accept">good pick</button> <button class="chip" data-v="reject">skip them</button>`;
    d.querySelectorAll('button').forEach(b => b.onclick = async () => { let reason = ''; if (b.dataset.v === 'reject') { reason = prompt('Why skip ' + sg.person + '? It is kept as a learned rule for 30 days.'); if (reason === null) return }
      try { await post('/api/feedback', { pr: sr.pr, person: sg.person, verdict: b.dataset.v, reason, scope: sr.scope }); d.textContent = sg.person + ': saved to your memory graph.'; loadMemory().catch(() => { }) } catch (er) { d.textContent = er.message } }); return d }))
}
/* console (section 02) */
/* the right-hand panel always shows ONE answer's evidence: mark it, and let a click on any earlier answer switch to it */
function setCurrent(m) { $$('#chat .msg').forEach(x => x.classList.toggle('cur', x === m)) }
$('#chat').addEventListener('click', e => { const m = e.target.closest('.msg'); if (m && m._r && !e.target.closest('a,button,input') && !m.classList.contains('cur')) { setCurrent(m); showEvidence(m._r.evidence, m._r.trace) } });
function pushConsole(q, r, label, keepTop) {
  const m = document.createElement('div'); m.className = 'msg';
  m.innerHTML = (label ? `<div class="label">${esc(label)}</div>` : '') + `<div class="qq">${esc(q)}</div><div class="aa">${fmt(r.answer)}</div>` + tagsHtml(r);
  m._r = r; $('#chat').append(m); setCurrent(m); showEvidence(r.evidence, r.trace); feedbackButtons(m, r); $('#chat').scrollTop = keepTop ? 0 : Math.max(0, m.offsetTop - 12); return m
}
async function askConsole(q) {
  if (busy) return; busy = true; $('#askBtn').disabled = true; $('#hbtn').disabled = true;
  const m = document.createElement('div'); m.className = 'msg'; m.innerHTML = `<div class="qq">${esc(q)}</div><div class="aa" id="cs"></div>`; $('#chat').append(m); $('#chat').scrollTop = 1e9;
  const steps = new Steps(m.querySelector('#cs')); steps.add('Reading your question');
  try { const r = await streamAsk(q, progress(steps)); HIST.push({ q: q.slice(0, 400), a: (r.answer || '').slice(0, 1200) });
    steps.done(); m.remove(); pushConsole(q, r); loadMemory().catch(() => { }) }
  catch (err) { m.querySelector('#cs').innerHTML = `<span style="color:var(--bad)">${esc(err.message)}</span>`; m.querySelector('#cs').removeAttribute('id') }
  busy = false; $('#askBtn').disabled = false; $('#hbtn').disabled = false
}
function askQuestion(q) { $('#ask').scrollIntoView({ behavior: 'smooth' }); setTimeout(() => askConsole(q), 350) }
$('#f').onsubmit = e => { e.preventDefault(); const q = $('#q').value.trim(); if (q) { $('#q').value = ''; askConsole(q) } };
function renderStarters() {
  $('#starters').innerHTML = (STARTERS[tenant] || STARTERS.falkordb).map(([lab, qs]) => `<div class="label">${esc(lab)}</div><div class="row">${qs.map(q => `<button class="chip" type="button">${esc(q)}</button>`).join('')}</div>`).join('');
  $$('#starters .chip').forEach(c => c.onclick = () => askConsole(c.textContent))
}
/* hero (above the fold) */
function heroBody(r) {
  const sr = r.structured && r.structured.suggest_reviewers;
  if (!(sr && sr.suggestions && sr.suggestions.length)) return `<div class="ans">${fmt(r.answer)}</div>`;
  return sr.suggestions.slice(0, 3).map((x, i) => `<div class="who"><div class="n">${i + 1}</div><div><b>${esc(x.person)}</b> <span class="muted small">score ${x.score}</span><div class="small muted">${x.because.slice(0, 2).map(b => `${esc(b.role.toLowerCase())} ${link(esc(b.pr))}`).join(' &middot; ')}</div></div></div>`).join('')
}
function heroResult(q, r, label) {
  $('#hout').innerHTML = (label ? `<div class="label" style="margin-bottom:8px">${esc(label)}</div>` : '') + `${heroBody(r)}${tagsHtml(r)}<div id="htrail" style="margin-top:14px;border:1px solid var(--line2);background:var(--paper)"></div><p style="margin:12px 0 0"><button class="btn sm" id="hopen" type="button">Open the full trail, graph and Cypher &darr;</button></p>`;
  drawTrail($('#htrail'), r.evidence, { compact: true });
  $('#hopen').onclick = () => { $('#chat').innerHTML = ''; pushConsole(q, r); $('#ask').scrollIntoView({ behavior: 'smooth' }) }
}
async function askHero(q) {
  if (busy) return; busy = true; $('#hbtn').disabled = true; $('#askBtn').disabled = true;
  $('#hout').innerHTML = `<div class="label" style="margin-bottom:8px">${esc(q)}</div><div id="hs"></div>`;
  const steps = new Steps($('#hs')); steps.add('Reading your question');
  try { const r = await streamAsk(q, progress(steps)); HIST.push({ q: q.slice(0, 400), a: (r.answer || '').slice(0, 1200) }); steps.done(); heroResult(q, r); loadMemory().catch(() => { }) }
  catch (err) { $('#hout').innerHTML = `<p style="color:var(--bad);margin:0 0 10px">${esc(err.message)}</p><p class="small muted" style="margin:0">Showing the pre-computed example instead.</p>`; setTimeout(showHeroExample, 2200) }
  busy = false; $('#hbtn').disabled = false; $('#askBtn').disabled = false
}
function showHeroExample() {
  if (tenant === 'falkordb' && EXAMPLE) heroResult(EXAMPLE.question, EXAMPLE, 'Pre-computed example. Ask your own above.');
  else $('#hout').innerHTML = '<p class="muted" style="margin:0">Pick a question above or type your own. Every answer shows the reasoning trail behind it.</p>'
}
$('#hf').onsubmit = e => { e.preventDefault(); const q = $('#hq').value.trim(); if (q) { $('#hq').value = ''; askHero(q) } };
function renderHeroChips() {
  const qs = HERO_Q[tenant] || HERO_Q.falkordb; $('#hq').placeholder = qs[0];
  $('#hchips').innerHTML = qs.map(q => `<button class="chip" type="button">${esc(q)}</button>`).join('');
  $$('#hchips .chip').forEach(c => c.onclick = () => askHero(c.textContent))
}

/* ---------- ticker, stats, judges, video ---------- */
async function loadTicker() {
  try { const t = await getJSON('/api/ticker?tenant=' + tenant, tsnap('ticker')); const h = t.map(x => `<span><i>&#9679;</i><b>${esc(x.source)}</b> decided: ${esc(x.text)}</span>`).join(''); $('#ticker').innerHTML = h + h } catch (e) { $('#ticker').innerHTML = '' }
}
function renderStats() {
  const s = (OV && OV.stats) || {}, e = EVAL && EVAL.test && EVAL.test['KEYSTONE (graph blend)'], f = EVAL && EVAL.facts && EVAL.facts.decisions;
  const cells = [[(s.PR || 0).toLocaleString(), 'Pull requests in the graph'], [(s.Decision || 0).toLocaleString(), 'Decisions traced to a source'], [e ? pct(e['hit@3']) + '%' : '-', 'Top-3 reviewer accuracy, held out'], [f ? Math.round(f.rejected / f.proposed * 100) + '%' : '-', 'Model proposals rejected by code']];
  $('#stats').innerHTML = cells.map(([v, l]) => `<div><b>${v}</b><span class="label">${l}</span></div>`).join('')
}
function applyConfig() {
  const v = CONFIG.videoUrl; if (v) { let src = v; const m = v.match(/(?:youtu\.be\/|v=|embed\/)([A-Za-z0-9_-]{11})/); if (m) src = 'https://www.youtube.com/embed/' + m[1];
    $('#vframe').innerHTML = `<iframe src="${esc(src)}" title="Keystone demo video" allow="accelerometer; autoplay; clipboard-write; encrypted-media; picture-in-picture" allowfullscreen></iframe>`; $('#video').hidden = false; $('#watch').hidden = false }
  if (CONFIG.blogUrl) { const b = $('#lBlog'); b.href = CONFIG.blogUrl; b.hidden = false }
}

/* ---------- 01 problem: map grouped by repo ---------- */
const heat = sh => { const t = Math.min(1, Math.max(0, (sh - .2) / .6)); const hue = t < .5 ? 165 - (t / .5) * 125 : 40 - ((t - .5) / .5) * 26; return { bg: `hsl(${Math.round(hue)} ${Math.round(18 + t * 52)}% ${Math.round(74 - t * 26)}%)`, warm: t > .45 } };
async function loadProblem() {
  const [mp, rk] = await Promise.all([getJSON('/api/riskmap?tenant=' + tenant, tsnap('riskmap')), getJSON('/api/risk?tenant=' + tenant, tsnap('risk'))]);
  const groups = {}; mp.forEach(m => (groups[m.module.split(':')[0]] = groups[m.module.split(':')[0]] || []).push(m));
  const order = Object.entries(groups).sort((a, b) => b[1].reduce((s, x) => s + x.recent_prs, 0) - a[1].reduce((s, x) => s + x.recent_prs, 0));
  const mx = Math.max(...mp.map(m => m.recent_prs), 1);
  $('#map').innerHTML = order.map(([repo, ms]) => { const hot = ms.filter(m => m.share >= .5).length;
    return `<div class="group"><div class="gh"><b>${esc(repo.split('/').pop())}</b><span class="label">${ms.length} modules${hot ? ` &middot; <span style="color:var(--accent)">${hot} held ${'≥'} 50% by one person</span>` : ''}</span></div><div class="map">` +
      ms.map(m => { const h = heat(m.share); return `<button class="tile ${h.warm ? 'w' : ''}" data-m="${esc(modPath(m.module))}" title="${esc(m.module)}: ${esc(m.top_expert)} holds ${pct(m.share)}% of ${m.recent_prs} touches, ${m.active_backups} active backups" style="background:${h.bg};flex:${Math.max(1, Math.round(m.recent_prs / mx * 12))} 1 ${Math.max(70, Math.round(40 + m.recent_prs / mx * 120))}px">${esc(modPath(m.module).split('/').slice(-2).join('/'))}<br>${pct(m.share)}%</button>` }).join('') + '</div></div>' }).join('') || '<div class="muted small">Not enough history in this graph.</div>';
  $$('#map .tile').forEach(t => t.onclick = () => askQuestion('Who knows ' + t.dataset.m + ' best?'));
  const b = rk.bus_factor.at_risk_modules.slice(0, 4);
  $('#topRisks').innerHTML = b.length ? b.map(m => `<div class="it"><div class="t">${esc(repoShort(m.module))} / ${esc(modPath(m.module))}</div><div class="bar"><i style="width:${pct(m.share)}%"></i></div><div class="small muted">${esc(m.top_expert)} holds ${pct(m.share)}% of ${m.recent_prs} recent touches &middot; ${m.active_backups} active backups &middot; last active ${ago(m.top_expert_last_active_days)}</div></div>`).join('')
    : '<div class="muted small">No module shows concentrated knowledge in this graph. That is a result too.</div>'
}
async function loadNetwork() {
  const o = await getJSON('/api/overview?tenant=' + tenant, tsnap('overview'));
  if (cyNet) cyNet.destroy();
  const top = new Set([...o.nodes].sort((a, b) => b.pagerank - a.pagerank).slice(0, 22).map(n => n.id));
  cyNet = cytoscape({ container: $('#netbox'), minZoom: .25, maxZoom: 2.5,
    elements: [...o.nodes.map(n => ({ data: { id: n.id, label: top.has(n.id) ? n.id : '', kind: 'Person', name: n.id, title: 'Home repo: ' + n.community, home: n.community, s: 12 + Math.sqrt(n.pagerank * 5000) } })), ...o.edges.map((e, i) => ({ data: { id: 'o' + i, source: e.source, target: e.target } }))],
    layout: { name: 'cose', animate: false, padding: 30, nodeRepulsion: 30000, idealEdgeLength: 70, gravity: .4, numIter: 2500, nodeDimensionsIncludeLabels: true, randomize: true },
    style: [{ selector: 'node', style: { width: 'data(s)', height: 'data(s)', 'background-color': n => n.data('home') ? PAL[homeIdx(n.data('home'))] : (ENT[n.data('kind')] || '#888'), label: 'data(label)', 'font-size': 10, 'font-family': 'Inter', color: '#14211e', 'text-valign': 'bottom', 'text-margin-y': 3, 'text-background-color': '#e8e2d3', 'text-background-opacity': .85, 'text-background-padding': 1, 'transition-property': 'opacity', 'transition-duration': '0.15s' } },
      { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#14211e' } },
      { selector: 'edge', style: { width: .7, 'line-color': '#8a8470', opacity: .4, 'curve-style': 'haystack' } },
      { selector: '.faded', style: { opacity: .1 } }] });
  cyNet.fit(undefined, 30); wireCy(cyNet, $('#netbox'), $('#ncard'));
  cyNet.on('mouseover', 'node', e => { $('#netInfo').textContent = e.target.id() + ' (home: ' + e.target.data('home') + ')' })
}
$$('.seg button').forEach(b => b.onclick = () => {
  $$('.seg button').forEach(x => x.classList.toggle('on', x === b)); const net = b.dataset.v === 'net';
  $('#mapView').hidden = net; $('#netView').hidden = !net; $('#mapHint').textContent = net ? 'Click a person, double-click to expand' : 'Click a tile to ask Keystone';
  if (net) loadNetwork().catch(() => { })
});

/* ---------- 03 remember ---------- */
const mem = { stage: 0, person: null, before: [], after: [], notes: [] };
const who = (arr, strike) => arr.map((x, i) => `<div class="row">${strike && strike === x.person ? `<s>${i + 1}. ${esc(x.person)}</s>` : `${i + 1}. <b>${esc(x.person)}</b>`}<span class="sc">${x.score}</span></div>`).join('');
function renderMem() {
  const pr = DEFAULT_PR[tenant] || DEFAULT_PR.falkordb, p = mem.person || 'the top reviewer';
  const st = i => mem.stage > i ? 'done' : mem.stage === i ? 'cur' : '';
  $('#memSteps').innerHTML = `
    <div class="step ${st(0)}"><div class="num">${mem.stage > 0 ? '&#10003;' : '1'}</div><div><h3>Ask for reviewers</h3><p>Who should review <span class="mono">${esc(pr)}</span>?</p>
      <button class="btn dark sm" id="m1" ${mem.stage > 0 ? 'disabled' : ''}>Ask</button>${mem.before.length ? `<div class="result">${who(mem.before)}</div>` : ''}</div></div>
    <div class="step ${st(1)}"><div class="num">${mem.stage > 1 ? '&#10003;' : '2'}</div><div><h3>Teach it something</h3><p>Tell it ${esc(p)} is on leave for 14 days. It writes a rule into <i>your</i> graph.</p>
      <button class="btn dark sm" id="m2" ${mem.stage !== 1 ? 'disabled' : ''}>Mark ${esc(p)} on leave</button>
      ${mem.stage > 1 ? `<div class="result">Stored: skip <b>${esc(p)}</b> for 14 days (graph <span class="mono">mem_${esc(USER)}</span>).</div>` : ''}</div></div>
    <div class="step ${st(2)}"><div class="num">${mem.stage > 2 ? '&#10003;' : '3'}</div><div><h3>Ask again</h3><p>Same question. A different answer, with the reason.</p>
      <button class="btn dark sm" id="m3" ${mem.stage !== 2 ? 'disabled' : ''}>Ask again</button>
      ${mem.after.length ? `<div class="result">${who(mem.after)}${mem.notes.map(n => `<div class="note">${esc(n)}</div>`).join('')}</div>` : ''}</div></div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding-top:16px"><button class="btn sm" id="mReset" ${mem.stage ? '' : 'disabled'}>Reset demo</button>
      <span class="small muted">Or say it in the Ask box:</span><button class="chip" id="mSay" type="button">Naseem77 is on leave for two weeks</button></div>`;
  const run = (id, fn) => { const b = $(id); if (b) b.onclick = async () => { b.disabled = true; try { await fn() } catch (e) { alert(e.message) } renderMem(); loadMemory().catch(() => { }) } };
  run('#m1', async () => { const r = await post('/api/demo/reviewers', { pr }); if (r.error) throw new Error(r.error); mem.before = r.suggestions; mem.person = r.suggestions[0] && r.suggestions[0].person; mem.stage = 1 });
  run('#m2', async () => { const r = await post('/api/demo/unavailable', { person: mem.person, days: 14, reason: 'on leave' }); if (r.error) throw new Error(r.error); mem.stage = 2 });
  run('#m3', async () => { const r = await post('/api/demo/reviewers', { pr }); mem.after = r.suggestions; mem.notes = r.memory_notes || []; mem.stage = 3 });
  run('#mReset', async () => { if (mem.person) await post('/api/demo/forget', { person: mem.person }); Object.assign(mem, { stage: 0, person: null, before: [], after: [], notes: [] }) });
  const say = $('#mSay'); if (say) say.onclick = () => askQuestion('Naseem77 is on leave for the next two weeks. Who should review ' + pr + ' then?')
}
async function loadMemory() {
  const m = await j('/api/memory?user=' + USER);
  $('#memPanel').innerHTML = `<h3>What Keystone stored about you</h3><p class="small muted" style="margin:0">In your own graph, <span class="mono">mem_${esc(USER)}</span>. No other graph can see it.</p>
    <div class="layer">Procedural &middot; rules</div>${m.rules.length ? m.rules.map(r => `<div class="item">Skip <b>${esc(r.person)}</b> <span class="muted">under ${esc(r.scope)} &middot; ${esc(r.reason || 'no reason')} &middot; expires in ${r.expires_in_days} days</span></div>`).join('') : '<div class="small muted">No rules yet.</div>'}
    <div class="layer">Semantic &middot; feedback</div><div class="small muted">${Object.keys(m.feedback).length ? esc(Object.entries(m.feedback).map(([k, v]) => v + ' ' + k).join(', ')) : 'No accept or reject feedback yet.'}</div>
    <div class="layer">Episodic &middot; recent questions</div>${m.episodes.length ? m.episodes.slice(0, 4).map(e => `<div class="item">${esc(e.q)}</div>`).join('') : '<div class="small muted">Nothing asked yet.</div>'}
    <div class="layer">Working memory</div><div class="small muted">The last three turns of your chat travel with each question, so "who else?" works.</div>`
}

/* ---------- 04 act ---------- */
const act = { stage: 0, task: null, route: null, done: null, queued: 0 };
async function loadBoard() {
  const b = await j('/api/coord/board?tenant=' + tenant);
  $('#board').innerHTML = b.length ? b.slice(0, 12).map(t => `<div class="qrow"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><b class="mono small">${esc(t.id)}</b><span class="badge ${t.status === 'done' ? 'live' : ''}">${esc(t.status)}${t.by ? ' &middot; ' + esc(t.by) : ''}</span></div><div class="small">${esc(t.title)}</div>${t.risk.length ? `<div class="small muted">touches at-risk: ${t.risk.map(esc).join(', ')}</div>` : ''}</div>`).join('') : '<div class="small muted">Empty. Step 1 fills it.</div>';
  const proposed = b.find(t => t.status === 'proposed'); if (proposed && act.stage < 2) { act.task = proposed.id; act.stage = 2 }
  if (!b.some(t => t.status === 'queued') && !proposed && act.stage === 1) act.stage = 0
}
function renderAct() {
  const st = i => act.stage > i ? 'done' : act.stage === i ? 'cur' : '';
  const prop = act.route && act.route.suggestions ? act.route.suggestions.slice(0, 3).map((x, i) => `<div class="row">${i + 1}. <b>${esc(x.person)}</b><span class="sc">${x.score}</span></div>`).join('') : '';
  $('#actSteps').innerHTML = `
    <div class="step ${st(0)}"><div class="num">${act.stage > 0 ? '&#10003;' : '1'}</div><div><h3>Triage agent queues open PRs</h3><p>Finds open pull requests and flags the ones touching at-risk modules.</p><button class="btn dark sm" id="a1" ${act.stage !== 0 ? 'disabled' : ''}>Run triage</button>${act.queued ? `<div class="result">Queued ${act.queued} tasks.</div>` : ''}</div></div>
    <div class="step ${st(1)}"><div class="num">${act.stage > 1 ? '&#10003;' : '2'}</div><div><h3>A router claims one and proposes reviewers</h3><p>One atomic write claims the top-priority task. Two workers cannot claim the same.</p><button class="btn dark sm" id="a2" ${act.stage !== 1 ? 'disabled' : ''}>Claim next task</button>${act.route ? `<div class="result"><div class="small muted">${esc(act.route.pr)}: ${esc(act.route.title)}</div>${prop}</div>` : ''}</div></div>
    <div class="step ${st(2)}"><div class="num">${act.stage > 2 ? '&#10003;' : '3'}</div><div><h3>You approve, an executor acts</h3><p>Opens an issue in our sandbox repo with the recommendation and evidence.</p><button class="btn dark sm" id="a3" ${act.stage !== 2 ? 'disabled' : ''}>Approve</button> <button class="btn sm" id="a3r" ${act.stage !== 2 ? 'disabled' : ''}>Reject</button>
      ${act.done ? `<div class="result">${act.done.status === 'executed' ? `Done. A real issue was created: <a href="${esc(act.done.request.created)}" target="_blank" rel="noopener">${esc(act.done.request.created)}</a>` : act.done.status === 'rejected' ? 'Rejected. Nothing was written.' : `Dry run (no write token, or the daily cap was reached). The exact request:<pre>${esc(JSON.stringify(act.done.request, null, 1)).slice(0, 700)}</pre>`}</div>` : ''}</div></div>
    <div style="padding-top:16px"><button class="btn sm" id="aReset" ${act.stage ? '' : 'disabled'}>Start over</button></div>`;
  const run = (id, fn) => { const b = $(id); if (b) b.onclick = async () => { b.disabled = true; try { await fn() } catch (e) { alert(e.message) } await loadBoard().catch(() => { }); renderAct() } };
  run('#a1', async () => { const r = await post('/api/coord/triage', {}); act.queued = r.queued; act.stage = 1 });
  run('#a2', async () => { const r = await post('/api/coord/route', { worker: 'router-' + (1 + Math.floor(Math.random() * 3)) }); if (!r.task) throw new Error('No queued tasks. Run triage first.'); act.task = r.task; act.route = r.proposal; act.stage = 2 });
  run('#a3', async () => { act.done = await post('/api/coord/decide', { task: act.task, approve: true }); act.stage = 3 });
  run('#a3r', async () => { act.done = await post('/api/coord/decide', { task: act.task, approve: false }); act.stage = 3 });
  run('#aReset', async () => { Object.assign(act, { stage: 0, task: null, route: null, done: null, queued: 0 }) })
}

/* ---------- 05 trust ---------- */
function renderTrust() {
  const e = EVAL; if (!e || !e.test) return;
  const names = [['popular-reviewers (all-time)', 'Most popular reviewers'], ['recent-reviewers (repo prior)', 'Recent reviewers in the repo'], ['file-history (CODEOWNERS/blame-style)', 'File history (CODEOWNERS style)'], ['vector-only (embedding kNN, no graph)', 'Vector search only, no graph'], ['KEYSTONE (graph blend)', 'Keystone (graph)']];
  $('#bigNum').textContent = pct(e.test['KEYSTONE (graph blend)']['hit@3']) + '%';
  $('#evalNote').textContent = `${e.n_test} held-out pull requests` + (e.gain_vs_file ? `. Beats the file-history baseline by ${(e.gain_vs_file.mean * 100).toFixed(1)} points (95% CI ${(e.gain_vs_file.lo * 100).toFixed(1)} to ${(e.gain_vs_file.hi * 100).toFixed(1)}).` : '.');
  $('#bars').innerHTML = names.filter(([k]) => e.test[k]).map(([k, label]) => { const v = e.test[k]['hit@3']; return `<div class="row ${k.startsWith('KEYSTONE') ? 'me' : ''}"><span>${label}</span><div class="track"><div class="fill" style="width:${pct(v)}%"></div></div><span class="v">${v.toFixed(2)}</span></div>` }).join('');
  if (e.per_repo) $('#perRepo').innerHTML = '<table><tr><th>repo</th><th>PRs</th><th>Keystone</th><th>file history</th><th>vector only</th></tr>' + Object.entries(e.per_repo).filter(([, v]) => v.n >= 5).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.n}</td><td><b>${v.keystone.toFixed(2)}</b></td><td>${v.file_history.toFixed(2)}</td><td>${v.vector_only.toFixed(2)}</td></tr>`).join('') + '</table><div class="small muted" style="margin-top:6px">Repos with fewer than 5 test PRs are omitted.</div>';
  const f = e.facts && e.facts.decisions;
  if (f) { const kp = f.kept / f.proposed * 100; $('#funnel').innerHTML = `<div style="width:${kp}%;background:var(--good)">${f.kept.toLocaleString()} kept</div><div style="width:${100 - kp}%;background:var(--bad)">${f.rejected.toLocaleString()} rejected</div>`; $('#funnelNote').textContent = `${Math.round(100 - kp)}% of ${f.proposed.toLocaleString()} model proposals were thrown away by code.` }
  if (e.qa) { $('#kRoute').textContent = Math.round(e.qa.routing.accuracy * e.qa.routing.n) + '/' + e.qa.routing.n; $('#kRet').textContent = pct(e.qa.retrieval['recall@5']) + '%' }
}

/* ---------- boot ---------- */
function observeNav() { const links = $$('#links a'), secs = links.map(a => $(a.getAttribute('href'))); const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) links.forEach((a, i) => a.classList.toggle('on', secs[i] === en.target)) }), { rootMargin: '-45% 0px -50% 0px' }); secs.forEach(s => s && io.observe(s)) }
function consoleIntro() {
  $('#chat').innerHTML = ''; lastEv = null;
  if (tenant === 'falkordb' && EXAMPLE) pushConsole(EXAMPLE.question, EXAMPLE, 'Example (pre-computed)', true);
  else { $('#pane-trail').innerHTML = '<div class="label" style="padding:28px">Ask a question to see the reasoning trail behind the answer.</div>'; $('#trace').innerHTML = ''; $('#key').innerHTML = '' }
}
async function loadTenantData() {
  renderStarters(); renderHeroChips(); Object.assign(mem, { stage: 0, person: null, before: [], after: [], notes: [] }); Object.assign(act, { stage: 0, task: null, route: null, done: null, queued: 0 }); HIST = [];
  const tasks = [getJSON('/api/overview?tenant=' + tenant, tsnap('overview')).then(o => { OV = o; renderStats() }), loadProblem(), loadTicker(), loadBoard(), loadMemory()];
  await Promise.allSettled(tasks); renderMem(); renderAct(); renderStats()
}
(async () => {
  observeNav();
  const [ex, ev, cf] = await Promise.allSettled([j('/example.json'), getJSON('/api/eval', s => s.eval), j('/config.json')]);
  EXAMPLE = ex.status === 'fulfilled' ? ex.value : null; EVAL = ev.status === 'fulfilled' ? ev.value : null; CONFIG = cf.status === 'fulfilled' ? cf.value : {};
  applyConfig(); renderTrust();
  try { const ts = await getJSON('/api/tenants', s => s.tenants); $('#tenant').innerHTML = ts.map(t => `<option>${esc(t)}</option>`).join(''); tenant = ts.includes('falkordb') ? 'falkordb' : ts[0]; $('#tenant').value = tenant } catch (e) { $('#tenant').innerHTML = '<option>falkordb</option>' }
  $('#tenant').onchange = e => { tenant = e.target.value; $('#heroNote').textContent = tenant === 'falkordb' ? "FalkorDB's own repositories" : 'pallets: click and flask'; consoleIntro(); showHeroExample(); loadTenantData() };
  consoleIntro(); showHeroExample(); await loadTenantData()
})();
