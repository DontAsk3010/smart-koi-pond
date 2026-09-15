# ruff: noqa: E501

FAULT_CONTROLS_UI_SCRIPT = r"""
(function(){
  const acceptanceState={history:[],maxHistory:180,lastSnapshot:null};
  const esc=v=>String(v??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const finite=v=>{if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null};
  const fmt=(v,unit='',digits=3)=>{const n=finite(v);return n===null?'UNAVAILABLE':`${n.toFixed(digits)}${unit}`};
  const by=id=>document.getElementById(id);

  function installStyle(){
    if(document.getElementById('functionalAcceptanceStyle'))return;
    const style=document.createElement('style');
    style.id='functionalAcceptanceStyle';
    style.textContent=`
      .fa-shell{border-color:#315a76!important;background:linear-gradient(180deg,#0c2030,#091723)!important}
      .fa-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap;margin-bottom:10px}.fa-title{font-size:14px;font-weight:900;letter-spacing:.05em}.fa-badge{border:1px solid #8f7330;color:#f3d77b;border-radius:999px;padding:4px 8px;font-size:10px;font-weight:800}.fa-note{font-size:11px;color:#86a0b4;margin:5px 0 10px}.fa-scenarios{display:grid;grid-template-columns:repeat(4,minmax(145px,1fr));gap:7px;margin:8px 0 12px}.fa-scenarios .btn{font-size:10px;padding:8px}.fa-chemistry{display:grid;grid-template-columns:repeat(6,minmax(105px,1fr));gap:7px;align-items:end;margin:8px 0 12px}.fa-field label{display:block;font-size:9px;color:#7892a6;margin-bottom:3px;text-transform:uppercase;letter-spacing:.04em}.fa-field input,.fa-field select{width:100%}.fa-evidence{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:9px}.fa-panel{border:1px solid #1f3b50;border-radius:9px;background:#071521;padding:9px;min-width:0}.fa-panel h4{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:#a7c0d1;margin:0 0 7px}.fa-kv{display:grid;grid-template-columns:1fr auto;gap:4px 9px;font-size:10px}.fa-kv span{color:#7f98aa}.fa-kv strong{text-align:right;color:#e5f3fb;overflow-wrap:anywhere}.fa-list{display:grid;gap:4px;max-height:150px;overflow:auto}.fa-row{border-top:1px solid #173146;padding-top:5px;font-size:9px;color:#a8bdca}.fa-row:first-child{border-top:0;padding-top:0}.fa-row b{color:#eef8fc}.fa-trend{height:130px}.fa-trend canvas{height:130px!important}.fa-source-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}.fa-status{margin-top:8px;border:1px solid #1d394e;border-radius:7px;padding:6px 8px;background:#06131e;font-size:10px;color:#91a9b9;min-height:28px}.fa-warning{border-left:3px solid #b68624;background:#2b210b;padding:7px 9px;font-size:10px;color:#e7ca75;margin-top:8px}.fa-good{color:#83e8ae!important}.fa-bad{color:#ff9da5!important}.fa-muted{color:#71899b!important}@media(max-width:1100px){.fa-scenarios{grid-template-columns:repeat(2,1fr)}.fa-chemistry{grid-template-columns:repeat(3,1fr)}.fa-evidence{grid-template-columns:1fr 1fr}}@media(max-width:720px){.fa-scenarios,.fa-chemistry,.fa-evidence{grid-template-columns:1fr}}`;
    document.head.appendChild(style);
  }

  function acceptanceCard(){
    const card=document.createElement('div');
    card.id='functionalAcceptanceHarness';
    card.className='card span12 fa-shell';
    card.innerHTML=`
      <div class="fa-head"><div><div class="fa-title">VISUAL FUNCTIONAL ACCEPTANCE — CANONICAL CLOSED LOOP</div><div class="fa-note">Production-intent acceptance harness. Presets are explicit SIMULATION engineering disturbances, not real pond measurements or production setpoints. Outcomes are never calculated in this browser; they are read back from the canonical runtime.</div></div><div id="faModeBadge" class="fa-badge">SIMULATION REQUIRED</div></div>
      <div class="label">Scenario Families</div>
      <div class="fa-scenarios">
        <button class="btn danger" id="faNitriteHigh">Nitrite HIGH · 0.60 mg/L</button><button class="btn danger" id="faNitriteEmergency">Nitrite EMERGENCY · 1.60</button>
        <button class="btn danger" id="faNitrateHigh">Nitrate HIGH · 25 mg/L</button><button class="btn danger" id="faLowDo">Low DO · 3.80 mg/L</button>
        <button class="btn danger" id="faPhHigh">pH HIGH · 9.20</button><button class="btn danger" id="faPhLow">pH LOW · 5.80</button>
        <button class="btn danger" id="faPumpFail">Main Pump Failure</button><button class="btn ok" id="faPumpRepair">Repair Main Pump</button>
      </div>
      <div class="label">TAN + pH + Temperature → Molecular NH3</div>
      <div class="fa-chemistry">
        <div class="fa-field"><label>TAN-N mg/L</label><input id="faTan" type="number" min="0" step="0.01" value="0.50"></div>
        <div class="fa-field"><label>pH</label><input id="faPh" type="number" min="0" max="14" step="0.1" value="7.50"></div>
        <div class="fa-field"><label>Temperature °C</label><input id="faTemp" type="number" step="0.1" value="20.0"></div>
        <button class="btn" id="faApplyChemistry">Apply Exact Inputs</button><button class="btn" id="faSameTanLowerRisk">Same TAN · pH 7.5 / 20°C</button><button class="btn danger" id="faSameTanHigherRisk">Same TAN · pH 8.5 / 28°C</button>
      </div>
      <div class="label">Source-Water Safety</div>
      <div class="fa-source-actions"><button class="btn danger" id="faUnsafeSource">Load Explicit UNSAFE Source</button><button class="btn ok" id="faSafeSource">Load Qualified Safer Source</button><input id="faDrainTarget" type="number" min="0" max="100" step="0.1" value="80" aria-label="Acceptance drain target"><input id="faRefillTarget" type="number" min="0" max="100" step="0.1" value="85" aria-label="Acceptance refill target"><button class="btn" id="faAttemptWaterChange">Attempt Governed Water Change</button><button class="btn" id="faRestoreBaseline">Restore Simulation Acceptance Baseline</button></div>
      <div class="fa-warning">Unsafe source must be rejected before drain/refill begins. Qualified source is still subject to every other canonical water-change interlock. Automatic acid/base/salt/binder dosing remains CLOSED.</div>
      <div class="fa-evidence" style="margin-top:10px">
        <div class="fa-panel"><h4>Input · Quality · Provenance</h4><div id="faInputs" class="fa-kv"></div></div>
        <div class="fa-panel"><h4>Reference / Recovery Band</h4><div id="faThresholds" class="fa-kv"></div></div>
        <div class="fa-panel"><h4>Derived State · Classification</h4><div id="faClassification" class="fa-kv"></div></div>
        <div class="fa-panel"><h4>Requested → Final Command → Feedback</h4><div id="faCommands" class="fa-list"></div></div>
        <div class="fa-panel"><h4>Verification · Recovery · Lockout</h4><div id="faVerification" class="fa-list"></div></div>
        <div class="fa-panel"><h4>Incident Start / End · Event Timeline</h4><div id="faTimeline" class="fa-list"></div></div>
        <div class="fa-panel" style="grid-column:1/-1"><h4>Canonical Trend After Action</h4><div class="controls"><select id="faTrendMetric"><option value="nh3">Molecular NH3</option><option value="tan">TAN</option><option value="nitrite">Nitrite</option><option value="nitrate">Nitrate</option><option value="ph">pH</option><option value="do">DO</option></select></div><div class="fa-trend"><canvas id="faTrendCanvas"></canvas></div><div class="fa-note">Browser history stores only values already published by the canonical runtime; gaps remain gaps and are never replaced with zero.</div></div>
      </div>
      <div id="faCommandStatus" class="fa-status">Ready · all scenario writes use canonical /api/command via sendCommand().</div>`;
    return card;
  }

  function installFaultControls(){
    const grid=document.querySelector('#simulator .grid');
    if(!grid||document.getElementById('hardwareFaultCard'))return;
    installStyle();

    const hardware=document.createElement('div');
    hardware.id='hardwareFaultCard';
    hardware.className='card span6';
    hardware.innerHTML=`
      <div class="label">Virtual Hardware Fault & Repair</div>
      <div class="controls">
        <select id="faultAsset"><option value="main_pump">Main Pump</option><option value="backup_pump">Backup Pump</option><option value="primary_aerator">Primary Aerator</option><option value="backup_aerator">Backup Aerator</option><option value="top_up_valve">Top-up Valve</option><option value="drain_valve">Drain Valve</option><option value="backwash_valve">Backwash Valve</option><option value="feeder">Feeder</option><option value="uv_lamp">UV Lamp</option></select>
        <select id="actuatorFaultMode"><option value="failed_off">Failed OFF</option><option value="degraded">Degraded effectiveness</option></select>
        <input id="actuatorFaultValue" type="number" min="0" max="0.99" step="0.05" value="0.5" aria-label="Degraded effectiveness">
        <button class="btn danger" type="button" id="injectActuatorFaultButton">Inject</button><button class="btn ok" type="button" id="repairActuatorButton">Repair / Clear</button>
      </div><div class="muted">Failed OFF removes process effect. Degraded mode preserves motion but reduces effectiveness.</div>`;

    const recovery=document.createElement('div');
    recovery.id='safeRecoveryCard';
    recovery.className='card span6';
    recovery.innerHTML=`
      <div class="label">Safe Reset & Automatic Scenario</div><div class="controls"><button class="btn danger" type="button" id="safeRuntimeResetButton">Safe Runtime Reset</button><input id="autoFaultDelay" type="number" min="0" step="1" value="30" aria-label="Automatic fault delay in seconds"><button class="btn" type="button" id="scheduleFaultButton">Schedule selected fault</button></div><div class="muted">Reset preserves simulated hardware faults, de-energizes outputs, and enters governed reconciliation. Automatic scheduling uses simulation time.</div>`;

    grid.appendChild(hardware);grid.appendChild(recovery);grid.appendChild(acceptanceCard());
    bindHardwareControls();bindAcceptanceControls();
  }

  function bindHardwareControls(){
    by('injectActuatorFaultButton').addEventListener('click',()=>{const asset=by('faultAsset').value,mode=by('actuatorFaultMode').value,payload={asset_id:asset,mode};if(mode==='degraded')payload.value=Number(by('actuatorFaultValue').value);sendCommand('inject_actuator_fault',payload,'engineering')});
    by('repairActuatorButton').addEventListener('click',()=>sendCommand('clear_actuator_fault',{asset_id:by('faultAsset').value},'engineering'));
    by('safeRuntimeResetButton').addEventListener('click',()=>sendCommand('safe_runtime_reset',{},'engineering'));
    by('scheduleFaultButton').addEventListener('click',()=>{const asset=by('faultAsset').value,mode=by('actuatorFaultMode').value,scenarioPayload={asset_id:asset,mode};if(mode==='degraded')scenarioPayload.value=Number(by('actuatorFaultValue').value);sendCommand('schedule_scenario_trigger',{scenario_action:'inject_actuator_fault',scenario_payload:scenarioPayload,after_seconds:Number(by('autoFaultDelay').value),one_shot:true},'engineering')});
  }

  async function setEnvironment(parameter,value){await sendCommand('set_environment_state',{parameter,value:Number(value)},'engineering')}
  async function applyChemistry(tan,ph,temp){await setEnvironment('tan',tan);await setEnvironment('ph',ph);await setEnvironment('temperature',temp)}
  function markStatus(message){const e=by('faCommandStatus');if(e)e.textContent=message}

  function sourceProfile(qualified){
    return qualified?{
      profile_id:'acceptance-qualified-source',revision:'scenario-1',source_reference:'VIRTUAL_ACCEPTANCE_SCENARIO_QUALIFIED_SOURCE',source_type:'OTHER',temperature_c:27,dissolved_oxygen_mg_l:6.5,ph:7.2,total_ammonia_nitrogen_mg_l:0.05,nitrite_mg_l:0.02,nitrate_mg_l:5,alkalinity_mg_l_as_caco3:100,free_chlorine_residual_mg_l:0,chloramine_residual_mg_l:0,pond_use_qualification:'QUALIFIED',qualification_basis:'SIMULATION_ACCEPTANCE_PRESET_EXPLICIT_EVIDENCE',qualification_reference:'VIRTUAL_ACCEPTANCE_SCENARIO_QUALIFICATION_RECORD',provenance:'USER_CONFIGURED_SCENARIO'
    }:{
      profile_id:'acceptance-unsafe-source',revision:'scenario-1',source_reference:'VIRTUAL_ACCEPTANCE_SCENARIO_UNSAFE_SOURCE',source_type:'OTHER',temperature_c:27,dissolved_oxygen_mg_l:6.0,ph:7.2,total_ammonia_nitrogen_mg_l:0.10,nitrite_mg_l:0.05,nitrate_mg_l:10,alkalinity_mg_l_as_caco3:100,free_chlorine_residual_mg_l:0.50,chloramine_residual_mg_l:0,pond_use_qualification:'NOT_QUALIFIED',provenance:'USER_CONFIGURED_SCENARIO'
    };
  }

  function bindAcceptanceControls(){
    by('faNitriteHigh').onclick=()=>setEnvironment('nitrite',0.60);by('faNitriteEmergency').onclick=()=>setEnvironment('nitrite',1.60);by('faNitrateHigh').onclick=()=>setEnvironment('nitrate',25);by('faLowDo').onclick=()=>setEnvironment('do',3.80);by('faPhHigh').onclick=()=>setEnvironment('ph',9.20);by('faPhLow').onclick=()=>setEnvironment('ph',5.80);
    by('faPumpFail').onclick=()=>sendCommand('inject_actuator_fault',{asset_id:'main_pump',mode:'failed_off'},'engineering');by('faPumpRepair').onclick=()=>sendCommand('clear_actuator_fault',{asset_id:'main_pump'},'engineering');
    by('faApplyChemistry').onclick=()=>applyChemistry(by('faTan').value,by('faPh').value,by('faTemp').value);by('faSameTanLowerRisk').onclick=()=>applyChemistry(by('faTan').value,7.5,20);by('faSameTanHigherRisk').onclick=()=>applyChemistry(by('faTan').value,8.5,28);
    by('faUnsafeSource').onclick=()=>sendCommand('configure_source_water_profile',{profile:sourceProfile(false),actor:'functional-acceptance-ui'},'engineering');by('faSafeSource').onclick=()=>sendCommand('configure_source_water_profile',{profile:sourceProfile(true),actor:'functional-acceptance-ui'},'engineering');
    by('faAttemptWaterChange').onclick=()=>sendCommand('start_water_change',{target_drain_level_pct:Number(by('faDrainTarget').value),target_refill_level_pct:Number(by('faRefillTarget').value),reason:'VISUAL_FUNCTIONAL_ACCEPTANCE_SOURCE_WATER'},'engineering');
    by('faRestoreBaseline').onclick=async()=>{markStatus('Restoring explicit SIMULATION acceptance baseline…');await setEnvironment('do',6);await setEnvironment('ph',7.2);await setEnvironment('temperature',27);await setEnvironment('tan',0.10);await setEnvironment('nitrite',0.05);await setEnvironment('nitrate',10);await sendCommand('clear_actuator_fault',{asset_id:'main_pump'},'engineering');markStatus('Acceptance baseline commands issued through canonical runtime.')};
    by('faTrendMetric').onchange=()=>drawAcceptanceTrend();
  }

  function measurement(snapshot,id){return snapshot?.validated?.[id]||null}
  function qualityText(m){return m?`${m.quality||'—'} / ${m.availability||'—'} · ${m.source_state||'—'} · ${m.adapter_id||'—'}`:'UNAVAILABLE'}
  function setKv(id,rows){const e=by(id);if(e)e.innerHTML=rows.map(([k,v])=>`<span>${esc(k)}</span><strong>${esc(v)}</strong>`).join('')}

  function renderInputs(snapshot){
    const p=snapshot.pond_truth||{},est=snapshot.estimate||{},nh3=est.values?.unionized_ammonia_nh3_mg_l,der=est.derivation?.unionized_ammonia_nh3_mg_l||{};
    setKv('faInputs',[
      ['DO',`${fmt(p.dissolved_oxygen_mg_l,' mg/L',2)} · ${qualityText(measurement(snapshot,'do'))}`],['pH',`${fmt(p.ph,'',2)} · ${qualityText(measurement(snapshot,'ph'))}`],['Temperature',`${fmt(p.temperature_c,' °C',2)} · ${qualityText(measurement(snapshot,'temperature'))}`],['TAN-N',`${fmt(p.total_ammonia_nitrogen_mg_l,' mg/L')} · ${qualityText(measurement(snapshot,'tan'))}`],['Nitrite',`${fmt(p.nitrite_mg_l,' mg/L')} · ${qualityText(measurement(snapshot,'nitrite'))}`],['Nitrate',`${fmt(p.nitrate_mg_l,' mg/L')} · ${qualityText(measurement(snapshot,'nitrate'))}`],['Molecular NH3',`${fmt(nh3,' mg/L',5)} · ${est.provenance?.unionized_ammonia_nh3_mg_l||'UNAVAILABLE'}`],['NH3 formula',der.formula_id||der.status||'UNAVAILABLE']]);
  }

  function renderThresholds(snapshot){
    const t=snapshot.water_recovery?.threshold_profile||{};const configured=t.configured===true;const status=t.status||(configured?'CONFIGURED':'UNAVAILABLE');
    setKv('faThresholds',[
      ['Authority',configured?`${status} · ${t.profile_id||'profile'}`:`${status} · production setpoint claimed: NO`],['TAN watch / emergency',configured?`${fmt(t.tan_watch_above)} / ${fmt(t.tan_emergency_above)} mg/L`:'UNAVAILABLE until governed profile'],['NH3 watch / emergency',configured?`${fmt(t.nh3_watch_above,'',5)} / ${fmt(t.nh3_emergency_above,'',5)} mg/L`:'UNAVAILABLE until governed profile'],['Nitrite watch / emergency',configured?`${fmt(t.nitrite_watch_above)} / ${fmt(t.nitrite_emergency_above)} mg/L`:'UNAVAILABLE until governed profile'],['Nitrate upper reference',configured?`${fmt(t.nitrate_watch_above)} mg/L`:'UNAVAILABLE until governed profile'],['pH watch band',configured?`${fmt(t.ph_watch_below,'',2)} – ${fmt(t.ph_watch_above,'',2)}`:'UNAVAILABLE until governed profile'],['Recovery band',configured?`NH3 < ${fmt(t.nh3_recover_below,'',5)} · nitrite < ${fmt(t.nitrite_recover_below)} · pH ${fmt(t.ph_recover_low,'',2)}–${fmt(t.ph_recover_high,'',2)}`:'UNAVAILABLE / automatic WQ exchange disabled'],['Chemical dosing','DISABLED / CLOSED']]);
  }

  function renderClassification(snapshot){
    const est=snapshot.estimate||{},der=est.derivation?.unionized_ammonia_nh3_mg_l||{},src=snapshot.hydraulics?.water_exchange?.source_water||{},qual=src.qualification||{};
    setKv('faClassification',[
      ['System state',snapshot.classification?.state||'UNAVAILABLE'],['Reason code(s)',(snapshot.classification?.reasons||[]).join(' · ')||'UNAVAILABLE'],['Molecular NH3',fmt(est.values?.unionized_ammonia_nh3_mg_l,' mg/L',5)],['NH3 provenance',est.provenance?.unionized_ammonia_nh3_mg_l||'UNAVAILABLE'],['NH3 basis',der.basis||der.status||'UNAVAILABLE'],['Source-water qualification',`${qual.state||'INPUT_REQUIRED'} · ${qual.reason||'UNAVAILABLE'}`],['Execution mode',snapshot.execution_mode||'UNAVAILABLE'],['Real actuator authority','CLOSED by current gate']]);
    const badge=by('faModeBadge');if(badge){badge.textContent=snapshot.execution_mode==='SIMULATION'?'SIMULATION · VIRTUAL I/O ONLY':`${snapshot.execution_mode||'UNKNOWN'} · DISTURBANCE WRITES BLOCKED`;badge.className=`fa-badge ${snapshot.execution_mode==='SIMULATION'?'fa-good':'fa-bad'}`}
  }

  function renderCommands(snapshot){
    const box=by('faCommands');if(!box)return;const commands=Object.values(snapshot.commands||{});if(!commands.length){box.innerHTML='<div class="fa-row fa-muted">No command intent published in this cycle.</div>';return}box.innerHTML=commands.map(c=>{const f=snapshot.feedback?.[c.asset_id]||snapshot.assets?.[c.asset_id]||{};return `<div class="fa-row"><b>${esc(c.asset_id)}</b> · requested ${c.requested_on?'ON':'OFF'} → final ${c.final_on?'ON':'OFF'} · ${c.accepted?'ACCEPTED':'INHIBITED'}<br>${esc(c.owner||'—')} · ${esc(c.reason||'—')} · feedback ${f.feedback_on?'ON':'OFF'} · ${esc(f.availability||'UNAVAILABLE')} · effect ${esc(f.effectiveness??'UNAVAILABLE')}</div>`}).join('')
  }

  function renderVerification(snapshot){
    const box=by('faVerification');if(!box)return;const tasks=(snapshot.verification||[]).slice(-5).reverse();const wr=snapshot.water_recovery?.water_quality||{};let html=tasks.map(v=>`<div class="fa-row"><b>${esc(v.asset_id)} · ${esc(v.status)}</b><br>${esc(v.parameter)} · baseline ${esc(v.baseline)} · observed ${esc(v.observed_value??'UNAVAILABLE')} · due ${esc(v.due_at||'—')}</div>`).join('');html+=`<div class="fa-row"><b>Water-quality recovery</b><br>active ${esc(wr.active?.reason||'NONE')} · last ${esc(wr.last_outcome||'UNAVAILABLE')} · lockout ${esc(wr.lockout_reason||'NONE')} · attempts ${esc(JSON.stringify(wr.attempt_counts||{}))}</div>`;box.innerHTML=html
  }

  function renderTimeline(snapshot){
    const box=by('faTimeline');if(!box)return;const incidents=(snapshot.incidents||[]).slice(-2).reverse();let html=incidents.map(i=>`<div class="fa-row"><b>${esc(i.trigger_code)} · ${esc(i.lifecycle)}</b><br>start ${esc(i.opened_at||'UNAVAILABLE')} · end ${esc(i.resolved_at||'OPEN')} · incident ${esc(i.incident_id)}</div>`).join('');const events=(typeof eventBuffer!=='undefined'?eventBuffer:[]).slice(-6).reverse();html+=events.map(e=>`<div class="fa-row"><b>#${esc(e.sequence)} · ${esc(e.code)}</b><br>${esc(e.timestamp)} · ${esc(e.event_type)}</div>`).join('');box.innerHTML=html||'<div class="fa-row fa-muted">No incident/event evidence yet.</div>'
  }

  function pushAcceptanceHistory(snapshot){
    if(typeof playbackMode!=='undefined'&&playbackMode)return;const p=snapshot.pond_truth||{},est=snapshot.estimate||{};acceptanceState.history.push({t:snapshot.timestamp,do:finite(p.dissolved_oxygen_mg_l),ph:finite(p.ph),tan:finite(p.total_ammonia_nitrogen_mg_l),nitrite:finite(p.nitrite_mg_l),nitrate:finite(p.nitrate_mg_l),nh3:finite(est.values?.unionized_ammonia_nh3_mg_l)});if(acceptanceState.history.length>acceptanceState.maxHistory)acceptanceState.history.shift()
  }

  function drawAcceptanceTrend(){
    const canvas=by('faTrendCanvas');if(!canvas)return;const metric=by('faTrendMetric')?.value||'nh3',vals=acceptanceState.history.map(v=>v[metric]);const rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;canvas.width=Math.max(1,rect.width*dpr);canvas.height=Math.max(1,130*dpr);const x=canvas.getContext('2d');x.scale(dpr,dpr);const w=rect.width,h=130;x.clearRect(0,0,w,h);x.strokeStyle='#20364d';x.strokeRect(.5,.5,w-1,h-1);const present=vals.filter(Number.isFinite);if(present.length<2){x.fillStyle='#8199aa';x.font='10px system-ui';x.fillText('Canonical trend evidence not sufficient yet.',8,16);return}let lo=Math.min(...present),hi=Math.max(...present);if(lo===hi){lo-=1;hi+=1}const pad=(hi-lo)*.1;lo-=pad;hi+=pad;x.strokeStyle='#55c9f1';x.lineWidth=2;x.beginPath();let started=false;vals.forEach((v,i)=>{if(!Number.isFinite(v)){started=false;return}const px=8+i*(w-16)/Math.max(1,vals.length-1),py=h-8-((v-lo)/(hi-lo))*(h-24);if(!started){x.moveTo(px,py);started=true}else{x.lineTo(px,py)}});x.stroke();x.fillStyle='#8199aa';x.font='10px system-ui';x.fillText(`${metric.toUpperCase()} · ${lo.toFixed(4)} – ${hi.toFixed(4)}`,8,14)
  }

  function installCockpitShortcut(){
    if(by('faCockpitShortcut'))return;const actions=document.querySelector('#ownerOperationalCockpit .oc-actions');if(!actions)return;const b=document.createElement('button');b.id='faCockpitShortcut';b.className='btn wide';b.textContent='Open Functional Acceptance';b.onclick=()=>{const tab=document.querySelector('#tabs button[data-view="simulator"]');if(tab)tab.click();setTimeout(()=>by('functionalAcceptanceHarness')?.scrollIntoView({behavior:'smooth',block:'start'}),50)};actions.appendChild(b)
  }

  function renderAcceptance(snapshot,{push=true}={}){if(!snapshot)return;acceptanceState.lastSnapshot=snapshot;installCockpitShortcut();renderInputs(snapshot);renderThresholds(snapshot);renderClassification(snapshot);renderCommands(snapshot);renderVerification(snapshot);renderTimeline(snapshot);if(push)pushAcceptanceHistory(snapshot);drawAcceptanceTrend()}

  installFaultControls();
  const previousSnapshot=window.renderSnapshot;window.renderSnapshot=function(snapshot,options){previousSnapshot(snapshot,options);renderAcceptance(snapshot,{push:!(options&&options.push===false)})};
  const previousPublication=window.renderPublication;window.renderPublication=function(pub){previousPublication(pub);if(pub?.snapshot)renderTimeline(pub.snapshot)};
  const previousSend=window.sendCommand;window.sendCommand=async function(action,payload,role){markStatus(`${action}: sending through canonical command boundary…`);const result=await previousSend(action,payload,role);const source=by('commandResult');markStatus(source?.textContent||`${action}: completed`);return result};
  window.addEventListener('resize',drawAcceptanceTrend);
  if(typeof displayed!=='undefined'&&displayed)renderAcceptance(displayed,{push:false});
})();
"""