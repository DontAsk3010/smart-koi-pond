# ruff: noqa: E501

INCIDENT_RECOVERY_STORY_STYLE = r"""
<style id="incident-recovery-story-style">
.inc-story{display:grid;gap:9px;margin-top:10px}.inc-head{display:grid;grid-template-columns:repeat(4,minmax(140px,1fr));gap:8px}.inc-head .asset{min-height:68px}.inc-stage-grid{display:grid;grid-template-columns:repeat(4,minmax(155px,1fr));gap:8px}.inc-stage{border:1px solid var(--line);border-radius:8px;padding:9px;background:#0a1725;min-height:104px}.inc-stage.hit{border-color:#557ec7}.inc-stage.bad{border-color:#74373d}.inc-stage.good{border-color:#2f7656}.inc-stage .stage-title{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-weight:800}.inc-stage .stage-code{font-weight:750;margin:4px 0}.inc-stage .stage-detail{font-size:11px;color:var(--muted);word-break:break-word}.inc-seq{font-size:11px;color:#a8d0ff}.inc-readonly{border-left:3px solid #557ec7;padding:7px 9px;background:#0b1d30}.inc-future{border-left-color:#8a6726}.inc-evidence-table{max-height:340px;overflow:auto}.inc-evidence-table table{font-size:12px}@media(max-width:1000px){.inc-stage-grid,.inc-head{grid-template-columns:repeat(2,minmax(140px,1fr))}}@media(max-width:560px){.inc-stage-grid,.inc-head{grid-template-columns:1fr}}
</style>
"""

INCIDENT_RECOVERY_STORY_SCRIPT = r"""
(function(){
  const STAGES=[
    ['detect','1 · Trigger / Detect'],
    ['classify','2 · Classify / Alarm'],
    ['act','3 · Command / Fallback'],
    ['feedback','4 · Device Feedback'],
    ['verify','5 · Process Verification'],
    ['recover','6 · Recovery / Reconcile'],
    ['escalate','7 · Escalate / Lockout'],
    ['resolve','8 · Resolve']
  ];
  function stamp(v){const n=Date.parse(v);return Number.isFinite(n)?n:null}
  function incidentFromSnapshot(id){return(displayed?.incidents||[]).find(i=>i.incident_id===id)||null}
  function eventStage(ev){
    const type=String(ev?.event_type||'').toUpperCase(),code=String(ev?.code||'').toUpperCase();
    if(code==='INCIDENT_RESOLVED'||code.includes('ALARM_RESOLVED'))return'resolve';
    if(code.includes('LOCKOUT')||code.includes('ABORT')||code.includes('ESCALAT')||code.includes('FAILED_RESPONSE')||code.includes('INSUFFICIENT_EVIDENCE'))return'escalate';
    if(type==='VERIFICATION'||code.includes('VERIF'))return'verify';
    if(type==='RECOVERY'||code.includes('RECOVER')||code.includes('RECONCIL'))return'recover';
    if(type==='FEEDBACK'||code.includes('FEEDBACK'))return'feedback';
    if(type==='COMMAND'||code.includes('COMMAND')||code.includes('BACKUP')||code.includes('FALLBACK'))return'act';
    if(type==='ALARM'||code.includes('ALARM')||type==='STATE'||code.includes('CLASSIF'))return'classify';
    if(type==='INCIDENT'||type==='SENSOR_QUALITY'||type==='SCENARIO'||code.includes('FAULT')||code.includes('DETECT')||code.includes('TRIGGER'))return'detect';
    return null;
  }
  function eventTone(ev){const code=String(ev?.code||'').toUpperCase();if(code.includes('FAIL')||code.includes('LOCKOUT')||code.includes('ABORT')||code.includes('ESCALAT'))return'bad';if(code.includes('SUCCESS')||code.includes('RESOLVED')||code.includes('RECOVERED')||code.includes('COMPLETE'))return'good';return'hit'}
  function pointInTimeEvidence(events,incident){
    const start=Number(incident?.start_event_sequence);const end=incident?.end_event_sequence===null||incident?.end_event_sequence===undefined?null:Number(incident.end_event_sequence);const cutoff=playbackMode&&displayed?.timestamp?stamp(displayed.timestamp):null;
    return(events||[]).filter(ev=>{const seq=Number(ev.sequence),time=stamp(ev.timestamp);if(Number.isFinite(start)&&seq<start)return false;if(Number.isFinite(end)&&seq>end)return false;if(cutoff!==null&&time!==null&&time>cutoff)return false;return true}).sort((a,b)=>Number(a.sequence)-Number(b.sequence));
  }
  function latestByStage(events){const result={};events.forEach(ev=>{const stage=eventStage(ev);if(stage)result[stage]=ev});return result}
  function verificationSummary(){
    const tasks=displayed?.verification||[];if(!tasks.length)return'NO VERIFICATION TASK EVIDENCE';const counts={};tasks.forEach(v=>{const k=String(v.status||'UNKNOWN');counts[k]=(counts[k]||0)+1});return Object.entries(counts).map(([k,v])=>`${k}: ${v}`).join(' · ')
  }
  function install(){const box=document.getElementById('incidentEvidence');if(!box||document.getElementById('incidentStory'))return;box.style.display='none';const story=document.createElement('div');story.id='incidentStory';story.className='inc-story';box.insertAdjacentElement('afterend',story)}
  function renderEmpty(message='Select an incident to view causal evidence.') {install();const story=document.getElementById('incidentStory');if(story)story.innerHTML=`<div class="inc-readonly">${escapeHtml(message)}</div>`}
  function renderStory(id,rawEvents){
    install();const incident=incidentFromSnapshot(id),story=document.getElementById('incidentStory');if(!story)return;if(!incident){renderEmpty('Incident is not present in the displayed canonical snapshot.');return}
    const events=pointInTimeEvidence(rawEvents,incident),stages=latestByStage(events),futureFiltered=playbackMode&&(rawEvents||[]).length>events.length;
    const resolvedAtPoint=incident.lifecycle==='RESOLVED'&&!!stages.resolve;const escalated=events.some(ev=>eventStage(ev)==='escalate');
    let html=`<div class="inc-readonly${futureFiltered?' inc-future':''}"><b>${playbackMode?'PLAYBACK / READ ONLY':'LIVE / READ ONLY'}</b> · Story uses only canonical incident boundaries and ordered events${futureFiltered?' · future evidence after the selected playback timestamp is hidden':''}. Command/feedback alone never proves recovery.</div>`;
    html+=`<div class="inc-head"><div class="asset"><div class="label">Incident</div><b>${escapeHtml(incident.incident_id)}</b><div class="muted">${escapeHtml(incident.trigger_code||'UNKNOWN TRIGGER')}</div></div><div class="asset"><div class="label">Lifecycle at displayed point</div><b>${escapeHtml(incident.lifecycle||'UNKNOWN')}</b><div class="muted">${resolvedAtPoint?'Resolution event present':(escalated?'Escalation/lockout evidence present':'No resolution claim')}</div></div><div class="asset"><div class="label">Evidence range</div><b>#${escapeHtml(incident.start_event_sequence??'—')} → #${escapeHtml(incident.end_event_sequence??'OPEN')}</b><div class="muted">${events.length} visible ordered events</div></div><div class="asset"><div class="label">Verification at displayed point</div><b>${escapeHtml(verificationSummary())}</b></div></div>`;
    html+='<div class="inc-stage-grid">';STAGES.forEach(([key,title])=>{const ev=stages[key];const tone=ev?eventTone(ev):'';html+=`<div class="inc-stage ${tone}"><div class="stage-title">${title}</div>${ev?`<div class="stage-code">${escapeHtml(ev.code)}</div><div class="inc-seq">#${escapeHtml(ev.sequence)} · ${escapeHtml(ev.timestamp)}</div><div class="stage-detail">${escapeHtml(JSON.stringify(ev.payload||{}))}</div>`:'<div class="stage-code muted">NO EVIDENCE AT THIS POINT</div><div class="stage-detail">No stage outcome is inferred.</div>'}</div>`});html+='</div>';
    if(!events.length){html+='<div class="muted">No incident evidence is visible at this point in time.</div>'}else{const rows=events.map(ev=>`<tr><td>${escapeHtml(ev.sequence)}</td><td>${escapeHtml(ev.timestamp)}</td><td>${escapeHtml(ev.event_type)}</td><td>${escapeHtml(ev.code)}</td><td>${escapeHtml(JSON.stringify(ev.payload||{}))}</td></tr>`).join('');html+=`<div class="inc-evidence-table"><table><thead><tr><th>Seq</th><th>Time</th><th>Type</th><th>Code</th><th>Evidence</th></tr></thead><tbody>${rows}</tbody></table></div>`}story.innerHTML=html;
  }
  window.loadIncident=async function(id){try{const r=await fetch(`/api/incident?id=${encodeURIComponent(id)}`,{cache:'no-store'}),j=await r.json();if(!r.ok)throw new Error(j.error||'incident lookup failed');renderStory(id,j.events||[])}catch(e){renderEmpty(e.message)}};
  const baseRenderIncidents=window.renderIncidents;window.renderIncidents=function(s){if(typeof baseRenderIncidents==='function')baseRenderIncidents(s);install();if(!(s?.incidents||[]).length)renderEmpty('No incident records in the displayed canonical snapshot.')};
  install();renderEmpty();
})();
"""
