# ruff: noqa: E501

SOURCE_WATER_UI_SCRIPT = r"""
(function(){
  function e(id){return document.getElementById(id)}
  function maybeNumber(id){const raw=e(id)?.value?.trim();if(!raw)return null;const n=Number(raw);if(!Number.isFinite(n))throw new Error(`${id} must be numeric`);return n}
  function requiredText(id){const value=(e(id)?.value||'').trim();if(!value)throw new Error(`${id}: INPUT REQUIRED`);return value}
  function show(value,unit=''){return value===null||value===undefined?'INPUT REQUIRED':`${Number(value).toFixed(3)}${unit}`}
  async function command(action,payload={}){
    if(typeof playbackMode!=='undefined'&&playbackMode)throw new Error('PLAYBACK / READ ONLY');
    const response=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json','X-Koi-Role':'engineering'},body:JSON.stringify({action,payload})});
    const body=await response.json();if(!response.ok)throw new Error(body.error||'command failed');
    if(body.publication){cursor=0;eventBuffer=[];renderPublication(body.publication)}
    text('commandResult',`${action}: accepted`);return body;
  }
  function install(){
    const integrated=e('integrated');if(!integrated||e('ivpSourceWaterCard'))return;
    const grid=integrated.querySelector('.grid');if(!grid)return;
    const card=document.createElement('div');card.id='ivpSourceWaterCard';card.className='card span12';card.innerHTML=`
      <div class="ivp-section-title">Source Water & Water Exchange — explicit chemistry / mass balance</div>
      <div class="ivp-input-note"><b>Tap / municipal / well / rain is only a source label.</b> It never creates chemistry values. Blank values remain INPUT REQUIRED. Backwash/drain discharge alone removes water and dissolved mass proportionally; concentration changes when replacement water is mixed or another selective process acts.</div>
      <div class="ivp-form">
        <div class="ivp-field"><label>Profile ID</label><input id="swProfileId" value="owner-source-water"></div>
        <div class="ivp-field"><label>Revision</label><input id="swRevision" value="r1"></div>
        <div class="ivp-field"><label>Source type</label><select id="swType"><option value="MUNICIPAL_TAP">Municipal / tap</option><option value="WELL">Well</option><option value="RAIN">Rain</option><option value="OTHER">Other</option></select></div>
        <div class="ivp-field"><label>Source / measurement reference</label><input id="swReference" placeholder="INPUT REQUIRED"></div>
        <div class="ivp-field"><label>Temperature (°C)</label><input id="swTemp" type="number" step="0.01" placeholder="unknown allowed"></div>
        <div class="ivp-field"><label>DO (mg/L)</label><input id="swDo" type="number" min="0" step="0.01" placeholder="unknown allowed"></div>
        <div class="ivp-field"><label>pH</label><input id="swPh" type="number" min="0" max="14" step="0.01" placeholder="unknown allowed"></div>
        <div class="ivp-field"><label>TAN / Ammonia-N (mg/L)</label><input id="swTan" type="number" min="0" step="0.001" placeholder="unknown allowed"></div>
        <div class="ivp-field"><label>Nitrite (mg/L)</label><input id="swNitrite" type="number" min="0" step="0.001" placeholder="unknown allowed"></div>
        <div class="ivp-field"><label>Nitrate (mg/L)</label><input id="swNitrate" type="number" min="0" step="0.001" placeholder="unknown allowed"></div>
        <div class="ivp-field"><label>Alkalinity / KH (mg/L as CaCO3)</label><input id="swKh" type="number" min="0" step="0.1" placeholder="unknown allowed"></div>
      </div>
      <div class="ivp-actions"><button class="btn ok" onclick="window.configureSourceWater()">Apply Source-Water Profile</button></div>
      <div class="ivp-form" style="margin-top:10px">
        <div class="ivp-field"><label>Water-change drain target (%)</label><input id="swDrainTarget" type="number" min="0" max="100" step="0.1" placeholder="e.g. 70"></div>
        <div class="ivp-field"><label>Water-change refill target (%)</label><input id="swRefillTarget" type="number" min="0" max="100" step="0.1" placeholder="e.g. 90"></div>
      </div>
      <div class="ivp-actions"><button class="btn" onclick="window.startGovernedWaterChange()">Start Governed Water Change</button></div>
      <div class="ivp-evidence" style="margin-top:10px">
        <div class="asset"><div class="label">Source Profile</div><div id="swProfileStatus" class="ivp-value">INPUT REQUIRED</div></div>
        <div class="asset"><div class="label">Last Discharge</div><div id="swDischarge" class="ivp-value">—</div></div>
        <div class="asset"><div class="label">Last Refill</div><div id="swRefill" class="ivp-value">—</div></div>
        <div class="asset"><div class="label">Nitrate after mix</div><div id="swNitrateAfter" class="ivp-value">—</div></div>
        <div class="asset"><div class="label">Nitrite after mix</div><div id="swNitriteAfter" class="ivp-value">—</div></div>
        <div class="asset"><div class="label">pH mix evidence</div><div id="swPhStatus" class="ivp-value" style="font-size:12px">—</div></div>
      </div>
      <div id="swEvidenceNote" class="ivp-source"></div>`;
    const raw=e('ivpRawState')?.closest('.card');if(raw)grid.insertBefore(card,raw);else grid.appendChild(card);
  }
  function result(exchange,name){return exchange?.last_exchange?.parameter_results?.[name]||null}
  function render(snapshot){
    install();if(!snapshot)return;
    const exchange=snapshot.hydraulics?.water_exchange||{};const source=exchange.source_water||{};const last=exchange.last_exchange||{};
    text('swProfileStatus',source.configured?`${source.profile_id} / ${source.revision}`:'INPUT REQUIRED');
    text('swDischarge',show(last.discharge_l,' L'));text('swRefill',show(last.refill_l,' L'));
    const nitrate=result(exchange,'nitrate_mg_l');const nitrite=result(exchange,'nitrite_mg_l');const ph=result(exchange,'ph');
    text('swNitrateAfter',nitrate?show(nitrate.after,' mg/L'):'—');text('swNitriteAfter',nitrite?show(nitrite.after,' mg/L'):'—');text('swPhStatus',ph?ph.status:'—');
    text('swEvidenceNote',`Model: ${exchange.model||'INPUT REQUIRED'} · source provenance: ${source.provenance||'UNAVAILABLE'} · pH laboratory-equilibrium claim: ${exchange.ph_model_is_laboratory_equilibrium===true?'YES':'NO'}`);
  }
  window.configureSourceWater=async function(){try{
    const profile={profile_id:requiredText('swProfileId'),revision:requiredText('swRevision'),source_reference:requiredText('swReference'),source_type:e('swType').value,temperature_c:maybeNumber('swTemp'),dissolved_oxygen_mg_l:maybeNumber('swDo'),ph:maybeNumber('swPh'),total_ammonia_nitrogen_mg_l:maybeNumber('swTan'),nitrite_mg_l:maybeNumber('swNitrite'),nitrate_mg_l:maybeNumber('swNitrate'),alkalinity_mg_l_as_caco3:maybeNumber('swKh'),provenance:'USER_CONFIGURED_SCENARIO'};
    await command('configure_source_water_profile',{profile,actor:'owner-ui'});
  }catch(err){text('commandResult',`configure_source_water_profile: ${err.message}`)}};
  window.startGovernedWaterChange=async function(){try{
    const drain=maybeNumber('swDrainTarget'),refill=maybeNumber('swRefillTarget');if(drain===null||refill===null)throw new Error('drain/refill targets: INPUT REQUIRED');if(refill<drain)throw new Error('refill target must be at or above drain target');
    await command('start_water_change',{target_drain_level_pct:drain,target_refill_level_pct:refill,reason:'INTEGRATED_VIRTUAL_POND_SOURCE_WATER_UI'});
  }catch(err){text('commandResult',`start_water_change: ${err.message}`)}};
  window.ivpBackwash=async function(){try{await command('start_filter_clean',{service_scope:[],reason:'INTEGRATED_VIRTUAL_POND_UI'})}catch(err){text('commandResult',`start_filter_clean: ${err.message}`)}};
  const previous=window.renderSnapshot;if(typeof previous==='function'){window.renderSnapshot=function(snapshot,options){previous(snapshot,options);render(snapshot)}}
  install();if(typeof displayed!=='undefined'&&displayed)render(displayed);
})();
"""
