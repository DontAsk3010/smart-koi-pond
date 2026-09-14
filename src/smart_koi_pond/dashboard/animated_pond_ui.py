# ruff: noqa: E501

ANIMATED_POND_STYLE = r"""
<style id="animated-pond-style">
.pond-stage{position:relative;min-height:430px;margin:12px 0 18px;border:1px solid #28506d;border-radius:14px;overflow:hidden;background:linear-gradient(180deg,#071829 0%,#0a2030 52%,#08131f 100%)}
.pond-stage .stage-title{position:absolute;left:14px;top:12px;z-index:5;font-weight:800;letter-spacing:.04em}.pond-stage .stage-meta{position:absolute;right:14px;top:12px;z-index:5;text-align:right;color:#9db5c7;font-size:12px}.pond-vessel{position:absolute;left:18%;right:18%;bottom:38px;height:235px;border:2px solid #3e7fa6;border-radius:22px 22px 38px 38px;overflow:hidden;background:#081a27;box-shadow:inset 0 0 35px rgba(65,163,210,.12)}
.pond-water{position:absolute;left:0;right:0;bottom:0;height:85%;min-height:2px;background:linear-gradient(180deg,rgba(44,155,206,.68),rgba(15,82,126,.83));transition:height .8s ease}.pond-water:before{content:"";position:absolute;left:-20%;top:-7px;width:140%;height:14px;background:radial-gradient(ellipse at center,rgba(140,224,255,.6) 0 32%,transparent 34%) 0 0/34px 12px;animation:waterRipple 2.4s linear infinite;opacity:.55}.pond-vessel.data-unavailable .pond-water{display:none}.pond-vessel.data-unavailable:before{content:"WATER LEVEL UNAVAILABLE";position:absolute;inset:0;display:grid;place-items:center;z-index:2;color:#c7d5df;font-size:12px;font-weight:800;letter-spacing:.08em;background:repeating-linear-gradient(135deg,rgba(100,132,153,.07) 0 10px,rgba(100,132,153,.14) 10px 20px)}
@keyframes waterRipple{to{transform:translateX(34px)}}
.pond-level-label{position:absolute;right:10px;bottom:10px;z-index:3;padding:4px 7px;background:rgba(3,15,24,.72);border:1px solid #2e617e;border-radius:6px;font-size:12px}.pond-do-label{position:absolute;left:10px;bottom:10px;z-index:3;padding:4px 7px;background:rgba(3,15,24,.72);border:1px solid #2e617e;border-radius:6px;font-size:12px}
.process-svg{position:absolute;inset:45px 20px 20px;width:calc(100% - 40px);height:calc(100% - 65px);pointer-events:none}.pipe{fill:none;stroke:#38536a;stroke-width:8;stroke-linecap:round;stroke-linejoin:round}.pipe.route-active{stroke:#55c7ff;stroke-dasharray:13 13;animation:pipeFlow 1s linear infinite}.pipe.route-backup.route-active{stroke:#83d8ff}.pipe.inlet-active{stroke:#65dbbb;stroke-dasharray:11 12;animation:pipeFlow .8s linear infinite}.pipe.discharge-active{stroke:#d5a460;stroke-dasharray:11 12;animation:pipeFlow .75s linear infinite}.pipe.backwash-active{stroke:#c78bff;stroke-dasharray:9 11;animation:pipeFlow .7s linear infinite}@keyframes pipeFlow{to{stroke-dashoffset:-26}}
.device-chip{position:absolute;z-index:4;min-width:118px;padding:7px 9px;border:1px solid #294760;background:rgba(7,21,34,.94);border-radius:8px;font-size:12px}.device-chip b{display:block;font-size:13px}.device-chip.active{border-color:#46b9e9;box-shadow:0 0 0 1px rgba(70,185,233,.22),0 0 16px rgba(70,185,233,.12)}.device-chip.failed{border-color:#ff5d68}.device-chip small{color:#8fa4b8}.chip-main{left:2%;top:88px}.chip-backup{left:2%;top:172px}.chip-aeration{right:2%;top:88px}.chip-water{right:2%;top:185px}
.bubbles{position:absolute;left:42%;right:42%;bottom:56px;height:150px;z-index:2;opacity:0;transition:opacity .35s}.bubbles.active{opacity:1}.bubble{position:absolute;bottom:0;width:9px;height:9px;border:1px solid rgba(207,243,255,.9);border-radius:50%;background:rgba(183,235,255,.18);animation:bubbleRise 2.2s linear infinite}.bubble:nth-child(2){left:30%;animation-delay:.5s}.bubble:nth-child(3){left:65%;animation-delay:1.1s}.bubble:nth-child(4){left:80%;animation-delay:.2s;width:6px;height:6px}.bubble:nth-child(5){left:45%;animation-delay:1.5s;width:12px;height:12px}@keyframes bubbleRise{0%{transform:translateY(0) scale(.7);opacity:.15}30%{opacity:.9}100%{transform:translateY(-145px) scale(1.25);opacity:0}}
.process-legend{position:absolute;left:14px;bottom:10px;z-index:5;font-size:11px;color:#8fa4b8}.process-warning{position:absolute;right:14px;bottom:10px;z-index:5;font-size:11px;color:#d7b86a;text-align:right;max-width:68%}.motion-paused .pipe.route-active,.motion-paused .pipe.inlet-active,.motion-paused .pipe.discharge-active,.motion-paused .pipe.backwash-active,.motion-paused .pond-water:before,.motion-paused .bubble{animation-play-state:paused!important}
@media(max-width:900px){.pond-stage{min-height:500px}.pond-vessel{left:8%;right:8%;bottom:70px}.device-chip{min-width:105px}.chip-main{left:2%;top:58px}.chip-backup{left:2%;top:124px}.chip-aeration{right:2%;top:58px}.chip-water{right:2%;top:140px}.process-svg{inset:35px 8px 40px;width:calc(100% - 16px);height:calc(100% - 75px)}}
</style>
"""

ANIMATED_POND_SCRIPT = r"""
(function(){
  function finite(v){if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null}
  function bounded(v,lo,hi=null){const n=finite(v);if(n===null)return null;return Math.max(lo,hi===null?n:Math.min(hi,n))}
  function esc(v){return String(v??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
  function num(v,d=2){const n=finite(v);return n===null?'UNAVAILABLE':n.toFixed(d)}
  function statusClass(path){if(!path)return'';if(path.availability==='FAILED'||path.verification_status==='FAILED_RESPONSE')return' failed';return path.motion_active?' active':''}
  function pathLabel(path){if(!path)return'UNAVAILABLE';const effect=bounded(path.effectiveness,0,1),effectLabel=effect===null?'UNAVAILABLE':`${Math.round(effect*100)}%`;return `${path.feedback_on?'ON':'OFF'} · ${esc(path.availability||'UNKNOWN')} · effect ${effectLabel}${path.verification_status?` · ${esc(path.verification_status)}`:''}`}
  function installStage(){
    const grid=document.getElementById('processGrid');if(!grid||document.getElementById('animatedPondStage'))return;
    const stage=document.createElement('div');stage.id='animatedPondStage';stage.className='pond-stage';stage.innerHTML=`
      <div class="stage-title">LIVE POND PROCESS — STATE-BOUND RENDERER</div><div id="pondStageMeta" class="stage-meta">Awaiting canonical runtime…</div>
      <svg class="process-svg" viewBox="0 0 1000 380" preserveAspectRatio="none" aria-label="Animated pond hydraulic process">
        <path id="mainFlowPath" class="pipe route-main" d="M185 205 C300 205 300 105 430 105 C570 105 565 205 815 205"/>
        <path id="backupFlowPath" class="pipe route-backup" d="M185 250 C315 250 330 315 500 315 C670 315 685 250 815 250"/>
        <path id="topUpPath" class="pipe" d="M845 70 L845 155 L770 155"/>
        <path id="drainPath" class="pipe" d="M500 285 L500 365"/>
        <path id="backwashPath" class="pipe" d="M300 120 L215 70 L120 70"/>
      </svg>
      <div id="pondVessel" class="pond-vessel"><div id="pondWater" class="pond-water"></div><div id="pondLevelLabel" class="pond-level-label">Level —</div><div id="pondDoLabel" class="pond-do-label">DO —</div></div>
      <div id="pondBubbles" class="bubbles"><i class="bubble"></i><i class="bubble"></i><i class="bubble"></i><i class="bubble"></i><i class="bubble"></i></div>
      <div id="chipMain" class="device-chip chip-main"><b>Main circulation</b><small>—</small></div><div id="chipBackup" class="device-chip chip-backup"><b>Backup circulation</b><small>—</small></div><div id="chipAeration" class="device-chip chip-aeration"><b>Aeration</b><small>—</small></div><div id="chipWater" class="device-chip chip-water"><b>Water management</b><small>—</small></div>
      <div class="process-legend">Motion = canonical runtime/process evidence, never decorative success.</div><div id="pondVisualWarning" class="process-warning">Waste/sludge quantity: NOT MODELED</div>`;
    grid.parentNode.insertBefore(stage,grid);
    const simControls=document.querySelector('#simulator .controls');
    if(simControls&&!document.getElementById('singleStepButton')){const b=document.createElement('button');b.id='singleStepButton';b.className='btn';b.textContent='Step +1s';b.onclick=()=>sendCommand('step',{seconds:1},'operator');simControls.appendChild(b)}
  }
  function filterEvidence(mf){
    if(!mf||!mf.configured)return'Waste/sludge quantity: NOT MODELED';
    const load=mf.loading_fraction==null?'UNAVAILABLE':`${(Number(mf.loading_fraction)*100).toFixed(1)}%`;
    const suspended=mf.suspended_solids_g==null?'UNAVAILABLE':`${num(mf.suspended_solids_g,2)} g`;
    const captured=mf.captured_solids_g==null?'UNAVAILABLE':`${num(mf.captured_solids_g,2)} g`;
    const tss=mf.tss_mg_l==null?'UNAVAILABLE':`${num(mf.tss_mg_l,3)} mg/L`;
    const turbidity=mf.turbidity_ntu==null?'UNAVAILABLE':`${num(mf.turbidity_ntu,2)} NTU`;
    return `Suspended ${suspended} · captured ${captured} · load ${load} · TSS ${tss} · turbidity ${turbidity} · clarity ${esc(mf.water_clarity_conclusion||'NOT_ESTABLISHED')}`;
  }
  function renderProcessVisual(pv){
    installStage();const stage=document.getElementById('animatedPondStage');if(!stage||!pv)return;
    stage.classList.toggle('motion-paused',!!pv.simulation_paused);
    const wm=pv.water_management||{},circ=pv.circulation||{},aer=pv.aeration||{},mf=pv.mechanical_filtration||{};
    const level=bounded(wm.water_level_pct,0,100),flow=bounded(circ.measured_total_flow_l_min,0),dox=bounded(pv.dissolved_oxygen_mg_l,0);
    const vessel=document.getElementById('pondVessel'),waterEl=document.getElementById('pondWater');
    vessel.classList.toggle('data-unavailable',level===null);
    if(level!==null)waterEl.style.height=`${level}%`;else waterEl.style.removeProperty('height');
    document.getElementById('pondLevelLabel').textContent=level===null?'Level UNAVAILABLE':`Level ${level.toFixed(1)}%`;
    document.getElementById('pondDoLabel').textContent=dox===null?'DO UNAVAILABLE':`DO ${dox.toFixed(2)} mg/L`;
    const primary=circ.primary||{},backup=circ.backup||{},ap=aer.primary||{},ab=aer.backup||{},top=wm.top_up||{},drain=wm.drain||{},bw=wm.backwash||{};
    document.getElementById('mainFlowPath').classList.toggle('route-active',flow!==null&&!!primary.motion_active&&!!circ.flow_motion_active);document.getElementById('backupFlowPath').classList.toggle('route-active',flow!==null&&!!backup.motion_active&&!!circ.flow_motion_active);
    document.getElementById('topUpPath').classList.toggle('inlet-active',!!top.motion_active);document.getElementById('drainPath').classList.toggle('discharge-active',!!drain.motion_active);document.getElementById('backwashPath').classList.toggle('backwash-active',!!bw.motion_active);
    const apEffect=bounded(ap.effectiveness,0,1),abEffect=bounded(ab.effectiveness,0,1);const bubbleStrength=Math.max(apEffect===null?0:apEffect*(ap.motion_active?1:0),abEffect===null?0:abEffect*(ab.motion_active?1:0));const bubbles=document.getElementById('pondBubbles');bubbles.classList.toggle('active',bubbleStrength>0);bubbles.style.opacity=bubbleStrength>0?String(.35+.65*bubbleStrength):'0';
    const main=document.getElementById('chipMain'),back=document.getElementById('chipBackup'),air=document.getElementById('chipAeration'),water=document.getElementById('chipWater');main.className=`device-chip chip-main${statusClass(primary)}`;back.className=`device-chip chip-backup${statusClass(backup)}`;air.className=`device-chip chip-aeration${statusClass(ap)||statusClass(ab)}`;water.className=`device-chip chip-water${(top.motion_active||drain.motion_active||bw.motion_active)?' active':''}`;
    main.querySelector('small').innerHTML=pathLabel(primary);back.querySelector('small').innerHTML=pathLabel(backup);air.querySelector('small').innerHTML=`Primary ${pathLabel(ap)}<br>Backup ${pathLabel(ab)}`;water.querySelector('small').innerHTML=`Top-up ${pathLabel(top)}<br>Drain ${pathLabel(drain)}<br>Backwash ${pathLabel(bw)}`;
    const flowLabel=flow===null?'Flow UNAVAILABLE':`${flow.toFixed(2)} L/min`;
    document.getElementById('pondStageMeta').innerHTML=`${esc(pv.classification)} · ${esc(pv.operating_mode)} / ${esc(pv.operating_phase)}<br>${flowLabel} · ${pv.simulation_paused?'PAUSED':'RUNNING'} · ${Number(pv.simulation_acceleration||1).toFixed(1)}×`;
    const rate=wm.quantitative_discharge_rate_l_min==null?'UNAVAILABLE':`${num(wm.quantitative_discharge_rate_l_min,2)} L/min`;
    document.getElementById('pondVisualWarning').textContent=`Discharge ${esc(wm.discharge_kind||'NONE')} · rate ${rate} · ${filterEvidence(mf)}`;
  }
  installStage();
  const baseRenderSnapshot=window.renderSnapshot;
  if(typeof baseRenderSnapshot==='function'){window.renderSnapshot=function(snapshot,options){baseRenderSnapshot(snapshot,options);renderProcessVisual(snapshot&&snapshot.process_visual)}}
  window.renderProcessVisual=renderProcessVisual;
  if(window.displayed&&window.displayed.process_visual)renderProcessVisual(window.displayed.process_visual);
})();
"""
