# ruff: noqa: E501

INTEGRATED_CONTROL_UI_SCRIPT = r"""
(function(){
  function byId(id){return document.getElementById(id)}
  function finite(id, required=false){
    const raw=(byId(id)?.value||'').trim();
    if(!raw){if(required)throw new Error(`${id}: INPUT REQUIRED`);return null}
    const value=Number(raw);
    if(!Number.isFinite(value))throw new Error(`${id} must be numeric`);
    return value;
  }
  function requiredText(id){
    const value=(byId(id)?.value||'').trim();
    if(!value)throw new Error(`${id}: INPUT REQUIRED`);
    return value;
  }
  async function command(action,payload={},role='engineering'){
    if(typeof playbackMode!=='undefined'&&playbackMode)throw new Error('PLAYBACK / READ ONLY');
    const response=await fetch('/api/command',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Koi-Role':role},
      body:JSON.stringify({action,payload})
    });
    const body=await response.json();
    if(!response.ok)throw new Error(body.error||'command failed');
    if(body.publication){cursor=0;eventBuffer=[];renderPublication(body.publication)}
    return body;
  }

  function assetFeedbackText(asset){
    if(!asset)return 'UNAVAILABLE';
    if(asset.feedback_on===true)return 'ON';
    if(asset.feedback_on===false)return 'OFF';
    return 'UNKNOWN';
  }
  function manualOwner(asset){
    const owner=asset?.owner;
    return owner==='MANUAL'||owner==='MAINTENANCE';
  }
  function setEquipmentFeedback(message,ok=true){
    const node=byId('ivpEquipmentControlFeedback');
    if(!node)return;
    node.style.borderLeftColor=ok?'#2f7656':'#a83f49';
    node.textContent=message;
  }
  function setActiveButton(id,active,enabled){
    const node=byId(id);
    if(!node)return;
    node.disabled=!enabled;
    node.className=active?'btn ok':'btn';
    node.setAttribute('aria-pressed',active?'true':'false');
  }
  function renderEquipmentControlState(snapshot){
    if(!snapshot)return;
    const main=snapshot.assets?.main_pump;
    const aerator=snapshot.assets?.primary_aerator;
    const mainManual=manualOwner(main);
    const aeratorManual=manualOwner(aerator);
    setActiveButton('ivpMainPumpOnButton',main?.feedback_on===true,mainManual);
    setActiveButton('ivpMainPumpOffButton',main?.feedback_on===false,mainManual);
    setActiveButton('ivpAeratorOnButton',aerator?.feedback_on===true,aeratorManual);
    setActiveButton('ivpAeratorOffButton',aerator?.feedback_on===false,aeratorManual);
    const status=byId('ivpEquipmentControlStatus');
    if(status){
      status.innerHTML=`<b>Actual canonical equipment state</b> · Main Pump: ${assetFeedbackText(main)} / owner ${escapeHtml(main?.owner||'UNKNOWN')} · Aerator: ${assetFeedbackText(aerator)} / owner ${escapeHtml(aerator?.owner||'UNKNOWN')}`;
    }
  }

  window.configureIntegratedPond=async function(){
    try{
      const backup=finite('ivpBackupFlow');
      const routes=[{
        route_id:'main-circulation',
        asset_id:'main_pump',
        rated_flow_l_min:finite('ivpMainFlow',true),
        role:'PRIMARY',
        base_throughput_factor:1,
        provenance:'USER_CONFIGURED_SCENARIO'
      }];
      if(backup!==null){
        routes.push({
          route_id:'backup-circulation',
          asset_id:'backup_pump',
          rated_flow_l_min:backup,
          role:'BACKUP',
          base_throughput_factor:1,
          provenance:'USER_CONFIGURED_SCENARIO'
        });
      }
      const profile={
        profile_id:requiredText('ivpProfileId'),
        revision:requiredText('ivpProfileRevision'),
        effective_volume_l:finite('ivpVolume',true),
        circulation_turnovers_per_hour_guide:finite('ivpTurnover',true),
        routes,
        top_up_flow_l_min:finite('ivpTopupFlow'),
        drain_flow_l_min:finite('ivpDrainFlow'),
        biomass_kg:finite('ivpBiomass'),
        feed_kg_per_day:finite('ivpFeed'),
        provenance:'USER_CONFIGURED_SCENARIO'
      };
      await command('configure_design_profile',{profile,actor:'owner-ui'});
      await command('configure_module',{module_id:'flow_monitoring',enabled:true,actor:'owner-ui'});
      await command('configure_module',{
        module_id:'backup_circulation',
        enabled:backup!==null,
        actor:'owner-ui'
      });
      text('commandResult',backup===null
        ? 'Pond profile active · modeled flow monitoring enabled · backup circulation remains DISABLED BY CONFIGURATION'
        : 'Pond profile active · modeled flow monitoring and explicit backup circulation enabled');
    }catch(error){text('commandResult',`configure_design_profile: ${error.message}`)}
  };

  window.ivpEnterManualControl=async function(){
    try{
      const snapshot=(typeof displayed!=='undefined'&&displayed)||(typeof latestLive!=='undefined'&&latestLive);
      if(snapshot?.operating_mode&&snapshot.operating_mode!=='NORMAL_AUTO'){
        throw new Error(`operating mode already active: ${snapshot.operating_mode}`);
      }
      const body=await command('start_manual_maintenance',{
        scope:['main_pump','primary_aerator'],
        service_locked:[],
        reason:'INTEGRATED_VIRTUAL_POND_MANUAL_EQUIPMENT_CONTROL'
      });
      const current=body?.publication?.snapshot;
      renderEquipmentControlState(current);
      setEquipmentFeedback('MANUAL CONTROL ACTIVE ✓ · Main Pump and Aerator can now accept ON/OFF commands',true);
      text('commandResult','Manual equipment control acquired for main pump + primary aerator');
    }catch(error){
      setEquipmentFeedback(`MANUAL CONTROL NOT ACQUIRED · ${error.message}`,false);
      text('commandResult',`manual ownership: ${error.message}`);
    }
  };

  window.ivpReturnAuto=async function(){
    try{
      const body=await command('return_to_auto',{},'operator');
      const current=body?.publication?.snapshot;
      renderEquipmentControlState(current);
      setEquipmentFeedback('RETURN TO AUTO REQUESTED · RECOVERY_SYNC now governs ownership transfer',true);
      text('commandResult','Return-to-AUTO requested; RECOVERY_SYNC governs ownership transfer');
    }catch(error){
      setEquipmentFeedback(`RETURN TO AUTO FAILED · ${error.message}`,false);
      text('commandResult',`return_to_auto: ${error.message}`);
    }
  };

  window.ivpManual=async function(asset,on){
    const label=asset==='main_pump'?'MAIN PUMP':'AERATOR';
    try{
      const snapshot=(typeof displayed!=='undefined'&&displayed)||(typeof latestLive!=='undefined'&&latestLive);
      const owner=snapshot?.assets?.[asset]?.owner;
      if(owner!=='MANUAL'&&owner!=='MAINTENANCE'){
        throw new Error('Enter Manual Equipment Control first; AUTO ownership cannot be bypassed');
      }
      const body=await command('manual_command',{
        asset_id:asset,
        on,
        reason:'INTEGRATED_VIRTUAL_POND_UI'
      });
      const current=body?.publication?.snapshot;
      renderEquipmentControlState(current);
      const feedback=current?.assets?.[asset];
      const actual=assetFeedbackText(feedback);
      setEquipmentFeedback(`${label} COMMAND ACCEPTED ✓ · requested ${on?'ON':'OFF'} · canonical feedback ${actual}`,true);
      text('commandResult',`${asset}: ${on?'ON':'OFF'} manual command accepted · feedback ${actual}`);
    }catch(error){
      setEquipmentFeedback(`${label} COMMAND REJECTED · ${error.message}`,false);
      text('commandResult',`manual_command: ${error.message}`);
    }
  };

  window.ivpBackwash=async function(){
    try{
      const snapshot=(typeof displayed!=='undefined'&&displayed)||(typeof latestLive!=='undefined'&&latestLive);
      const filter=snapshot?.hydraulics?.mechanical_filtration;
      if(!filter?.configured){
        throw new Error('Mechanical Filter profile is INPUT REQUIRED');
      }
      if(snapshot?.operating_mode&&snapshot.operating_mode!=='NORMAL_AUTO'){
        throw new Error(`operating mode already active: ${snapshot.operating_mode}`);
      }
      await command('start_filter_clean',{
        service_scope:[],
        reason:'INTEGRATED_VIRTUAL_POND_UI'
      });
      text('commandResult','Governed filter clean / backwash started through backwash valve workflow');
    }catch(error){text('commandResult',`start_filter_clean: ${error.message}`)}
  };

  function installOwnershipControls(){
    const integrated=byId('integrated');
    if(!integrated||byId('ivpOwnershipControls'))return;
    const actions=integrated.querySelector('.ivp-actions');
    if(!actions)return;
    const panel=document.createElement('div');
    panel.id='ivpOwnershipControls';
    panel.className='ivp-input-note';
    panel.innerHTML='<b>Command ownership is explicit.</b> Main Pump / Aerator ON-OFF buttons are disabled while AUTO owns the assets. Enter manual equipment control first; Return to AUTO uses governed recovery synchronization.';
    actions.parentNode.insertBefore(panel,actions);

    const equipmentStatus=document.createElement('div');
    equipmentStatus.id='ivpEquipmentControlStatus';
    equipmentStatus.className='ivp-input-note';
    equipmentStatus.innerHTML='<b>Actual canonical equipment state</b> · waiting for runtime publication';
    actions.insertAdjacentElement('afterend',equipmentStatus);
    const equipmentFeedback=document.createElement('div');
    equipmentFeedback.id='ivpEquipmentControlFeedback';
    equipmentFeedback.className='ivp-input-note';
    equipmentFeedback.textContent='Equipment command feedback will appear here.';
    equipmentStatus.insertAdjacentElement('afterend',equipmentFeedback);

    const existing=Array.from(actions.querySelectorAll('button'));
    const mainOn=existing.find((node)=>node.textContent.trim()==='Main Pump ON');
    const mainOff=existing.find((node)=>node.textContent.trim()==='Main Pump OFF');
    const aeratorOn=existing.find((node)=>node.textContent.trim()==='Aerator ON');
    const aeratorOff=existing.find((node)=>node.textContent.trim()==='Aerator OFF');
    if(mainOn)mainOn.id='ivpMainPumpOnButton';
    if(mainOff)mainOff.id='ivpMainPumpOffButton';
    if(aeratorOn)aeratorOn.id='ivpAeratorOnButton';
    if(aeratorOff)aeratorOff.id='ivpAeratorOffButton';

    const enter=document.createElement('button');
    enter.id='ivpEnterManualControlButton';
    enter.className='btn';
    enter.textContent='Enter Manual Equipment Control';
    enter.onclick=window.ivpEnterManualControl;
    const back=document.createElement('button');
    back.id='ivpReturnAutoButton';
    back.className='btn ok';
    back.textContent='Return to AUTO';
    back.onclick=window.ivpReturnAuto;
    actions.insertBefore(back,actions.firstChild);
    actions.insertBefore(enter,actions.firstChild);

    const current=(typeof displayed!=='undefined'&&displayed)||(typeof latestLive!=='undefined'&&latestLive);
    renderEquipmentControlState(current);
  }

  installOwnershipControls();
  const baseRender=window.renderSnapshot;
  if(typeof baseRender==='function'){
    window.renderSnapshot=function(snapshot,options){
      baseRender(snapshot,options);
      renderEquipmentControlState(snapshot);
    };
  }
})();
"""
