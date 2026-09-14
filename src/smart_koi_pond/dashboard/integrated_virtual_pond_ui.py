# ruff: noqa: E501

INTEGRATED_VIRTUAL_POND_STYLE = r"""
<style id="integrated-virtual-pond-style">
.ivp-status{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px;margin:8px 0}.ivp-badge{border:1px solid var(--line);border-radius:8px;padding:9px;background:#0a1725}.ivp-badge b{display:block;margin-bottom:4px}.ivp-ready{border-color:#2f7656}.ivp-required{border-color:#8a6726}.ivp-form{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px}.ivp-field{display:flex;flex-direction:column;gap:4px}.ivp-field label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}.ivp-field input,.ivp-field select{width:100%}.ivp-wide{grid-column:span 2}.ivp-full{grid-column:1/-1}.ivp-evidence{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:8px}.ivp-evidence .asset{min-height:76px}.ivp-value{font-size:19px;font-weight:750}.ivp-input-note{border-left:3px solid #b68624;background:#2a210d;padding:9px 11px;margin:8px 0;color:#f2d58b}.ivp-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.ivp-raw{max-height:250px}.ivp-section-title{font-weight:800;margin-bottom:7px}.ivp-source{font-size:11px;color:var(--muted)}
@media(max-width:1100px){.ivp-form{grid-template-columns:repeat(2,minmax(150px,1fr))}.ivp-evidence{grid-template-columns:repeat(3,minmax(120px,1fr))}.ivp-status{grid-template-columns:repeat(2,minmax(150px,1fr))}}
@media(max-width:600px){.ivp-form,.ivp-evidence,.ivp-status{grid-template-columns:1fr}.ivp-wide,.ivp-full{grid-column:span 1}}
</style>
"""

INTEGRATED_VIRTUAL_POND_SCRIPT = r"""
(function(){
  function el(id){return document.getElementById(id)}
  function finiteOrNull(id){const raw=el(id)?.value?.trim();if(!raw)return null;const n=Number(raw);if(!Number.isFinite(n))throw new Error(`${id} must be numeric`);return n}
  function requiredNumber(id){const n=finiteOrNull(id);if(n===null)throw new Error(`${id}: INPUT REQUIRED`);return n}
  function requiredText(id){const v=(el(id)?.value||'').trim();if(!v)throw new Error(`${id}: INPUT REQUIRED`);return v}
  function display(v,unit=''){return v===null||v===undefined?'INPUT REQUIRED':`${Number(v).toFixed(3)}${unit}`}
  function badge(id,label,ready,detail){const n=el(id);if(!n)return;n.className=`ivp-badge ${ready?'ivp-ready':'ivp-required'}`;n.innerHTML=`<b>${label}: ${ready?'CONFIGURED':'INPUT REQUIRED'}</b><span class="muted">${escapeHtml(detail||'')}</span>`}
  async function ivpCommand(action,payload={},role='engineering'){
    if(typeof playbackMode!=='undefined'&&playbackMode){throw new Error('PLAYBACK / READ ONLY')}
    const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json','X-Koi-Role':role},body:JSON.stringify({action,payload})});
    const j=await r.json();if(!r.ok)throw new Error(j.error||'command failed');
    if(j.publication){cursor=0;eventBuffer=[];renderPublication(j.publication)}
    text('commandResult',`${action}: accepted`);return j;
  }
  function installIntegratedView(){
    if(el('integrated'))return;
    const tabs=el('tabs');const main=document.querySelector('main');if(!tabs||!main)return;
    const button=document.createElement('button');button.dataset.view='integrated';button.textContent='Integrated Pond';tabs.appendChild(button);
    const section=document.createElement('section');section.id='integrated';section.className='view';section.innerHTML=`
      <div class="grid">
        <div class="card span12"><div class="label">Integrated Virtual Pond — Canonical Runtime</div><div class="ivp-input-note"><b>No hidden engineering defaults.</b> Pond/hydraulic, biological and mechanical-filter facts remain INPUT REQUIRED until explicitly entered. The water values visible before configuration are simulation initial-state values, not measurements from a physical pond.</div><div class="ivp-status"><div id="ivpDesignStatus" class="ivp-badge"></div><div id="ivpHydStatus" class="ivp-badge"></div><div id="ivpBioStatus" class="ivp-badge"></div><div id="ivpFilterStatus" class="ivp-badge"></div></div></div>
        <div class="card span12"><div class="label">Live Process Evidence</div><div class="ivp-evidence">
          <div class="asset"><div class="label">TAN / Ammonia-N</div><div id="ivpTan" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Nitrite</div><div id="ivpNitrite" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Nitrate</div><div id="ivpNitrate" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Alkalinity / KH</div><div id="ivpKh" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Suspended Waste</div><div id="ivpWaste" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Captured Solids</div><div id="ivpCaptured" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Filter Loading</div><div id="ivpLoading" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Filter Restriction</div><div id="ivpFilterFactor" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">TSS</div><div id="ivpTss" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Turbidity</div><div id="ivpTurbidity" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Backwash Removed</div><div id="ivpBackwashRemoved" class="ivp-value">—</div></div>
          <div class="asset"><div class="label">Backwash Discharge</div><div id="ivpDischarge" class="ivp-value">—</div></div>
        </div><div id="ivpHardwareEvidence" class="ivp-source"></div></div>
        <div class="card span12"><div class="ivp-section-title">1. Pond & Hydraulics — explicit configuration</div><div class="ivp-form">
          <div class="ivp-field"><label>Profile ID</label><input id="ivpProfileId" value="owner-pond-profile"></div>
          <div class="ivp-field"><label>Revision</label><input id="ivpProfileRevision" value="r1"></div>
          <div class="ivp-field"><label>Effective volume (L)</label><input id="ivpVolume" type="number" min="1" placeholder="INPUT REQUIRED"></div>
          <div class="ivp-field"><label>Turnover guide (/hour)</label><input id="ivpTurnover" type="number" min="0.01" step="0.01" placeholder="INPUT REQUIRED"></div>
          <div class="ivp-field"><label>Main pump rated flow (L/min)</label><input id="ivpMainFlow" type="number" min="0" placeholder="INPUT REQUIRED"></div>
          <div class="ivp-field"><label>Backup pump rated flow (L/min)</label><input id="ivpBackupFlow" type="number" min="0" placeholder="optional"></div>
          <div class="ivp-field"><label>Top-up flow (L/min)</label><input id="ivpTopupFlow" type="number" min="0" placeholder="optional"></div>
          <div class="ivp-field"><label>Drain flow (L/min)</label><input id="ivpDrainFlow" type="number" min="0" placeholder="optional"></div>
          <div class="ivp-field"><label>Biomass (kg)</label><input id="ivpBiomass" type="number" min="0" placeholder="optional until biology"></div>
          <div class="ivp-field"><label>Feed (kg/day)</label><input id="ivpFeed" type="number" min="0" step="0.001" placeholder="optional until biology"></div>
        </div><div class="ivp-actions"><button class="btn ok" onclick="window.configureIntegratedPond()">Apply Pond / Hydraulic Profile</button><button class="btn" onclick="window.ivpManual('main_pump',true)">Main Pump ON</button><button class="btn" onclick="window.ivpManual('main_pump',false)">Main Pump OFF</button><button class="btn" onclick="window.ivpManual('primary_aerator',true)">Aerator ON</button><button class="btn" onclick="window.ivpManual('primary_aerator',false)">Aerator OFF</button></div></div>
        <div class="card span12"><div class="ivp-section-title">2. Biology / Environment — source-backed or owner-entered values</div><div class="ivp-input-note">A source/reference is required. These fields are intentionally blank; the application will not silently invent biofilter or biological constants.</div><div class="ivp-form">
          <div class="ivp-field ivp-wide"><label>Source / reference</label><input id="ivpBioSource" placeholder="INPUT REQUIRED — manual/datasheet/reference"></div>
          <div class="ivp-field"><label>Biofilter ammonia capacity (g N/day)</label><input id="ivpBioAmmoniaCap" type="number" min="0" placeholder="required"></div>
          <div class="ivp-field"><label>Biofilter nitrite capacity (g N/day)</label><input id="ivpBioNitriteCap" type="number" min="0" placeholder="required"></div>
          <div class="ivp-field"><label>Fish O2 demand (g O2/kg/hour)</label><input id="ivpFishO2" type="number" min="0" step="0.001" placeholder="required"></div>
          <div class="ivp-field"><label>Feed O2 demand (g O2/kg feed)</label><input id="ivpFeedO2" type="number" min="0" step="0.001" placeholder="required"></div>
          <div class="ivp-field"><label>Ammonia-N generation (g/kg feed)</label><input id="ivpAmmoniaGen" type="number" min="0" step="0.001" placeholder="required"></div>
          <div class="ivp-field"><label>Solid waste (g/kg feed)</label><input id="ivpSolidWaste" type="number" min="0" step="0.001" placeholder="required"></div>
          <div class="ivp-field"><label>Nitrification O2 (g O2/g N)</label><input id="ivpNitrificationO2" type="number" min="0" step="0.001" placeholder="required"></div>
          <div class="ivp-field"><label>Alkalinity use (g CaCO3/g N)</label><input id="ivpAlkalinityUse" type="number" min="0" step="0.001" placeholder="required"></div>
          <div class="ivp-field"><label>Nitrification DO reference (mg/L)</label><input id="ivpDoReference" type="number" min="0" step="0.01" placeholder="required"></div>
          <div class="ivp-field"><label>pH drop per 100 mg/L alkalinity loss</label><input id="ivpPhDrop" type="number" min="0" step="0.001" placeholder="required"></div>
        </div><div class="ivp-actions"><button class="btn ok" onclick="window.configureIntegratedBiology()">Apply Biology Profile</button></div></div>
        <div class="card span12"><div class="ivp-section-title">3. Mechanical Filter — explicit device/process data</div><div class="ivp-form">
          <div class="ivp-field ivp-wide"><label>Source / reference</label><input id="ivpFilterSource" placeholder="INPUT REQUIRED — datasheet/manual/owner reference"></div>
          <div class="ivp-field"><label>Filtered route</label><select id="ivpFilterRoute"><option value="main-circulation">main-circulation</option><option value="backup-circulation">backup-circulation</option></select></div>
          <div class="ivp-field"><label>Capture efficiency / pass (0..1)</label><input id="ivpCaptureEff" type="number" min="0" max="1" step="0.01" placeholder="required"></div>
          <div class="ivp-field"><label>Max captured solids (g)</label><input id="ivpMaxSolids" type="number" min="0" placeholder="required"></div>
          <div class="ivp-field"><label>Min throughput at capacity (0..1)</label><input id="ivpMinThroughput" type="number" min="0" max="1" step="0.01" placeholder="required"></div>
          <div class="ivp-field"><label>Backwash solids removal (g/min)</label><input id="ivpBackwashRemoval" type="number" min="0" placeholder="required"></div>
          <div class="ivp-field"><label>Backwash discharge (L/min)</label><input id="ivpBackwashFlow" type="number" min="0" placeholder="optional / unknown allowed"></div>
          <div class="ivp-field"><label>Turbidity correlation (NTU per mg/L TSS)</label><input id="ivpTurbidityCorr" type="number" min="0" step="0.001" placeholder="optional / unknown allowed"></div>
        </div><div class="ivp-actions"><button class="btn ok" onclick="window.configureIntegratedFilter()">Apply Mechanical Filter</button><button class="btn" onclick="window.ivpBackwash()">Start Governed Filter Clean / Backwash</button></div></div>
        <div class="card span12"><div class="ivp-section-title">4. Water-state disturbance — Digital Twin only</div><div class="controls"><select id="ivpDisturbanceParam"><option value="do">DO (mg/L)</option><option value="ph">pH</option><option value="tan">TAN (mg/L)</option><option value="nitrite">Nitrite (mg/L)</option><option value="nitrate">Nitrate (mg/L)</option><option value="alkalinity">Alkalinity / KH (mg/L as CaCO3)</option><option value="waste_solids">Waste solids (g)</option><option value="water_level">Water level (%)</option><option value="temperature">Temperature (°C)</option></select><input id="ivpDisturbanceValue" type="number" step="0.01" placeholder="value"><button class="btn danger" onclick="window.ivpDisturb()">Apply Simulation Disturbance</button><button class="btn" onclick="window.ivpSafeReset()">Safe Runtime Reset</button></div><div class="notice">Disturbances act through the governed Scenario Controller. They never write real hardware.</div></div>
        <div class="card span12"><div class="label">Canonical Integrated State (Engineering view)</div><pre id="ivpRawState" class="ivp-raw">—</pre></div>
      </div>`;
    main.appendChild(section);
  }
  function renderIntegrated(s){
    installIntegratedView();if(!s)return;
    const design=s.design_profile||{},hyd=s.hydraulics||{},bio=s.biology||{},p=s.pond_truth||{};
    const mech=hyd.mechanical_filtration||{};
    badge('ivpDesignStatus','Pond Profile',!!design.configured,design.configured?`${display(design.effective_volume_l,' L')} · ${escapeHtml(design.provenance||'UNKNOWN')}`:'volume / routes / turnover not configured');
    badge('ivpHydStatus','Hydraulics',!!hyd.configured,hyd.configured?`${display(hyd.total_effective_flow_l_min,' L/min')} · requirement ${display(hyd.required_circulation_flow_l_min,' L/min')}`:'route-aware hydraulic model waiting for Pond Profile');
    badge('ivpBioStatus','Biology',!!bio.configured,bio.configured?`${escapeHtml(bio.status||'CONFIGURED')} · ${escapeHtml(bio.provenance||'UNKNOWN')}`:'explicit source/reference and parameters required');
    badge('ivpFilterStatus','Mechanical Filter',!!mech.configured,mech.configured?`${escapeHtml(mech.loading_status||'CONFIGURED')} · ${escapeHtml(mech.provenance||'UNKNOWN')}`:'explicit filter source/reference and parameters required');
    text('ivpTan',display(p.total_ammonia_nitrogen_mg_l,' mg/L'));text('ivpNitrite',display(p.nitrite_mg_l,' mg/L'));text('ivpNitrate',display(p.nitrate_mg_l,' mg/L'));text('ivpKh',display(p.alkalinity_mg_l_as_caco3,' mg/L'));text('ivpWaste',display(p.waste_solids_g,' g'));text('ivpCaptured',display(mech.captured_solids_g,' g'));text('ivpLoading',mech.loading_fraction==null?'INPUT REQUIRED':`${(Number(mech.loading_fraction)*100).toFixed(1)} %`);text('ivpFilterFactor',mech.process_throughput_factor==null?'INPUT REQUIRED':Number(mech.process_throughput_factor).toFixed(3));text('ivpTss',display(mech.tss_mg_l,' mg/L'));text('ivpTurbidity',display(mech.turbidity_ntu,' NTU'));text('ivpBackwashRemoved',display(mech.last_backwash_removed_g,' g'));text('ivpDischarge',display(mech.last_backwash_discharge_l,' L'));
    text('ivpHardwareEvidence',`Hardware conclusion: ${hyd.hardware_fault_conclusion||mech.hardware_fault_conclusion||'NOT ESTABLISHED'} · upgrade required: ${hyd.hardware_upgrade_required===true||mech.hardware_upgrade_required===true?'YES':'NO / NOT ESTABLISHED'} · sizing guidance is not a hardware lock.`);
    text('ivpRawState',JSON.stringify({design_profile:design,hydraulics:hyd,biology:bio,pond_truth:p,classification:s.classification,operating_status:s.operating_status},null,2));
  }
  window.configureIntegratedPond=async function(){try{
    const backup=finiteOrNull('ivpBackupFlow');const routes=[{route_id:'main-circulation',asset_id:'main_pump',rated_flow_l_min:requiredNumber('ivpMainFlow'),role:'PRIMARY',base_throughput_factor:1,provenance:'USER_CONFIGURED_SCENARIO'}];if(backup!==null)routes.push({route_id:'backup-circulation',asset_id:'backup_pump',rated_flow_l_min:backup,role:'BACKUP',base_throughput_factor:1,provenance:'USER_CONFIGURED_SCENARIO'});
    const profile={profile_id:requiredText('ivpProfileId'),revision:requiredText('ivpProfileRevision'),effective_volume_l:requiredNumber('ivpVolume'),circulation_turnovers_per_hour_guide:requiredNumber('ivpTurnover'),routes,top_up_flow_l_min:finiteOrNull('ivpTopupFlow'),drain_flow_l_min:finiteOrNull('ivpDrainFlow'),biomass_kg:finiteOrNull('ivpBiomass'),feed_kg_per_day:finiteOrNull('ivpFeed'),provenance:'USER_CONFIGURED_SCENARIO'};
    await ivpCommand('configure_design_profile',{profile,actor:'owner-ui'});
  }catch(e){text('commandResult',`configure_design_profile: ${e.message}`)}};
  window.configureIntegratedBiology=async function(){try{const profile={profile_id:'owner-biology-profile',revision:'r1',source_reference:requiredText('ivpBioSource'),biofilter_ammonia_capacity_g_n_per_day:requiredNumber('ivpBioAmmoniaCap'),biofilter_nitrite_capacity_g_n_per_day:requiredNumber('ivpBioNitriteCap'),fish_oxygen_demand_g_o2_per_kg_hour:requiredNumber('ivpFishO2'),feed_oxygen_demand_g_o2_per_kg_feed:requiredNumber('ivpFeedO2'),ammonia_n_generation_g_per_kg_feed:requiredNumber('ivpAmmoniaGen'),solid_waste_g_per_kg_feed:requiredNumber('ivpSolidWaste'),nitrification_oxygen_g_o2_per_g_n:requiredNumber('ivpNitrificationO2'),alkalinity_consumption_g_caco3_per_g_n:requiredNumber('ivpAlkalinityUse'),nitrification_do_reference_mg_l:requiredNumber('ivpDoReference'),ph_drop_per_100_mg_l_alkalinity_loss:requiredNumber('ivpPhDrop'),provenance:'USER_CONFIGURED_SCENARIO'};await ivpCommand('configure_biological_profile',{profile,actor:'owner-ui'})}catch(e){text('commandResult',`configure_biological_profile: ${e.message}`)}};
  window.configureIntegratedFilter=async function(){try{const profile={profile_id:'owner-mechanical-filter',revision:'r1',source_reference:requiredText('ivpFilterSource'),filtered_route_id:el('ivpFilterRoute').value,capture_efficiency_per_pass:requiredNumber('ivpCaptureEff'),max_captured_solids_g:requiredNumber('ivpMaxSolids'),minimum_route_throughput_factor_at_capacity:requiredNumber('ivpMinThroughput'),backwash_solids_removal_g_per_min:requiredNumber('ivpBackwashRemoval'),backwash_discharge_flow_l_min:finiteOrNull('ivpBackwashFlow'),turbidity_ntu_per_mg_l_tss:finiteOrNull('ivpTurbidityCorr'),provenance:'USER_CONFIGURED_SCENARIO'};await ivpCommand('configure_mechanical_filtration_profile',{profile,actor:'owner-ui'})}catch(e){text('commandResult',`configure_mechanical_filtration_profile: ${e.message}`)}};
  window.ivpDisturb=async function(){try{await ivpCommand('set_environment_state',{parameter:el('ivpDisturbanceParam').value,value:requiredNumber('ivpDisturbanceValue')})}catch(e){text('commandResult',`set_environment_state: ${e.message}`)}};
  window.ivpManual=async function(asset,on){try{await ivpCommand('manual_command',{asset_id:asset,on,reason:'INTEGRATED_VIRTUAL_POND_UI'},'engineering')}catch(e){text('commandResult',`manual_command: ${e.message}`)}};
  window.ivpBackwash=async function(){try{await ivpCommand('start_filter_clean',{service_scope:['mechanical_filter'],reason:'INTEGRATED_VIRTUAL_POND_UI'},'engineering')}catch(e){text('commandResult',`start_filter_clean: ${e.message}`)}};
  window.ivpSafeReset=async function(){try{await ivpCommand('safe_runtime_reset',{},'engineering')}catch(e){text('commandResult',`safe_runtime_reset: ${e.message}`)}};
  installIntegratedView();const base=window.renderSnapshot;if(typeof base==='function'){window.renderSnapshot=function(snapshot,options){base(snapshot,options);renderIntegrated(snapshot)}}window.renderIntegratedPond=renderIntegrated;if(typeof displayed!=='undefined'&&displayed)renderIntegrated(displayed);
})();
"""
