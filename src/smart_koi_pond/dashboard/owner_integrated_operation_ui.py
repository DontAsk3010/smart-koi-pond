# ruff: noqa: E501

OWNER_INTEGRATED_OPERATION_STYLE = r"""
<style id="owner-integrated-operation-style">
#ivpOwnershipControls,#ivpEquipmentControlStatus,#ivpEquipmentControlFeedback{display:none!important}
.oio-wrap{border-top:1px solid #20435a;margin-top:10px;padding-top:10px}.oio-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px}.oio-head b{font-size:12px;letter-spacing:.04em;text-transform:uppercase}.oio-badge{border:1px solid #35566c;border-radius:999px;padding:3px 8px;font-size:9px;font-weight:850;color:#a8c1d0}.oio-guide{display:grid;grid-template-columns:minmax(180px,1fr) minmax(210px,1.3fr) auto auto;gap:6px;align-items:center}.oio-guide select,.oio-guide button{min-height:34px}.oio-guide-text{border:1px solid #1d3b50;border-radius:8px;background:#071723;padding:7px 9px;font-size:10px;color:#9db5c5;min-height:34px}.oio-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:8px}.oio-box{border:1px solid #1d3a4f;border-radius:9px;background:#071723;padding:8px;min-width:0}.oio-box small{display:block;color:#6f8ca1;font-size:8px;font-weight:850;letter-spacing:.08em;margin-bottom:4px}.oio-box strong{display:block;color:#edf7fc;font-size:11px}.oio-box span{display:block;color:#86a0b2;font-size:9px;margin-top:3px;line-height:1.35}.oio-details{margin-top:7px;border:1px solid #1d384c;border-radius:8px;background:#07131e}.oio-details>summary{cursor:pointer;list-style:none;padding:7px 9px;font-size:10px;font-weight:800;color:#94adbd}.oio-details>summary::-webkit-details-marker{display:none}.oio-detail-body{padding:8px;border-top:1px solid #173146}.oio-sensor-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;align-items:end}.oio-sensor-grid label{display:block;font-size:8px;color:#708da0;margin-bottom:2px}.oio-sensor-grid input{width:100%;min-width:0}.oio-maint{display:grid;grid-template-columns:minmax(220px,1fr) auto;gap:8px;align-items:center}.oio-progress{font-size:10px;color:#a7bdca}.oio-manual{margin-top:8px;border:1px solid #1d384c;border-radius:8px;background:#07131e}.oio-manual>summary{cursor:pointer;padding:7px 9px;font-size:10px;font-weight:800;color:#8ca7b8}.oio-manual-buttons{display:flex;gap:6px;flex-wrap:wrap;padding:8px;border-top:1px solid #173146}.oio-manual-buttons .btn{font-size:10px;padding:6px 8px}
#functionalAcceptanceHarness{display:none!important}
@media(max-width:1100px){.oio-flow{grid-template-columns:1fr 1fr}.oio-guide{grid-template-columns:1fr 1fr}.oio-guide-text{grid-column:1/-1}.oio-sensor-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:720px){.oio-flow,.oio-guide,.oio-maint{grid-template-columns:1fr}.oio-sensor-grid{grid-template-columns:1fr 1fr}}
</style>
"""

OWNER_INTEGRATED_OPERATION_SCRIPT = r"""
(function(){
  const $=id=>document.getElementById(id);
  const esc=v=>String(v??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  let lastSnapshot=null;

  async function ownerCommand(action,payload={},role='engineering'){
    if(typeof playbackMode!=='undefined'&&playbackMode)throw new Error('PLAYBACK / READ ONLY');
    const response=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json','X-Koi-Role':role},body:JSON.stringify({action,payload})});
    const body=await response.json();
    if(!response.ok)throw new Error(body.error||'Perintah gagal');
    if(body.publication){cursor=0;eventBuffer=[];renderPublication(body.publication)}
    return body;
  }
  function reasonId(code){
    const map={NITRITE_HIGH:'Nitrit tinggi',NITRITE_EMERGENCY:'Nitrit darurat',NITRATE_HIGH:'Nitrat tinggi',TAN_HIGH:'TAN tinggi',TAN_EMERGENCY:'TAN darurat',NH3_HIGH:'NH3 berisiko tinggi',NH3_EMERGENCY:'NH3 darurat',DO_LOW:'Oksigen terlarut rendah',DO_EMERGENCY:'Oksigen terlarut darurat',PH_OUT_OF_TARGET:'pH di luar target',PH_EMERGENCY:'pH darurat',FLOW_LOW:'Aliran sirkulasi rendah',STATE_HEALTHY:'Kondisi terpantau normal'};return map[code]||code;
  }
  function assetId(id){const map={main_pump:'Pompa utama',backup_pump:'Pompa cadangan',primary_aerator:'Aerator utama',backup_aerator:'Aerator cadangan',feeder:'Pemberi pakan',top_up_valve:'Katup isi ulang',drain_valve:'Katup buang',backwash_valve:'Katup backwash'};return map[id]||id;}
  function testGuide(snapshot){return snapshot?.water_recovery?.owner_operation?.test_guidance?.presets||{};}
  function currentPreset(){return $('oioPreset')?.value||'nitrite_high';}
  function guideText(snapshot){const g=testGuide(snapshot)[currentPreset()];if(!g)return 'Nilai uji belum tersedia dari runtime.';const val=g.test_value==null?'UNAVAILABLE':`${g.test_value} ${g.unit||''}`.trim();const watch=g.watch_boundary==null?'—':g.watch_boundary;const emergency=g.emergency_boundary==null?'—':g.emergency_boundary;return `Nilai uji: ${val} · batas perhatian ${watch} · batas darurat ${emergency} · khusus SIMULASI, bukan setpoint produksi.`;}

  function install(){
    const dock=$('ocOwnerTestDock');if(!dock||$('ownerIntegratedOperation'))return;
    dock.innerHTML=`<div id="ownerIntegratedOperation" class="oio-wrap">
      <div class="oio-head"><b>Operasi & Penilaian Kolam</b><span id="oioMode" class="oio-badge">SIMULASI</span></div>
      <div class="oio-guide"><select id="oioPreset"><option value="nitrite_high">Nitrit Tinggi</option><option value="nitrite_emergency">Nitrit Darurat</option><option value="nitrate_high">Nitrat Tinggi</option><option value="do_low">DO Rendah</option><option value="do_emergency">DO Darurat</option><option value="ph_high">pH Tinggi</option><option value="ph_low">pH Rendah</option><option value="tan_high">TAN Tinggi</option><option value="pump_fail">Pompa Utama Gagal</option></select><div id="oioGuide" class="oio-guide-text">—</div><button id="oioRun" class="btn danger">Jalankan Uji</button><button id="oioNormal" class="btn">Kembalikan Normal</button></div>
      <div class="oio-flow"><div class="oio-box"><small>KONDISI KOLAM</small><strong id="oioCondition">—</strong><span id="oioConditionDetail">—</span></div><div class="oio-box"><small>TINDAKAN SISTEM</small><strong id="oioAction">—</strong><span id="oioActionDetail">—</span></div><div class="oio-box"><small>HASIL PEMULIHAN</small><strong id="oioResult">—</strong><span id="oioResultDetail">—</span></div><div class="oio-box"><small>SARAN PEMILIK</small><strong id="oioAdvice">—</strong><span id="oioAdviceDetail">—</span></div></div>
      <details class="oio-details"><summary>Input sensor virtual — untuk uji sebelum sensor fisik terpasang</summary><div class="oio-detail-body"><div class="oio-sensor-grid"><div><label>TAN mg/L</label><input id="oioTan" type="number" min="0" step="0.01"></div><div><label>Nitrit mg/L</label><input id="oioNitrite" type="number" min="0" step="0.01"></div><div><label>Nitrat mg/L</label><input id="oioNitrate" type="number" min="0" step="0.1"></div><div><label>DO mg/L</label><input id="oioDo" type="number" min="0" step="0.1"></div><div><label>pH</label><input id="oioPh" type="number" min="0" max="14" step="0.1"></div><div><label>Suhu °C</label><input id="oioTemp" type="number" step="0.1"></div><button id="oioApplySensors" class="btn" style="grid-column:1/-1">Kirim Data Sensor Virtual</button></div></div></details>
      <details class="oio-details" open><summary>Perawatan kolam</summary><div class="oio-detail-body"><div class="oio-maint"><div><b>Backwash & Pulihkan Air</b><div id="oioBackwashReadiness" class="oio-progress">Memeriksa kesiapan…</div><div id="oioBackwashProgress" class="oio-progress">—</div></div><button id="oioBackwash" class="btn ok">Mulai Backwash</button></div></div></details>
    </div>`;
    $('oioPreset').onchange=()=>render(lastSnapshot);
    $('oioRun').onclick=runPreset;
    $('oioNormal').onclick=restoreNormal;
    $('oioApplySensors').onclick=applySensorInputs;
    $('oioBackwash').onclick=runBackwash;
    moveManualControls();
  }

  function moveManualControls(){
    const integrated=$('integrated');if(!integrated||$('oioManualControls'))return;
    const ids=['ivpEnterManualControlButton','ivpReturnAutoButton','ivpMainPumpOnButton','ivpMainPumpOffButton','ivpAeratorOnButton','ivpAeratorOffButton'];
    const nodes=ids.map(id=>$(id)).filter(Boolean);if(!nodes.length)return;
    const details=document.createElement('details');details.id='oioManualControls';details.className='oio-manual';details.innerHTML='<summary>Kontrol Manual / Perawatan</summary><div class="oio-manual-buttons"></div>';
    const body=details.querySelector('.oio-manual-buttons');nodes.forEach(node=>{node.textContent=node.textContent.replace('Enter Manual Equipment Control','Ambil Kontrol Manual').replace('Return to AUTO','Kembali ke AUTO').replace('Main Pump','Pompa Utama').replace('Aerator','Aerator');body.appendChild(node)});
    const actions=integrated.querySelector('.ivp-actions');if(actions)actions.insertAdjacentElement('afterend',details);
  }

  async function runPreset(){
    try{
      const preset=currentPreset();
      if(preset==='pump_fail'){
        await ownerCommand('inject_actuator_fault',{asset_id:'main_pump',mode:'failed_off'},'engineering');return;
      }
      const g=testGuide(lastSnapshot)[preset];if(!g||g.test_value==null)throw new Error('Nilai uji belum tersedia dari policy aktif');
      await ownerCommand('set_environment_state',{parameter:g.parameter,value:Number(g.test_value)},'engineering');
    }catch(e){if($('oioResultDetail'))$('oioResultDetail').textContent=e.message;}
  }
  async function restoreNormal(){
    try{
      await ownerCommand('clear_actuator_fault',{asset_id:'main_pump'},'engineering').catch(()=>null);
      if(typeof window.faRestoreBaseline==='function'){window.faRestoreBaseline();return;}
      const values=[['do',6.0],['ph',7.2],['tan',0.0],['nitrite',0.0],['nitrate',0.0],['temperature',27.0]];
      for(const [parameter,value] of values)await ownerCommand('set_environment_state',{parameter,value},'engineering');
    }catch(e){if($('oioResultDetail'))$('oioResultDetail').textContent=e.message;}
  }
  async function applySensorInputs(){
    const inputs=[['tan','oioTan'],['nitrite','oioNitrite'],['nitrate','oioNitrate'],['do','oioDo'],['ph','oioPh'],['temperature','oioTemp']];
    try{
      for(const [parameter,id] of inputs){const raw=$(id).value.trim();if(raw!=='')await ownerCommand('set_environment_state',{parameter,value:Number(raw)},'engineering');}
    }catch(e){if($('oioResultDetail'))$('oioResultDetail').textContent=e.message;}
  }
  async function runBackwash(){
    try{
      const op=lastSnapshot?.water_recovery?.owner_operation||{};
      if(!op.backwash_restore_policy?.configured){
        if(lastSnapshot?.execution_mode!=='SIMULATION')throw new Error('Policy backwash harus dikonfigurasi oleh engineering sebelum operasi nyata');
        await ownerCommand('configure_backwash_restore_policy',{policy:{policy_id:'OWNER_SIMULATION_BACKWASH_V1',revision:'1',source_reference:'DISCLOSED_SIMULATION_TEST_POLICY',backwash_duration_seconds:60,minimum_safe_water_level_pct:70,restore_tolerance_pct:0.5},actor:'owner-simulation-ui'},'engineering');
      }
      await ownerCommand('start_integrated_backwash_restore',{reason:'OWNER_BACKWASH_AND_RESTORE'},'operator');
    }catch(e){if($('oioBackwashProgress'))$('oioBackwashProgress').textContent=`DITAHAN · ${e.message}`;}
  }

  function summarizeCommands(snapshot){
    const commands=Object.values(snapshot?.commands||{}).filter(c=>c.accepted);
    if(!commands.length)return['Tidak ada perintah baru','Sistem belum memerlukan perubahan perangkat pada siklus ini.'];
    const txt=commands.slice(0,3).map(c=>`${assetId(c.asset_id)} ${c.final_on?'ON':'OFF'}`).join(' · ');
    const reasons=commands.slice(0,3).map(c=>c.reason).join(' · ');return[txt,reasons];
  }
  function backwashReadiness(snapshot){
    const h=snapshot?.hydraulics||{},f=h.mechanical_filtration||{},w=h.water_exchange||{},s=w.source_water||{},op=snapshot?.water_recovery?.owner_operation||{};const missing=[];
    if(!f.configured)missing.push('profil filter');if(f.backwash_discharge_flow_l_min==null)missing.push('debit buang backwash');if(!h.configured)missing.push('profil kolam/debit top-up');if(!s.pond_use_qualified)missing.push('air sumber yang sudah lolos syarat');
    if(missing.length)return`Belum siap: ${missing.join(', ')}.`;
    return op.backwash_restore_policy?.configured?'Siap. Sistem akan backwash → hitung air hilang → isi ulang → hitung ulang kimia → verifikasi.':'Siap untuk simulasi. Policy uji yang terlihat akan dipasang saat tombol ditekan: 60 detik, batas level aman 70%.';
  }
  function render(snapshot){
    if(!snapshot)return;lastSnapshot=snapshot;install();moveManualControls();
    if($('oioMode'))$('oioMode').textContent=snapshot.execution_mode==='SIMULATION'?'SIMULASI · SENSOR VIRTUAL':snapshot.execution_mode;
    if($('oioGuide'))$('oioGuide').textContent=guideText(snapshot);
    const state=snapshot.classification?.state||'UNAVAILABLE',reasons=snapshot.classification?.reasons||[];
    if($('oioCondition'))$('oioCondition').textContent=state;if($('oioConditionDetail'))$('oioConditionDetail').textContent=reasons.slice(0,3).map(reasonId).join(' · ')||'—';
    const [act,actDetail]=summarizeCommands(snapshot);if($('oioAction'))$('oioAction').textContent=act;if($('oioActionDetail'))$('oioActionDetail').textContent=actDetail;
    const op=snapshot.water_recovery?.owner_operation||{},active=op.backwash_restore_active,last=op.backwash_restore_last,ver=snapshot.verification||[],latest=ver.length?ver[ver.length-1]:null;
    let result=last?.outcome||latest?.status||snapshot.water_recovery?.water_quality?.last_outcome||'MENUNGGU VERIFIKASI';let detail=last?.detail||(latest?`${assetId(latest.asset_id)} · ${latest.parameter}`:'Belum ada hasil pemulihan final.');
    if(active){result=active.stage;detail=`Level awal ${Number(active.starting_level_pct).toFixed(1)}%${active.post_backwash_level_pct!=null?` · sesudah backwash ${Number(active.post_backwash_level_pct).toFixed(1)}%`:''}`;}
    if($('oioResult'))$('oioResult').textContent=result;if($('oioResultDetail'))$('oioResultDetail').textContent=detail;
    const advice=op.owner_advisory||[];if($('oioAdvice'))$('oioAdvice').textContent=advice.length?'Ada arahan':'—';if($('oioAdviceDetail'))$('oioAdviceDetail').textContent=advice.join(' · ')||'Belum ada saran berbasis evidence.';
    if($('oioBackwashReadiness'))$('oioBackwashReadiness').textContent=backwashReadiness(snapshot);
    if($('oioBackwashProgress'))$('oioBackwashProgress').textContent=active?`Proses: ${active.stage}`:(last?`Terakhir: ${last.outcome} · level akhir ${Number(last.final_level_pct).toFixed(1)}%`:'Belum dijalankan.');
  }

  install();
  const base=window.renderSnapshot;if(typeof base==='function'){window.renderSnapshot=function(snapshot,options){base(snapshot,options);render(snapshot)}}
  if(typeof displayed!=='undefined'&&displayed)render(displayed);
})();
"""
