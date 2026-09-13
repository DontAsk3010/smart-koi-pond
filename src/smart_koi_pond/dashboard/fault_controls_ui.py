FAULT_CONTROLS_UI_SCRIPT = r"""
(function(){
  function installFaultControls(){
    const grid=document.querySelector('#simulator .grid');
    if(!grid||document.getElementById('hardwareFaultCard'))return;

    const hardware=document.createElement('div');
    hardware.id='hardwareFaultCard';
    hardware.className='card span6';
    hardware.innerHTML=`
      <div class="label">Virtual Hardware Fault & Repair</div>
      <div class="controls">
        <select id="faultAsset">
          <option value="main_pump">Main Pump</option>
          <option value="backup_pump">Backup Pump</option>
          <option value="primary_aerator">Primary Aerator</option>
          <option value="backup_aerator">Backup Aerator</option>
          <option value="top_up_valve">Top-up Valve</option>
          <option value="drain_valve">Drain Valve</option>
          <option value="backwash_valve">Backwash Valve</option>
          <option value="feeder">Feeder</option>
          <option value="uv_lamp">UV Lamp</option>
        </select>
        <select id="actuatorFaultMode">
          <option value="failed_off">Failed OFF</option>
          <option value="degraded">Degraded effectiveness</option>
        </select>
        <input id="actuatorFaultValue" type="number" min="0" max="0.99" step="0.05" value="0.5" aria-label="Degraded effectiveness">
        <button class="btn danger" type="button" id="injectActuatorFaultButton">Inject</button>
        <button class="btn ok" type="button" id="repairActuatorButton">Repair / Clear</button>
      </div>
      <div class="muted">Failed OFF removes process effect. Degraded mode preserves motion but reduces effectiveness.</div>`;

    const recovery=document.createElement('div');
    recovery.id='safeRecoveryCard';
    recovery.className='card span6';
    recovery.innerHTML=`
      <div class="label">Safe Reset & Automatic Scenario</div>
      <div class="controls">
        <button class="btn danger" type="button" id="safeRuntimeResetButton">Safe Runtime Reset</button>
        <input id="autoFaultDelay" type="number" min="0" step="1" value="30" aria-label="Automatic fault delay in seconds">
        <button class="btn" type="button" id="scheduleFaultButton">Schedule selected fault</button>
      </div>
      <div class="muted">Reset preserves simulated hardware faults, de-energizes outputs, and enters governed reconciliation. Automatic scheduling uses simulation time.</div>`;

    grid.appendChild(hardware);
    grid.appendChild(recovery);

    document.getElementById('injectActuatorFaultButton').addEventListener('click',()=>{
      const asset=document.getElementById('faultAsset').value;
      const mode=document.getElementById('actuatorFaultMode').value;
      const payload={asset_id:asset,mode};
      if(mode==='degraded')payload.value=Number(document.getElementById('actuatorFaultValue').value);
      sendCommand('inject_actuator_fault',payload,'engineering');
    });

    document.getElementById('repairActuatorButton').addEventListener('click',()=>{
      sendCommand('clear_actuator_fault',{asset_id:document.getElementById('faultAsset').value},'engineering');
    });

    document.getElementById('safeRuntimeResetButton').addEventListener('click',()=>{
      sendCommand('safe_runtime_reset',{},'engineering');
    });

    document.getElementById('scheduleFaultButton').addEventListener('click',()=>{
      const asset=document.getElementById('faultAsset').value;
      const mode=document.getElementById('actuatorFaultMode').value;
      const scenarioPayload={asset_id:asset,mode};
      if(mode==='degraded')scenarioPayload.value=Number(document.getElementById('actuatorFaultValue').value);
      sendCommand('schedule_scenario_trigger',{
        scenario_action:'inject_actuator_fault',
        scenario_payload:scenarioPayload,
        after_seconds:Number(document.getElementById('autoFaultDelay').value),
        one_shot:true
      },'engineering');
    });
  }

  installFaultControls();
})();
"""
