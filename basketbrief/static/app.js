'use strict';
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const usd = (v) => '$' + Number(v || 0).toLocaleString('en-US', {maximumFractionDigits:2});
const names = {coordinator:'Amal',finance:'Rana',field:'Sami',donor_a:'Northstar Foundation',donor_b:'Community Giving Circle'};
let workspace, role = 'coordinator', state, previous = '', polling = false, toastTimer, requestEpoch = 0;
function toast(message) { $('#toast').textContent = message; $('#toast').classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 5500); }
async function api(path = '', options = {}) {
  const headers = {...(options.body instanceof FormData ? {} : {'Content-Type':'application/json'}), Authorization:'Bearer ' + workspace.tokens[role], ...options.headers};
  const response = await fetch('/api/projects/' + workspace.id + path, {...options, headers});
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.error || (response.status === 422 ? 'Please check the evidence and try again.' : 'The request could not be completed.')); }
  return options.raw ? response : response.json();
}
function title(e) { if(e.kind === 'correction') return 'A correction from the field'; if(e.kind === 'receipt') return e.attachment ? 'Receipt image' : (/food/i.test(e.text) ? 'Food purchase receipt' : 'Transport receipt'); if(e.kind === 'expense_claim') return 'Transport expense'; return e.actor === 'field' ? 'Distribution update' : 'A reply from finance'; }
function sourceCards(evidence) {
  const ordinal = new Map(evidence.map((e, i) => [e.id, i + 1]));
  if (!evidence.length) return '<div class="empty-state"><p>Your evidence will appear here.</p></div>';
  return '<div class="evidence-list">' + evidence.map(e => `<article class="evidence-card"><div class="source-icon ${e.kind==='expense_claim'?'warning':''}" aria-hidden="true">${e.actor==='field'?'≋':'▤'}</div><div class="source-body"><div class="source-header"><h3>${esc(title(e))}</h3><span class="badge ${e.status==='review'?'amber':e.status==='pending'?'neutral':''}">${e.status==='accepted'?'✓ Linked':e.status==='pending'?'Reviewing':'Needs review'}</span></div><p class="source-meta">${esc(names[e.actor])} · Source ${ordinal.get(e.id) ?? e.id} · ${esc(e.kind.replace('_',' '))}</p><p class="source-excerpt">${esc(e.text)}</p><button class="text-button" data-source="${e.id}">View original source ↗</button></div></article>`).join('') + '</div>';
}
function storyline(s) {
  // Every word here is derived from live state. Nothing congratulates the team early.
  const open = s.questions.filter(q => q.status === 'open');
  const r = s.report, delivered = s.receipts.length, gap = Number(s.summary.unsupported || 0);
  const supersededBy = (r && r.status !== 'delivered' && delivered) ? r : null;
  if (s.busy) return {eyebrow:'SEPTEMBER DISTRIBUTION · REVIEW RUNNING', head:'Reading what<br><em>came in.</em>',
    body:'Every new source is being read, recorded against the figures, and reconciled into both donor drafts.', tone:'working'};
  if (s.jobs.find(j => j.status === 'failed')) return {eyebrow:'SEPTEMBER DISTRIBUTION · PAUSED', head:'The review<br><em>paused safely.</em>',
    body:'Nothing was lost. Your evidence is saved exactly as it arrived, and the review can be run again.', tone:'warn'};
  if (supersededBy) return {eyebrow:'SEPTEMBER DISTRIBUTION · CORRECTION ARRIVED', head:'A correction<br><em>changed the figures.</em>',
    body:`Version ${supersededBy.version - 1} is already with your donors. A later correction moved the numbers, so your old approval no longer applies — version ${supersededBy.version} is waiting for you.`, tone:'warn'};
  if (open.length) return {eyebrow:'SEPTEMBER DISTRIBUTION · ONE GAP', head:'One thing<br><em>is still missing.</em>',
    body:`BasketBrief asked ${esc(names[open[0].recipient])} for it directly, once. The answer will update both donor reports.`, tone:'warn'};
  if (r && r.status === 'delivered') return {eyebrow:'SEPTEMBER DISTRIBUTION · DELIVERED', head:'Accounted for.<br><em>And in their hands.</em>',
    body:`Version ${r.version} reached both donor inboxes. Your approval is bound to that exact version, and each delivery kept its own receipt.`, tone:'good'};
  if (r && r.status !== 'outdated') return {eyebrow:'SEPTEMBER DISTRIBUTION · READY FOR YOU', head:'The evidence<br><em>is in order.</em>',
    body: gap > 0 ? `Every source is recorded. ${usd(gap)} of reported spending still has no receipt, and the reports say so plainly.`
                  : 'Every source is recorded and every reported amount has a receipt behind it. Your approval sends this exact version.', tone:'ready'};
  return {eyebrow:'SEPTEMBER DISTRIBUTION · FIELD REPORT', head:'Let’s get the<br><em>story together.</em>',
    body:'Your sources are saved. BasketBrief will read them, chase what is missing, and draft both donor reports.', tone:'working'};
}
function art(s) {
  // The hero used to carry a clipart basket. It now carries the only thing worth
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
    ? cell('Baskets delivered','▧', skeleton ? '<span class="skeleton-bar"></span>' : 'Not yet reported', 'Waiting on the field team')
    : cell('Baskets delivered','▧', `${s.delivered}<small>of ${known(s.loaded) ?? '—'} loaded</small>`, `${known(s.returned) ?? '—'} returned · field-reported, not independently verified`);
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
    content = `<h2>Asked once.<br>Not asked again.</h2><p>BasketBrief went straight to ${esc(names[q.recipient])} — the person who has it — instead of routing it through you. One answer updates both donor reports.</p><div class="question-bubble"><div class="person"><span class="avatar">${esc(names[q.recipient][0])}</span>${esc(names[q.recipient])} · ${q.recipient==='finance'?'Finance':'Field team'}</div><p>${esc(q.text)}</p></div><button class="button secondary full" data-role="${q.recipient}">Answer as ${esc(names[q.recipient])} <span>↗</span></button>`; }
  else if (r && r.status !== 'delivered' && deliveredCount) { stageIndex = 2;
    content = `<h2>Your approval<br>no longer fits.</h2><p>A correction arrived after version ${r.version-1} was delivered. The figures moved, so the approval bound to the old version was refused and version ${r.version} is waiting.</p>${issueList(r)}<button class="button full" data-action="approve">Approve version ${r.version} and send the correction <span>↗</span></button>${ackBox(r)}`; }
  else if (r && r.status === 'delivered') { stageIndex = 3;
    content = `<h2>Accounted for.<br>And in the right hands.</h2><p>Version ${r.version} sits in both donor inboxes. Approval and delivery are recorded against this exact content hash.</p><button class="button full" data-role="donor_a">Open Northstar’s copy <span>↗</span></button><div class="step-foot">✓ ${deliveredCount} inbox deliveries · approved on version ${r.version}</div>`; }
  else if (r && r.status !== 'outdated') { stageIndex = 2;
    content = `<h2>Ready for your eyes.</h2><p>Approval shares this exact version with both donor inboxes, and binds your name to its content hash.</p><div class="question-bubble"><b>Version ${r.version}</b> · ${s.evidence.length} sources reviewed<br>${s.summary.delivered ?? 'No'} baskets field-reported · ${usd(s.summary.reported)} reported spending<br>Unique households: <b>${s.summary.households ?? 'not established'}</b></div>${issueList(r)}<button class="button full" data-action="approve">Approve version ${r.version} and deliver <span>↗</span></button>${ackBox(r)}`; }
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
  const st = storyline(s);
  return hero(st.eyebrow, st.head, st.body, s, st.tone) + metrics(s.summary, s.busy) + `<div class="workspace-grid"><section class="panel" id="sources"><div class="panel-head"><h2>The story, with sources.</h2><span class="count">${s.evidence.length} sources</span></div>${sourceCards(s.evidence)}<p class="panel-foot">Every figure links back to the source that stated it. A reported delivery is not independent proof of impact.</p></section>${nextStep(s)}</div>` + donors(s) + trace(s);
}
function contributor(s) {
 const finance=role==='finance', questions=s.questions.filter(q=>q.status==='open');
 return hero(finance?'FINANCE INBOX · RANA':'FIELD INBOX · SAMI',finance?'A little evidence.<br><em>A big difference.</em>':'Your side of<br><em>the story.</em>',finance?'Answer here once. BasketBrief will carry the evidence into both donor reports.':'Share what happened on the ground. Corrections update the figures and require a fresh coordinator approval.')+
 `<div class="contributor-layout"><div>${questions.map(q=>`<section class="contributor-question"><span class="eyebrow">BASKETBRIEF ASKED YOU</span><h3>One answer, two reports.</h3><p>${esc(q.text)}</p><span class="badge amber">Awaiting your reply</span></section>`).join('')}<section class="panel contributor-form" id="sources"><h2>${questions.length?'Reply with the evidence.':'Add an update.'}</h2><form id="evidence-form"><label for="evidence-kind">What are you sharing?</label><select id="evidence-kind" name="kind">${finance?'<option value="receipt">Receipt transcript</option><option value="message">Message / evidence unavailable</option><option value="expense_claim">Expense without a receipt</option>':'<option value="correction">Correction to the figures</option><option value="message">Field update</option>'}</select><label for="evidence-text">${finance?'Receipt text or reply':'What changed?'}</label><textarea id="evidence-text" name="text" placeholder="${finance?'Paste the receipt text, or explain what is still missing.':'For example: Correction: 100 loaded, 90 delivered, 10 returned.'}" required maxlength="10000"></textarea><div class="form-actions"><button class="button" type="submit">Send ${questions.length?'reply':'evidence'} <span>↗</span></button><span class="form-hint">Saved to this workspace</span></div></form>${finance?'<form id="upload-form"><label class="upload-label" for="receipt-image"><span class="upload-copy">Or upload a photo of the receipt</span><input id="receipt-image" type="file" accept="image/png,image/jpeg" required><span class="upload-cta">Choose image</span><span class="upload-name" id="receipt-name">No file chosen</span></label><button class="button secondary" type="submit">Upload & read receipt ↗</button><p class="form-hint">PNG / JPEG · Under 2 MB. AI transcription requires the live Bedrock engine.</p></form>':''}<div class="sample"><p>TRY THE FICTIONAL SCENARIO · inserts editable sample text</p>${finance?'<button type="button" data-sample="receipt">Use transport receipt</button><button type="button" data-sample="missing">Receipt cannot be found</button>':'<button type="button" data-sample="correction">Correct to 90 delivered</button>'}</div></section></div><section class="panel"><div class="panel-head"><h2>Your evidence.</h2><span class="count">${s.evidence.length} sources</span></div>${sourceCards(s.evidence)}<div class="evidence-note">Only your own evidence is visible in this role. The coordinator reviews the full report.</div></section></div>`;
}
function reportTable(s, ar=false) { const rows=ar?[['السلال المسلّمة حسب الفريق',s.delivered??'غير معروف'],['السلال المرتجعة',s.returned??'غير معروف'],['الأسر الفريدة',s.households??'غير معروف'],['الإنفاق المبلّغ عنه',usd(s.reported)],['الإنفاق المدعوم بإيصالات',usd(s.supported)],['إنفاق بلا إيصال',usd(s.unsupported)]]:[['Baskets delivered · field-reported',s.delivered??'Not established'],['Baskets returned',s.returned??'Not established'],['Unique households',s.households??'Not established'],['Reported spending',usd(s.reported)],['Receipt-supported spending',usd(s.supported)],['Spending without a receipt',usd(s.unsupported)]]; return '<table class="report-table">'+rows.map(([k,v])=>`<tr><th scope="row">${k}</th><td>${esc(v)}</td></tr>`).join('')+'</table>'; }
function donor(s) { const reports=s.inbox.filter(i=>i.kind==='report'), ar=role==='donor_b'; return hero('DONOR INBOX · '+esc(names[role]),'The work.<br><em>With the evidence.</em>','Approved snapshots from the September distribution. Each version stays as it was shared.',false)+`<section id="reports">${reports.length?reports.map(i=>`<article class="panel inbox-card" ${ar?'lang="ar" dir="rtl"':''}><span class="badge">✓ ${ar?'نسخة معتمدة':'Approved snapshot'} · v${i.body.version}</span><h2>${ar?'تقرير توزيع السلال الغذائية':'September food distribution'}</h2>${reportTable(i.body.summary,ar)}${i.body.issues.length?`<div class="issues">${i.body.issues.map(esc).join('<br>')}</div>`:''}<p class="report-disclosure">${ar?'سيناريو تجريبي ببيانات مصطنعة. أعداد التسليم من إفادة الفريق وليست تحققًا مستقلًا. الإيصال ليس إثباتًا للأثر.':esc(i.body.disclosure)}</p><button class="button secondary" data-export="${i.body.report_id}">${ar?'تنزيل التقرير':'Download report'} ↓</button><p class="receipt-id" dir="ltr">Native inbox receipt: ${esc(i.delivery_key)}<br>SHA-256 ${esc(i.body.hash)}</p></article>`).join(''):'<div class="panel empty-state"><div class="small-star" aria-hidden="true">✳</div><h2>Good things take a little follow-through.</h2><p>No report has been shared yet. The coordinator must review and approve a version before it appears here.</p><button class="button secondary" data-role="coordinator">Back to Amal’s workspace →</button></div>'}</section>`; }
function render(s) {
 const active=document.activeElement, saved={};
 $('#content').querySelectorAll('textarea,select,input[type="checkbox"]').forEach(el=>saved[el.id]={value:el.value,checked:el.checked});
 const focusId=active?.id, selection=active?.selectionStart, traceOpen=$('#trace')?.open;
 $('#content').innerHTML=role==='coordinator'?coordinator(s):role.startsWith('donor')?donor(s):contributor(s);
 for(const [id,v] of Object.entries(saved)) { const el=document.getElementById(id); if(el){el.value=v.value;el.checked=v.checked;} }
 if(traceOpen && $('#trace')) $('#trace').open=true;
 if(focusId && document.getElementById(focusId)){const el=document.getElementById(focusId);el.focus({preventScroll:true});if(typeof el.setSelectionRange==='function'&&selection!=null)el.setSelectionRange(selection,selection);}
}
async function refresh(force=false) {
 if(!workspace || polling) return; polling=true; const epoch=requestEpoch;
 try { const s=await api(); if(epoch!==requestEpoch)return;state=s; const key=JSON.stringify(s); if(force || key!==previous){render(s);previous=key;} }
 catch(e){toast(e.message);} finally{polling=false;}
}
async function switchRole(next) { role=next; $('#role').value=role; previous='';requestEpoch++; $('#content').innerHTML='<div class="loading"><span class="spinner"></span><p>Opening '+esc(names[role])+'’s workspace…</p></div>'; while(polling) await new Promise(r=>setTimeout(r,50)); await refresh(true); }
async function start(fresh=false) {
 try { if(!fresh){try{workspace=JSON.parse(sessionStorage.getItem('basketbrief.workspace'));}catch{workspace=null;}}
 if(!workspace || fresh){const r=await fetch('/api/projects',{method:'POST'});const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not create workspace.');workspace=data;sessionStorage.setItem('basketbrief.workspace',JSON.stringify(data));}
 $('#engine-label').textContent=workspace.engine==='bedrock'?'Live agent · Strands + Bedrock':'Local test parser · No AI';
 await switchRole('coordinator');
 }catch(e){$('#content').innerHTML='<div class="loading"><h1>The workspace could not open.</h1><p>'+esc(e.message)+'</p><button class="button" data-action="start">Try again</button></div>';}
}
async function showSource(id) {const e=state.evidence.find(e=>e.id===Number(id));if(!e)return;$('#source-content').innerHTML=`<h2>${esc(title(e))}</h2><p class="form-hint">${esc(names[e.actor])} · Source ${ordinal.get(e.id) ?? e.id} · ${esc(e.note||e.status)}</p><pre>${esc(e.text)}</pre>`;$('#source-dialog').showModal();if(e.attachment){try{const r=await api('/evidence/'+e.id+'/image',{raw:true});const url=URL.createObjectURL(await r.blob());const img=document.createElement('img');img.alt='Original uploaded receipt';img.src=url;img.onload=()=>URL.revokeObjectURL(url);$('#source-content').append(img);}catch(err){toast(err.message);}}}
$('#role').addEventListener('change',e=>switchRole(e.target.value));
document.addEventListener('change',e=>{if(e.target.id==='receipt-image'){const n=document.getElementById('receipt-name');if(n)n.textContent=e.target.files[0]?e.target.files[0].name.slice(0,42):'No file chosen';}});
$('#new-workspace').addEventListener('click',()=>{requestEpoch++;workspace=null;start(true);});
$('#close-dialog').addEventListener('click',()=>$('#source-dialog').close());
$('#source-dialog').addEventListener('click',e=>{if(e.target===$('#source-dialog'))$('#source-dialog').close();});
document.addEventListener('click', async e=>{
 const b=e.target.closest('button');if(!b)return;
 try {
 if(b.dataset.role){await switchRole(b.dataset.role);return;}
 if(b.dataset.source){await showSource(b.dataset.source);return;}
 if(b.dataset.sample){const samples={receipt:['receipt','TRANSPORT RECEIPT TR-204. Vehicle rental for September food distribution. Total USD 60.00. Paid. Synthetic receipt.'],missing:['message','I cannot find the transport receipt. Keep the USD 60 expense reported but unsupported.'],correction:['correction','Correction to our previous update: 100 baskets loaded, 90 baskets delivered, 10 returned to storage. Unique household count is still unknown.']};const [kind,text]=samples[b.dataset.sample];$('#evidence-kind').value=kind;$('#evidence-text').value=text;$('#evidence-text').focus();return;}
 if(b.dataset.export){b.disabled=true;const response=await api('/reports/'+b.dataset.export,{raw:true});const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download='BasketBrief-report-'+b.dataset.export+(role==='donor_b'?'-ar':'')+'.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);return;}
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
