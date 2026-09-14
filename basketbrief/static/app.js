'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const usd = (v) => '$' + Number(v || 0).toLocaleString('en-US', {maximumFractionDigits:2});
const names = {coordinator:'Amal',finance:'Rana',field:'Sami',donor_a:'Northstar Foundation',donor_b:'Community Giving Circle'};
let workspace, role = 'coordinator', state, previous = '', polling = false, toastTimer, requestEpoch = 0;
function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 5500); }
async function api(path = '', options = {}) { return apiAs(role, path, options); }
async function apiAs(who, path = '', options = {}) {
  const headers = {...(options.body instanceof FormData ? {} : {'Content-Type':'application/json'}), Authorization:'Bearer ' + workspace.tokens[who], ...options.headers};
  const response = await fetch('/api/projects/' + workspace.id + path, {...options, headers});
  if (!response.ok) { const data = await response.json().catch(() => ({})); const error = new Error(data.error || (response.status === 422 ? 'Please check the evidence and try again.' : 'The request could not be completed.')); error.status=response.status; throw error; }
  return options.raw ? response : response.json();
}
function title(e) { if(e.kind === 'correction') return 'A correction from the delivery team'; if(e.kind === 'receipt') return e.attachment ? 'Receipt image' : (/kit|supplies/i.test(e.text) ? 'Supplies receipt' : 'Truck hire receipt'); if(e.kind === 'expense_claim') return 'Truck hire, receipt missing'; return e.actor === 'field' ? 'Delivery update' : 'A reply from supplies'; }
function sourceCards(evidence) {
  const ordinal = new Map(evidence.map((e, i) => [e.id, i + 1]));
  if (!evidence.length) return '<div class="empty-state"><p>Your evidence will appear here.</p></div>';
  return '<div class="evidence-list">' + evidence.map(e => `<article class="evidence-card"><div class="source-icon ${e.kind==='expense_claim'?'warning':''}" aria-hidden="true">${e.actor==='field'?'≋':'▤'}</div><div class="source-body"><div class="source-header"><h3>${esc(title(e))}</h3><span class="badge ${e.status==='review'?'amber':e.status==='pending'?'neutral':''}">${e.status==='accepted'?'✓ Linked':e.status==='pending'?'Reviewing':e.status==='superseded'?'Updated later':'Needs review'}</span></div><p class="source-meta">${esc(names[e.actor])} · Source ${ordinal.get(e.id) ?? e.id} · ${esc(e.kind.replace('_',' '))}</p><p class="source-excerpt">${esc(e.text)}</p><button class="text-button" data-source="${e.id}">View original source ↗</button></div></article>`).join('') + '</div>';
}
/* ── the guided run ───────────────────────────────────────────────────────
   Every step below calls the same API a person would, as the same role, against
   the same live agent. Nothing here is animated or pre-recorded: the captions
   only narrate what the workbench underneath is actually doing. */
let storyRunning = false, storyAbort = false;

function caption(text, step, total) {
  const el = $('#story-caption');
  if (!el) return;
  el.innerHTML = `<span class="story-step">${step}/${total}</span><span>${esc(text)}</span>` +
    `<button class="story-stop" data-action="stop-story">Stop</button>`;
  el.dataset.step = String(step);   // the recorder marks its cuts off this
  el.classList.add('show');
}
function captionDone(text) {
  const el = $('#story-caption');
  if (!el) return;
  el.innerHTML = `<span class="story-step done">✓</span><span>${esc(text)}</span>` +
    `<button class="story-stop" data-action="try-your-own">Try it with your own receipt ↗</button>`;
}
const pause = (ms) => new Promise(r => setTimeout(r, ms));

async function untilIdle(limit = 150) {
  for (let i = 0; i < limit; i++) {
    if (storyAbort) throw new Error('stopped');
    await pause(1400);
    const st = await apiAs('coordinator');
    state = st; render(st); previous = JSON.stringify(st);
    if (!st.busy) {
      const failed = st.jobs.find(j => j.status === 'failed');
      if (failed) throw new Error(failed.error);
      if (!st.report) throw new Error('The review did not produce a report.');
      return st;
    }
  }
  throw new Error('The review is taking longer than expected.');
}

async function playStory() {
  if (storyRunning) return;
  storyRunning = true; storyAbort = false; document.body.classList.add("story-active");
  const N = 11;
  try {
    if (state?.report?.status === 'delivered' || state?.evidence?.length > 3) await start(true);
    if (role !== 'coordinator') await switchRole('coordinator');
    caption('Three sources arrived from two different people. The agent is reading them now.', 1, N);
    let st = await untilIdle();

    const open = st.questions.filter(q => q.status === 'open');
    caption(open.length
      ? `It recorded what each source states, found the gap, and asked ${names[open[0].recipient]} — once, directly.`
      : 'It recorded what each source states.', 2, N);
    await pause(3800);

    if (open.length) {
      caption('Rana answers with a photograph of the receipt. Amazon Nova Pro reads it before the review starts.', 3, N);
      const blob = await (await fetch('/static/sample-receipt.png')).blob();
      const body = new FormData();
      body.append('file', new File([blob], 'transport-receipt.png', {type: 'image/png'}));
      body.append('question_id', open[0].id);
      await apiAs('finance', '/upload', {method: 'POST', body});
      st = await untilIdle();
      caption('Read from the photograph: vendor, invoice, two line items, sixty dollars. Every reported dollar now has a receipt behind it.', 4, N);
      await pause(4200);
    }

    const report = st.report;
    if (report && report.status !== 'delivered') {
      caption('In this guided simulation, Amal reviews and approves this exact version. The approval is bound to its content hash.', 5, N);
      await pause(3200);
      await apiAs('coordinator', '/approve', {method: 'POST',
        body: JSON.stringify({report_id: report.id, hash: report.hash, acknowledge: true})});
      st = await untilIdle(10);
      caption('Delivered to both donor inboxes, each with its own receipt.', 6, N);
      await pause(3600);
    }

    caption('Hours later the field team recounts at the church hall: 88 delivered, not 92.', 7, N);
    await apiAs('field', '/evidence', {method: 'POST', body: JSON.stringify({
      text: 'Correction: we recounted at the church hall. 88 kits were delivered, not 92.', kind: 'message', question_id: null})});
    st = await untilIdle();
    await pause(2600);

    let refused = false;
    if (report) {
      try {
        await apiAs('coordinator', '/approve', {method: 'POST',
          body: JSON.stringify({report_id: report.id, hash: report.hash, acknowledge: true})});
      } catch (e) { if (e.status !== 409) throw e; refused = true; }
    }
    caption(refused
      ? 'Both reports were redrafted, the arithmetic gap is stated plainly — and the approval bound to the old version was refused. It cannot be reused for a version nobody read.'
      : 'Both reports were redrafted and the arithmetic gap is stated plainly.', 8, N);
    await pause(4500);
    const fieldQuestion = st.questions.find(q => q.status === 'open' && q.recipient === 'field');
    if (!fieldQuestion) throw new Error('No follow-up was delivered for the distribution gap.');
    caption('BasketBrief asks Sami to check storage. His simulated reply confirms 12 returned kits; it does not invent households.', 9, N);
    await apiAs('field', '/evidence', {method:'POST', body:JSON.stringify({
      text:'Storage recount complete. Returned kits: 12.',
      kind:'correction',question_id:fieldQuestion.id})});
    st = await untilIdle();
    if (st.report.payload.issues.length || st.summary.returned !== 12) throw new Error('The clarification did not resolve the discrepancy.');
    caption('The gap is resolved: 88 delivered plus 12 returned. Amal can inspect both changes before approving the amendment.', 10, N);
    await pause(5500);
    await apiAs('coordinator','/approve',{method:'POST',body:JSON.stringify({report_id:st.report.id,hash:st.report.hash,acknowledge:false})});
    st = await untilIdle(10);
    caption('Both donors receive the approved amendment and its exact changes. Their original report stays unchanged.', 11, N);
    await pause(5000);
    captionDone('Live computation, fictional participants. The agent followed both gaps through to an approved amendment.');
  } catch (e) {
    if (String(e.message) !== 'stopped') captionDone('The run stopped: ' + e.message);
    else $('#story-caption').classList.remove('show');
  } finally { storyRunning = false; document.body.classList.remove("story-active"); await refresh(true); }
}

/* ── bring your own receipt ───────────────────────────────────────────────
   A visitor should not have to care about strangers before they believe any of
   this. The first thing offered is their own piece of paper, read by the same
   deployed reader, with the same guards shown refusing what is not printed on it.
   Nothing is stored and it never enters a workspace. */
let ownReading = null, ownBusy = false, ownPreview = null;

function ownReceipt() {
  const r = ownReading;
  let body;
  if (ownBusy) {
    body = `<div class="own-wait"><span class="spinner"></span> Identifying the document and checking its transcription…</div>`;
  } else if (!r) {
    body = `<label class="own-drop" for="own-file">
        <input id="own-file" type="file" accept="image/png,image/jpeg">
        <b>Drop a receipt here</b>
        <span>A clear purchase receipt, with its final total and currency visible. PNG or JPEG, under 2 MB.</span>
        <span class="own-cta">Choose an image</span>
      </label>
      <p class="own-foot">It is read by the same agent this team uses, and thrown away immediately. Nothing is stored and nothing enters a workspace.</p>`;
  } else if (r.error || r.status === 'unsupported') {
    body = `<div class="own-result"><p class="own-bad">${esc(r.error || r.reason || 'This document is outside the purchase receipt scope.')}</p>
      <p class="own-foot">No expense amount was accepted. Account statements and transfers are not purchase receipts.</p>
      <button class="button secondary" data-action="own-reset">Try another <span>↻</span></button></div>`;
  } else {
    const types = {receipt:'Purchase receipt',invoice:'Invoice · payment not established',utility_bill:'Utility bill · amount due'};
    const rows = [
      ['Document', types[r.document_type] || 'Unconfirmed'],
      ['Vendor', r.vendor || '—'], ['Invoice', r.invoice_no || '—'],
      ['Date', r.date || '—'], ['Transcribed total', r.stated_total != null ? `${r.stated_total} ${r.currency || '(currency not established)'}` : 'Not established'],
    ];
    if (r.summed_total != null) rows.push(['Transcribed item sum', r.summed_total]);
    const verdict = r.mismatch
      ? `<p class="own-flag">${esc(r.mismatch)} <b>The printed total was not rewritten.</b></p>`
      : (r.stated_total != null && r.summed_total != null
          ? `<p class="own-foot">The transcribed amounts agree arithmetically. That does not prove the image was read correctly.</p>`
          : '');
    const warnings = (r.warnings || []).map(w => `<p class="own-flag">${esc(w)}</p>`).join('');
    const eligible = r.eligible_for_expense === true;
    body = `<div class="own-result">
      <p class="${r.status === 'needs_review' ? 'own-flag' : 'own-foot'}">${r.status === 'needs_review' ? 'Unconfirmed transcription — review the original.' : 'Machine transcription — compare every figure with the original.'}</p>
      <dl class="own-facts">${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(String(v))}</dd></div>`).join('')}</dl>
      ${verdict}${warnings}
      <div class="own-guard"><span>${eligible ? 'Proposed receipt amount · still requires coordinator review' : 'No expense amount accepted'}</span>
        <div>${eligible ? (r.recordable || []).map(n => `<code>${esc(n)} ${esc(r.currency || '')}</code>`).join('') : ''}</div>
        <small>${eligible ? 'The image checks passed, but they can still be wrong. This preview records nothing.' : 'Bills show an amount due, not proof of payment. Unsupported or uncertain documents cannot support a workspace expense.'}</small></div>
      <p class="own-foot">Read in ${esc(String(r.seconds ?? '—'))}s · original review required</p>
      <button class="button secondary" data-action="own-reset">Read another <span>↻</span></button></div>`;
  }
  return `<section class="own" id="own"><div class="own-head">
      <span class="eyebrow">TRY A DOCUMENT · OPTIONAL</span>
      <h2>Check a receipt of your own.</h2>
      <p>Try the receipt reader on your own image. Compare its transcription with the original before trusting the figures.</p>
    <ul class="own-list">
      <li><b>It transcribes, it does not decide.</b> Amazon Nova Pro reads the picture; code turns it into typed fields.</li>
      <li><b>It checks the document type first.</b> Account statements and transfers cannot become purchase expenses.</li>
      <li><b>It checks the transcription against the image.</b> Arithmetic is a separate check; either can still miss an error. A human reviews the source.</li>
    </ul>
    </div><div class="own-body">${ownPreview ? `<figure class="own-original"><a href="${esc(ownPreview)}" target="_blank" rel="noopener"><img src="${esc(ownPreview)}" alt="Open your original document at full size"></a><figcaption>Your original · open the image to inspect it at full size</figcaption></figure>` : ''}${body}</div></section>`;
}

async function readOwn(file) {
  if (!storyRunning) $('#story-caption').classList.remove('show');
  if (ownPreview) URL.revokeObjectURL(ownPreview);
  ownPreview = URL.createObjectURL(file);
  ownBusy = true; ownReading = null; render(state);
  try {
    const body = new FormData(); body.append('file', file);
    const response = await fetch('/api/read-receipt', {method: 'POST', body});
    const data = await response.json();
    ownReading = response.ok ? data : {ok: false, error: data.error || 'That did not read as a receipt.'};
  } catch (e) {
    ownReading = {ok: false, error: 'The reader could not be reached.'};
  } finally { ownBusy = false; render(state); }
}

function statusStrip(s) {
  // A workbench, not a landing page: one line of state, the figures inline,
  // and the work itself given the whole frame underneath.
  const st = storyline(s);
  const f = s.summary, gap = Number(f.unsupported || 0);
  const known = v => (v === null || v === undefined) ? '—' : v;
  const fig = (label, value, sub, mod = '') =>
    `<div class="figure ${mod}"><span class="figure-label">${label}</span>` +
    `<b class="figure-value">${value}</b><span class="figure-sub">${sub}</span></div>`;
  return `<section class="strip ${st.tone}" id="overview">
    <div class="strip-head">
      <div class="eyebrow">${st.eyebrow}</div>
      <h1>${st.head.replace(/<br>/g, ' ')}</h1>
      <p>${st.body}</p>
    </div>
    <div class="figures">
      ${fig('Kits delivered', known(f.delivered), known(f.delivered) === '—' ? 'not yet reported'
            : `of ${known(f.loaded)} loaded · ${known(f.returned)} returned`)}
      ${fig('Receipt-supported', usd(f.supported), `of ${usd(f.reported)} reported`)}
      ${fig('Needs a receipt', gap > 0 ? usd(gap) : (Number(f.reported) ? '$0' : '—'),
            gap > 0 ? 'reported, not documented' : 'every amount documented', gap > 0 ? 'is-gap' : '')}
    </div>
  </section>`;
}

function liveTimeline(s) {
  const kinds = {tool:'tool', fact:'recorded', request:'recorded', question:'asked', report:'drafted',
                 approval:'approved', delivery:'delivered', guardrail:'blocked', review:'unresolved',
                 correction:'correction', vision:'read image', ledger:'ledger', complete:'done', agent:'cycle',
                 evidence:'new source', error:'error', gate:'gate', reply:'reply', workspace:'start'};
  const rows = s.events.slice(0, 60).reverse().map(e => {
    const d = e.detail && typeof e.detail === 'object' ? e.detail : {};
    let extra = '';
    if (d.amount) extra = `${d.amount} ${d.supported === false ? '· unsupported' : '· receipt-backed'}`;
    else if (d.delivered !== undefined || d.loaded !== undefined) extra = Object.entries(d)
      .filter(([k, v]) => ['loaded','delivered','returned','households'].includes(k) && v !== null)
      .map(([k, v]) => `${k} ${v}`).join(' · ');
    else if (d.seconds) extra = `${d.seconds}s${d.input_tokens ? ' · ' + (d.input_tokens/1000).toFixed(1) + 'k in' : ''}`;
    else if (d.vendor_new) extra = 'vendor not seen before in this team\u2019s history';
    else if (d.vendor_known) extra = 'vendor seen in a previous distribution';
    else if (d.model) extra = String(d.model);
    else if (d.reason) extra = String(d.reason);
    else if (d.text) extra = String(d.text);
    return `<div class="live-row ${e.kind}"><time>${new Date(e.created*1000).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</time>` +
      `<span class="live-kind">${esc(kinds[e.kind] || e.kind)}</span>` +
      `<span class="live-body"><b>${esc(e.title)}</b>${extra ? `<em>${esc(extra).slice(0,150)}</em>` : ''}</span></div>`;
  }).join('');
  return `<section class="panel live" aria-label="What the agent did">
    <div class="panel-head"><h2>The agent, step by step.</h2>
      <span class="count">${s.busy ? '<span class="spinner"></span> running' : s.events.length + ' steps'}</span></div>
    <div class="live-list" id="live-list">${rows || '<div class="empty-state"><p>Waiting for the first cycle.</p></div>'}</div>
  </section>`;
}

function statusBar(s) {
  const last = s.events.find(e => e.kind === 'complete');
  const d = last && typeof last.detail === 'object' ? last.detail : {};
  const cell = (k, v) => `<span><i>${k}</i>${esc(String(v))}</span>`;
  return `<div class="status-bar" role="status">
    <span class="${s.busy ? 'bar-run' : 'bar-idle'}"><span class="${s.busy ? 'spinner' : 'status-dot'}"></span>${s.busy ? 'reviewing' : 'idle'}</span>
    ${cell('engine', s.project.engine === 'bedrock' ? 'strands · bedrock' : 'local parser')}
    ${cell('model', d.model || (s.project.engine === 'bedrock' ? 'nova-pro' : 'none'))}
    ${cell('revision', 'r' + s.project.revision)}
    ${cell('last cycle', d.seconds ? d.seconds + 's' : '—')}
    ${cell('sources', s.evidence.length)}
    ${cell('deliveries', s.receipts.length)}
  </div>`;
}

function storyline(s) {
  // Every word here is derived from live state. Nothing congratulates the team early.
  const open = s.questions.filter(q => q.status === 'open');
  const r = s.report, delivered = s.receipts.length, gap = Number(s.summary.unsupported || 0);
  const supersededBy = (r && r.status !== 'delivered' && delivered) ? r : null;
  if (s.busy) return {eyebrow:'FLOOD RELIEF · WEEK ONE · REVIEW RUNNING', head:'Reading what<br><em>came in.</em>',
    body:'Every new source is being read, recorded against the figures, and reconciled into both donor drafts.', tone:'working'};
  if (s.jobs.find(j => j.status === 'failed')) return {eyebrow:'FLOOD RELIEF · WEEK ONE · PAUSED', head:'The review<br><em>paused safely.</em>',
    body:'Nothing was lost. Your evidence is saved exactly as it arrived, and the review can be run again.', tone:'warn'};
  if (supersededBy) return {eyebrow:'FLOOD RELIEF · WEEK ONE · CORRECTION ARRIVED', head:open.length ? 'A correction.<br><em>Followed through.</em>' : 'The correction<br><em>is ready.</em>',
    body:open.length ? 'The counts changed after the report was shared. BasketBrief asked the field team to reconcile them; the previous approval cannot authorize this amendment.' : 'The field team clarified the counts. Review the changes against the last delivered report, then approve the amendment for both donors.' , tone:'warn'};
  if (open.length) return {eyebrow:'FLOOD RELIEF · WEEK ONE · ONE GAP', head:'One thing<br><em>is still missing.</em>',
    body:`BasketBrief asked ${esc(names[open[0].recipient])} for it directly, once. The answer will update both donor reports.`, tone:'warn'};
  if (r && r.status === 'delivered') return {eyebrow:'FLOOD RELIEF · WEEK ONE · DELIVERED', head:'Accounted for.<br><em>And in their hands.</em>',
    body:`Version ${r.version} reached both donor inboxes. Your approval is bound to that exact version, and each delivery kept its own receipt.`, tone:'good'};
  if (r && r.status !== 'outdated') return {eyebrow:'FLOOD RELIEF · WEEK ONE · READY FOR YOU', head:'The evidence<br><em>is in order.</em>',
    body: gap > 0 ? `Every source is recorded. ${usd(gap)} of reported spending still has no receipt, and the reports say so plainly.`
                  : 'Every source is recorded and every reported amount has a receipt behind it. Your approval sends this exact version.', tone:'ready'};
  return {eyebrow:'FLOOD RELIEF · WEEK ONE · FIELD REPORT', head:'Let’s get the<br><em>story together.</em>',
    body:'Your sources are saved. BasketBrief will read them, chase what is missing, and draft both donor reports.', tone:'working'};
}
function art(s) {
  // The hero used to carry a clipart illustration. It now carries the only thing worth
  // putting next to the headline: where this report actually stands right now.
  if (!s) return '';
  const r = s.report, open = s.questions.filter(q => q.status === 'open').length;
  const delivered = s.receipts.length;
  const rows = [
    ['Sources read', s.evidence.filter(e => e.status !== 'pending').length + ' of ' + s.evidence.length],
    ['Open questions', open ? String(open) : 'none'],
    ['Report', r ? 'version ' + r.version + ' · ' + (r.status === 'outdated' ? 'superseded' : r.status) : 'not drafted yet'],
    ['Donor deliveries', delivered ? String(delivered) : 'none yet'],
  ];
  return `<aside class="hero-panel" aria-label="Where this report stands">
    <div class="hero-panel-head">Where this stands</div>
    <dl>${rows.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
    <p class="hero-panel-foot">Fictional team · synthetic evidence</p></aside>`;
}
function hero(eyebrow, headline, description, withArt=true, tone='') { return `<section class="hero ${tone}" id="overview"><div class="hero-copy"><div class="eyebrow">${eyebrow}</div><h1>${headline}</h1><p>${description}</p></div>${withArt?art(withArt===true?null:withArt):''}</section>`; }
function metrics(s, busy) {
  const known = (v) => v === null || v === undefined ? null : v;
  const gap = Number(s.unsupported || 0), reported = Number(s.reported || 0);
  const skeleton = busy && known(s.delivered) === null;
  const cell = (label, symbol, value, foot, mod='') => `<article class="metric ${mod} ${skeleton?'is-skeleton':''}"><div class="metric-top">${label} <span class="metric-symbol" aria-hidden="true">${symbol}</span></div><div class="metric-value">${value}</div><div class="metric-foot">${foot}</div></article>`;
  const delivered = known(s.delivered) === null
    ? cell('Kits delivered','▧', skeleton ? '<span class="skeleton-bar"></span>' : 'Not yet reported', 'Waiting on the field team')
    : cell('Kits delivered','▧', `${s.delivered}<small>of ${known(s.loaded) ?? '—'} loaded</small>`, `${known(s.returned) ?? '—'} returned · field-reported, not independently verified`);
  const supported = cell('Receipt-supported','✓', usd(s.supported), reported ? `of ${usd(reported)} reported spending` : 'No spending recorded yet');
  const waiting = gap > 0
    ? cell('Still needs a receipt','◷', usd(gap), 'Reported by the team, not yet documented', 'is-gap')
    : cell('Still needs a receipt','✓', reported ? '$0' : '—', reported ? 'Every reported amount has a receipt' : 'No spending recorded yet');
  return `<section class="metrics" aria-label="Distribution figures">${delivered}${supported}${waiting}</section>`;
}
function nextStep(s) {
  const open = s.questions.filter(q=>q.status==='open'), r = s.report, failed = s.jobs.find(j=>j.status==='failed');
  const deliveredCount = s.receipts.length;
  const stages = ['Gathering', 'Following up', 'Your approval', 'Delivered'];
  let stageIndex = 0, content;
  if (s.busy) { stageIndex = 1; content = `<h2 class="working-indicator"><span class="spinner"></span> Following the evidence.</h2><p>New sources, unanswered questions and both donor drafts are being reconciled. You can watch another role meanwhile — each one sees only its own evidence.</p>`; }
  else if (failed) { content = `<h2>The review needs a retry.</h2><p>${esc(failed.error)}</p><button class="button full" data-action="retry">Run the review again <span>↻</span></button>`; }
  else if (open.length) { stageIndex = 1; const q = open[0];
    content = `<h2>A clear question.<br>To the right person.</h2><p>BasketBrief went straight to ${esc(names[q.recipient])} — the person who has it — instead of routing it through you. One answer updates both donor reports.</p><div class="question-bubble"><div class="person"><span class="avatar">${esc(names[q.recipient][0])}</span>${esc(names[q.recipient])} · ${q.recipient==='finance'?'Supplies & receipts':'Delivery team'}</div><p>${esc(q.text)}</p></div><button class="button secondary full" data-role="${q.recipient}">Answer as ${esc(names[q.recipient])} <span>↗</span></button>`; }
  else if (r && r.status !== 'delivered' && deliveredCount) { stageIndex = 2;
    content = `<h2>The correction.<br>Ready to share.</h2><p>A clarification arrived after the previous report was delivered. Review exactly what changed before sharing this amendment.</p>${changeTable(r.payload)}${issueList(r)}<button class="button full" data-action="approve">Approve version ${r.version} and send the correction <span>↗</span></button>${ackBox(r)}`; }
  else if (r && r.status === 'delivered') { stageIndex = 3;
    content = `<h2>Approved.<br>And in the right hands.</h2><p>Version ${r.version} sits in both donor inboxes. Approval and delivery are recorded against this exact content hash.</p><button class="button full" data-role="donor_a">Open Northstar’s copy <span>↗</span></button><div class="step-foot">✓ ${deliveredCount} inbox deliveries · approved on version ${r.version}</div>`; }
  else if (r && r.status !== 'outdated') { stageIndex = 2;
    content = `<h2>Ready for your eyes.</h2><p>Approval shares this exact version with both donor inboxes, and binds your name to its content hash.</p><div class="question-bubble"><b>Version ${r.version}</b> · ${s.evidence.length} sources reviewed<br>${s.summary.delivered ?? 'No'} kits field-reported · ${usd(s.summary.reported)} reported spending<br>Unique households: <b>${s.summary.households ?? 'not established'}</b></div>${issueList(r)}<button class="button full" data-action="approve">Approve version ${r.version} and deliver <span>↗</span></button>${ackBox(r)}`; }
  else { content = `<h2>Getting the story together.</h2><p>Your sources are saved. BasketBrief will prepare the next report version.</p><button class="button secondary" data-action="retry">Start the review</button>`; }
  const rail = stages.map((label,i)=>`<span class="stage ${i===stageIndex?'now':i<stageIndex?'done':''}">${label}</span>`).join('');
  return `<section class="panel next-step" aria-label="What happens next"><div class="step-label"><span class="eyebrow">WHAT NEEDS YOU</span></div>${content}<div class="stage-rail" aria-hidden="true">${rail}</div></section>`;
}

function issueList(r) {
  const issues = (r.payload && r.payload.issues) || [];
  if (!issues.length) return '';
  return `<ul class="issue-list">${issues.map(i=>`<li>${esc(i.note)}</li>`).join('')}</ul>`;
}

function ackBox(r) {
  const issues = (r.payload && r.payload.issues) || [];
  const incomplete = Number(r.payload.summary.unsupported) > 0 || issues.length;
  if (!incomplete) return '<div class="step-foot">Nothing unresolved. This version is complete.</div>';
  return `<label class="ack"><input type="checkbox" id="acknowledge"> I have read the unresolved items above and still want to share this version.</label>`;
}
function donors(s) { const delivered=s.report?.status==='delivered'; return `<section class="donors" id="reports"><div class="section-line"><h2 class="section-title">Two reports. One effort.</h2></div>${[['donor_a','✳','Northstar Foundation','English · Financial & delivery brief'],['donor_b','◌','Community Giving Circle','العربية · ملخص التوزيع والإنفاق']].map(([r,icon,name,desc])=>`<article class="donor-card"><div class="donor-mark ${r==='donor_b'?'blue':''}" aria-hidden="true">${icon}</div><div><h3>${name}</h3><p>${desc}</p>${delivered?`<button class="text-button" data-role="${r}">Open delivered report ↗</button>`:''}</div><span class="badge ${delivered?'':'neutral'}">${delivered?'✓ Delivered':'Draft'}</span></article>`).join('')}<p class="form-hint">Same approved evidence. Two languages. No invented impact claims.</p></section>`; }
function trace(s) { return `<details class="trace" id="trace"><summary><span>Behind the brief · ${s.events.length} recent recorded steps</span><span>${s.project.engine==='bedrock'?'Strands + Amazon Bedrock':'Local test parser · No AI'}</span></summary><div class="trace-list">${s.events.map(e=>`<div class="trace-event"><time>${new Date(e.created*1000).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}</time><div><span class="trace-kind">${esc(e.kind)}</span>${esc(e.title)}<p>${esc(e.detail.reason || e.detail.text || (e.kind==='complete'?JSON.stringify(e.detail):e.detail.hash?'Snapshot '+e.detail.hash.slice(0,18)+'…':e.detail.receipt||''))}</p></div></div>`).join('')}</div></details>`; }
function coordinator(s) {
  return statusStrip(s) + `<div class="bench">
      <section class="panel" id="sources"><div class="panel-head"><h2>Evidence.</h2><span class="count">${s.evidence.length} sources</span></div>${sourceCards(s.evidence)}<p class="panel-foot">Every figure links back to the source that stated it. A reported delivery is not independent proof of impact.</p></section>
      ${liveTimeline(s)}
      <div class="bench-right">${nextStep(s)}${donors(s)}</div>
    </div>` + statusBar(s) + ownReceipt();
}
function contributor(s) {
 const finance=role==='finance', questions=s.questions.filter(q=>q.status==='open');
 return hero(finance?'SUPPLIES INBOX · RANA':'DELIVERY INBOX · SAMI',finance?'A little evidence.<br><em>A big difference.</em>':'Your side of<br><em>the story.</em>',finance?'Answer here once. BasketBrief will carry the evidence into both donor reports.':'Share what happened on the ground. Corrections update the figures and require a fresh coordinator approval.')+
 `<div class="contributor-layout"><div>${questions.map(q=>`<section class="contributor-question"><span class="eyebrow">BASKETBRIEF ASKED YOU</span><h3>One answer, two reports.</h3><p>${esc(q.text)}</p><span class="badge amber">Awaiting your reply</span></section>`).join('')}<section class="panel contributor-form" id="sources"><h2>${questions.length?'Reply with the evidence.':'Add an update.'}</h2><form id="evidence-form"><label for="evidence-kind">What are you sharing?</label><select id="evidence-kind" name="kind">${finance?'<option value="receipt">Receipt transcript</option><option value="message">Message / evidence unavailable</option><option value="expense_claim">Expense without a receipt</option>':'<option value="correction">Correction to the figures</option><option value="message">Field update</option>'}</select><label for="evidence-text">${finance?'Receipt text or reply':'What changed?'}</label><textarea id="evidence-text" name="text" placeholder="${finance?'Paste the receipt text, or explain what is still missing.':'For example: Correction: 100 loaded, 90 delivered, 10 returned.'}" required maxlength="10000"></textarea><div class="form-actions"><button class="button" type="submit">Send ${questions.length?'reply':'evidence'} <span>↗</span></button><span class="form-hint">Saved to this workspace</span></div></form>${finance?'<form id="upload-form"><label class="upload-label" for="receipt-image"><span class="upload-copy">Or upload a photo of the receipt</span><input id="receipt-image" type="file" accept="image/png,image/jpeg" required><span class="upload-cta">Choose image</span><span class="upload-name" id="receipt-name">No file chosen</span></label><button class="button secondary" type="submit">Upload & read receipt ↗</button><p class="form-hint">PNG / JPEG · Under 2 MB. AI transcription requires the live Bedrock engine.</p></form>':''}<div class="sample"><p>TRY THE FICTIONAL SCENARIO · inserts editable sample text</p>${finance?'<button type="button" data-sample="receipt">Use transport receipt</button><button type="button" data-sample="missing">Receipt cannot be found</button>':'<button type="button" data-sample="correction">Correct to 88 delivered</button><button type="button" data-sample="resolution">Confirm 12 returned</button>'}</div></section></div><section class="panel"><div class="panel-head"><h2>Your evidence.</h2><span class="count">${s.evidence.length} sources</span></div>${sourceCards(s.evidence)}<div class="evidence-note">Only your own evidence is visible in this role. The coordinator reviews the full report.</div></section></div>`;
}
function changeTable(payload, ar=false) {
  const changes = Object.entries(payload?.changes || {});
  if (!payload?.amends || !changes.length) return '';
  const labels = ar ? {delivered:'الطرود المسلّمة',returned:'الطرود المرتجعة',loaded:'الطرود المحمّلة',households:'الأسر',reported:'الإنفاق المبلّغ',supported:'إنفاق بإيصالات',unsupported:'إنفاق بلا إيصال'} : {delivered:'Delivered kits',returned:'Returned kits',loaded:'Loaded kits',households:'Households',reported:'Reported spending',supported:'Receipt-supported',unsupported:'Without receipt'};
  return `<section class="changes" aria-label="${ar?'التغييرات':'Changes since the delivered report'}"><div class="eyebrow">${ar?'تعديل على النسخة':'AMENDMENT TO VERSION'} ${payload.amends.version}</div><table class="report-table"><thead><tr><th>${ar?'البند':'What changed'}</th><th>${ar?'السابق':'Before'}</th><th>${ar?'الجديد':'Now'}</th></tr></thead><tbody>${changes.map(([k,v])=>`<tr><th scope="row">${esc(labels[k]||k)}</th><td>${esc(v.before??(ar?'غير معروف':'Unknown'))}</td><td><strong>${esc(v.after??(ar?'غير معروف':'Unknown'))}</strong></td></tr>`).join('')}</tbody></table></section>`;
}

function reportTable(s, ar=false) { const rows=ar?[['الطرود المسلّمة حسب الفريق',s.delivered??'غير معروف'],['الطرود المرتجعة',s.returned??'غير معروف'],['الأسر الفريدة',s.households??'غير معروف'],['الإنفاق المبلّغ عنه',usd(s.reported)],['الإنفاق المدعوم بإيصالات',usd(s.supported)],['إنفاق بلا إيصال',usd(s.unsupported)]]:[['Kits delivered · field-reported',s.delivered??'Not established'],['Kits returned',s.returned??'Not established'],['Unique households',s.households??'Not established'],['Reported spending',usd(s.reported)],['Receipt-supported spending',usd(s.supported)],['Spending without a receipt',usd(s.unsupported)]]; return '<table class="report-table">'+rows.map(([k,v])=>`<tr><th scope="row">${k}</th><td>${esc(v)}</td></tr>`).join('')+'</table>'; }
function amendmentNote(s, ar) {
  // Named in the donor's own language, and only ever about the existence of a
  // newer version — never its figures, which no human has approved yet.
  if (!s.amendment) return '';
  const {pending, held} = s.amendment;
  return `<div class="amend-note" ${ar?'lang="ar" dir="rtl"':''}>${ar
    ? `وصل تصحيح بعد إرسال النسخة ${held}. النسخة ${pending} بانتظار موافقة المنسّقة، وما تقرأه هنا هو ما أُرسل إليك بالضبط.`
    : `A correction arrived after version ${held} was sent to you. Version ${pending} is with the coordinator for approval — what you are reading is exactly what was delivered.`}</div>`;
}
function donor(s) { const reports=s.inbox.filter(i=>i.kind==='report'), ar=role==='donor_b'; return hero('DONOR INBOX · '+esc(names[role]),'The work.<br><em>With the evidence.</em>','Approved snapshots from the first week of flood relief. Each version stays as it was shared.',false)+amendmentNote(s,ar)+`<section id="reports">${reports.length?reports.map(i=>`<article class="panel inbox-card" ${ar?'lang="ar" dir="rtl"':''}><span class="badge">✓ ${ar?'نسخة معتمدة':'Approved snapshot'} · v${i.body.version}</span><h2>${ar?'تقرير إغاثة الفيضان — الأسبوع الأول':'Flood relief distribution — week one'}</h2>${changeTable(i.body,ar)}${reportTable(i.body.summary,ar)}${i.body.issues.length?`<div class="issues">${i.body.issues.map(esc).join('<br>')}</div>`:''}<p class="report-disclosure">${ar?'سيناريو تجريبي ببيانات مصطنعة. أعداد التسليم من إفادة الفريق وليست تحققًا مستقلًا. الإيصال ليس إثباتًا للأثر.':esc(i.body.disclosure)}</p><button class="button secondary" data-export="${i.body.report_id}">${ar?'تنزيل التقرير':'Download report'} ↓</button><p class="receipt-id" dir="ltr">Native inbox receipt: ${esc(i.delivery_key)}<br>SHA-256 ${esc(i.body.hash)}</p></article>`).join(''):'<div class="panel empty-state"><div class="small-star" aria-hidden="true">✳</div><h2>Good things take a little follow-through.</h2><p>No report has been shared yet. The coordinator must review and approve a version before it appears here.</p><button class="button secondary" data-role="coordinator">Back to Amal’s workspace →</button></div>'}</section>`; }
function render(s) {
 const active=document.activeElement, saved={};
 $('#content').querySelectorAll('textarea,select,input[type="checkbox"]').forEach(el=>saved[el.id]={value:el.value,checked:el.checked});
 const focusId=active?.id, selection=active?.selectionStart, traceOpen=$('#trace')?.open;
 $('#content').innerHTML=role==='coordinator'?coordinator(s):role.startsWith('donor')?donor(s):contributor(s);
 for(const [id,v] of Object.entries(saved)) { const el=document.getElementById(id); if(el){el.value=v.value;el.checked=v.checked;} }
 if(traceOpen && $('#trace')) $('#trace').open=true;
 const live=$('#live-list'); if(live) live.scrollTop=live.scrollHeight;
 if(focusId && document.getElementById(focusId)){const el=document.getElementById(focusId);el.focus({preventScroll:true});if(typeof el.setSelectionRange==='function'&&selection!=null)el.setSelectionRange(selection,selection);}
}
async function refresh(force=false) {
 if(!workspace || polling) return; polling=true; const epoch=requestEpoch;
 try { const s=await api(); if(epoch!==requestEpoch)return;state=s; const key=JSON.stringify(s); if(force || key!==previous){render(s);previous=key;} }
 catch(e){toast(e.message);} finally{polling=false;}
}
function storyButton() {
  return `<button class="button story-button" data-action="play-story">Play the whole story <span>▶</span></button>`;
}
async function switchRole(next) { role=next; $('#role').value=role; previous='';requestEpoch++; $('#content').innerHTML='<div class="loading"><span class="spinner"></span><p>Opening '+esc(names[role])+'’s workspace…</p></div>'; while(polling) await new Promise(r=>setTimeout(r,50)); await refresh(true); }
async function start(fresh=false) {
 try { if(!fresh){try{workspace=JSON.parse(sessionStorage.getItem('basketbrief.workspace'));}catch{workspace=null;}}
 if(!workspace || fresh){const r=await fetch('/api/projects',{method:'POST'});const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not create workspace.');workspace=data;sessionStorage.setItem('basketbrief.workspace',JSON.stringify(data));}
 $('#engine-label').textContent=workspace.engine==='bedrock'?'Live agent · Strands + Bedrock':'Local test parser · No AI';
 await switchRole('coordinator');
 }catch(e){$('#content').innerHTML='<div class="loading"><h1>The workspace could not open.</h1><p>'+esc(e.message)+'</p><button class="button" data-action="start">Try again</button></div>';}
}
async function showSource(id) {
 const index=state.evidence.findIndex(e=>e.id===Number(id));if(index<0)return;
 const e=state.evidence[index];
 $('#source-content').innerHTML=`<h2>${esc(title(e))}</h2><p class="form-hint">${esc(names[e.actor])} · Source ${index+1} · ${esc(e.note||e.status)}</p><pre>${esc(e.text)}</pre>`;
 $('#source-dialog').showModal();
 if(e.attachment){try{const r=await api('/evidence/'+e.id+'/image',{raw:true});const url=URL.createObjectURL(await r.blob());const img=document.createElement('img');img.alt='Original uploaded receipt';img.src=url;img.onload=()=>URL.revokeObjectURL(url);$('#source-content').append(img);}catch(err){toast(err.message);}}
}
$('#role').addEventListener('change',e=>switchRole(e.target.value));
document.addEventListener('change',e=>{if(e.target.id==='own-file'&&e.target.files[0]){readOwn(e.target.files[0]);return;}
 if(e.target.id==='receipt-image'){const n=document.getElementById('receipt-name');if(n)n.textContent=e.target.files[0]?e.target.files[0].name.slice(0,42):'No file chosen';}});
$('#new-workspace').addEventListener('click',()=>{requestEpoch++;workspace=null;start(true);});
$('#close-dialog').addEventListener('click',()=>$('#source-dialog').close());
$('#source-dialog').addEventListener('click',e=>{if(e.target===$('#source-dialog'))$('#source-dialog').close();});
document.addEventListener('click', async e=>{
 const b=e.target.closest('button');if(!b)return;
 try {
 if(b.dataset.role){await switchRole(b.dataset.role);return;}
 if(b.dataset.source){await showSource(b.dataset.source);return;}
 if(b.dataset.sample){const samples={receipt:['receipt','TRUCK HIRE RECEIPT TR-204. Vehicle rental for the flood relief run. Total USD 60.00. Paid. Synthetic receipt.'],missing:['message','I cannot find the transport receipt. Keep the USD 60 expense reported but unsupported.'],correction:['correction','Correction: 88 kits were delivered, not 92.'],resolution:['correction','Storage recount complete. Returned kits: 12.']};const [kind,text]=samples[b.dataset.sample];$('#evidence-kind').value=kind;$('#evidence-text').value=text;$('#evidence-text').focus();return;}
 if(b.dataset.export){b.disabled=true;const response=await api('/reports/'+b.dataset.export,{raw:true});const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='BasketBrief-report-'+b.dataset.export+(role==='donor_b'?'-ar':'')+'.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);return;}
 if(b.dataset.action==='own-reset'){ownReading=null;if(ownPreview)URL.revokeObjectURL(ownPreview);ownPreview=null;render(state);return;}
 if(b.dataset.action==='play-story'){playStory();return;}
 if(b.dataset.action==='stop-story'){storyAbort=true;return;}
 if(b.dataset.action==='try-your-own'){$('#story-caption').classList.remove('show');await switchRole('finance');return;}
 if(b.dataset.action==='start'){await start(true);return;}
 if(b.dataset.action==='retry'){b.disabled=true;await api('/retry',{method:'POST'});toast('The review is queued. Your evidence is saved.');await refresh(true);}
 if(b.dataset.action==='approve'){b.disabled=true;const report=state.report;await api('/approve',{method:'POST',body:JSON.stringify({report_id:report.id,hash:report.hash,acknowledge:$('#acknowledge')?.checked||false})});toast('Approved version '+report.version+' delivered to both donor inboxes.');await refresh(true);}
 }catch(err){toast(err.message);}finally{b.disabled=false;}
});
document.addEventListener('submit',async e=>{
 if(!['evidence-form','upload-form'].includes(e.target.id))return;e.preventDefault();const button=e.target.querySelector('button[type="submit"]');button.disabled=true;
 try {const q=state.questions.find(q=>q.status==='open');let result;
 if(e.target.id==='upload-form'){const file=$('#receipt-image').files[0];if(!file)throw new Error('Choose a receipt image.');const body=new FormData();body.append('file',file);if(q)body.append('question_id',q.id);result=await api('/upload',{method:'POST',body});e.target.reset();}
 else{result=await api('/evidence',{method:'POST',body:JSON.stringify({text:$('#evidence-text').value,kind:$('#evidence-kind').value,question_id:q?.id??null})});$('#evidence-text').value='';}
 toast(result.duplicate?'This source was already saved. No duplicate was added.':'Evidence saved. BasketBrief is reviewing the update.');await refresh(true);
 }catch(err){toast(err.message);}finally{button.disabled=false;}
});
start();setInterval(()=>{if(!document.hidden)refresh();},1600);
