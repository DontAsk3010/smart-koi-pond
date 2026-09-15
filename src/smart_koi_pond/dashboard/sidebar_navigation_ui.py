# ruff: noqa: E501

SIDEBAR_NAVIGATION_STYLE = r"""
<style id="owner-sidebar-navigation-style">
:root{--owner-sidebar-width:208px}
body{padding-left:var(--owner-sidebar-width)}
#tabs.owner-sidebar{position:fixed;left:0;top:0;bottom:0;z-index:50;width:var(--owner-sidebar-width);display:flex;flex-direction:column;gap:4px;overflow-y:auto;padding:12px 10px 14px;background:linear-gradient(180deg,#081b2d 0%,#071522 55%,#06111c 100%);border-right:1px solid #24435d;border-bottom:0;box-shadow:8px 0 28px rgba(0,0,0,.18)}
#tabs.owner-sidebar .owner-side-brand{padding:3px 8px 14px;margin-bottom:5px;border-bottom:1px solid #1e3a51}
#tabs.owner-sidebar .owner-side-brand strong{display:block;font-size:15px;letter-spacing:.035em;color:#f0f7fb}
#tabs.owner-sidebar .owner-side-brand span{display:block;margin-top:2px;font-size:9px;letter-spacing:.11em;color:#69c7ec;text-transform:uppercase}
#tabs.owner-sidebar .owner-nav-group{padding:11px 9px 4px;font-size:9px;letter-spacing:.12em;color:#6f8ca3;text-transform:uppercase;font-weight:800}
#tabs.owner-sidebar button{flex:none;width:100%;display:flex;align-items:center;gap:9px;text-align:left;border:1px solid transparent;border-radius:7px;padding:9px 9px;background:transparent;color:#bdd0de;white-space:normal;font-size:12px;line-height:1.2}
#tabs.owner-sidebar button::before{content:attr(data-owner-icon);width:17px;flex:0 0 17px;text-align:center;color:#77c8ee;font-size:14px}
#tabs.owner-sidebar button:hover{border-color:#285274;background:#0d2b43;color:#f0f8fc}
#tabs.owner-sidebar button.active{border-color:#2a6290;background:linear-gradient(90deg,#0b3b61,#0c2940);color:#fff;box-shadow:inset 3px 0 0 #46bfff}
#tabs.owner-sidebar button[data-view="integrated"]{margin-top:auto;border-top-color:#1f4058}
#tabs.owner-sidebar .owner-sidebar-note{padding:10px 8px 0;margin-top:5px;border-top:1px solid #1f3a50;color:#69859b;font-size:9px;line-height:1.45}
header{left:var(--owner-sidebar-width)}
main{max-width:none;margin:0;padding:14px 16px 24px}
@media(max-width:820px){body{padding-left:0}#tabs.owner-sidebar{position:sticky;top:0;bottom:auto;width:100%;height:auto;flex-direction:row;align-items:center;padding:7px 8px;overflow-x:auto;border-right:0;border-bottom:1px solid #24435d;box-shadow:none}#tabs.owner-sidebar .owner-side-brand,#tabs.owner-sidebar .owner-nav-group,#tabs.owner-sidebar .owner-sidebar-note{display:none}#tabs.owner-sidebar button{width:auto;min-width:max-content;padding:8px 10px}#tabs.owner-sidebar button[data-view="integrated"]{margin-top:0}header{left:0}}
</style>
"""

SIDEBAR_NAVIGATION_SCRIPT = r"""
(function(){
  const LABELS={
    overview:['Overview','▦'],
    process:['Pond Schematic','◉'],
    trends:['Trends & Graphs','⌁'],
    simulator:['Scenario Simulator','⚙'],
    logic:['Control Logic','⌘'],
    events:['Event Log','▤'],
    integrated:['Settings / Configuration','⚙']
  };
  const ORDER=['overview','process','trends','simulator','logic','events','integrated'];
  function installOwnerSidebar(){
    const tabs=document.getElementById('tabs');
    if(!tabs||tabs.dataset.ownerSidebar==='1')return;
    tabs.dataset.ownerSidebar='1';
    tabs.classList.add('owner-sidebar');

    const existing={};
    Array.from(tabs.querySelectorAll('button[data-view]')).forEach(button=>{
      existing[button.dataset.view]=button;
      const spec=LABELS[button.dataset.view];
      if(spec){button.textContent=spec[0];button.dataset.ownerIcon=spec[1]}
    });

    const brand=document.createElement('div');
    brand.className='owner-side-brand';
    brand.innerHTML='<strong>SMART KOI POND</strong><span>Closed-loop control system</span>';
    tabs.prepend(brand);

    const operatorLabel=document.createElement('div');
    operatorLabel.className='owner-nav-group';
    operatorLabel.textContent='Operator';
    tabs.appendChild(operatorLabel);

    ORDER.filter(id=>id!=='integrated').forEach(id=>{if(existing[id])tabs.appendChild(existing[id])});

    if(existing.integrated){
      const configLabel=document.createElement('div');
      configLabel.className='owner-nav-group';
      configLabel.textContent='Configuration';
      tabs.appendChild(configLabel);
      tabs.appendChild(existing.integrated);
    }

    const note=document.createElement('div');
    note.className='owner-sidebar-note';
    note.textContent='Navigation only · canonical runtime remains authoritative';
    tabs.appendChild(note);
  }
  installOwnerSidebar();
  window.installOwnerSidebar=installOwnerSidebar;
})();
"""
