/* Keystone UI. Every interactive element calls the real API; nothing here is mocked. */
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const USER = (() => { try { let u = localStorage.ks_user; if (!u) { u = 'u' + Math.random().toString(36).slice(2, 9); localStorage.ks_user = u } return u } catch (e) { return 'demo' } })();
let tenant = 'falkordb', HIST = [], busy = false, cyEv = null, cyNet = null, EXAMPLE = null, EVAL = null;
const ENT = { Person: '#6366f1', PR: '#10b981', Issue: '#f59e0b', Module: '#eab308', File: '#94a3b8', Decision: '#ec4899', Topic: '#06b6d4' };
const PAL = ['#6366f1', '#10b981', '#f59e0b', '#ec4899', '#06b6d4', '#f97316', '#8b5cf6', '#ef4444', '#14b8a6', '#d946ef'];
const HOMES = []; const homeIdx = h => { let i = HOMES.indexOf(h); if (i < 0) { HOMES.push(h); i = HOMES.length - 1 } return i % PAL.length };
const DEFAULT_PR = { falkordb: 'FalkorDB/GraphRAG-SDK#328', pallets: 'pallets/click#3827' };
const STARTERS = {
  falkordb: [['Who should review', ['Who should review FalkorDB/GraphRAG-SDK#328?']],
             ['Who knows', ['Who knows variable-length traversal best?', 'Who owns graph/src/runtime?']],
             ['Where is knowledge at risk', ['Which modules are most at risk of losing knowledge?']],
             ['Why was it decided', ['Why did the team run redis-server as an unprivileged user in Docker?']],
             ['How people connect', ['Who connects the different repositories?']]],
  pallets: [['Who should review', ['Who should review pallets/click#3827?']],
            ['Who knows', ['Who knows the shell completion code best?']],
            ['Where is knowledge at risk', ['Which modules are most at risk of losing knowledge?']],
            ['Why was it decided', ['Why was Python 3.9 support dropped?']],
            ['How people connect', ['Who connects click and flask?']]]
};

/* ---------- helpers ---------- */
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const REF = /([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)#(\d+)/g;
const link = t => t.replace(REF, '<a href="https://github.com/$1/pull/$2" target="_blank" rel="noopener">$1#$2</a>');
const fmt = t => link(esc(String(t || '').replace(/\*\*|__/g, '')));
const j = async (u, o) => { const r = await fetch(u, o); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText); return r.json() };
const post = (u, b) => j(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tenant, user: USER, ...b }) });
const theme = () => { const d = matchMedia('(prefers-color-scheme: dark)').matches; return { ink: d ? '#e8eaf0' : '#0f172a', bg: d ? '#12151c' : '#ffffff', edge: d ? '#475069' : '#a3adc2' } };
const pct = v => Math.round(v * 100);
const ago = d => d < 1 ? 'today' : d === 1 ? '1 day ago' : d < 60 ? d + ' days ago' : Math.round(d / 30) + ' months ago';
const modPath = m => m.split(':').slice(1).join(':');
const heat = sh => { const t = Math.min(1, Math.max(0, (sh - .2) / .6)); const h = t < .5 ? 215 - t * 2 * 110 : 105 - (t - .5) * 2 * 97; return `hsl(${Math.round(h)} ${Math.round(55 + t * 15)}% ${Math.round(44 - t * 4)}%)` };
const shortNode = n => { const id = n.id, k = n.label;
  if (/^[^\s#]+\/[^\s#]+#\d+$/.test(id)) return id.split('/').pop();
  if (k === 'Module') return id.split(':').pop().split('/').slice(-2).join('/') || id;
  const t = n.name || id; return t.length > 24 ? t.slice(0, 24) + '...' : t };

/* ---------- evidence / generic graph ---------- */
function drawGraph(el, ev, opt = {}) {
  if (!ev || !ev.nodes.length) { el.innerHTML = '<div class="muted small" style="padding:24px">No graph for this answer.</div>'; return null }
  el.innerHTML = '';
  const t = theme(), ids = new Set(ev.nodes.map(n => n.id)), c = opt.compact;
  const els = [...ev.nodes.map(n => ({ data: { id: n.id, label: shortNode(n), kind: n.label, title: n.title || n.name } })),
    ...ev.edges.filter(e => ids.has(e.source) && ids.has(e.target)).map((e, i) => ({ data: { id: 'e' + i, source: e.source, target: e.target, label: c ? '' : e.type } }))];
  const cy = cytoscape({ container: el, elements: els, maxZoom: 1.15, minZoom: .3, wheelSensitivity: .3,
    layout: { name: 'cose', animate: false, padding: c ? 24 : 50, nodeRepulsion: c ? 9000 : 14000, idealEdgeLength: c ? 80 : 105, nodeOverlap: 30, gravity: .5, numIter: 2500, nodeDimensionsIncludeLabels: true, randomize: true },
    style: [{ selector: 'node', style: { 'background-color': n => ENT[n.data('kind')] || '#888', label: 'data(label)', color: t.ink, 'font-size': c ? 9 : 11, 'text-valign': 'bottom', 'text-margin-y': 5, width: c ? 16 : 22, height: c ? 16 : 22,
        'text-background-color': t.bg, 'text-background-opacity': .85, 'text-background-padding': 2, 'text-background-shape': 'roundrectangle', 'text-wrap': 'ellipsis', 'text-max-width': 110 } },
      { selector: 'node:selected', style: { 'border-width': 3, 'border-color': t.ink } },
      { selector: 'edge', style: { width: 1.3, 'line-color': t.edge, 'curve-style': 'bezier', 'target-arrow-shape': 'triangle', 'target-arrow-color': t.edge, label: 'data(label)', 'font-size': 8, color: t.edge, 'text-rotation': 'autorotate', 'text-background-color': t.bg, 'text-background-opacity': .8, 'text-background-padding': 1 } }] });
  cy.fit(undefined, c ? 20 : 50); if (cy.zoom() > 1.15) { cy.zoom(1.15); cy.center() }
  if (opt.onTap) cy.on('tap', 'node', e => opt.onTap(e.target.data()));
  return cy;
}
function nodeInfo(d) {
  const id = d.id, k = d.kind; let h = `<b>${esc(k)}</b> ${esc(d.title || d.label)}`;
  if (/^[^\s#]+\/[^\s#]+#\d+$/.test(id)) { const [r, n] = id.split('#'); h += ` <a href="https://github.com/${r}/${k === 'Issue' ? 'issues' : 'pull'}/${n}" target="_blank" rel="noopener">${esc(id)}</a>` }
  else if (k === 'Person') h += ` <a href="https://github.com/${esc(id)}" target="_blank" rel="noopener">github.com/${esc(id)}</a>`;
  else if (k === 'Module') h += ` <span class="muted">${esc(id)}</span>`;
  $('#nodeinfo').innerHTML = h
}
function showEvidence(ev) {
  cyEv = drawGraph($('#evbox'), ev, { onTap: nodeInfo });
  $('#nodeinfo').textContent = 'Click a node to see what it is. PRs and people link to GitHub.';
  const used = [...new Set((ev.nodes || []).map(n => n.label))];
  $('#key').innerHTML = used.map(k => `<span><i style="background:${ENT[k] || '#888'}"></i>${esc(k)}</span>`).join('') + '<span>This subgraph is what the queries returned</span>'
}
function showTrace(tr) {
  $('#trace').innerHTML = tr.length ? tr.map(t => `<details class="q" open><summary><b>${esc(t.tool)}</b> <span class="muted">${esc(JSON.stringify(t.args))} &middot; ${t.ms} ms &middot; ${t.queries.length} quer${t.queries.length === 1 ? 'y' : 'ies'}</span></summary>` +
    t.queries.map(q => `<pre>${esc(q.cypher)}\n-- ${q.rows} rows, ${q.ms} ms</pre>`).join('') + '</details>').join('') : '<div class="muted small" style="padding:18px">No tools were needed for this answer.</div>'
}
const tagsHtml = r => { const q = r.trace.reduce((a, t) => a + t.queries.length, 0), ms = r.trace.reduce((a, t) => a + t.ms, 0);
  return `<div class="tags">${r.trace.map(t => `<span class="tag">${esc(t.tool)}</span>`).join('')}<span class="tag">${q} Cypher quer${q === 1 ? 'y' : 'ies'}</span><span class="tag">${ms} ms in graph</span><span class="tag">${r.evidence.nodes.length} evidence nodes</span></div>` };

/* ---------- hero ---------- */
function renderHero() {
  const ov = window.__ov || { stats: {} }, s = ov.stats, e = EVAL && EVAL.test && EVAL.test['KEYSTONE (graph blend)'];
  $('#heroStats').innerHTML = [[s.Repo, 'repositories'], [(s.PR || 0).toLocaleString(), 'pull requests'], [(s.Decision || 0).toLocaleString(), 'decisions with sources'], [e ? pct(e['hit@3']) + '%' : '-', 'top-3 reviewer accuracy']]
    .map(([v, l]) => `<div class="stat"><b>${v ?? '-'}</b><span>${l}</span></div>`).join('');
}
function renderProof() {
  const box = $('#proof'); if (!EXAMPLE) { box.innerHTML = ''; return }
  const sr = EXAMPLE.structured && EXAMPLE.structured.suggest_reviewers;
  const list = sr ? sr.suggestions.slice(0, 2).map((x, i) => `<div class="who"><div class="n">${i + 1}</div><div><b>${esc(x.person)}</b> <span class="s">score ${x.score}</span><div class="s">${x.because.slice(0, 2).map(b => `${esc(b.role.toLowerCase())} ${link(esc(b.pr))}`).join(' &middot; ')}</div></div></div>`).join('') : `<div class="small">${fmt(EXAMPLE.answer).slice(0, 300)}</div>`;
  box.innerHTML = `<div class="q"><span>${esc(EXAMPLE.question)}</span><small>pre-computed example</small></div><div class="body"><div class="ans">${list}<div class="s muted small" style="margin-top:6px">Because they authored or reviewed earlier PRs touching the same files. The graph on the right is the evidence.</div></div><div class="gr" id="proofGraph"></div></div>`;
  drawGraph($('#proofGraph'), EXAMPLE.evidence, { compact: true })
}

/* ---------- 1 problem ---------- */
async function loadProblem() {
  const [mp, rk] = await Promise.all([j('/api/riskmap?tenant=' + tenant), j('/api/risk?tenant=' + tenant)]);
  const mx = Math.max(...mp.map(m => m.recent_prs), 1);
  $('#map').innerHTML = mp.map(m => `<button class="tile" data-m="${esc(modPath(m.module))}" title="${esc(m.module)}: ${esc(m.top_expert)} holds ${pct(m.share)}% of ${m.recent_prs} touches, ${m.active_backups} active backups" style="background:${heat(m.share)};flex:${Math.max(1, Math.round(m.recent_prs / mx * 14))} 1 ${Math.max(58, Math.round(30 + m.recent_prs / mx * 130))}px"><b>${esc(m.module.split(':')[0].split('/').pop())}</b>${esc(modPath(m.module).split('/').slice(-2).join('/'))} ${pct(m.share)}%</button>`).join('') || '<div class="muted small">Not enough history in this graph.</div>';
  $$('#map .tile').forEach(t => t.onclick = () => askQuestion('Who knows ' + t.dataset.m + ' best?'));
  const b = rk.bus_factor.at_risk_modules.slice(0, 4);
  $('#topRisks').innerHTML = b.length ? b.map(m => `<div><div class="t">${esc(m.module.split(':')[0].split('/').pop())} / ${esc(modPath(m.module))}</div><div class="bar"><i style="width:${pct(m.share)}%"></i></div><div class="m">${esc(m.top_expert)} holds ${pct(m.share)}% of ${m.recent_prs} recent touches &middot; ${m.active_backups} active backups &middot; last active ${ago(m.top_expert_last_active_days)}</div></div>`).join('')
    : '<div class="muted small">No module shows concentrated knowledge in this graph. That is a result too.</div>'
}
async function loadNetwork() {
  const o = await j('/api/overview?tenant=' + tenant), t = theme();
  if (cyNet) cyNet.destroy();
  const top = new Set([...o.nodes].sort((a, b) => b.pagerank - a.pagerank).slice(0, 22).map(n => n.id));
  cyNet = cytoscape({ container: $('#netbox'), minZoom: .3, maxZoom: 2, wheelSensitivity: .3,
    elements: [...o.nodes.map(n => ({ data: { id: n.id, label: top.has(n.id) ? n.id : '', home: n.community, s: 12 + Math.sqrt(n.pagerank * 5000) } })), ...o.edges.map((e, i) => ({ data: { id: 'o' + i, source: e.source, target: e.target } }))],
    layout: { name: 'cose', animate: false, padding: 30, nodeRepulsion: 30000, idealEdgeLength: 70, gravity: .4, numIter: 2500, nodeDimensionsIncludeLabels: true, randomize: true },
    style: [{ selector: 'node', style: { width: 'data(s)', height: 'data(s)', 'background-color': n => PAL[homeIdx(n.data('home'))], label: 'data(label)', 'font-size': 10, color: t.ink, 'text-valign': 'bottom', 'text-margin-y': 3, 'text-background-color': t.bg, 'text-background-opacity': .8, 'text-background-padding': 1 } },
      { selector: 'edge', style: { width: .7, 'line-color': t.edge, opacity: .35, 'curve-style': 'haystack' } }] });
  cyNet.fit(undefined, 30);
  cyNet.on('mouseover', 'node', e => { $('#netInfo').textContent = e.target.id() + ' (home: ' + e.target.data('home') + ')' });
  cyNet.on('tap', 'node', e => window.open('https://github.com/' + e.target.id(), '_blank', 'noopener'))
}
$$('.seg button').forEach(b => b.onclick = () => {
  $$('.seg button').forEach(x => x.classList.toggle('on', x === b));
  const net = b.dataset.v === 'net'; $('#mapView').hidden = net; $('#netView').hidden = !net;
  $('#mapHint').textContent = net ? 'Hover for a name, click to open GitHub.' : 'Click any tile to ask Keystone about it.';
  if (net) loadNetwork().catch(() => { })
});

/* ---------- 2 ask ---------- */
function renderStarters() {
  $('#starters').innerHTML = (STARTERS[tenant] || STARTERS.falkordb).map(([lab, qs]) => `<div class="row"><span class="lab">${esc(lab)}</span>${qs.map(q => `<button class="chip" type="button">${esc(q)}</button>`).join('')}</div>`).join('');
  $$('#starters .chip').forEach(c => c.onclick = () => askQuestion(c.textContent))
}
$$('.tabs button').forEach(b => b.onclick = () => {
  $$('.tabs button').forEach(x => x.classList.toggle('on', x === b));
  $('#tab-ev').hidden = b.dataset.t !== 'ev'; $('#tab-tr').hidden = b.dataset.t !== 'tr';
  if (b.dataset.t === 'ev' && cyEv) cyEv.resize()
});
function askQuestion(q) { $('#ask').scrollIntoView({ behavior: 'smooth' }); setTimeout(() => { $('#q').value = q; $('#f').requestSubmit() }, 350) }
$('#f').onsubmit = async e => {
  e.preventDefault(); if (busy) return; const q = $('#q').value.trim(); if (!q) return; $('#q').value = ''; busy = true; $('#askBtn').disabled = true;
  const m = document.createElement('div'); m.className = 'msg'; m.innerHTML = `<div class="qq">${esc(q)}</div><div class="aa muted dots">Querying the graph</div>`;
  $('#chat').append(m); $('#chat').scrollTop = 1e9;
  try {
    const r = await post('/api/ask', { question: q, history: HIST.slice(-3) }); HIST.push({ q: q.slice(0, 400), a: (r.answer || '').slice(0, 1200) });
    const a = m.querySelector('.aa'); a.className = 'aa'; a.innerHTML = fmt(r.answer); m.insertAdjacentHTML('beforeend', tagsHtml(r));
    showEvidence(r.evidence); showTrace(r.trace);
    const sr = r.structured && r.structured.suggest_reviewers;
    if (sr && sr.suggestions) m.append(...sr.suggestions.map(sg => {
      const d = document.createElement('div'); d.className = 'small muted'; d.style.marginTop = '8px';
      d.innerHTML = `${esc(sg.person)}: <button class="chip" data-v="accept">good pick</button> <button class="chip" data-v="reject">skip them</button>`;
      d.querySelectorAll('button').forEach(b => b.onclick = async () => {
        let reason = ''; if (b.dataset.v === 'reject') { reason = prompt('Why skip ' + sg.person + '? It is kept as a learned rule for 30 days.'); if (reason === null) return }
        try { await post('/api/feedback', { pr: sr.pr, person: sg.person, verdict: b.dataset.v, reason, scope: sr.scope }); d.textContent = sg.person + ': saved to your memory graph.'; loadMemory() } catch (er) { d.textContent = er.message }
      }); return d
    }));
    loadMemory().catch(() => { })
  } catch (err) { const a = m.querySelector('.aa'); a.className = 'aa err'; a.textContent = err.message }
  busy = false; $('#askBtn').disabled = false; $('#chat').scrollTop = 1e9
};

/* ---------- 3 remember ---------- */
const mem = { stage: 0, person: null, before: [], after: [], notes: [] };
const who = (arr, strike) => arr.map((x, i) => `<div class="row">${strike && strike === x.person ? `<s>${i + 1}. ${esc(x.person)}</s>` : `${i + 1}. <b>${esc(x.person)}</b>`}<span class="sc">${x.score}</span></div>`).join('');
function renderMem() {
  const pr = DEFAULT_PR[tenant] || DEFAULT_PR.falkordb, p = mem.person || 'the top reviewer';
  const st = i => mem.stage > i ? 'done' : mem.stage === i ? 'cur' : '';
  $('#memSteps').innerHTML = `
    <div class="step ${st(0)}"><div class="num">${mem.stage > 0 ? '&#10003;' : 1}</div><div><h3>Ask for reviewers</h3><p>Who should review <span class="mono">${esc(pr)}</span>?</p>
      <button class="btn sm primary" id="m1" ${mem.stage > 0 ? 'disabled' : ''}>Ask</button>${mem.before.length ? `<div class="result">${who(mem.before)}</div>` : ''}</div></div>
    <div class="step ${st(1)}"><div class="num">${mem.stage > 1 ? '&#10003;' : 2}</div><div><h3>Teach it something</h3><p>Tell it ${esc(p)} is on leave for 14 days. It writes a rule into <i>your</i> graph.</p>
      <button class="btn sm primary" id="m2" ${mem.stage !== 1 ? 'disabled' : ''}>Mark ${esc(p)} on leave</button>
      ${mem.stage > 1 ? `<div class="result">Stored: skip <b>${esc(p)}</b> for 14 days (graph <span class="mono">mem_${esc(USER)}</span>).</div>` : ''}</div></div>
    <div class="step ${st(2)}"><div class="num">${mem.stage > 2 ? '&#10003;' : 3}</div><div><h3>Ask again</h3><p>Same question. A different answer, with the reason.</p>
      <button class="btn sm primary" id="m3" ${mem.stage !== 2 ? 'disabled' : ''}>Ask again</button>
      ${mem.after.length ? `<div class="result">${who(mem.after)}${mem.notes.map(n => `<div class="note">${esc(n)}</div>`).join('')}</div>` : ''}</div></div>
    <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding-top:14px"><button class="btn sm" id="mReset" ${mem.stage ? '' : 'disabled'}>Reset demo</button>
      <span class="small muted">You can also just say it in the Ask box.</span><button class="chip" id="mSay" type="button">Naseem77 is on leave for two weeks</button></div>`;
  const run = (id, fn) => { const b = $(id); if (b) b.onclick = async () => { b.disabled = true; try { await fn() } catch (e) { alert(e.message) } renderMem(); loadMemory().catch(() => { }) } };
  run('#m1', async () => { const r = await post('/api/demo/reviewers', { pr }); if (r.error) throw new Error(r.error); mem.before = r.suggestions; mem.person = r.suggestions[0] && r.suggestions[0].person; mem.stage = 1 });
  run('#m2', async () => { const r = await post('/api/demo/unavailable', { person: mem.person, days: 14, reason: 'on leave' }); if (r.error) throw new Error(r.error); mem.stage = 2 });
  run('#m3', async () => { const r = await post('/api/demo/reviewers', { pr }); mem.after = r.suggestions; mem.notes = r.memory_notes || []; mem.stage = 3 });
  run('#mReset', async () => { if (mem.person) await post('/api/demo/forget', { person: mem.person }); Object.assign(mem, { stage: 0, person: null, before: [], after: [], notes: [] }) });
  const say = $('#mSay'); if (say) say.onclick = () => askQuestion('Naseem77 is on leave for the next two weeks. Who should review ' + pr + ' then?')
}
async function loadMemory() {
  const m = await j('/api/memory?user=' + USER);
  $('#memPanel').innerHTML = `<h3>What Keystone stored about you</h3><p class="small muted" style="margin:0 0 8px">In your own graph, <span class="mono">mem_${esc(USER)}</span>. Nobody else's graph can see it.</p>
    <div class="layer">Procedural: rules</div>${m.rules.length ? m.rules.map(r => `<div class="item">Skip <b>${esc(r.person)}</b> <span class="muted">under ${esc(r.scope)} &middot; ${esc(r.reason || 'no reason')} &middot; expires in ${r.expires_in_days} days</span></div>`).join('') : '<div class="small muted">No rules yet.</div>'}
    <div class="layer" style="margin-top:14px">Semantic: feedback</div><div class="small muted">${Object.keys(m.feedback).length ? esc(Object.entries(m.feedback).map(([k, v]) => v + ' ' + k).join(', ')) : 'No accept or reject feedback yet.'}</div>
    <div class="layer" style="margin-top:14px">Episodic: recent questions</div>${m.episodes.length ? m.episodes.slice(0, 4).map(e => `<div class="item">${esc(e.q)}</div>`).join('') : '<div class="small muted">Nothing asked yet.</div>'}
    <div class="layer" style="margin-top:14px">Working memory</div><div class="small muted">The last three turns of your chat travel with each question, so "who else?" works.</div>`
}

/* ---------- 4 act ---------- */
const act = { stage: 0, task: null, route: null, done: null };
async function loadBoard() {
  const b = await j('/api/coord/board?tenant=' + tenant);
  $('#board').innerHTML = b.length ? b.slice(0, 12).map(t => `<div class="item" style="border:1px solid var(--line);border-radius:10px;padding:8px 10px;margin:6px 0"><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><b class="mono small">${esc(t.id)}</b><span class="badge ${t.status === 'done' ? 'live' : ''}">${esc(t.status)}${t.by ? ' &middot; ' + esc(t.by) : ''}</span></div><div class="small">${esc(t.title)}</div>${t.risk.length ? `<div class="small muted">touches at-risk: ${t.risk.map(esc).join(', ')}</div>` : ''}</div>`).join('')
    : '<div class="small muted">Empty. Step 1 fills it.</div>';
  const proposed = b.find(t => t.status === 'proposed'); if (proposed && act.stage < 2) { act.task = proposed.id; act.stage = 2 }
  if (!b.some(t => t.status === 'queued') && !proposed && act.stage === 1) act.stage = 0
}
function renderAct() {
  const st = i => act.stage > i ? 'done' : act.stage === i ? 'cur' : '';
  const prop = act.route && act.route.suggestions ? act.route.suggestions.slice(0, 3).map((x, i) => `<div class="row">${i + 1}. <b>${esc(x.person)}</b><span class="sc">${x.score}</span></div>`).join('') : '';
  $('#actSteps').innerHTML = `
    <div class="step ${st(0)}"><div class="num">${act.stage > 0 ? '&#10003;' : 1}</div><div><h3>Triage agent queues open PRs</h3><p>Finds open pull requests and flags the ones touching at-risk modules.</p><button class="btn sm primary" id="a1" ${act.stage !== 0 ? 'disabled' : ''}>Run triage</button>${act.queued ? `<div class="result">Queued ${act.queued} tasks.</div>` : ''}</div></div>
    <div class="step ${st(1)}"><div class="num">${act.stage > 1 ? '&#10003;' : 2}</div><div><h3>A router claims one and proposes reviewers</h3><p>One atomic write claims the top-priority task. Two workers cannot claim the same.</p><button class="btn sm primary" id="a2" ${act.stage !== 1 ? 'disabled' : ''}>Claim next task</button>${act.route ? `<div class="result"><div class="small muted">${esc(act.route.pr)}: ${esc(act.route.title)}</div>${prop}</div>` : ''}</div></div>
    <div class="step ${st(2)}"><div class="num">${act.stage > 2 ? '&#10003;' : 3}</div><div><h3>You approve, an executor acts</h3><p>Opens an issue in our sandbox repo with the recommendation and evidence.</p><button class="btn sm primary" id="a3" ${act.stage !== 2 ? 'disabled' : ''}>Approve</button> <button class="btn sm" id="a3r" ${act.stage !== 2 ? 'disabled' : ''}>Reject</button>
      ${act.done ? `<div class="result">${act.done.status === 'executed' ? `Done. A real issue was created: <a href="${esc(act.done.request.created)}" target="_blank" rel="noopener">${esc(act.done.request.created)}</a>` : act.done.status === 'rejected' ? 'Rejected. Nothing was written.' : `Dry run (no write token or daily cap reached). The exact request is below.<pre>${esc(JSON.stringify(act.done.request, null, 1)).slice(0, 700)}</pre>`}</div>` : ''}</div></div>
    <div style="padding-top:14px"><button class="btn sm" id="aReset" ${act.stage ? '' : 'disabled'}>Start over</button></div>`;
  const run = (id, fn) => { const b = $(id); if (b) b.onclick = async () => { b.disabled = true; try { await fn() } catch (e) { alert(e.message) } await loadBoard().catch(() => { }); renderAct() } };
  run('#a1', async () => { const r = await post('/api/coord/triage', {}); act.queued = r.queued; act.stage = 1 });
  run('#a2', async () => { const r = await post('/api/coord/route', { worker: 'router-' + (1 + Math.floor(Math.random() * 3)) }); if (!r.task) throw new Error('No queued tasks. Run triage first.'); act.task = r.task; act.route = r.proposal; act.stage = 2 });
  run('#a3', async () => { act.done = await post('/api/coord/decide', { task: act.task, approve: true }); act.stage = 3 });
  run('#a3r', async () => { act.done = await post('/api/coord/decide', { task: act.task, approve: false }); act.stage = 3 });
  run('#aReset', async () => { Object.assign(act, { stage: 0, task: null, route: null, done: null, queued: 0 }) })
}

/* ---------- 5 trust ---------- */
function renderTrust() {
  const e = EVAL; if (!e || !e.test) return;
  const names = [['popular-reviewers (all-time)', 'Most popular reviewers'], ['recent-reviewers (repo prior)', 'Recent reviewers in the repo'], ['file-history (CODEOWNERS/blame-style)', 'File history (CODEOWNERS style)'], ['vector-only (embedding kNN, no graph)', 'Vector search only, no graph'], ['KEYSTONE (graph blend)', 'Keystone (graph)']];
  $('#bigNum').textContent = pct(e.test['KEYSTONE (graph blend)']['hit@3']) + '%';
  $('#evalNote').textContent = `${e.n_test} held-out pull requests` + (e.gain_vs_file ? `. Beats the file-history baseline by ${(e.gain_vs_file.mean * 100).toFixed(1)} points (95% CI ${(e.gain_vs_file.lo * 100).toFixed(1)} to ${(e.gain_vs_file.hi * 100).toFixed(1)}).` : '.');
  $('#bars').innerHTML = names.filter(([k]) => e.test[k]).map(([k, label]) => { const v = e.test[k]['hit@3']; return `<div class="row ${k.startsWith('KEYSTONE') ? 'me' : ''}"><span>${label}</span><div class="track"><div class="fill" style="width:${pct(v)}%"></div></div><span class="v">${v.toFixed(2)}</span></div>` }).join('');
  if (e.per_repo) $('#perRepo').innerHTML = '<table><tr><th>repo</th><th>PRs</th><th>Keystone</th><th>file history</th><th>vector only</th></tr>' + Object.entries(e.per_repo).filter(([, v]) => v.n >= 5).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v.n}</td><td><b>${v.keystone.toFixed(2)}</b></td><td>${v.file_history.toFixed(2)}</td><td>${v.vector_only.toFixed(2)}</td></tr>`).join('') + '</table><div class="small muted" style="margin-top:6px">Repos with fewer than 5 test PRs are omitted.</div>';
  const f = e.facts && e.facts.decisions;
  if (f) { const kp = f.kept / f.proposed * 100;
    $('#funnel').innerHTML = `<div style="width:${kp}%;background:var(--good)">${f.kept.toLocaleString()} kept</div><div style="width:${100 - kp}%;background:var(--bad)">${f.rejected.toLocaleString()} rejected</div>`;
    $('#funnelNote').textContent = `${Math.round(100 - kp)}% of ${f.proposed.toLocaleString()} model proposals were thrown away by code.` }
  if (e.qa) { $('#kRoute').textContent = Math.round(e.qa.routing.accuracy * e.qa.routing.n) + '/' + e.qa.routing.n; $('#kRet').textContent = pct(e.qa.retrieval['recall@5']) + '%' }
}

/* ---------- boot / navigation ---------- */
function observeNav() {
  const links = $$('#links a'), secs = links.map(a => $(a.getAttribute('href')));
  const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) links.forEach((a, i) => a.classList.toggle('on', secs[i] === en.target)) }), { rootMargin: '-45% 0px -50% 0px' });
  secs.forEach(s => s && io.observe(s))
}
async function loadTenantData() {
  renderStarters(); Object.assign(mem, { stage: 0, person: null, before: [], after: [], notes: [] }); Object.assign(act, { stage: 0, task: null, route: null, done: null, queued: 0 }); HIST = [];
  const tasks = [j('/api/overview?tenant=' + tenant).then(o => { window.__ov = o; renderHero() }), loadProblem(), loadBoard(), loadMemory()];
  await Promise.allSettled(tasks); renderMem(); renderAct()
}
function showExampleInConsole() {
  $('#chat').innerHTML = '<div class="msg muted small">Pick a starter below or ask your own question. Answers come only from graph queries.</div>';
  if (tenant !== 'falkordb' || !EXAMPLE) { $('#evbox').innerHTML = '<div class="muted small" style="padding:24px">Ask a question to see the subgraph behind the answer.</div>'; $('#trace').innerHTML = ''; return }
  const m = document.createElement('div'); m.className = 'msg'; m.innerHTML = `<div class="muted small">Example (pre-computed)</div><div class="qq">${esc(EXAMPLE.question)}</div><div class="aa">${fmt(EXAMPLE.answer)}</div>` + tagsHtml(EXAMPLE);
  $('#chat').append(m); showEvidence(EXAMPLE.evidence); showTrace(EXAMPLE.trace)
}
(async () => {
  observeNav();
  try { const ts = await j('/api/tenants'); $('#tenant').innerHTML = ts.map(t => `<option>${esc(t)}</option>`).join(''); tenant = ts.includes('falkordb') ? 'falkordb' : ts[0]; $('#tenant').value = tenant } catch (e) { }
  $('#tenant').onchange = e => { tenant = e.target.value; showExampleInConsole(); loadTenantData() };
  const [ex, ev] = await Promise.allSettled([j('/example.json'), j('/api/eval')]);
  EXAMPLE = ex.status === 'fulfilled' ? ex.value : null; EVAL = ev.status === 'fulfilled' ? ev.value : null;
  renderProof(); renderTrust(); showExampleInConsole(); await loadTenantData(); renderHero()
})();
