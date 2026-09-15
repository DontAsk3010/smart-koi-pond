# ruff: noqa: E501

OWNER_COCKPIT_MOTION_GUARD_STYLE = r"""
<style id="owner-cockpit-motion-guard-style">
.oc-scene.motion-paused .oc-waterline,
.oc-scene.motion-paused .oc-route.active,
.oc-scene.motion-paused .oc-bubbles i{animation-play-state:paused!important}

/* Owner test experience: pond remains visible; explanation is progressive disclosure. */
#faCockpitShortcut{display:none!important}
#functionalAcceptanceHarness .fa-note,
#functionalAcceptanceHarness .fa-warning,
#hardwareFaultCard .muted,
#safeRecoveryCard .muted{display:none!important}
#functionalAcceptanceHarness{padding:10px!important}
#functionalAcceptanceHarness .fa-head{margin-bottom:6px!important;align-items:center!important}
#functionalAcceptanceHarness .fa-title{font-size:12px!important;letter-spacing:.04em!important}
#functionalAcceptanceHarness .fa-badge{padding:3px 7px!important;font-size:9px!important}
#functionalAcceptanceHarness .fa-scenarios{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:5px!important;margin:6px 0!important}
#functionalAcceptanceHarness .fa-scenarios .btn{padding:6px 7px!important;min-height:32px!important}
#functionalAcceptanceHarness .fa-evidence{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:6px!important;margin-top:7px!important}
#functionalAcceptanceHarness .fa-panel{padding:7px!important;border-radius:8px!important}
#functionalAcceptanceHarness .fa-list{max-height:104px!important}
#functionalAcceptanceHarness .fa-status{min-height:0!important;margin-top:6px!important;padding:5px 7px!important}
.fa-compact-details{margin-top:7px;border:1px solid #203b50;border-radius:8px;background:#071521}
.fa-compact-details>summary{cursor:pointer;list-style:none;padding:7px 9px;font-size:10px;font-weight:800;color:#a9c0cf;letter-spacing:.04em}
.fa-compact-details>summary::-webkit-details-marker{display:none}
.fa-compact-details[open]>summary{border-bottom:1px solid #173146}
.fa-compact-details-body{padding:8px}
.fa-compact-details .fa-chemistry{grid-template-columns:repeat(3,minmax(0,1fr))!important;margin:0 0 7px!important}
.fa-compact-details .fa-source-actions{margin:0!important}
.fa-tech-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:8px}
.fa-tech-grid .fa-panel[style]{grid-column:auto!important}

.oc-test-dock{border-top:1px solid #20435a;margin-top:10px;padding-top:9px}
.oc-test-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}
.oc-test-head strong{font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:#d9edf7}
.oc-test-badge{font-size:9px;font-weight:850;padding:3px 7px;border:1px solid #31536a;border-radius:999px;color:#91b2c5;white-space:nowrap}
.oc-test-controls{display:grid;grid-template-columns:minmax(170px,1fr) auto auto auto;gap:6px;align-items:center}
.oc-test-controls select,.oc-test-controls .btn{min-height:32px}
.oc-test-controls .btn{padding:6px 9px;font-size:10px}
.oc-test-result{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:7px}
.oc-test-result>div{border:1px solid #1d3a4f;border-radius:8px;background:#071723;padding:7px 8px;min-width:0}
.oc-test-result small{display:block;color:#6f8ca1;font-size:8px;font-weight:850;letter-spacing:.08em;margin-bottom:3px}
.oc-test-result strong{display:block;color:#e7f4fa;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.oc-test-result span{display:block;color:#819daf;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
.oc-test-more{margin-top:6px;border:1px solid #1d384c;border-radius:7px;background:#07131e}
.oc-test-more>summary{cursor:pointer;list-style:none;padding:6px 8px;font-size:9px;font-weight:800;color:#8faaba}
.oc-test-more>summary::-webkit-details-marker{display:none}
.oc-test-more-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:5px;padding:7px;border-top:1px solid #173146;align-items:end}
.oc-test-more-grid label{display:block;font-size:8px;color:#708da0;margin-bottom:2px;text-transform:uppercase}
.oc-test-more-grid input{width:100%;min-width:0}
.oc-test-more-grid .btn{font-size:9px;padding:6px}

@media(max-width:1100px){
  #functionalAcceptanceHarness .fa-scenarios{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .fa-tech-grid{grid-template-columns:1fr}
  .oc-test-controls{grid-template-columns:1fr auto auto auto}
  .oc-test-more-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media(max-width:720px){
  .oc-test-controls{grid-template-columns:1fr 1fr}
  .oc-test-controls select{grid-column:1/-1}
  .oc-test-result{grid-template-columns:1fr}
  .oc-test-more-grid{grid-template-columns:1fr 1fr}
}
</style>
"""

OWNER_COCKPIT_MOTION_GUARD_SCRIPT = r"""
(function(){
  function syncCockpitMotion(snapshot){
    const scene=document.getElementById('ocScene');
    if(scene)scene.classList.toggle('motion-paused',!!snapshot?.simulation_paused);
  }

  const esc=v=>String(v??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const click=id=>{const e=document.getElementById(id);if(e)e.click()};

  function compactDetailedSimulator(){
    const harness=document.getElementById('functionalAcceptanceHarness');
    if(!harness||harness.dataset.compact==='1')return;
    harness.dataset.compact='1';
    const title=harness.querySelector('.fa-title');if(title)title.textContent='Functional Test & Response';
    const status=document.getElementById('faCommandStatus');if(status&&status.textContent.startsWith('Ready'))status.textContent='READY';

    const chemistry=harness.querySelector('.fa-chemistry');
    const source=harness.querySelector('.fa-source-actions');
    if(chemistry&&source){
      const advanced=document.createElement('details');advanced.className='fa-compact-details';
      advanced.innerHTML='<summary>Chemistry & water-change controls</summary><div class="fa-compact-details-body"></div>';
      const body=advanced.querySelector('.fa-compact-details-body');
      const chemistryLabel=chemistry.previousElementSibling;
      const sourceLabel=source.previousElementSibling;
      chemistry.parentNode.insertBefore(advanced,chemistryLabel||chemistry);
      if(chemistryLabel)body.appendChild(chemistryLabel);body.appendChild(chemistry);
      if(sourceLabel)body.appendChild(sourceLabel);body.appendChild(source);
    }

    const evidence=harness.querySelector('.fa-evidence');
    if(evidence){
      const panels=Array.from(evidence.children);
      if(panels.length>=7){
        const classification=panels[2],commands=panels[3],verification=panels[4];
        const rename=(panel,text)=>{const h=panel?.querySelector('h4');if(h)h.textContent=text};
        rename(classification,'Condition');rename(commands,'Action');rename(verification,'Result');
        const details=document.createElement('details');details.className='fa-compact-details';
        details.innerHTML='<summary>Technical evidence</summary><div class="fa-tech-grid"></div>';
        const tech=details.querySelector('.fa-tech-grid');
        [panels[0],panels[1],panels[5],panels[6]].forEach(p=>{if(p)tech.appendChild(p)});
        evidence.parentNode.insertBefore(details,evidence.nextSibling);
      }
    }
  }

  function installOwnerTestDock(){
    if(document.getElementById('ocOwnerTestDock'))return;
    const centerCard=document.querySelector('#ownerOperationalCockpit .oc-center .oc-card');
    const takeover=centerCard?.querySelector('.oc-takeover');
    if(!centerCard||!takeover)return;
    const dock=document.createElement('div');dock.id='ocOwnerTestDock';dock.className='oc-test-dock';dock.innerHTML=`
      <div class="oc-test-head"><strong>Test & Response</strong><span id="ocTestBadge" class="oc-test-badge">READY</span></div>
      <div class="oc-test-controls">
        <select id="ocTestPreset" aria-label="Test scenario">
          <option value="nitriteHigh">Nitrite High</option><option value="nitriteEmergency">Nitrite Emergency</option><option value="nitrateHigh">Nitrate High</option><option value="lowDo">Low DO</option><option value="phHigh">pH High</option><option value="phLow">pH Low</option><option value="pumpFail">Main Pump Failure</option>
        </select>
        <button class="btn danger" id="ocRunTest">Run</button><button class="btn ok" id="ocTestRepair">Repair</button><button class="btn" id="ocTestBaseline">Baseline</button>
      </div>
      <div class="oc-test-result">
        <div><small>Condition</small><strong id="ocTestCondition">—</strong><span id="ocTestConditionDetail">—</span></div>
        <div><small>Action</small><strong id="ocTestAction">—</strong><span id="ocTestActionDetail">—</span></div>
        <div><small>Result</small><strong id="ocTestResult">—</strong><span id="ocTestResultDetail">—</span></div>
      </div>
      <details class="oc-test-more"><summary>More tests</summary><div class="oc-test-more-grid">
        <div><label>TAN-N mg/L</label><input id="ocTestTan" type="number" min="0" step="0.01" value="0.50"></div>
        <div><label>pH</label><input id="ocTestPh" type="number" min="0" max="14" step="0.1" value="7.50"></div>
        <div><label>Temp °C</label><input id="ocTestTemp" type="number" step="0.1" value="20.0"></div>
        <button class="btn" id="ocTestChemistry">Apply NH3 Inputs</button><button class="btn danger" id="ocTestUnsafeSource">Unsafe Source</button><button class="btn ok" id="ocTestSafeSource">Safe Source</button>
        <div><label>Drain %</label><input id="ocTestDrain" type="number" min="0" max="100" step="0.1" value="80"></div>
        <div><label>Refill %</label><input id="ocTestRefill" type="number" min="0" max="100" step="0.1" value="85"></div>
        <button class="btn" id="ocTestWaterChange">Water Change</button>
      </div></details>`;
    takeover.insertAdjacentElement('afterend',dock);

    const presetTargets={nitriteHigh:'faNitriteHigh',nitriteEmergency:'faNitriteEmergency',nitrateHigh:'faNitrateHigh',lowDo:'faLowDo',phHigh:'faPhHigh',phLow:'faPhLow',pumpFail:'faPumpFail'};
    document.getElementById('ocRunTest').onclick=()=>{const v=document.getElementById('ocTestPreset').value;click(presetTargets[v]);const b=document.getElementById('ocTestBadge');if(b)b.textContent='RUNNING'};
    document.getElementById('ocTestRepair').onclick=()=>click('faPumpRepair');
    document.getElementById('ocTestBaseline').onclick=()=>click('faRestoreBaseline');
    document.getElementById('ocTestChemistry').onclick=()=>{
      const map=[['faTan','ocTestTan'],['faPh','ocTestPh'],['faTemp','ocTestTemp']];map.forEach(([to,from])=>{const a=document.getElementById(to),b=document.getElementById(from);if(a&&b)a.value=b.value});click('faApplyChemistry');
    };
    document.getElementById('ocTestUnsafeSource').onclick=()=>click('faUnsafeSource');
    document.getElementById('ocTestSafeSource').onclick=()=>click('faSafeSource');
    document.getElementById('ocTestWaterChange').onclick=()=>{
      const d=document.getElementById('faDrainTarget'),r=document.getElementById('faRefillTarget'),od=document.getElementById('ocTestDrain'),or=document.getElementById('ocTestRefill');if(d&&od)d.value=od.value;if(r&&or)r.value=or.value;click('faAttemptWaterChange');
    };
  }

  function renderOwnerTest(snapshot){
    if(!snapshot)return;installOwnerTestDock();
    const condition=document.getElementById('ocTestCondition'),conditionDetail=document.getElementById('ocTestConditionDetail'),action=document.getElementById('ocTestAction'),actionDetail=document.getElementById('ocTestActionDetail'),result=document.getElementById('ocTestResult'),resultDetail=document.getElementById('ocTestResultDetail'),badge=document.getElementById('ocTestBadge');
    const state=snapshot.classification?.state||'UNAVAILABLE';const reasons=snapshot.classification?.reasons||[];
    if(condition)condition.textContent=state;if(conditionDetail)conditionDetail.textContent=reasons.slice(0,2).join(' · ')||'No active reason';
    const commands=Object.values(snapshot.commands||{});const last=commands.length?commands[commands.length-1]:null;
    if(action)action.textContent=last?`${last.asset_id} ${last.final_on?'ON':'OFF'}`:'NO COMMAND';
    if(actionDetail)actionDetail.textContent=last?`${last.accepted?'ACCEPTED':'INHIBITED'} · ${last.reason||last.owner||'—'}`:'Canonical controller has no command in this cycle';
    const ver=(snapshot.verification||[]);const latest=ver.length?ver[ver.length-1]:null;const wr=snapshot.water_recovery?.water_quality||{};
    if(result)result.textContent=latest?.status||wr.last_outcome||'UNAVAILABLE';
    const flow=snapshot.process_visual?.circulation?.measured_total_flow_l_min;
    if(resultDetail)resultDetail.textContent=`${latest?.asset_id||'No verification task'} · flow ${flow==null?'UNAVAILABLE':`${Number(flow).toFixed(1)} L/min`}`;
    if(badge)badge.textContent=snapshot.execution_mode==='SIMULATION'?state:(snapshot.execution_mode||'UNKNOWN');
  }

  compactDetailedSimulator();installOwnerTestDock();
  const baseRenderSnapshot=window.renderSnapshot;
  if(typeof baseRenderSnapshot==='function'){
    window.renderSnapshot=function(snapshot,options){
      baseRenderSnapshot(snapshot,options);
      syncCockpitMotion(snapshot);
      renderOwnerTest(snapshot);
      compactDetailedSimulator();
    };
  }
  if(window.displayed){syncCockpitMotion(window.displayed);renderOwnerTest(window.displayed)}
})();
"""
