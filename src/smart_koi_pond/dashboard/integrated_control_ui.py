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
      if(backup!==null){
        await command('configure_module',{module_id:'backup_circulation',enabled:true,actor:'owner-ui'});
      }
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
      await command('start_manual_maintenance',{
        scope:['main_pump','primary_aerator'],
        service_locked:[],
        reason:'INTEGRATED_VIRTUAL_POND_MANUAL_EQUIPMENT_CONTROL'
      });
      text('commandResult','Manual equipment control acquired for main pump + primary aerator');
    }catch(error){text('commandResult',`manual ownership: ${error.message}`)}
  };

  window.ivpReturnAuto=async function(){
    try{
      await command('return_to_auto',{},'operator');
      text('commandResult','Return-to-AUTO requested; RECOVERY_SYNC governs ownership transfer');
    }catch(error){text('commandResult',`return_to_auto: ${error.message}`)}
  };

  window.ivpManual=async function(asset,on){
    try{
      const snapshot=(typeof displayed!=='undefined'&&displayed)||(typeof latestLive!=='undefined'&&latestLive);
      const owner=snapshot?.assets?.[asset]?.owner;
      if(owner!=='MANUAL'&&owner!=='MAINTENANCE'){
        throw new Error('Enter Manual Equipment Control first; AUTO ownership cannot be bypassed');
      }
      await command('manual_command',{
        asset_id:asset,
        on,
        reason:'INTEGRATED_VIRTUAL_POND_UI'
      });
      text('commandResult',`${asset}: ${on?'ON':'OFF'} manual command accepted`);
    }catch(error){text('commandResult',`manual_command: ${error.message}`)}
  };

  function installOwnershipControls(){
    const integrated=byId('integrated');
    if(!integrated||byId('ivpOwnershipControls'))return;
    const actions=integrated.querySelector('.ivp-actions');
    if(!actions)return;
    const panel=document.createElement('div');
    panel.id='ivpOwnershipControls';
    panel.className='ivp-input-note';
    panel.innerHTML='<b>Command ownership is explicit.</b> Main Pump / Aerator ON-OFF buttons are blocked while AUTO owns the assets. Enter manual equipment control first; Return to AUTO uses governed recovery synchronization.';
    actions.parentNode.insertBefore(panel,actions);
    const enter=document.createElement('button');
    enter.className='btn';
    enter.textContent='Enter Manual Equipment Control';
    enter.onclick=window.ivpEnterManualControl;
    const back=document.createElement('button');
    back.className='btn ok';
    back.textContent='Return to AUTO';
    back.onclick=window.ivpReturnAuto;
    actions.insertBefore(back,actions.firstChild);
    actions.insertBefore(enter,actions.firstChild);
  }

  installOwnershipControls();
})();
"""
