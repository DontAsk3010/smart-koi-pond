# ruff: noqa: E501

GOVERNANCE_STATUS_STYLE = r"""
<style id="governance-status-style">
.gov-grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:8px;margin-top:8px}.gov-cell{border:1px solid var(--line);border-radius:8px;padding:9px;background:#0a1725;min-width:0}.gov-cell b{display:block;margin-bottom:3px}.gov-good{border-color:#2f7656}.gov-warn{border-color:#8a6726}.gov-bad{border-color:#74373d}.gov-meta{font-size:11px;color:var(--muted);word-break:break-word}.gov-story{margin-top:8px;padding:9px 10px;border-left:3px solid #557ec7;background:#0b1d30}.gov-story.bad{border-left-color:#ff5d68}.gov-story.warn{border-left-color:#f3c64b}.dot.degraded{background:var(--warn)}
@media(max-width:900px){.gov-grid{grid-template-columns:repeat(2,minmax(150px,1fr))}}@media(max-width:520px){.gov-grid{grid-template-columns:1fr}}
</style>
"""

GOVERNANCE_STATUS_SCRIPT = r"""
(function(){
  const safe=(v)=>String(v===null||v===undefined?'UNAVAILABLE':v).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
  const effectValue=(a)=>{if(!a||a.effectiveness===null||a.effectiveness===undefined||a.effectiveness==='')return null;const n=Number(a.effectiveness);return Number.isFinite(n)?Math.max(0,Math.min(1,n)):null};
  const failedAvailability=new Set(['FAILED','UNAVAILABLE','UNAVAILABLE_OFFLINE','OFFLINE','UNKNOWN']);
  const plannedAvailability=new Set(['PLANNED_OFF','MAINTENANCE_UNAVAILABLE','SERVICE_LOCKED','CALIBRATION']);
  function truthfulAssetHtml(a){
    if(!a)return '<span class="muted">UNAVAILABLE</span>';
    const availability=String(a.availability||'UNKNOWN'),effect=effectValue(a),verification=a.verification_status||null;
    const failed=failedAvailability.has(availability)||verification==='FAILED_RESPONSE'||(a.feedback_on&&effect!==null&&effect<=0);
    const degraded=!failed&&(plannedAvailability.has(availability)||verification==='INSUFFICIENT_EVIDENCE'||(a.feedback_on&&(effect===null||effect<1)));
    const cls=failed?'bad':(degraded?'degraded':(a.feedback_on?'on':(plannedAvailability.has(availability)?'plan':'')));
    const effectLabel=effect===null?'UNAVAILABLE':`${Math.round(effect*100)}%`;
    const verificationLabel=verification?` · verify ${safe(verification)}`:'';
    return `<span class="dot ${cls}"></span><b>${a.feedback_on?'ON':'OFF'}</b><br><span class="muted">${safe(a.owner||'UNKNOWN')} · ${safe(availability)} · effect ${effectLabel}${verificationLabel}</span>`;
  }
  window.assetHtml=truthfulAssetHtml;
  window.updateAssets=function(s){
    const box=document.getElementById('overviewAssets');if(box){box.innerHTML='';Object.entries(s.assets||{}).forEach(([id,a])=>{const d=document.createElement('div');d.className='asset';d.innerHTML=`<div class="name">${safe(id)}</div>${truthfulAssetHtml(a)}`;box.appendChild(d)})}
    // Only Mini-SCADA process nodes own replaceable asset markup. Animated pond
    // equipment chips also carry asset identity for drill-down, but their nested
    // renderer DOM (<small>, labels, etc.) must never be replaced here.
    document.querySelectorAll('#processGrid [data-asset]').forEach(n=>{const id=n.dataset.asset;n.innerHTML=`${safe(id.replaceAll('_',' '))}<br>${truthfulAssetHtml(s.assets?.[id])}`});
  };
  function installGovernanceStatus(){
    if(document.getElementById('governanceStatusCard'))return;
    const grid=document.querySelector('#logic .grid');if(!grid)return;
    const card=document.createElement('div');card.id='governanceStatusCard';card.className='card span12';card.innerHTML=`
      <div class="label">Governed Configuration / Update / Self-Recovery</div>
      <div id="govSource" class="muted">Awaiting canonical runtime snapshot…</div>
      <div class="gov-grid">
        <div id="govConfig" class="gov-cell"><b>Configuration</b><span class="gov-meta">—</span></div>
        <div id="govSoftware" class="gov-cell"><b>Software / Update</b><span class="gov-meta">—</span></div>
        <div id="govTransaction" class="gov-cell"><b>Last Transaction</b><span class="gov-meta">—</span></div>
        <div id="govRecovery" class="gov-cell"><b>Recovery Supervisor</b><span class="gov-meta">—</span></div>
      </div><div id="govStory" class="gov-story">No governed change/recovery evidence published yet.</div>`;
    grid.appendChild(card);
  }
  function cell(id,kind,html){const n=document.getElementById(id);if(!n)return;n.className=`gov-cell ${kind||''}`;const meta=n.querySelector('.gov-meta');if(meta)meta.innerHTML=html}
  function renderGovernanceStatus(s){
    installGovernanceStatus();if(!s)return;
    const cfg=s.configuration_control||{},tx=cfg.last_transaction||null,upd=cfg.software_update||null,rec=s.recovery_control||{},active=rec.active||null,last=rec.last_completed||null;
    const playback=(typeof playbackMode!=='undefined'&&playbackMode);const govSource=document.getElementById('govSource');if(govSource)govSource.textContent=playback?'HISTORIAN FRAME / READ ONLY · canonical point-in-time governance state':'LIVE CANONICAL SNAPSHOT · governance state is runtime-published';
    const cfgMismatch=cfg.active_configuration_version&&cfg.last_good_configuration_version&&cfg.active_configuration_version!==cfg.last_good_configuration_version;
    cell('govConfig',cfgMismatch?'gov-warn':'gov-good',`Active ${safe(cfg.active_configuration_version)}<br>LAST_GOOD ${safe(cfg.last_good_configuration_version)}<br>partial active: ${safe(cfg.partial_configuration_active)}`);
    const updateState=upd?.state||'NO_STAGED_UPDATE',updateBad=['ROLLED_BACK','HOLD','REJECTED'].includes(updateState),updateWarn=['STAGED','ACTIVATING','VERIFYING','ROLLING_BACK'].includes(updateState);
    cell('govSoftware',updateBad?'gov-bad':(updateWarn?'gov-warn':'gov-good'),`Active ${safe(cfg.active_software_version)}<br>LAST_GOOD ${safe(cfg.last_good_software_version)}<br>${safe(updateState)}${upd?` · candidate ${safe(upd.candidate_software_version)}`:''}`);
    const txState=tx?.state||'NO_TRANSACTION',txBad=['REJECTED','ROLLED_BACK','HOLD'].includes(txState),txWarn=['PRECHECK','STAGED','ACTIVATING','VERIFYING','ROLLING_BACK'].includes(txState);
    cell('govTransaction',txBad?'gov-bad':(txWarn?'gov-warn':'gov-good'),tx?`${safe(txState)} · ${safe(tx.scope)}<br>${safe(tx.transaction_id)}<br>verify ${safe(tx.verification_result)} · rollback ${safe(tx.rollback_result)}`:'No configuration transaction published');
    const record=active||last,state=record?.state||(active?'UNKNOWN':'IDLE'),recBad=['LOCKED_OUT','ESCALATED'].includes(state),recWarn=!!active&&!['RECOVERED'].includes(state);
    cell('govRecovery',recBad?'gov-bad':(recWarn?'gov-warn':'gov-good'),record?`${safe(state)} · ${safe(record.plan_id)} r${safe(record.plan_revision)}<br>attempt ${safe(record.attempt_count)} / ${safe(rec.retry_limit)} · action ${safe(record.current_action)}<br>verify ${safe(record.verification_result)} · fallback ${safe(record.fallback_active)} · escalated ${safe(record.escalated)}`:'IDLE · no recovery record');
    const story=document.getElementById('govStory');const source=active?'ACTIVE RECOVERY':(last?'LAST COMPLETED RECOVERY':'RECOVERY IDLE');if(story){story.className=`gov-story ${recBad?'bad':(recWarn?'warn':'')}`;story.innerHTML=record?`<b>${safe(source)}:</b> ${safe(record.reason)} · affected ${safe((record.affected_assets||[]).join(', ')||'UNAVAILABLE')} · state ${safe(state)} · next eligible ${safe(record.next_eligible_at)}.`:'Recovery supervisor reports no active/completed recovery record.';}
  }
  installGovernanceStatus();
  const baseRenderSnapshot=window.renderSnapshot;
  if(typeof baseRenderSnapshot==='function'){window.renderSnapshot=function(snapshot,options){baseRenderSnapshot(snapshot,options);window.updateAssets(snapshot);renderGovernanceStatus(snapshot)}}
  window.renderGovernanceStatus=renderGovernanceStatus;
  if(window.displayed){window.updateAssets(window.displayed);renderGovernanceStatus(window.displayed)}
})();
"""
