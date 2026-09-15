# ruff: noqa: E501

TREND_EVENT_STYLE = r"""
<style id="trend-event-style">
.trend-meta{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 10px}.trend-chip{border:1px solid var(--line);border-radius:999px;padding:4px 8px;background:#0a1725;font-size:11px}.trend-chip b{margin-right:4px}.trend-marker-table{margin-top:10px}.trend-marker-table table{font-size:12px}.trend-marker-table .muted{font-size:11px}.trend-readonly{border-left:3px solid #557ec7;padding:7px 9px;background:#0b1d30;margin:7px 0}.trend-warn{border-left-color:#8a6726}.trend-bad{border-left-color:#74373d}
</style>
"""

TREND_EVENT_SCRIPT = r"""
(function(){
  const SERIES={cTemp:'temp',cDo:'do',cPh:'ph',cLevel:'level',cFlow:'flow'};
  const EVENT_TYPES=new Set(['ALARM','COMMAND','VERIFICATION','RECOVERY','STATE_CHANGE','FAULT','MODE','CONFIGURATION']);
  const EVENT_CODE_TOKENS=['ALARM','COMMAND','FAULT','FAIL','RECOVER','VERIFY','VERIFICATION','MODE','BLACKOUT','POWER','RETURN_TO_AUTO','MAINTENANCE','WATER_CHANGE','TOP_UP','DRAIN','BACKWASH','FILTER','PUMP','AERATOR'];
  let historianLoaded=false;
  function finite(v){return typeof v==='number'&&Number.isFinite(v)}
  function ts(v){const n=Date.parse(v);return Number.isFinite(n)?n:null}
  function pointFromSnapshot(s){const p=s?.pond_truth||{};return{t:s?.timestamp,temp:p.temperature_c,do:p.dissolved_oxygen_mg_l,ph:p.ph,level:p.water_level_pct,flow:p.circulation_flow_l_min}}
  function install(){
    const trends=document.getElementById('trends');if(!trends||document.getElementById('trendEventMeta'))return;
    const notice=trends.querySelector('.notice');const meta=document.createElement('div');meta.id='trendEventMeta';meta.innerHTML=`<div class="trend-readonly">Historian-backed timeline. Operational event markers come only from the loaded canonical ordered event stream. Missing values create a visible gap; they are never plotted as zero.</div><div class="trend-meta"><span class="trend-chip"><b id="trendSource">—</b> timeline source</span><span class="trend-chip"><b id="trendPointCount">0</b> points</span><span class="trend-chip"><b id="trendMarkerCount">0</b> visible markers</span><span class="trend-chip"><b id="trendWindow">—</b></span></div><div id="trendEventTable" class="trend-marker-table"></div>`;
    if(notice)notice.insertAdjacentElement('afterend',meta);else trends.prepend(meta);
  }
  function upsertPoint(point){
    if(!point?.t)return;const stamp=ts(point.t);if(stamp===null)return;
    const idx=history.findIndex(v=>v.t===point.t);if(idx>=0)history[idx]=point;else history.push(point);
    history.sort((a,b)=>(ts(a.t)||0)-(ts(b.t)||0));if(history.length>maxHistory)history.splice(0,history.length-maxHistory);
  }
  function relevantEvent(ev){
    const type=String(ev?.event_type||'').toUpperCase(),code=String(ev?.code||'').toUpperCase();return EVENT_TYPES.has(type)||EVENT_CODE_TOKENS.some(token=>code.includes(token));
  }
  function timelineBounds(){
    const stamps=history.map(v=>ts(v.t)).filter(Number.isFinite);if(!stamps.length)return null;return{lo:Math.min(...stamps),hi:Math.max(...stamps)}
  }
  function visibleEvents(){
    const bounds=timelineBounds();if(!bounds)return[];return eventBuffer.filter(ev=>{const t=ts(ev.timestamp);return t!==null&&t>=bounds.lo&&t<=bounds.hi&&relevantEvent(ev)});
  }
  function markerKind(ev){
    const code=String(ev?.code||'').toUpperCase(),type=String(ev?.event_type||'').toUpperCase();if(code.includes('FAIL')||code.includes('FAULT')||code.includes('ABORT')||code.includes('LOCKOUT')||type==='ALARM')return'bad';if(code.includes('RECOVER')||code.includes('VERIF')||code.includes('RETURN_TO_AUTO'))return'good';return'warn';
  }
  function markerStroke(kind){return kind==='bad'?'#ff5d68':(kind==='good'?'#31d07c':'#f3c64b')}
  function playbackTimestamp(){return playbackMode&&displayed?.timestamp?ts(displayed.timestamp):null}
  function drawEnhanced(id,key){
    const c=document.getElementById(id);if(!c)return;const r=c.getBoundingClientRect(),dpr=window.devicePixelRatio||1;c.width=Math.max(1,r.width*dpr);c.height=Math.max(1,150*dpr);const x=c.getContext('2d');x.scale(dpr,dpr);const w=r.width,h=150;x.clearRect(0,0,w,h);x.strokeStyle='#20364d';x.strokeRect(.5,.5,w-1,h-1);
    const bounds=timelineBounds(),values=history.map(v=>v[key]).filter(finite);if(!bounds||values.length<1){x.fillStyle='#8fa4b8';x.font='11px system-ui';x.fillText('UNAVAILABLE — no canonical trend evidence',8,18);return}
    let lo=Math.min(...values),hi=Math.max(...values);if(hi===lo){hi+=1;lo-=1}const pad=(hi-lo)*.1;hi+=pad;lo-=pad;const span=Math.max(1,bounds.hi-bounds.lo);const xpos=t=>8+((t-bounds.lo)/span)*(w-16);const ypos=v=>h-8-((v-lo)/(hi-lo))*(h-16);
    x.strokeStyle='#58b7ff';x.lineWidth=2;x.beginPath();let drawing=false;history.forEach(v=>{const t=ts(v.t),value=v[key];if(t===null||!finite(value)){drawing=false;return}const xx=xpos(t),yy=ypos(value);if(!drawing){x.moveTo(xx,yy);drawing=true}else{x.lineTo(xx,yy)}});x.stroke();
    visibleEvents().forEach(ev=>{const t=ts(ev.timestamp);if(t===null)return;const xx=xpos(t);x.strokeStyle=markerStroke(markerKind(ev));x.lineWidth=1;x.setLineDash([3,3]);x.beginPath();x.moveTo(xx,18);x.lineTo(xx,h-5);x.stroke();x.setLineDash([])});
    const cursor=playbackTimestamp();if(cursor!==null&&cursor>=bounds.lo&&cursor<=bounds.hi){const xx=xpos(cursor);x.strokeStyle='#a8d0ff';x.lineWidth=2;x.beginPath();x.moveTo(xx,3);x.lineTo(xx,h-3);x.stroke()}
    x.fillStyle='#8fa4b8';x.font='11px system-ui';x.fillText(`${lo.toFixed(2)} – ${hi.toFixed(2)}`,8,13);const start=new Date(bounds.lo).toISOString().replace('T',' ').slice(0,19),end=new Date(bounds.hi).toISOString().replace('T',' ').slice(0,19);x.fillText(start,8,h-5);const ew=x.measureText(end).width;x.fillText(end,Math.max(8,w-ew-8),h-5);
  }
  function renderMarkerTable(){
    install();const markers=visibleEvents();const bounds=timelineBounds();const source=document.getElementById('trendSource'),count=document.getElementById('trendPointCount'),markerCount=document.getElementById('trendMarkerCount'),windowNode=document.getElementById('trendWindow');if(source)source.textContent=historianLoaded?'HISTORIAN + LIVE':(history.length?'LIVE BUFFER ONLY':'UNAVAILABLE');if(count)count.textContent=String(history.length);if(markerCount)markerCount.textContent=String(markers.length);if(windowNode)windowNode.textContent=bounds?`${new Date(bounds.lo).toISOString()} → ${new Date(bounds.hi).toISOString()}`:'NO TIMELINE';
    const box=document.getElementById('trendEventTable');if(!box)return;if(!markers.length){box.innerHTML='<div class="muted">No matching loaded operational event markers inside the current trend window.</div>';return}
    const rows=markers.slice(-20).reverse().map(ev=>`<tr><td>${escapeHtml(ev.timestamp)}</td><td>${escapeHtml(ev.event_type)}</td><td>${escapeHtml(ev.code)}</td><td>${escapeHtml(JSON.stringify(ev.payload||{}))}</td></tr>`).join('');box.innerHTML=`<table><thead><tr><th>Time</th><th>Type</th><th>Marker</th><th>Evidence</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  window.draw=function(id,key){drawEnhanced(id,key)};
  window.drawAll=function(){Object.entries(SERIES).forEach(([id,key])=>drawEnhanced(id,key));renderMarkerTable()};
  window.pushHistory=function(s){if(playbackMode)return;upsertPoint(pointFromSnapshot(s));window.drawAll()};
  const baseRenderEvents=window.renderEvents;window.renderEvents=function(){if(typeof baseRenderEvents==='function')baseRenderEvents();window.drawAll()};
  const baseRenderSnapshot=window.renderSnapshot;window.renderSnapshot=function(snapshot,options){baseRenderSnapshot(snapshot,options);window.drawAll()};
  window.loadHistory=async function(){try{const r=await fetch('/api/history?limit=300',{cache:'no-store'}),j=await r.json();if(!r.ok)throw new Error(j.error||'history failed');const frames=j.frames||[];history.length=0;frames.forEach(f=>upsertPoint(pointFromSnapshot(f.snapshot)));historianLoaded=true;const select=document.getElementById('historyFrames');select.innerHTML='';[...frames].reverse().forEach(f=>{const o=document.createElement('option');o.value=f.frame_sequence;o.textContent=`#${f.frame_sequence} · ${f.timestamp} · event #${f.event_sequence}`;select.appendChild(o)});text('playbackStatus',`${frames.length} historian frames loaded`);window.drawAll()}catch(e){historianLoaded=false;text('playbackStatus',e.message);window.drawAll()}};
  install();window.loadHistory();window.drawAll();
})();
"""
