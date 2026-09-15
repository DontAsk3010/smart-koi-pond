# ruff: noqa: E501

EQUIPMENT_DETAIL_STYLE = r"""
<style id="equipment-detail-style">
.clickable-asset{cursor:pointer;transition:border-color .15s ease,transform .15s ease}.clickable-asset:hover,.clickable-asset:focus{border-color:#4c86b8;outline:none}.clickable-asset:focus{box-shadow:0 0 0 2px rgba(76,134,184,.25)}
.eqd-card{display:none;margin-top:10px}.eqd-card.open{display:block}.eqd-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}.eqd-title{font-size:20px;font-weight:800}.eqd-source{font-size:11px;color:var(--muted);text-align:right}.eqd-grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px;margin-top:10px}.eqd-cell{border:1px solid var(--line);background:#0a1725;border-radius:8px;padding:9px;min-height:86px}.eqd-cell b{display:block;margin-bottom:4px}.eqd-cell.bad{border-color:#74373d}.eqd-cell.warn{border-color:#8a6726}.eqd-cell.good{border-color:#2f7656}.eqd-detail{font-size:12px;color:#c7d5df;word-break:break-word}.eqd-events{margin-top:10px;border-top:1px solid var(--line);padding-top:8px}.eqd-event{padding:7px 0;border-bottom:1px solid rgba(32,54,77,.65);font-size:12px}.eqd-event:last-child{border-bottom:0}.eqd-none{color:var(--muted);font-style:italic}.eqd-close{background:#10253a;color:var(--text);border:1px solid var(--line);border-radius:7px;padding:6px 9px;cursor:pointer}
@media(max-width:900px){.eqd-grid{grid-template-columns:repeat(2,minmax(150px,1fr))}}@media(max-width:520px){.eqd-grid{grid-template-columns:1fr}}
</style>
"""

EQUIPMENT_DETAIL_SCRIPT = r"""
(function(){
  let selectedAssetId=null;
  const safe=(v)=>String(v===null||v===undefined?'UNAVAILABLE':v).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const bool=(v)=>v===true?'YES':(v===false?'NO':'UNAVAILABLE');
  const percent=(v)=>{if(v===null||v===undefined||v==='')return'UNAVAILABLE';const n=Number(v);return Number.isFinite(n)?`${Math.round(Math.max(0,Math.min(1,n))*100)}%`:'UNAVAILABLE'};
  function install(){
    const process=document.getElementById('process');if(!process||document.getElementById('equipmentDetailCard'))return;
    const card=document.createElement('div');card.id='equipmentDetailCard';card.className='card eqd-card';card.innerHTML=`
      <div class="eqd-head"><div><div class="label">Equipment / Process Drill-Down</div><div id="eqdTitle" class="eqd-title">—</div></div><div><button id="eqdClose" class="eqd-close" type="button">Close</button><div id="eqdSource" class="eqd-source">—</div></div></div>
      <div class="eqd-grid">
        <div id="eqdAsset" class="eqd-cell"><b>Asset State</b><div class="eqd-detail">—</div></div>
        <div id="eqdCommand" class="eqd-cell"><b>Requested / Final Command</b><div class="eqd-detail">—</div></div>
        <div id="eqdFeedback" class="eqd-cell"><b>Device Feedback / Effect</b><div class="eqd-detail">—</div></div>
        <div id="eqdVerification" class="eqd-cell"><b>Verification</b><div class="eqd-detail">—</div></div>
        <div id="eqdDependencies" class="eqd-cell"><b>Module / Dependencies</b><div class="eqd-detail">—</div></div>
        <div id="eqdOperating" class="eqd-cell"><b>Operating Context</b><div class="eqd-detail">—</div></div>
        <div id="eqdAuthority" class="eqd-cell"><b>Source / Authority</b><div class="eqd-detail">—</div></div>
        <div id="eqdEvidence" class="eqd-cell"><b>Diagnostic Evidence</b><div class="eqd-detail">—</div></div>
      </div><div class="eqd-events"><b>Recent matching events from loaded canonical event stream</b><div id="eqdEvents"></div></div>`;
    process.appendChild(card);
    document.getElementById('eqdClose').onclick=()=>{selectedAssetId=null;card.classList.remove('open')};
    decorate();
  }
  function decorate(){
    document.querySelectorAll('#process [data-asset]').forEach(n=>{n.classList.add('clickable-asset');n.tabIndex=0;n.setAttribute('role','button');n.setAttribute('aria-label',`Open ${n.dataset.asset} equipment detail`)});
    const mappings={chipMain:'main_pump',chipBackup:'backup_pump',chipAeration:'primary_aerator',chipWater:'top_up_valve'};
    Object.entries(mappings).forEach(([id,asset])=>{const n=document.getElementById(id);if(n){n.dataset.asset=asset;n.classList.add('clickable-asset');n.tabIndex=0;n.setAttribute('role','button');n.setAttribute('aria-label',`Open ${asset} equipment detail`)}});
  }
  function matchingModules(s,id){
    const modules=s?.capability?.registry?.modules||{};return Object.entries(modules).filter(([,m])=>Array.isArray(m.asset_ids)&&m.asset_ids.includes(id));
  }
  function matchingVerification(s,id){return (s?.verification||[]).filter(v=>v.asset_id===id)}
  function eventMatchesAsset(ev,id){
    const p=ev?.payload||{};if(p.asset_id===id||p.device_id===id)return true;
    for(const key of ['asset_ids','affected_assets','scope','service_scope']){if(Array.isArray(p[key])&&p[key].includes(id))return true}
    return false;
  }
  function matchingEvents(s,id){
    if(typeof eventBuffer==='undefined'||!Array.isArray(eventBuffer))return[];
    const cutoff=(typeof playbackMode!=='undefined'&&playbackMode&&s?.timestamp)?Date.parse(s.timestamp):null;
    return eventBuffer.filter(ev=>eventMatchesAsset(ev,id)&&(cutoff===null||!Number.isFinite(cutoff)||!ev.timestamp||Date.parse(ev.timestamp)<=cutoff)).slice(-8).reverse();
  }
  function cell(id,kind,html){const n=document.getElementById(id);if(!n)return;n.className=`eqd-cell ${kind||''}`;const d=n.querySelector('.eqd-detail');if(d)d.innerHTML=html}
  function assetKind(asset,feedback,verification){
    const availability=String(asset?.availability||feedback?.availability||'UNKNOWN');const failed=availability==='FAILED'||availability==='OFFLINE'||availability==='UNAVAILABLE'||verification.some(v=>v.status==='FAILED_RESPONSE');if(failed)return'bad';
    const degraded=availability==='DEGRADED'||availability==='PLANNED_OFF'||availability==='MAINTENANCE_UNAVAILABLE'||verification.some(v=>v.status==='INSUFFICIENT_EVIDENCE');return degraded?'warn':'good';
  }
  function render(s){
    install();decorate();if(!selectedAssetId||!s)return;
    const id=selectedAssetId,asset=s.assets?.[id]||null,command=s.commands?.[id]||null,feedback=s.feedback?.[id]||null,verification=matchingVerification(s,id),modules=matchingModules(s,id),events=matchingEvents(s,id),operating=s.operating_status||{};
    const card=document.getElementById('equipmentDetailCard');card.classList.add('open');document.getElementById('eqdTitle').textContent=id.replaceAll('_',' ').toUpperCase();document.getElementById('eqdSource').textContent=(typeof playbackMode!=='undefined'&&playbackMode)?`HISTORIAN / READ ONLY · ${s.timestamp||'timestamp unavailable'}`:`LIVE CANONICAL SNAPSHOT · ${s.timestamp||'timestamp unavailable'}`;
    const kind=assetKind(asset,feedback,verification);
    cell('eqdAsset',kind,asset?`owner <b>${safe(asset.owner)}</b><br>availability ${safe(asset.availability)}<br>feedback ON ${bool(asset.feedback_on)} · effectiveness ${percent(asset.effectiveness)}`:'ASSET STATE UNAVAILABLE IN SNAPSHOT');
    cell('eqdCommand',command?(command.accepted?'good':'warn'):'',command?`requested ${bool(command.requested_on)} → final ${bool(command.final_on)}<br>owner ${safe(command.owner)} · accepted ${bool(command.accepted)}<br>reason ${safe(command.reason)}`:'NO CURRENT COMMAND PUBLISHED FOR THIS SNAPSHOT');
    cell('eqdFeedback',feedback?(feedback.availability==='FAILED'?'bad':''):'',feedback?`commanded ${bool(feedback.commanded_on)} · feedback ${bool(feedback.feedback_on)}<br>availability ${safe(feedback.availability)} · effect ${percent(feedback.effectiveness)}<br>feedback time ${safe(feedback.timestamp)}`:'DEVICE FEEDBACK UNAVAILABLE');
    const verificationHtml=verification.length?verification.slice(-4).reverse().map(v=>`${safe(v.status)} · ${safe(v.parameter)}<br><span class="muted">baseline ${safe(v.baseline)} · observed ${safe(v.observed_value)} · due ${safe(v.due_at)}</span>`).join('<br>'):'NO VERIFICATION TASK PUBLISHED FOR THIS ASSET/SNAPSHOT';
    cell('eqdVerification',verification.some(v=>v.status==='FAILED_RESPONSE')?'bad':(verification.some(v=>v.status==='PENDING')?'warn':''),verificationHtml);
    const moduleHtml=modules.length?modules.map(([mid,m])=>`${safe(mid)} · ${safe(m.operational_state)}<br><span class="muted">capabilities ${(m.capabilities_provided||[]).map(safe).join(', ')||'UNAVAILABLE'}${(m.reasons||[]).length?` · reasons ${(m.reasons||[]).map(safe).join(', ')}`:''}</span>`).join('<br>'):'NO MODULE/DEPENDENCY MAPPING PUBLISHED FOR THIS ASSET';
    cell('eqdDependencies',modules.some(([,m])=>!['AVAILABLE','ACTIVE','READY'].includes(String(m.operational_state)))?'warn':'',moduleHtml);
    const scoped=Array.isArray(operating.scope)&&operating.scope.includes(id);cell('eqdOperating',scoped?'warn':'',`mode ${safe(s.operating_mode)} · phase ${safe(operating.phase)}<br>asset in declared operating scope ${bool(scoped)}<br>reason ${safe(operating.reason)}`);
    cell('eqdAuthority','',`source ${safe(feedback?.source_state||asset?.source_state)}<br>authority ${safe(feedback?.authority_state||asset?.authority_state)}<br>adapter ${safe(feedback?.adapter_id||asset?.adapter_id)} · device ${safe(feedback?.device_id||asset?.device_id)}`);
    const diagnostic=[];if(command)diagnostic.push(`command ${command.accepted?'accepted':'inhibited'}: ${command.reason}`);if(feedback&&command&&command.final_on!==feedback.feedback_on)diagnostic.push('COMMAND / FEEDBACK MISMATCH');verification.forEach(v=>diagnostic.push(`verification ${v.status}: ${v.parameter}`));modules.forEach(([,m])=>(m.reasons||[]).forEach(r=>diagnostic.push(`dependency ${r}`)));cell('eqdEvidence',diagnostic.some(x=>x.includes('FAILED')||x.includes('MISMATCH'))?'bad':'',diagnostic.length?diagnostic.map(safe).join('<br>'):'NO ADDITIONAL DIAGNOSTIC EVIDENCE IN CURRENT SNAPSHOT');
    const eventsNode=document.getElementById('eqdEvents');eventsNode.innerHTML=events.length?events.map(ev=>`<div class="eqd-event"><b>#${safe(ev.sequence)} · ${safe(ev.code)}</b><br><span class="muted">${safe(ev.timestamp)} · ${safe(ev.event_type)}</span></div>`).join(''):'<div class="eqd-none">NO MATCHING EVENT IN THE LOADED EVENT STREAM FOR THIS POINT IN TIME</div>';
  }
  function openAsset(id){if(!id)return;selectedAssetId=id;const processTab=document.querySelector('#tabs [data-view="process"]');if(processTab&&typeof showView==='function')showView('process');render(typeof displayed!=='undefined'?displayed:null);document.getElementById('equipmentDetailCard')?.scrollIntoView({behavior:'smooth',block:'nearest'})}
  document.addEventListener('click',ev=>{const target=ev.target.closest('#process [data-asset]');if(target){openAsset(target.dataset.asset);return}const overview=ev.target.closest('#overviewAssets .asset');if(overview){const name=overview.querySelector('.name')?.textContent?.trim();if(name)openAsset(name)}});
  document.addEventListener('keydown',ev=>{if(ev.key!=='Enter'&&ev.key!==' ')return;const target=ev.target.closest('#process [data-asset]');if(target){ev.preventDefault();openAsset(target.dataset.asset)}});
  install();
  const baseRenderSnapshot=window.renderSnapshot;
  if(typeof baseRenderSnapshot==='function'){window.renderSnapshot=function(snapshot,options){baseRenderSnapshot(snapshot,options);render(snapshot)}}
  window.openEquipmentDetail=openAsset;window.renderEquipmentDetail=render;
  if(typeof displayed!=='undefined'&&displayed)render(displayed);
})();
"""
