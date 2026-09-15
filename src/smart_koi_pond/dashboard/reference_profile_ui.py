# ruff: noqa: E501

import json

from smart_koi_pond.digital_twin.hydraulics import reference_standard_metric_v1

_REFERENCE_PROFILE_JSON = json.dumps(
    reference_standard_metric_v1().to_dict(),
    separators=(",", ":"),
)

REFERENCE_PROFILE_UI_SCRIPT = f"""
(function(){{
  const REFERENCE_PROFILE={_REFERENCE_PROFILE_JSON};
  const byId=(id)=>document.getElementById(id);
  const numberOrNull=(id)=>{{
    const raw=(byId(id)?.value||'').trim();
    if(!raw)return null;
    const value=Number(raw);
    if(!Number.isFinite(value))throw new Error(`${{id}} must be numeric`);
    return value;
  }};
  const textOr=(id,fallback)=>((byId(id)?.value||'').trim()||fallback);
  async function command(action,payload={{}},role='engineering'){{
    if(typeof playbackMode!=='undefined'&&playbackMode)throw new Error('PLAYBACK / READ ONLY');
    const response=await fetch('/api/command',{{
      method:'POST',
      headers:{{'Content-Type':'application/json','X-Koi-Role':role}},
      body:JSON.stringify({{action,payload}})
    }});
    const body=await response.json();
    if(!response.ok)throw new Error(body.error||'command failed');
    if(body.publication){{cursor=0;eventBuffer=[];renderPublication(body.publication)}}
    return body;
  }}
  function setValue(id,value){{const node=byId(id);if(node)node.value=value??''}}
  function sameNumber(a,b){{
    if(a===null||a===undefined||b===null||b===undefined)return a==null&&b==null;
    return Math.abs(Number(a)-Number(b))<1e-9;
  }}
  function referenceMainRoute(){{return REFERENCE_PROFILE.routes[0]}}
  function findPondActions(form){{
    const parent=form?.parentElement;
    if(!parent)return null;
    return Array.from(parent.children).find((node)=>node.classList?.contains('ivp-actions'))||null;
  }}
  function setPondFeedback(message,ok=true){{
    const form=byId('ivpVolume')?.closest('.ivp-form');
    if(!form)return;
    const actions=findPondActions(form);
    let node=byId('ivpPondProfileFeedback');
    if(!node){{
      node=document.createElement('div');
      node.id='ivpPondProfileFeedback';
      node.className='ivp-input-note';
      if(actions)actions.insertAdjacentElement('afterend',node);
      else form.insertAdjacentElement('afterend',node);
    }}
    node.style.borderLeftColor=ok?'#2f7656':'#a83f49';
    node.textContent=message;
  }}
  function populateReferenceFields(){{
    setValue('ivpProfileId',REFERENCE_PROFILE.profile_id);
    setValue('ivpProfileRevision',REFERENCE_PROFILE.revision);
    setValue('ivpLength',REFERENCE_PROFILE.length_m);
    setValue('ivpWidth',REFERENCE_PROFILE.width_m);
    setValue('ivpDepth',REFERENCE_PROFILE.water_depth_m);
    setValue('ivpVolume',REFERENCE_PROFILE.effective_volume_l);
    setValue('ivpTurnover',REFERENCE_PROFILE.circulation_turnovers_per_hour_guide);
    setValue('ivpMainFlow',referenceMainRoute().rated_flow_l_min);
    setValue('ivpBackupFlow','');
    setValue('ivpTopupFlow','');
    setValue('ivpDrainFlow','');
    setValue('ivpBiomass','');
    setValue('ivpFeed','');
  }}
  function installReferenceProfileControls(){{
    const integrated=byId('integrated');
    if(!integrated)return;
    const form=byId('ivpVolume')?.closest('.ivp-form');
    if(!form)return;
    const volumeField=byId('ivpVolume')?.closest('.ivp-field');
    if(!byId('ivpLength')){{
      const lengthField=document.createElement('div');
      lengthField.className='ivp-field';
      lengthField.innerHTML='<label>Length (m)</label><input id="ivpLength" type="number" min="0.01" step="0.01">';
      form.insertBefore(lengthField,volumeField);
    }}
    if(!byId('ivpWidth')){{
      const widthField=document.createElement('div');
      widthField.className='ivp-field';
      widthField.innerHTML='<label>Width (m)</label><input id="ivpWidth" type="number" min="0.01" step="0.01">';
      form.insertBefore(widthField,volumeField);
    }}
    if(!byId('ivpDepth')){{
      const depthField=document.createElement('div');
      depthField.className='ivp-field';
      depthField.innerHTML='<label>Water depth (m)</label><input id="ivpDepth" type="number" min="0.01" step="0.01">';
      form.insertBefore(depthField,volumeField);
    }}

    if(!byId('ivpReferenceProfilePanel')){{
      const panel=document.createElement('div');
      panel.id='ivpReferenceProfilePanel';
      panel.className='ivp-input-note';
      panel.innerHTML='<b>Reference Standard Metric V1 available.</b> 4.0 m × 2.0 m × 1.5 m = 12,000 L nominal, turnover guidance 1.0×/hour. This is an expert-reference product baseline, <b>not a measurement of your pond</b>. Change any field for another pond; dependent requirements recalculate and the override remains visible.';
      form.parentNode.insertBefore(panel,form);
    }}

    const actions=findPondActions(form);
    if(actions){{
      if(!byId('ivpUseReferenceButton')){{
        const useReference=document.createElement('button');
        useReference.id='ivpUseReferenceButton';
        useReference.className='btn ok';
        useReference.textContent='Use Reference Standard Metric V1';
        useReference.onclick=window.ivpUseReferenceProfile;
        actions.insertBefore(useReference,actions.firstChild);
      }}
      if(!byId('ivpCalculateVolumeButton')){{
        const calc=document.createElement('button');
        calc.id='ivpCalculateVolumeButton';
        calc.className='btn';
        calc.textContent='Calculate Nominal Volume from Geometry';
        calc.onclick=window.ivpCalculateNominalVolume;
        const useReference=byId('ivpUseReferenceButton');
        actions.insertBefore(calc,useReference?.nextSibling||actions.firstChild);
      }}
    }}
    const mainLabel=byId('ivpMainFlow')?.closest('.ivp-field')?.querySelector('label');
    if(mainLabel)mainLabel.textContent='Main route declared/reference flow (L/min)';
    populateReferenceFields();
  }}

  window.ivpCalculateNominalVolume=function(){{
    try{{
      const length=numberOrNull('ivpLength');
      const width=numberOrNull('ivpWidth');
      const depth=numberOrNull('ivpDepth');
      if(!(length>0&&width>0&&depth>0))throw new Error('length, width and water depth must be positive');
      const litres=length*width*depth*1000;
      setValue('ivpVolume',litres.toFixed(1));
      const message=`Nominal geometric volume = ${{litres.toFixed(1)}} L. Effective operating volume may still be edited separately.`;
      text('commandResult',message);
      setPondFeedback(message,true);
    }}catch(error){{
      const message=`geometry: ${{error.message}}`;
      text('commandResult',message);
      setPondFeedback(message,false);
    }}
  }};

  window.ivpUseReferenceProfile=async function(){{
    try{{
      populateReferenceFields();
      await command('configure_design_profile',{{profile:REFERENCE_PROFILE,actor:'owner-ui-reference-profile'}});
      await command('configure_module',{{module_id:'flow_monitoring',enabled:true,actor:'owner-ui-reference-profile'}});
      await command('configure_module',{{module_id:'backup_circulation',enabled:false,actor:'owner-ui-reference-profile'}});
      const message='PROFILE APPLIED ✓ · REFERENCE_STANDARD_METRIC_V1 active · 12,000 L · 1.0×/hour · EXPERT_REFERENCE_PROFILE · NOT SITE MEASUREMENT';
      text('commandResult',message);
      setPondFeedback(message,true);
    }}catch(error){{
      const message=`PROFILE NOT APPLIED · reference profile: ${{error.message}}`;
      text('commandResult',message);
      setPondFeedback(message,false);
    }}
  }};

  window.configureIntegratedPond=async function(){{
    try{{
      const length=numberOrNull('ivpLength');
      const width=numberOrNull('ivpWidth');
      const depth=numberOrNull('ivpDepth');
      const volume=numberOrNull('ivpVolume');
      const turnover=numberOrNull('ivpTurnover');
      const mainFlow=numberOrNull('ivpMainFlow');
      if(!(volume>0))throw new Error('ivpVolume: INPUT REQUIRED');
      if(!(turnover>0))throw new Error('ivpTurnover: INPUT REQUIRED');
      if(mainFlow===null||mainFlow<0)throw new Error('ivpMainFlow: INPUT REQUIRED');
      const backup=numberOrNull('ivpBackupFlow');
      const overridden=[];
      if(!sameNumber(length,REFERENCE_PROFILE.length_m))overridden.push('length_m');
      if(!sameNumber(width,REFERENCE_PROFILE.width_m))overridden.push('width_m');
      if(!sameNumber(depth,REFERENCE_PROFILE.water_depth_m))overridden.push('water_depth_m');
      if(!sameNumber(volume,REFERENCE_PROFILE.effective_volume_l))overridden.push('effective_volume_l');
      if(!sameNumber(turnover,REFERENCE_PROFILE.circulation_turnovers_per_hour_guide))overridden.push('circulation_turnovers_per_hour_guide');
      if(!sameNumber(mainFlow,referenceMainRoute().rated_flow_l_min))overridden.push('main_route_flow_l_min');
      if(backup!==null)overridden.push('backup_route_flow_l_min');
      const topup=numberOrNull('ivpTopupFlow');if(topup!==null)overridden.push('top_up_flow_l_min');
      const drain=numberOrNull('ivpDrainFlow');if(drain!==null)overridden.push('drain_flow_l_min');
      const biomass=numberOrNull('ivpBiomass');if(biomass!==null)overridden.push('biomass_kg');
      const feed=numberOrNull('ivpFeed');if(feed!==null)overridden.push('feed_kg_per_day');
      const profileId=textOr('ivpProfileId',REFERENCE_PROFILE.profile_id);
      if(profileId!==REFERENCE_PROFILE.profile_id)overridden.push('profile_id');
      const custom=overridden.length>0;
      const provenance=custom?'USER_CONFIGURED':'EXPERT_REFERENCE_PROFILE';
      const routes=[{{
        route_id:'main-circulation',asset_id:'main_pump',rated_flow_l_min:mainFlow,
        role:'PRIMARY',base_throughput_factor:1,
        provenance:sameNumber(mainFlow,referenceMainRoute().rated_flow_l_min)?'EXPERT_REFERENCE_PROFILE':'USER_CONFIGURED'
      }}];
      if(backup!==null)routes.push({{
        route_id:'backup-circulation',asset_id:'backup_pump',rated_flow_l_min:backup,
        role:'BACKUP',base_throughput_factor:1,provenance:'USER_CONFIGURED'
      }});
      const profile={{
        profile_id:profileId,
        revision:textOr('ivpProfileRevision',custom?'user-r1':REFERENCE_PROFILE.revision),
        effective_volume_l:volume,
        circulation_turnovers_per_hour_guide:turnover,
        routes,
        top_up_flow_l_min:topup,
        drain_flow_l_min:drain,
        biomass_kg:biomass,
        feed_kg_per_day:feed,
        length_m:length,
        width_m:width,
        water_depth_m:depth,
        reference_profile_id:REFERENCE_PROFILE.profile_id,
        overridden_fields:overridden,
        provenance
      }};
      await command('configure_design_profile',{{profile,actor:'owner-ui'}});
      await command('configure_module',{{module_id:'flow_monitoring',enabled:true,actor:'owner-ui'}});
      await command('configure_module',{{module_id:'backup_circulation',enabled:backup!==null,actor:'owner-ui'}});
      const message=custom
        ? `PROFILE APPLIED ✓ · User pond profile active · reference lineage ${{REFERENCE_PROFILE.profile_id}} · overrides: ${{overridden.join(', ')}}`
        : `PROFILE APPLIED ✓ · ${{REFERENCE_PROFILE.profile_id}} active · expert reference · NOT SITE MEASUREMENT`;
      text('commandResult',message);
      setPondFeedback(message,true);
    }}catch(error){{
      const message=`PROFILE NOT APPLIED · configure_design_profile: ${{error.message}}`;
      text('commandResult',message);
      setPondFeedback(message,false);
    }}
  }};

  installReferenceProfileControls();
}})();
"""
