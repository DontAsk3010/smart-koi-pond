# ruff: noqa: E501

VIRTUAL_POND_HOME_STYLE = r"""
<style id="virtual-pond-home-style">
#process.virtual-pond-home .card{padding:14px}.vp-home{display:grid;grid-template-columns:minmax(280px,1.35fr) minmax(280px,.65fr);gap:12px;margin:8px 0 14px}.vp-hero,.vp-summary{border:1px solid var(--line);border-radius:12px;background:linear-gradient(180deg,#0a1c2b,#091724);padding:14px}.vp-kicker{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#77c8ee;font-weight:800}.vp-title{font-size:24px;font-weight:850;margin:5px 0 3px}.vp-subtitle{color:var(--muted);max-width:760px}.vp-truth{display:flex;gap:7px;flex-wrap:wrap;margin-top:11px}.vp-truth span{padding:5px 8px;border:1px solid var(--line);border-radius:999px;background:#081522;font-size:11px}.vp-truth .ready{border-color:#2f7656;color:#9de7be}.vp-truth .required{border-color:#8a6726;color:#f2d58b}.vp-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.vp-summary{display:grid;grid-template-columns:1fr 1fr;gap:8px}.vp-metric{border:1px solid #1d3850;border-radius:9px;background:#081522;padding:10px;min-width:0}.vp-metric .vp-label{font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}.vp-metric .vp-value{font-size:18px;font-weight:800;margin-top:2px;overflow-wrap:anywhere}.vp-metric .vp-detail{font-size:10px;color:var(--muted);margin-top:2px}.vp-source{grid-column:1/-1;border-top:1px solid var(--line);padding-top:8px;color:var(--muted);font-size:11px}.vp-state-normal{color:var(--ok)}.vp-state-watch,.vp-state-degraded{color:var(--warn)}.vp-state-correcting{color:var(--corr)}.vp-state-emergency,.vp-state-failsafe{color:var(--bad)}
@media(max-width:900px){.vp-home{grid-template-columns:1fr}.vp-title{font-size:21px}}@media(max-width:520px){.vp-summary{grid-template-columns:1fr}.vp-source{grid-column:span 1}}
</style>
"""

VIRTUAL_POND_HOME_SCRIPT = r"""
(function(){
  function el(id){return document.getElementById(id)}
  function esc(v){return String(v??'—').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
  function finite(v){if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)?n:null}
  function value(v,unit='',digits=2){const n=finite(v);return n===null?'UNAVAILABLE':`${n.toFixed(digits)}${unit}`}
  function set(id,v){const n=el(id);if(n)n.textContent=v}
  function truthChip(id,label,ready){const n=el(id);if(!n)return;n.className=ready?'ready':'required';n.textContent=`${label}: ${ready?'CONFIGURED':'INPUT REQUIRED'}`}
  function installHome(){
    const section=el('process'),grid=el('processGrid'),tabs=el('tabs');
    if(!section||!grid||!tabs||el('virtualPondHome'))return;
    section.classList.add('virtual-pond-home');
    document.title='Smart Koi Pond — Virtual Pond';
    const home=document.createElement('div');home.id='virtualPondHome';home.className='vp-home';home.innerHTML=`
      <div class="vp-hero">
        <div class="vp-kicker">SMART KOI POND · CANONICAL RUNTIME</div>
        <div class="vp-title">Virtual Pond</div>
        <div class="vp-subtitle">Detailed process view of the governed pond. The owner operational cockpit is the primary browser surface; this page remains the deeper schematic view. Motion, equipment state and water values are projections of the canonical runtime; unavailable evidence stays unavailable.</div>
        <div class="vp-truth"><span id="vpPondTruth">Pond Profile: INPUT REQUIRED</span><span id="vpBioTruth">Biology: INPUT REQUIRED</span><span id="vpFilterTruth">Filter: INPUT REQUIRED</span><span class="required">REAL DEVICE CONTROL: CLOSED</span></div>
        <div class="vp-actions"><button id="vpOpenIntegrated" class="btn ok">Open Integrated Setup</button><button id="vpOpenOverview" class="btn">Overview</button><button id="vpOpenEvents" class="btn">Historian / Events</button></div>
      </div>
      <div class="vp-summary">
        <div class="vp-metric"><div class="vp-label">System State</div><div id="vpState" class="vp-value">—</div><div id="vpMode" class="vp-detail">—</div></div>
        <div class="vp-metric"><div class="vp-label">Dissolved Oxygen</div><div id="vpDo" class="vp-value">UNAVAILABLE</div><div class="vp-detail">Canonical pond state</div></div>
        <div class="vp-metric"><div class="vp-label">Water Level</div><div id="vpLevel" class="vp-value">UNAVAILABLE</div><div class="vp-detail">Canonical pond state</div></div>
        <div class="vp-metric"><div class="vp-label">Circulation Flow</div><div id="vpFlow" class="vp-value">UNAVAILABLE</div><div class="vp-detail">No false zero for unavailable flow</div></div>
        <div id="vpSource" class="vp-source">Awaiting canonical runtime snapshot…</div>
      </div>`;
    const stage=el('animatedPondStage');grid.parentNode.insertBefore(home,stage||grid);
    el('vpOpenIntegrated').onclick=()=>{const b=tabs.querySelector('[data-view="integrated"]');if(b)b.click()};
    el('vpOpenOverview').onclick=()=>{const b=tabs.querySelector('[data-view="overview"]');if(b)b.click()};
    el('vpOpenEvents').onclick=()=>{const b=tabs.querySelector('[data-view="events"]');if(b)b.click()};
  }
  function renderHome(s){
    installHome();if(!s)return;
    const p=s.pond_truth||{},pv=s.process_visual||{},hyd=s.hydraulics||{},design=s.design_profile||{},bio=s.biology||{},filter=hyd.mechanical_filtration||{};
    const state=String(pv.classification||'UNAVAILABLE');
    const stateEl=el('vpState');if(stateEl){stateEl.textContent=state;stateEl.className=`vp-value vp-state-${state.toLowerCase()}`}
    set('vpMode',`${pv.operating_mode||'UNAVAILABLE'} / ${pv.operating_phase||'UNAVAILABLE'}`);
    set('vpDo',value(p.dissolved_oxygen_mg_l,' mg/L'));
    set('vpLevel',value(p.water_level_pct,' %',1));
    set('vpFlow',value(p.circulation_flow_l_min,' L/min'));
    truthChip('vpPondTruth','Pond Profile',!!design.configured);
    truthChip('vpBioTruth','Biology',!!bio.configured);
    truthChip('vpFilterTruth','Filter',!!filter.configured);
    set('vpSource',`Source: ${pv.source||'CANONICAL_RUNTIME_SNAPSHOT'} · ${s.timestamp||'timestamp unavailable'} · ${pv.simulation_paused?'PAUSED':'RUNNING'} · ${Number(pv.simulation_acceleration||1).toFixed(1)}×`);
  }
  installHome();
  const baseRenderSnapshot=window.renderSnapshot;
  if(typeof baseRenderSnapshot==='function'){window.renderSnapshot=function(snapshot,options){baseRenderSnapshot(snapshot,options);renderHome(snapshot)}}
  window.renderVirtualPondHome=renderHome;
})();
"""
