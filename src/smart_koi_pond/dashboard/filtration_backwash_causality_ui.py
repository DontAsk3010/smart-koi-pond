# ruff: noqa: E501

FILTRATION_BACKWASH_CAUSALITY_STYLE = r"""
<style id="filtration-backwash-causality-style">
.fbc-card{margin-top:10px}.fbc-note{border-left:3px solid #557ec7;background:#0b1d30;padding:8px 10px;margin:8px 0}.fbc-chain{display:grid;grid-template-columns:repeat(6,minmax(155px,1fr));gap:8px;align-items:stretch}.fbc-stage{position:relative;border:1px solid var(--line);background:#0a1725;border-radius:9px;padding:10px;min-height:140px}.fbc-stage:not(:last-child):after{content:"→";position:absolute;right:-9px;top:48%;z-index:2;color:#6e91ae;font-weight:900;background:var(--panel);padding:0 2px}.fbc-title{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:800}.fbc-value{font-weight:800;margin:5px 0;word-break:break-word}.fbc-detail{font-size:11px;color:#b8cad7;word-break:break-word}.fbc-stage.good{border-color:#2f7656}.fbc-stage.warn{border-color:#8a6726}.fbc-stage.bad{border-color:#74373d}.fbc-stage.active{border-color:#7750a1;box-shadow:0 0 0 1px rgba(199,139,255,.16)}.fbc-footer{margin-top:9px;display:grid;grid-template-columns:1fr 1fr;gap:8px}.fbc-evidence{border:1px solid var(--line);border-radius:8px;padding:8px;background:#081421;font-size:11px}.fbc-evidence b{display:block;margin-bottom:3px}@media(max-width:1200px){.fbc-chain{grid-template-columns:repeat(3,minmax(155px,1fr))}.fbc-stage:nth-child(3):after{display:none}}@media(max-width:700px){.fbc-chain{grid-template-columns:1fr}.fbc-stage:after{display:none}.fbc-footer{grid-template-columns:1fr}}
</style>
"""

FILTRATION_BACKWASH_CAUSALITY_SCRIPT = r"""
(function(){
  const safe=v=>String(v===null||v===undefined?'UNAVAILABLE':v).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const finite=v=>{if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null};
  const num=(v,d=2,unit='')=>{const n=finite(v);return n===null?'UNAVAILABLE':`${n.toFixed(d)}${unit}`};
  const pct=v=>{const n=finite(v);return n===null?'UNAVAILABLE':`${(n*100).toFixed(1)}%`};
  const yesno=v=>v===true?'YES':(v===false?'NO':'UNAVAILABLE');
  function install(){
    const process=document.getElementById('process');if(!process||document.getElementById('filtrationBackwashCausality'))return;
    const card=document.createElement('div');card.id='filtrationBackwashCausality';card.className='card fbc-card';card.innerHTML=`
      <div class="label">Mechanical Filtration / Backwash — Evidence Causality</div>
      <div class="fbc-note"><b>Canonical process evidence only.</b> Valve command or feedback ON does not prove filter cleaning. Solids removal, water loss, hydraulic consequence and verification are displayed separately. Missing evidence remains UNAVAILABLE.</div>
      <div class="fbc-chain">
        <div id="fbcLoad" class="fbc-stage"><div class="fbc-title">1 · Filter Loading</div><div class="fbc-value">—</div><div class="fbc-detail">—</div></div>
        <div id="fbcHydraulic" class="fbc-stage"><div class="fbc-title">2 · Hydraulic Consequence</div><div class="fbc-value">—</div><div class="fbc-detail">—</div></div>
        <div id="fbcCommand" class="fbc-stage"><div class="fbc-title">3 · Backwash Command / Feedback</div><div class="fbc-value">—</div><div class="fbc-detail">—</div></div>
        <div id="fbcRemoval" class="fbc-stage"><div class="fbc-title">4 · Solids Removal / Water Loss</div><div class="fbc-value">—</div><div class="fbc-detail">—</div></div>
        <div id="fbcRefill" class="fbc-stage"><div class="fbc-title">5 · Refill / Source-Water Dependency</div><div class="fbc-value">—</div><div class="fbc-detail">—</div></div>
        <div id="fbcVerify" class="fbc-stage"><div class="fbc-title">6 · Post-Process Evidence</div><div class="fbc-value">—</div><div class="fbc-detail">—</div></div>
      </div>
      <div class="fbc-footer"><div class="fbc-evidence"><b>Evidence provenance</b><span id="fbcProvenance">—</span></div><div class="fbc-evidence"><b>Interpretation boundary</b><span id="fbcBoundary">—</span></div></div>`;
    const grid=process.querySelector('#processGrid');if(grid)grid.insertAdjacentElement('afterend',card);else process.appendChild(card);
  }
  function stage(id,kind,value,detail){const el=document.getElementById(id);if(!el)return;el.className=`fbc-stage ${kind||''}`;el.querySelector('.fbc-value').innerHTML=value;el.querySelector('.fbc-detail').innerHTML=detail}
  function verificationFor(s,id){return(s?.verification||[]).filter(v=>v.asset_id===id)}
  function render(s){
    install();if(!s)return;
    const hyd=s.hydraulics||{},mf=hyd.mechanical_filtration||{},routes=hyd.routes||{},routeId=mf.filtered_route_id||null,route=routeId?routes[routeId]||{}:{},wm=s.process_visual?.water_management||{},bwPath=wm.backwash||{},asset=s.assets?.backwash_valve||{},cmd=s.commands?.backwash_valve||null,fb=s.feedback?.backwash_valve||null,verify=verificationFor(s,'backwash_valve'),exchange=hyd.water_exchange||{},source=exchange.source_water||{},qual=source.qualification||{},recovery=s.water_recovery||{};
    if(!mf.configured){stage('fbcLoad','warn','INPUT REQUIRED','Mechanical-filtration profile is not configured. No loading, capacity or cleaning conclusion is inferred.');stage('fbcHydraulic','warn','UNAVAILABLE','Filtered route / process restriction evidence unavailable.');stage('fbcCommand','',`${asset.feedback_on?'ON':'OFF'} · ${safe(asset.availability||'UNKNOWN')}`,'Backwash actuator state is separate from filtration-process evidence.');stage('fbcRemoval','warn','UNAVAILABLE','No governed quantitative filtration model is configured.');stage('fbcRefill',source.configured?'':'warn',source.configured?safe(qual.state||'INPUT_REQUIRED'):'INPUT REQUIRED','Source-water evidence is independent from filter configuration.');stage('fbcVerify','warn','NO COMPLETION CLAIM','Required filtration-process evidence is unavailable.');text('fbcProvenance','Mechanical filtration UNAVAILABLE');text('fbcBoundary','No hardware fault, cleaning success or water-clarity conclusion is inferred.');return}
    const loading=finite(mf.loading_fraction),loadingKind=loading===null?'warn':(loading>=1?'bad':(loading>=0.75?'warn':'good'));
    stage('fbcLoad',loadingKind,`Load ${pct(mf.loading_fraction)}`,`Captured ${num(mf.captured_solids_g,2,' g')} / capacity ${num(mf.max_captured_solids_g,2,' g')}<br>Suspended ${num(mf.suspended_solids_g,2,' g')} · TSS ${num(mf.tss_mg_l,3,' mg/L')}<br>Status ${safe(mf.loading_status||'UNKNOWN')} · clarity ${safe(mf.water_clarity_conclusion||'NOT_ESTABLISHED')}`);
    const processFactor=finite(mf.process_throughput_factor),runtimeFactor=finite(route.runtime_throughput_factor),effectiveFlow=finite(route.effective_flow_l_min),hydKind=(processFactor!==null&&processFactor<0.75)?'warn':'';
    stage('fbcHydraulic',hydKind,`Process factor ${pct(mf.process_throughput_factor)}`,`Filtered route ${safe(routeId)}<br>Independent restriction factor ${pct(route.independent_restriction_factor)} · runtime throughput ${pct(route.runtime_throughput_factor)}<br>Effective modeled flow ${num(route.effective_flow_l_min,2,' L/min')} · last filter-route flow ${num(mf.last_route_flow_l_min,2,' L/min')}`);
    const bwActive=!!bwPath.motion_active,failed=asset.availability==='FAILED'||verify.some(v=>v.status==='FAILED_RESPONSE');const commandValue=cmd?`Requested ${yesno(cmd.requested_on)} → final ${yesno(cmd.final_on)}`:'NO CURRENT COMMAND';
    stage('fbcCommand',failed?'bad':(bwActive?'active':''),commandValue,`Feedback ${yesno(fb?.feedback_on??asset.feedback_on)} · owner ${safe(asset.owner)} · availability ${safe(asset.availability)}<br>Reason ${safe(cmd?.reason)} · process motion evidence ${yesno(bwActive)}`);
    const removed=finite(mf.last_backwash_removed_g),discharge=finite(mf.last_backwash_discharge_l),removalKind=bwActive?'active':(removed!==null&&removed>0?'good':'');
    stage('fbcRemoval',removalKind,`Last removed ${num(mf.last_backwash_removed_g,2,' g')}`,`Last discharge ${num(mf.last_backwash_discharge_l,2,' L')}<br>Cumulative removed ${num(mf.cumulative_backwash_removed_g,2,' g')} · cumulative discharge ${num(mf.cumulative_backwash_discharge_l,2,' L')}<br>Configured discharge rate ${num(mf.backwash_discharge_flow_l_min,2,' L/min')}`);
    const qualified=source.pond_use_qualified===true&&qual.pond_use_qualified===true;const qualificationState=source.configured?(qualified?'QUALIFIED':'NOT QUALIFIED / INPUT REQUIRED'):'INPUT REQUIRED';
    stage('fbcRefill',qualified?'good':'warn',qualificationState,`Water level ${num(wm.water_level_pct,1,'%')} · expected ${safe(wm.expected_level_direction)}<br>Auto top-up source-qualified ${yesno(recovery.source_water_qualified??qualified)} · requirement ${yesno(recovery.source_water_qualification_required)}<br>Source provenance ${safe(source.provenance)} · type alone proves safety: NO`);
    const statuses=verify.map(v=>String(v.status||'UNKNOWN'));const verificationFailed=statuses.includes('FAILED_RESPONSE')||statuses.includes('INSUFFICIENT_EVIDENCE'),verificationPassed=statuses.includes('VERIFIED_SUCCESS');let outcome='NO COMPLETION / RECOVERY CLAIM',kind='warn';if(bwActive){outcome='BACKWASH IN PROGRESS — NO COMPLETION CLAIM';kind='active'}else if(verificationFailed){outcome='VERIFICATION NOT SATISFIED';kind='bad'}else if(removed!==null&&removed>0){outcome='SOLIDS-REMOVAL EVIDENCE PRESENT';kind=verificationPassed?'good':'warn'};
    const verificationText=verify.length?verify.slice(-4).map(v=>`${safe(v.status)} · ${safe(v.parameter)} · observed ${safe(v.observed_value)}`).join('<br>'):'NO BACKWASH-VALVE VERIFICATION TASK PUBLISHED';
    stage('fbcVerify',kind,outcome,`${verificationText}<br>Current process factor ${pct(mf.process_throughput_factor)} · current modeled route flow ${num(route.effective_flow_l_min,2,' L/min')}<br>Current values are evidence, not proof of physical filter cleanliness.`);
    text('fbcProvenance',`filtration ${safe(mf.provenance)} · route ${safe(hyd.profile_provenance||'UNAVAILABLE')} · water volume ${safe(mf.water_volume_basis||'UNAVAILABLE')}`);
    text('fbcBoundary',`Turbidity ${num(mf.turbidity_ntu,2,' NTU')} · clarity ${safe(mf.water_clarity_conclusion||'NOT_ESTABLISHED')} · hardware fault conclusion ${safe(mf.hardware_fault_conclusion||'NOT_ESTABLISHED')} · hardware upgrade required ${yesno(mf.hardware_upgrade_required)}`);
  }
  install();const previous=window.renderSnapshot;if(typeof previous==='function'){window.renderSnapshot=function(snapshot,options){previous(snapshot,options);render(snapshot)}}window.renderFiltrationBackwashCausality=render;if(typeof displayed!=='undefined'&&displayed)render(displayed);
})();
"""
