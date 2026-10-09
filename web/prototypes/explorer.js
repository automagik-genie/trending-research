'use strict';
// All source-derived content is rendered as text. This is a local design study,
// not a production Scene adapter, financial model, or publication workflow.
const ROOT = '/investigations/frontier-economics/';
const PINS = {
  'evidence.json': 'e452bf54e446ccda30602ca0d2b21188571c78f79bbe4ed7d72d08b9e2d2be93',
  'assessment.md': '1868924ae64190276b8fef2f4b356f64fa01b426bfb3ca0bf71df3e7d13fbeaa'
};
const DIRECTIONS = {relationship: 'Relationships first', timeline: 'Timeline first', questions: 'Questions first'};
const TITLES = {buffer: 'Diversified-partner buffer', fragility: 'Financing-dependent fragility', substitutes: 'Value migrates to substitutes'};
const $ = id => document.getElementById(id);
let pack, revision, hypotheses, rows, sources, spans, entities, state, loading = false;
let question = null, questionStep = 'hypotheses', returnFocus = null;
function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
}
function append(parent, ...children) { parent.append(...children); return parent; }
function button(label, action, id) {
  const n = node('button', label); n.type = 'button';
  if (id) n.dataset.action = id;
  n.addEventListener('click', action); return n;
}
function link(label, uri, download = false) {
  const n = node('a', label);
  // Same-origin links are authored routes; remote links must be plain HTTPS.
  try {
    const u = new URL(uri, location.origin);
    if (u.username || u.password || (u.origin !== location.origin && u.protocol !== 'https:')) return node('span', label + ' (unsafe link withheld)');
    if (u.origin === location.origin && !u.pathname.startsWith(ROOT)) return node('span', label + ' (unapproved local path)');
    n.href = u.href;
    if (download) n.download = u.pathname.split('/').pop();
    else { n.target = '_blank'; n.rel = 'noopener noreferrer'; }
  } catch { return node('span', label + ' (invalid link withheld)'); }
  return n;
}
function fields(parent, values) {
  const dl = node('dl');
  for (const [k, v] of Object.entries(values)) append(dl, node('dt', k), node('dd', v === null ? 'Unknown (null)' : String(v)));
  parent.append(dl);
}
function raw(parent, label, value) {
  const d = node('details', undefined, 'raw');
  append(d, node('summary', label), node('pre', typeof value === 'string' ? value : JSON.stringify(value, null, 2)));
  parent.append(d);
}
function chosenRows() { return rows.filter(r => state.entity_ids.includes(r.observation.entity_id)); }
function readState() {
  const baseline = {scene_id: pack.scenes[0].id, entity_ids: [...pack.scenes[0].entity_ids], evidence_cutoff: pack.scenes[0].evidence_cutoff,
    method_version: pack.scenes[0].method_version, publication_revision_id: pack.scenes[0].publication_revision_id, lens: 'relationship', detail_id: null};
  try {
    const saved = JSON.parse(decodeURIComponent(location.hash.slice(1)));
    // Identity is pinned, never silently substituted by a URL from another revision.
    for (const key of ['scene_id', 'evidence_cutoff', 'method_version', 'publication_revision_id']) if (saved[key] !== baseline[key]) throw Error('different revision');
    if (!Object.hasOwn(DIRECTIONS, saved.lens) || !Array.isArray(saved.entity_ids) || saved.entity_ids.some(id => !baseline.entity_ids.includes(id))) throw Error('invalid selection');
    baseline.entity_ids = [...new Set(saved.entity_ids)]; baseline.lens = saved.lens;
    if (rows.some(r => r.observation.id === saved.detail_id && baseline.entity_ids.includes(r.observation.entity_id)) || hypotheses.some(h => h.id === saved.detail_id)) baseline.detail_id = saved.detail_id;
  } catch { /* An absent or foreign URL starts this exact pinned revision. */ }
  return baseline;
}
function save(push = false) {
  const hash = '#' + encodeURIComponent(JSON.stringify(state));
  if (location.hash !== hash) history[push ? 'pushState' : 'replaceState'](null, '', hash);
}
function openDetail(id, trigger) {
  returnFocus = trigger?.dataset.action || null;
  state.detail_id = id; save(true); render(); $('inspector').focus();
}
function closeDetail() {
  state.detail_id = null; save(true); render();
  const target = [...document.querySelectorAll('[data-action]')].find(n => n.dataset.action === returnFocus);
  const disclosure = target?.closest('details');
  if (disclosure) disclosure.open = true;
  (target || $('overview')).focus();
}
function sourceButton(row, prefix = 'Inspect source') {
  const b = button(prefix + ' · ' + row.observation.id.split(':').pop(), () => openDetail(row.observation.id, b), row.observation.id);
  return b;
}
function hypothesisButton(h) {
  const b = button(TITLES[h.key], () => openDetail(h.id, b), h.id);
  b.append(node('span', 'Conditional explanation · inspect strongest counterevidence and invalidation'));
  return b;
}
function sourceDate(t) {
  if (!t) return 'Unknown source date';
  if (t.precision === 9) return t.time.slice(1, 5) + ' (source year)';
  if (t.precision === 11) return t.time.slice(1, 11) + ' (civil source day)';
  return t.time + ' (source precision ' + t.precision + ')';
}
function sectionHead(title, description) {
  return append(node('div', undefined, 'section-head'), node('h2', title), node('p', description, 'small'));
}
function alternatives(parent) {
  const box = node('section', undefined, 'hypotheses');
  box.append(node('h3', 'Competing explanations'));
  box.append(node('p', 'All three cite the same baseline. Their missing premises remain unknown; these are not contradictory observed results.', 'small'));
  hypotheses.forEach(h => box.append(hypothesisButton(h))); parent.append(box);
}
function counterweight(parent) {
  const c = node('section', undefined, 'counter');
  append(c, node('h3', 'Strongest available counterweight to a collapse story'), node('p', hypotheses.find(h => h.key === 'fragility').counter));
  c.append(node('p', 'Against the buffer explanation: ' + hypotheses.find(h => h.key === 'buffer').counter));
  const b = button('Inspect counterevidence and its limits', () => openDetail('assessment:issue6:fragility:1', b), 'counterevidence');
  c.append(b); parent.append(c);
}
function rowTable(parent, selected) {
  if (!selected.length) { parent.append(node('p', 'No licensed financial rows for this selection. Missing finances are unknown, not zero.', 'empty')); return; }
  const wrap = node('div', undefined, 'table-scroll'), table = node('table');
  table.append(node('caption', 'Secondary P2139 corporate revenue assertions · unverified financial meaning'));
  const labels = ['Entity', 'Source label', 'Signed quantity USD', 'Raw bounds USD', 'Community rank', 'Evidence'];
  const head = node('thead'), hr = node('tr'); labels.forEach(l => { const th = node('th', l); th.scope = 'col'; hr.append(th); }); head.append(hr); table.append(head);
  const body = node('tbody');
  for (const r of selected) {
    const tr = node('tr'); tr.dataset.observation = r.observation.id;
    const v = r.statement.mainsnak.datavalue.value;
    const values = [entities.get(r.observation.entity_id).name, sourceDate(r.time), v.amount, (v.lowerBound ?? 'null') + ' / ' + (v.upperBound ?? 'null'), r.statement.rank];
    values.forEach((v, i) => { const td = node('td', v); td.dataset.label = labels[i]; tr.append(td); });
    const td = node('td'); td.dataset.label = 'Evidence'; td.append(sourceButton(r)); tr.append(td); body.append(tr);
  }
  table.append(body); wrap.append(table); parent.append(wrap);
}
function relationshipView(parent) {
  parent.append(sectionHead('Follow the attribution, not a money trail', 'Entity → source assertion → conditional explanation. No verified payment, financing, or investment relationship exists in this pack.'));
  for (const id of state.entity_ids) {
    const selected = rows.filter(r => r.observation.entity_id === id);
    const section = node('section', undefined, 'relationship'); section.dataset.entity = id;
    const entity = append(node('div', undefined, 'entity'), node('h3', entities.get(id).name), node('p', id, 'small'));
    const connections = node('div');
    connections.append(node('h4', 'Evidence attributed to this entity'));
    connections.append(node('p', selected.length ? selected.length + ' complete revenue statement objects. Corporate-wide, secondary, not AI allocations.' : 'No licensed financial original acquired. All economics remain unknown.', 'small'));
    const d = node('details'); append(d, node('summary', 'Explore ' + entities.get(id).name + ' source assertions')); rowTable(d, selected); connections.append(d);
    connections.append(node('h4', 'Curation links to explanations (not transactions)'));
    const links = node('div', undefined, 'connections'); hypotheses.forEach(h => links.append(hypothesisButton(h))); connections.append(links);
    append(section, entity, connections); parent.append(section);
  }
  counterweight(parent);
}
function timelineView(parent) {
  parent.append(sectionHead('Read the source labels through time', 'Civil year/day precision, not event timestamps or comparable accounting periods. Observation, ingestion and computation clocks are separate in detail.'));
  counterweight(parent); alternatives(parent);
  const selected = [...chosenRows()].sort((a, b) => a.time.time.localeCompare(b.time.time) || a.observation.id.localeCompare(b.observation.id));
  if (!selected.length) { rowTable(parent, selected); return; }
  const list = node('ol', undefined, 'timeline');
  for (const r of selected) {
    const li = node('li'); li.dataset.observation = r.observation.id;
    li.append(node('p', sourceDate(r.time), 'date'));
    const b = sourceButton(r, entities.get(r.observation.entity_id).name);
    b.append(node('span', r.statement.mainsnak.datavalue.value.amount + ' USD · ' + r.statement.rank + ' community rank · secondary assertion', 'amount'));
    li.append(b); list.append(li);
  }
  parent.append(list);
}
function questionView(parent) {
  parent.append(sectionHead('Start with a question, then challenge an explanation', 'Choose a bounded research question. Compare conditional explanations before opening the same underlying evidence. No automated answer or private inference.'));
  const list = node('ol', undefined, 'question-list');
  for (const q of revision.questions) {
    const li = node('li'); const b = button(q.text, () => { question = q.id; questionStep = 'hypotheses'; render(); }, q.id);
    b.setAttribute('aria-pressed', String(question === q.id)); li.append(b); list.append(li);
  }
  parent.append(list);
  if (!question) { parent.append(node('p', 'Select a question to compare explanations. Sources and counterevidence also remain available below.', 'small')); counterweight(parent); rowTable(parent, chosenRows()); return; }
  const step = node('section', undefined, 'step');
  const selected = revision.questions.find(q => q.id === question);
  step.append(node('h3', selected.text));
  const nav = node('nav'); nav.setAttribute('aria-label', 'Question exploration step');
  for (const [key, label] of [['hypotheses', '1 · Compare explanations'], ['evidence', '2 · Inspect evidence'], ['gaps', '3 · Identify missing premises']]) {
    const b = button(label, () => { questionStep = key; render(); }); b.setAttribute('aria-pressed', String(questionStep === key)); nav.append(b);
  }
  step.append(nav);
  if (questionStep === 'hypotheses') { alternatives(step); counterweight(step); }
  if (questionStep === 'evidence') { counterweight(step); rowTable(step, chosenRows()); }
  if (questionStep === 'gaps') {
    append(step, node('p', 'Every selected entity has explicit null inputs below. Neither a corporate revenue statement nor a repeated announcement fills these gaps.'), button('Go to unknown economics', () => $('gaps').scrollIntoView()));
    counterweight(step);
  }
  parent.append(step);
}
function renderIdentity() {
  $('identity').replaceChildren();
  const box = node('div', undefined, 'identity');
  append(box, node('p', 'Pinned draft · ' + revision.revision + ' · ' + state.entity_ids.length + ' entities selected'));
  const d = node('details'); d.append(node('summary', 'Inspect exact Scene, cutoff, method, revision and pack digest'));
  fields(d, {...state, entity_ids: state.entity_ids.join(', '), pack_sha256: PINS['evidence.json'], assessment_sha256: PINS['assessment.md'], contract_version: pack.contract_version});
  box.append(d); $('identity').append(box);
}
function renderGaps() {
  const parent = $('gaps'); parent.replaceChildren(node('h2', 'Unknown is not zero'));
  parent.append(node('p', 'No qualified private financial original for OpenAI or Anthropic. Corporate figures for Microsoft and Amazon do not establish these AI economics. No bubble-burst date is predicted.'));
  const topics = node('div', undefined, 'topics'); revision.topics.forEach(t => topics.append(node('span', t.replaceAll('_', ' ') + ' · unknown'))); parent.append(topics);
  const grid = node('div', undefined, 'unknowns');
  for (const id of state.entity_ids) {
    const d = node('details'); d.append(node('summary', entities.get(id).name + ' · inspect all missing financial inputs'));
    fields(d, Object.fromEntries(Object.entries(revision.unknowns[id]).map(([k, v]) => [k.replaceAll('_', ' '), v]))); grid.append(d);
  }
  parent.append(grid);
  parent.append(node('p', 'Narrative read receipts do not confer retained quotation/translation rights, independent corroboration, or internet-wide sentiment. Coverage and freshness of financial reality are unmeasured; source_checked means text/byte checking only.', 'small'));
}
function showHypothesis(parent, h) {
  append(parent, node('h2', TITLES[h.key]), node('p', 'Authored conditional interpretation · issue-6-engineer · ' + h.id, 'small'));
  fields(parent, {'Interpretation': h.interpretation, 'Assumptions (not measured)': h.assumptions, 'Strongest available counterevidence / limit': h.counter, 'Observable invalidation': h.invalidation});
  const a = pack.assessments.find(a => a.id === h.id);
  fields(parent, {'Evidence cutoff': a.evidence_cutoff, 'Computation': a.computed_at, 'Method': a.method_version, 'Verification': a.confidence.verification + ' (text/bytes only)', 'Coverage numerator': a.confidence.coverage.numerator, 'Coverage denominator': a.confidence.coverage.denominator, 'Newest financial evidence': a.confidence.freshness.newest_evidence_at, 'Independence rationale': a.confidence.independence.rationale});
  parent.append(node('h3', 'Inspect the baseline cited by this explanation'));
  rowTable(parent, chosenRows());
}
function showRow(parent, row) {
  const obs = row.observation, source = sources.get(row.span.source_revision_id), reason = JSON.parse(source.reason);
  append(parent, node('h2', entities.get(obs.entity_id).name + ' · ' + sourceDate(row.time)), node('p', 'Source-attributed secondary community assertion, not issuer-verified recognized revenue or AI revenue.', 'warning'));
  const q = row.statement.mainsnak.datavalue.value;
  fields(parent, {'Observation': obs.id, 'Claim': row.claim.id, 'Evidence span': row.span.id, 'Raw signed quantity': q.amount + ' USD', 'Raw lower bound': q.lowerBound ?? null, 'Raw upper bound': q.upperBound ?? null, 'Community rank (not truth)': row.statement.rank, 'Scope': obs.scope, 'Source publication instant': source.source_published_at, 'Observed at': source.observed_at, 'Ingested at (local registration)': source.ingested_at, 'Event start': obs.event_validity.start, 'Event end': obs.event_validity.end, 'Accounting period start': obs.period.start, 'Accounting period end': obs.period.end, 'Assessment cutoff': state.evidence_cutoff, 'Assessment computation': pack.assessments[0].computed_at});
  parent.append(node('h3', 'Source access · exact canonical view → complete original'));
  parent.append(link('Open pinned Wikidata source revision', source.uri));
  fields(parent, {'Canonical source revision': source.id, 'Canonical content SHA256': source.content_sha256, 'Canonical span selector': JSON.stringify(row.span.selector), 'Origin (not independent corroboration)': source.origin_id, 'Original encoded SHA256': reason.original_sha256, 'Original decoded SHA256': reason.decoded_sha256, 'Exact decoded-original selector': JSON.stringify(reason.selector), 'Raw original quote SHA256': reason.raw_quote_sha256, 'Normalizer': reason.normalizer, 'Original source revision': reason.source_revision});
  parent.append(link('Download complete licensed gzip original · ' + reason.original_path.split('/').pop(), '/' + reason.original_path, true));
  raw(parent, 'Full canonical statement · amount, bounds, rank, qualifiers and references', row.statement);
  raw(parent, 'Exact cited span text (untrusted evidence)', row.span.quote);
  raw(parent, 'Full canonical source-view text (untrusted evidence)', source.content_text);
  parent.append(node('h3', 'Referenced URLs · unacquired and unverified'));
  const urls = [];
  function collect(v) {
    if (!v || typeof v !== 'object') return;
    if (v.datatype === 'url' && typeof v.datavalue?.value === 'string') urls.push(v.datavalue.value);
    Object.values(v).forEach(x => { if (typeof x === 'object') collect(x); });
  }
  collect(row.statement.references);
  if (!urls.length) parent.append(node('p', 'No URL reference in this complete statement. Other reference identifiers remain in raw evidence.'));
  const ul = node('ul'); [...new Set(urls)].forEach(u => ul.append(append(node('li'), link(u, u)))); parent.append(ul);
  counterweight(parent);
}
function render() {
  if (!pack) return;
  renderIdentity();
  $('lenses').replaceChildren();
  for (const [key, label] of Object.entries(DIRECTIONS)) {
    const b = button(label, () => { state.lens = key; save(true); render(); $('lenses').querySelector('[aria-pressed=true]').focus(); });
    b.setAttribute('aria-pressed', String(state.lens === key)); b.dataset.lens = key; $('lenses').append(b);
  }
  // Keep checkbox nodes stable so a selection change does not lose keyboard focus.
  for (const input of $('entities').querySelectorAll('input')) input.checked = state.entity_ids.includes(input.value);
  const overview = $('overview'); overview.tabIndex = -1; overview.replaceChildren();
  if (!state.entity_ids.length) overview.append(node('p', 'No entities selected. Choose one or more entities above; missing selection is not zero economic activity.', 'empty'));
  else ({relationship: relationshipView, timeline: timelineView, questions: questionView})[state.lens](overview);
  const inspector = $('inspector'); inspector.replaceChildren(); inspector.hidden = !state.detail_id;
  $('workspace').classList.toggle('has-detail', Boolean(state.detail_id));
  if (state.detail_id) {
    inspector.append(button('Return to overview', closeDetail, 'close-detail'));
    const h = hypotheses.find(h => h.id === state.detail_id);
    if (h) showHypothesis(inspector, h);
    else showRow(inspector, rows.find(r => r.observation.id === state.detail_id));
  }
  renderGaps();
}
async function pinned(name) {
  const response = await fetch(ROOT + name, {cache: 'no-store', credentials: 'omit'});
  if (!response.ok) throw Error(name + ': HTTP ' + response.status);
  const bytes = await response.arrayBuffer();
  const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(b => b.toString(16).padStart(2, '0')).join('');
  if (digest !== PINS[name]) throw Error(name + ': pinned digest mismatch; no evidence rendered');
  return new TextDecoder('utf-8', {fatal: true}).decode(bytes);
}
async function load() {
  if (loading) return;
  loading = true; pack = null; $('entities').disabled = true; $('reload').disabled = true;
  $('lenses').replaceChildren(); $('identity').replaceChildren(); $('overview').replaceChildren(); $('gaps').replaceChildren(); $('inspector').hidden = true;
  $('status').className = ''; $('status').textContent = 'Loading the same pinned real evidence pack…';
  try {
    const [json, markdown] = await Promise.all([pinned('evidence.json'), pinned('assessment.md')]);
    const candidate = JSON.parse(json);
    const record = JSON.parse(markdown.split('```json\n')[1].split('\n```')[0]);
    if (candidate.contract_version !== '1.0.0' || record.pack_sha256 !== PINS['evidence.json']) throw Error('Unsupported evidence identity');
    sources = new Map(candidate.source_revisions.map(s => [s.id, s])); spans = new Map(candidate.evidence_spans.map(s => [s.id, s])); entities = new Map(candidate.entities.map(e => [e.id, e]));
    rows = candidate.observations.map(observation => {
      const span = spans.get(observation.evidence_span_ids[0]); const statement = JSON.parse(span.quote);
      return {observation, span, statement, time: statement.qualifiers.P585[0].datavalue.value, claim: candidate.claims.find(c => c.id === 'claim:issue6:reported:' + observation.id.split(':').pop())};
    });
    hypotheses = Object.keys(TITLES).map((key, i) => {
      const text = markdown.split('### ' + ['A', 'B', 'C'][i] + '. ')[1].split('\n### ')[0].split('\n## ')[0];
      const bullet = label => text.split('- **' + label + ':** ')[1]?.split('\n')[0];
      return {key, id: 'assessment:issue6:' + key + ':1', interpretation: bullet('Interpretation'), assumptions: bullet('Assumptions'), counter: bullet(key === 'fragility' ? 'Strongest available counterevidence' : 'Strongest available counterevidence/limit'), invalidation: bullet('Observable invalidation')};
    });
    if (hypotheses.some(h => !h.counter || !h.invalidation)) throw Error('Authored alternatives unavailable');
    pack = candidate; revision = record; state = readState(); save();
    $('entities').replaceChildren(node('legend', 'Keep entities selected across directions'));
    for (const id of pack.scenes[0].entity_ids) {
      const label = node('label'), input = node('input'); input.type = 'checkbox'; input.value = id;
      input.addEventListener('change', () => {
        state.entity_ids = [...$('entities').querySelectorAll('input:checked')].map(n => n.value);
        const row = rows.find(r => r.observation.id === state.detail_id);
        if (row && !state.entity_ids.includes(row.observation.entity_id)) state.detail_id = null;
        save(true); render();
      });
      append(label, input, document.createTextNode(entities.get(id).name)); $('entities').append(label);
    }
    $('entities').disabled = false; render();
    $('status').textContent = 'Both exact byte digests verified. 38 secondary statements, four companies, three conditional explanations. No invented financial facts.';
  } catch (error) {
    pack = null; $('status').className = 'error'; $('status').textContent = 'Evidence unavailable: ' + error.message + '. No financial output. Retry with Reload pinned evidence.';
  } finally { loading = false; $('reload').disabled = false; }
}
$('reload').addEventListener('click', load);
window.addEventListener('popstate', () => { if (pack) { state = readState(); render(); } });
load();
