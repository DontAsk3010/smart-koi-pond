# ruff: noqa: E501

BABYLON_JS_URL = "https://cdn.jsdelivr.net/npm/babylonjs@9.26.1/babylon.min.js"

BROWSER_3D_POND_STYLE = r"""
<style id="browser-3d-pond-style">
.oc-scene .pond3d-shell{position:absolute;inset:0;z-index:2;display:none;overflow:hidden;border-radius:inherit;background:linear-gradient(180deg,#8fb8c9 0%,#c9d8c9 42%,#365845 100%)}
.oc-scene.three-ready .pond3d-shell{display:block}
.oc-scene.three-ready .oc-process-svg,.oc-scene.three-ready .oc-pond,.oc-scene.three-ready>.oc-koi,.oc-scene.three-ready>.oc-bubbles{display:none!important}
.oc-scene.three-ready .oc-node{z-index:6;background:rgba(6,20,31,.78);backdrop-filter:blur(5px);box-shadow:0 4px 14px rgba(0,0,0,.2);transform:scale(.92)}
.pond3d-canvas{display:block;width:100%;height:100%;touch-action:none;outline:none}
.pond3d-badge{position:absolute;left:12px;bottom:10px;z-index:7;display:flex;gap:6px;align-items:center;flex-wrap:wrap;pointer-events:none}
.pond3d-pill{font-size:9px;line-height:1.2;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:5px 7px;border-radius:999px;border:1px solid rgba(220,240,248,.28);background:rgba(4,17,27,.78);color:#d9edf6;backdrop-filter:blur(6px)}
.pond3d-pill.reference{color:#f4d98b;border-color:rgba(244,217,139,.45)}
.pond3d-pill.live{color:#8ee8ff;border-color:rgba(83,203,255,.5)}
.pond3d-pill.warn{color:#ffd38a;border-color:rgba(255,186,73,.5)}
.pond3d-fallback{position:absolute;left:50%;bottom:12px;transform:translateX(-50%);z-index:7;display:none;max-width:80%;padding:6px 9px;border-radius:8px;border:1px solid #744b28;background:rgba(43,27,13,.9);color:#ffd59a;font-size:10px;text-align:center}
.oc-scene.three-unavailable .pond3d-fallback{display:block}
.pond3d-evidence{position:absolute;right:12px;bottom:10px;z-index:7;padding:6px 8px;border-radius:8px;background:rgba(4,17,27,.78);border:1px solid rgba(220,240,248,.22);color:#b8ced9;font-size:9px;text-align:right;pointer-events:none;max-width:245px;backdrop-filter:blur(6px)}
.pond3d-evidence b{color:#ecf7fb}
@media(max-width:900px){.oc-scene.three-ready .oc-node{display:none}.pond3d-evidence{max-width:52%;font-size:8px}.pond3d-pill{font-size:8px}.oc-scene .pond3d-shell{min-height:500px}}
@media(max-width:520px){.pond3d-badge{left:8px;bottom:7px}.pond3d-evidence{right:8px;bottom:7px;max-width:58%}.pond3d-pill.reference{display:none}}
</style>
"""

BROWSER_3D_POND_SCRIPT = rf"""
(function(){{
  'use strict';
  const BABYLON_URL={BABYLON_JS_URL!r};
  const BAD_AVAILABILITY=new Set(['FAILED','UNAVAILABLE','UNAVAILABLE_OFFLINE','UNKNOWN']);
  const INACTIVE_AVAILABILITY=new Set(['UNSUPPORTED','MAINTENANCE_UNAVAILABLE','PLANNED_OFF','CALIBRATION']);
  let runtime=null;
  let installing=false;

  function canonicalSnapshot(){{
    try{{
      if(typeof displayed!=='undefined'&&displayed)return displayed;
      if(typeof latestLive!=='undefined'&&latestLive)return latestLive;
    }}catch(_err){{}}
    return null;
  }}

  function loadBabylon(){{
    if(window.BABYLON)return Promise.resolve(window.BABYLON);
    if(window.__smartKoiBabylonPromise)return window.__smartKoiBabylonPromise;
    window.__smartKoiBabylonPromise=new Promise((resolve,reject)=>{{
      const existing=document.querySelector('script[data-smart-koi-babylon]');
      if(existing){{
        existing.addEventListener('load',()=>window.BABYLON?resolve(window.BABYLON):reject(new Error('Babylon loaded without global')),
          {{once:true}});
        existing.addEventListener('error',()=>reject(new Error('Babylon presentation dependency unavailable')),{{once:true}});
        return;
      }}
      const script=document.createElement('script');
      script.src=BABYLON_URL;script.async=true;script.dataset.smartKoiBabylon='9.26.1';script.crossOrigin='anonymous';
      script.onload=()=>window.BABYLON?resolve(window.BABYLON):reject(new Error('Babylon loaded without global'));
      script.onerror=()=>reject(new Error('Babylon presentation dependency unavailable'));
      document.head.appendChild(script);
    }});
    return window.__smartKoiBabylonPromise;
  }}

  function routeState(path){{
    if(!path)return'unavailable';
    if(path.verification_status==='FAILED_RESPONSE'||path.availability==='FAILED')return'failed';
    if(BAD_AVAILABILITY.has(String(path.availability||'UNKNOWN')))return'unavailable';
    if(INACTIVE_AVAILABILITY.has(String(path.availability||'UNKNOWN')))return'inactive';
    return path.motion_active===true?'active':'standby';
  }}

  function finiteNumber(value){{
    if(value===null||value===undefined||value==='')return null;
    const n=Number(value);return Number.isFinite(n)?n:null;
  }}

  function makeMaterial(B,scene,name,color,options={{}}){{
    const mat=new B.PBRMaterial(name,scene);
    mat.albedoColor=color;mat.metallic=options.metallic??0.08;mat.roughness=options.roughness??0.72;
    if(options.alpha!==undefined)mat.alpha=options.alpha;
    if(options.emissive)mat.emissiveColor=options.emissive;
    if(options.backFaceCulling===false)mat.backFaceCulling=false;
    return mat;
  }}

  function tube(B,scene,name,points,radius,material){{
    const mesh=B.MeshBuilder.CreateTube(name,{{path:points,radius,tessellation:18,cap:B.Mesh.CAP_ALL,updatable:false}},scene);
    mesh.material=material;mesh.isPickable=false;return mesh;
  }}

  function pump(B,scene,id,x,z,bodyMat){{
    const root=new B.TransformNode(id+'Root',scene);root.position=new B.Vector3(x,.58,z);
    const body=B.MeshBuilder.CreateCylinder(id+'Body',{{height:.72,diameter:.78,tessellation:28}},scene);body.rotation.z=Math.PI/2;body.parent=root;body.material=bodyMat;
    const motor=B.MeshBuilder.CreateCylinder(id+'Motor',{{height:.72,diameter:.52,tessellation:28}},scene);motor.rotation.z=Math.PI/2;motor.position.x=-.62;motor.parent=root;motor.material=bodyMat;
    const base=B.MeshBuilder.CreateBox(id+'Base',{{width:1.75,height:.16,depth:.9}},scene);base.position.y=-.43;base.parent=root;base.material=bodyMat;
    [body,motor,base].forEach(m=>{{m.metadata={{assetId:id}};m.isPickable=true;}});
    return root;
  }}

  function equipmentBox(B,scene,id,label,x,z,w,d,h,material){{
    const mesh=B.MeshBuilder.CreateBox(id,{{width:w,depth:d,height:h}},scene);mesh.position=new B.Vector3(x,h/2,z);mesh.material=material;mesh.metadata={{assetId:id,label}};mesh.isPickable=true;
    const cap=B.MeshBuilder.CreateBox(id+'Cap',{{width:w*1.05,depth:d*1.05,height:.08}},scene);cap.position=new B.Vector3(x,h+.04,z);cap.material=material;cap.metadata={{assetId:id,label}};cap.isPickable=true;
    return mesh;
  }}

  function createFish(B,scene,index,material){{
    const root=new B.TransformNode('ambientKoi'+index,scene);
    const body=B.MeshBuilder.CreateSphere('ambientKoiBody'+index,{{diameter:1,segments:12}},scene);body.scaling=new B.Vector3(.46,.16,.16);body.parent=root;body.material=material;body.isPickable=false;
    const tail=B.MeshBuilder.CreateCylinder('ambientKoiTail'+index,{{height:.04,diameter:.34,tessellation:3}},scene);tail.rotation.z=Math.PI/2;tail.position.x=-.48;tail.scaling.z=.65;tail.parent=root;tail.material=material;tail.isPickable=false;
    root.scaling=new B.Vector3(.9,.9,.9);return root;
  }}

  function createBubbleField(B,scene,prefix,x,z,count,material){{
    const bubbles=[];
    for(let i=0;i<count;i++){{
      const b=B.MeshBuilder.CreateSphere(prefix+i,{{diameter:.075+((i%3)*.018),segments:6}},scene);b.material=material;b.isPickable=false;b.position.set(x+((i%3)-1)*.18,.18+(i%5)*.18,z+(((i*2)%3)-1)*.14);b.metadata={{seed:i*.137}};b.setEnabled(false);bubbles.push(b);
    }}
    return bubbles;
  }}

  function createFlowBeads(B,scene,prefix,points,count,material){{
    const beads=[];
    for(let i=0;i<count;i++){{
      const bead=B.MeshBuilder.CreateSphere(prefix+i,{{diameter:.13,segments:7}},scene);bead.material=material;bead.isPickable=false;bead.metadata={{phase:i/count}};bead.setEnabled(false);beads.push(bead);
    }}
    return beads;
  }}

  function pointOnPolyline(B,points,t){{
    const clamped=((t%1)+1)%1;const lengths=[];let total=0;
    for(let i=0;i<points.length-1;i++){{const len=B.Vector3.Distance(points[i],points[i+1]);lengths.push(len);total+=len;}}
    if(total<=0)return points[0].clone();let target=clamped*total;
    for(let i=0;i<lengths.length;i++){{if(target<=lengths[i])return B.Vector3.Lerp(points[i],points[i+1],target/lengths[i]);target-=lengths[i];}}
    return points[points.length-1].clone();
  }}

  function setPathMaterial(B,material,state){{
    const palette={{active:new B.Color3(.10,.72,1.0),failed:new B.Color3(.95,.08,.08),standby:new B.Color3(.12,.19,.23),inactive:new B.Color3(.22,.22,.20),unavailable:new B.Color3(.28,.19,.08)}};
    const c=palette[state]||palette.standby;material.albedoColor=c;material.emissiveColor=state==='active'?c.scale(.72):(state==='failed'?c.scale(.48):B.Color3.Black());
  }}

  function installScene(B,host){{
    if(runtime)return runtime;
    const shell=document.createElement('div');shell.className='pond3d-shell';shell.innerHTML='<canvas id="pond3dCanvas" class="pond3d-canvas" aria-label="Interactive 3D koi pond process visualization"></canvas><div class="pond3d-badge"><span class="pond3d-pill live">3D · CANONICAL PROCESS VISUAL</span><span class="pond3d-pill reference">REFERENCE VISUAL LAYOUT · NOT SITE MEASUREMENT</span></div><div id="pond3dEvidence" class="pond3d-evidence"><b>3D preparing</b><br>waiting for canonical snapshot</div>';
    host.appendChild(shell);
    let canvas=shell.querySelector('#pond3dCanvas');
    const engine=new B.Engine(canvas,true,{{preserveDrawingBuffer:false,stencil:true,adaptToDeviceRatio:false}},false);
    const mobile=window.matchMedia('(max-width: 900px)').matches;
    engine.setHardwareScalingLevel(Math.max(1,Math.min(mobile?2:1.5,window.devicePixelRatio||1)));
    const scene=new B.Scene(engine);scene.clearColor=new B.Color4(.64,.77,.82,1);
    scene.imageProcessingConfiguration.contrast=1.08;scene.imageProcessingConfiguration.exposure=.96;
    const camera=new B.ArcRotateCamera('pond3dCamera',-1.18,1.05,mobile?17.5:15.5,new B.Vector3(0,.6,.2),scene);
    camera.lowerRadiusLimit=9;camera.upperRadiusLimit=23;camera.lowerBetaLimit=.48;camera.upperBetaLimit=1.42;camera.wheelPrecision=45;camera.pinchPrecision=80;camera.panningSensibility=0;camera.attachControl(canvas,true);
    const hemi=new B.HemisphericLight('pond3dHemi',new B.Vector3(.2,1,.1),scene);hemi.intensity=.92;hemi.groundColor=new B.Color3(.19,.25,.2);
    const sun=new B.DirectionalLight('pond3dSun',new B.Vector3(-.4,-1,.35),scene);sun.position=new B.Vector3(4,9,-4);sun.intensity=1.25;

    const mat={{}};
    mat.ground=makeMaterial(B,scene,'groundMat',new B.Color3(.19,.34,.20),{{roughness:.95}});
    mat.stone=makeMaterial(B,scene,'stoneMat',new B.Color3(.28,.30,.29),{{roughness:.84}});
    mat.wall=makeMaterial(B,scene,'wallMat',new B.Color3(.16,.18,.17),{{roughness:.78}});
    mat.water=makeMaterial(B,scene,'waterMat',new B.Color3(.02,.31,.46),{{alpha:.76,metallic:.05,roughness:.16,emissive:new B.Color3(.005,.055,.075),backFaceCulling:false}});
    mat.water.transparencyMode=B.Material.MATERIAL_ALPHABLEND;
    mat.primary=makeMaterial(B,scene,'primaryPipeMat',new B.Color3(.12,.19,.23),{{metallic:.25,roughness:.42}});
    mat.backup=makeMaterial(B,scene,'backupPipeMat',new B.Color3(.12,.19,.23),{{metallic:.25,roughness:.42}});
    mat.pump=makeMaterial(B,scene,'pumpMat',new B.Color3(.14,.18,.22),{{metallic:.56,roughness:.34}});
    mat.filter=makeMaterial(B,scene,'filterMat',new B.Color3(.17,.27,.31),{{metallic:.2,roughness:.48}});
    mat.bio=makeMaterial(B,scene,'bioMat',new B.Color3(.18,.32,.24),{{metallic:.12,roughness:.56}});
    mat.uv=makeMaterial(B,scene,'uvMat',new B.Color3(.25,.28,.33),{{metallic:.65,roughness:.28}});
    mat.air=makeMaterial(B,scene,'bubbleMat',new B.Color3(.75,.93,1),{{alpha:.64,roughness:.08,emissive:new B.Color3(.12,.2,.26)}});mat.air.transparencyMode=B.Material.MATERIAL_ALPHABLEND;
    mat.flow=makeMaterial(B,scene,'flowBeadMat',new B.Color3(.08,.72,1),{{emissive:new B.Color3(.08,.62,1),roughness:.2}});
    mat.koiOrange=makeMaterial(B,scene,'koiOrange',new B.Color3(.94,.34,.06),{{roughness:.43}});
    mat.koiWhite=makeMaterial(B,scene,'koiWhite',new B.Color3(.9,.86,.76),{{roughness:.43}});
    mat.koiDark=makeMaterial(B,scene,'koiDark',new B.Color3(.12,.11,.1),{{roughness:.43}});

    const ground=B.MeshBuilder.CreateGround('pond3dGround',{{width:18,height:13,subdivisions:2}},scene);ground.material=mat.ground;ground.position.y=-.55;ground.isPickable=false;
    const deck=B.MeshBuilder.CreateGround('pond3dDeck',{{width:11,height:7,subdivisions:1}},scene);deck.material=mat.stone;deck.position.y=-.50;deck.isPickable=false;

    const pondW=8.2,pondD=4.25,wall=.28;
    const bottom=B.MeshBuilder.CreateBox('pond3dBasin',{{width:pondW,depth:pondD,height:.18}},scene);bottom.position.y=-.34;bottom.material=mat.wall;bottom.isPickable=false;
    const walls=[
      B.MeshBuilder.CreateBox('pond3dWallN',{{width:pondW+wall*2,depth:wall,height:1.25}},scene),
      B.MeshBuilder.CreateBox('pond3dWallS',{{width:pondW+wall*2,depth:wall,height:1.25}},scene),
      B.MeshBuilder.CreateBox('pond3dWallE',{{width:wall,depth:pondD,height:1.25}},scene),
      B.MeshBuilder.CreateBox('pond3dWallW',{{width:wall,depth:pondD,height:1.25}},scene)
    ];
    walls[0].position.set(0,.08,pondD/2+wall/2);walls[1].position.set(0,.08,-pondD/2-wall/2);walls[2].position.set(pondW/2+wall/2,.08,0);walls[3].position.set(-pondW/2-wall/2,.08,0);walls.forEach(w=>{{w.material=mat.wall;w.isPickable=false;}});
    const water=B.MeshBuilder.CreateGround('pond3dWater',{{width:pondW-.42,height:pondD-.42,subdivisions:10}},scene);water.material=mat.water;water.position.y=.48;water.isPickable=false;

    pump(B,scene,'main_pump',-6.1,-2.1,mat.pump);pump(B,scene,'backup_pump',-6.1,2.1,mat.pump);
    equipmentBox(B,scene,'mechanical_filter','Mechanical Filter',-3.1,4.55,1.35,1.35,1.65,mat.filter);
    equipmentBox(B,scene,'biofilter','Biofilter',-.65,4.55,1.55,1.55,1.5,mat.bio);
    const uv=B.MeshBuilder.CreateCylinder('uv_lamp',{{height:1.5,diameter:.55,tessellation:24}},scene);uv.position.set(2.1,.75,4.55);uv.material=mat.uv;uv.metadata={{assetId:'uv_lamp'}};uv.isPickable=true;
    const aerator=B.MeshBuilder.CreateCylinder('primary_aerator',{{height:.58,diameter:.9,tessellation:24}},scene);aerator.position.set(5.8,.3,-2.5);aerator.material=mat.pump;aerator.metadata={{assetId:'primary_aerator'}};aerator.isPickable=true;

    const primaryPoints=[new B.Vector3(-5.7,.72,-2.1),new B.Vector3(-4.5,.72,-2.1),new B.Vector3(-4.5,.72,3.7),new B.Vector3(-3.1,.72,3.7),new B.Vector3(-3.1,.72,4.0),new B.Vector3(-.65,.72,4.0),new B.Vector3(2.1,.72,4.0),new B.Vector3(4.75,.72,3.25),new B.Vector3(4.75,.72,.3),new B.Vector3(3.75,.72,.3)];
    const backupPoints=[new B.Vector3(-5.7,.72,2.1),new B.Vector3(-4.9,.72,2.1),new B.Vector3(-4.9,1.05,3.25),new B.Vector3(-3.7,1.05,3.25),new B.Vector3(-3.7,1.05,4.45),new B.Vector3(-1.5,1.05,4.45),new B.Vector3(1.3,1.05,4.45),new B.Vector3(3.0,1.05,4.0),new B.Vector3(5.05,1.05,2.8),new B.Vector3(5.05,1.05,-.35),new B.Vector3(3.75,1.05,-.35)];
    tube(B,scene,'pond3dPrimaryRoute',primaryPoints,.115,mat.primary);tube(B,scene,'pond3dBackupRoute',backupPoints,.10,mat.backup);
    const primaryBeads=createFlowBeads(B,scene,'primaryFlowBead',primaryPoints,mobile?7:12,mat.flow);
    const backupBeads=createFlowBeads(B,scene,'backupFlowBead',backupPoints,mobile?7:12,mat.flow);
    const primaryBubbles=createBubbleField(B,scene,'primaryBubble',1.35,.45,mobile?7:12,mat.air);
    const backupBubbles=createBubbleField(B,scene,'backupBubble',-1.25,-.45,mobile?5:9,mat.air);
    const koi=[createFish(B,scene,0,mat.koiOrange),createFish(B,scene,1,mat.koiWhite),createFish(B,scene,2,mat.koiDark),createFish(B,scene,3,mat.koiOrange)];

    for(let i=0;i<20;i++){{
      const stone=B.MeshBuilder.CreateSphere('landscapeStone'+i,{{diameter:.25+((i%4)*.06),segments:7}},scene);const angle=(i/20)*Math.PI*2;stone.position.set(Math.cos(angle)*(5.1+(i%2)*.55),-.36,Math.sin(angle)*(3.25+(i%3)*.22));stone.scaling.y=.55;stone.material=mat.stone;stone.isPickable=false;
    }}

    const status={{snapshot:null,pv:null,elapsed:0}};
    scene.onPointerObservable.add(info=>{{
      if(info.type!==B.PointerEventTypes.POINTERPICK)return;const assetId=info.pickInfo?.pickedMesh?.metadata?.assetId;
      if(assetId&&typeof window.openEquipmentDetail==='function')window.openEquipmentDetail(assetId);
    }});

    function updateWater(pv){{
      const level=finiteNumber(pv?.water_management?.water_level_pct);
      if(level===null){{water.setEnabled(false);return;}}
      water.setEnabled(true);const normalized=Math.max(0,Math.min(100,level))/100;water.position.y=-.22+(normalized*.83);
      mat.water.alpha=.56+normalized*.18;
    }}

    function updateEvidence(snapshot,pv){{
      const node=shell.querySelector('#pond3dEvidence');if(!node)return;
      const flow=finiteNumber(pv?.circulation?.measured_total_flow_l_min);const level=finiteNumber(pv?.water_management?.water_level_pct);
      const mode=typeof playbackMode!=='undefined'&&playbackMode?'PLAYBACK / READ ONLY':'LIVE';
      node.innerHTML=`<b>${mode}</b> · ${pv?.classification||'UNKNOWN'}<br>Flow ${flow===null?'UNAVAILABLE':flow.toFixed(1)+' L/min'} · Level ${level===null?'UNAVAILABLE':level.toFixed(1)+'%'}`;
    }}

    function applyCanonical(snapshot){{
      const pv=snapshot?.process_visual;if(!pv)return;
      status.snapshot=snapshot;status.pv=pv;
      const primaryState=routeState(pv.circulation?.primary),backupState=routeState(pv.circulation?.backup);
      setPathMaterial(B,mat.primary,primaryState);setPathMaterial(B,mat.backup,backupState);
      const flowKnown=finiteNumber(pv.circulation?.measured_total_flow_l_min)!==null;
      const primaryActive=flowKnown&&pv.circulation?.flow_motion_active===true&&pv.circulation?.primary?.motion_active===true;
      const backupActive=flowKnown&&pv.circulation?.flow_motion_active===true&&pv.circulation?.backup?.motion_active===true;
      primaryBeads.forEach(x=>x.setEnabled(primaryActive));backupBeads.forEach(x=>x.setEnabled(backupActive));
      primaryBubbles.forEach(x=>x.setEnabled(pv.aeration?.primary?.motion_active===true));backupBubbles.forEach(x=>x.setEnabled(pv.aeration?.backup?.motion_active===true));
      updateWater(pv);updateEvidence(snapshot,pv);
    }}

    scene.registerBeforeRender(()=>{{
      const snapshot=canonicalSnapshot();if(snapshot!==status.snapshot)applyCanonical(snapshot);
      const pv=status.pv;if(!pv)return;const paused=pv.simulation_paused===true;const dt=paused?0:Math.min(.05,engine.getDeltaTime()/1000);status.elapsed+=dt;
      if(!paused){{
        const flow=finiteNumber(pv.circulation?.measured_total_flow_l_min);const speed=flow===null?0:Math.max(.08,Math.min(.65,flow/420));
        primaryBeads.forEach((b,i)=>{{if(b.isEnabled())b.position.copyFrom(pointOnPolyline(B,primaryPoints,(b.metadata.phase+status.elapsed*speed)%1));}});
        backupBeads.forEach((b,i)=>{{if(b.isEnabled())b.position.copyFrom(pointOnPolyline(B,backupPoints,(b.metadata.phase+status.elapsed*speed)%1));}});
        [...primaryBubbles,...backupBubbles].forEach((b,i)=>{{if(!b.isEnabled())return;b.position.y+=dt*(.45+(i%4)*.09);if(b.position.y>1.15)b.position.y=.12+(i%3)*.03;}});
        koi.forEach((fish,i)=>{{const a=status.elapsed*(.14+i*.018)+(i*Math.PI*.5);const rx=2.6-(i%2)*.35,rz=1.15+(i%2)*.25;fish.position.set(Math.cos(a)*rx,.04+(i%2)*.12,Math.sin(a)*rz);fish.rotation.y=-a+Math.PI/2;fish.scaling.x=.86+Math.sin(status.elapsed*2+i)*.025;}});
        if(water.isEnabled()){{mat.water.emissiveColor=new B.Color3(.006,.045+.012*Math.sin(status.elapsed*.8),.064+.018*Math.sin(status.elapsed*.8));}}
      }}
    }});

    engine.runRenderLoop(()=>scene.render());
    const resize=()=>engine.resize();window.addEventListener('resize',resize,{{passive:true}});
    host.classList.add('three-ready');host.classList.remove('three-unavailable');
    runtime={{engine,scene,shell,applyCanonical,destroy:()=>{{window.removeEventListener('resize',resize);engine.stopRenderLoop();scene.dispose();engine.dispose();shell.remove();host.classList.remove('three-ready');}}}};
    applyCanonical(canonicalSnapshot());return runtime;
  }}

  function fallback(host,error){{
    host.classList.remove('three-ready');host.classList.add('three-unavailable');
    let node=host.querySelector('.pond3d-fallback');if(!node){{node=document.createElement('div');node.className='pond3d-fallback';host.appendChild(node);}}
    node.textContent='3D UNAVAILABLE · 2D CANONICAL COCKPIT REMAINS ACTIVE';
    console.warn('Smart Koi Pond 3D renderer fallback:',error);
  }}

  function start(attempt=0){{
    if(runtime||installing)return;const host=document.getElementById('ocScene');
    if(!host){{if(attempt<80)setTimeout(()=>start(attempt+1),125);return;}}
    installing=true;loadBabylon().then(B=>{{try{{installScene(B,host);}}catch(err){{fallback(host,err);}}}}).catch(err=>fallback(host,err)).finally(()=>{{installing=false;}});
  }}

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>start(),{{once:true}});else start();
  window.SmartKoiPond3D={{start,canonicalSnapshot,dependency:BABYLON_URL}};
}})();
"""
