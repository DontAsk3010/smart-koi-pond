OWNER_COCKPIT_MOTION_GUARD_STYLE = r"""
<style id="owner-cockpit-motion-guard-style">
.oc-scene.motion-paused .oc-waterline,
.oc-scene.motion-paused .oc-route.active,
.oc-scene.motion-paused .oc-bubbles i{animation-play-state:paused!important}
</style>
"""

OWNER_COCKPIT_MOTION_GUARD_SCRIPT = r"""
(function(){
  function syncCockpitMotion(snapshot){
    const scene=document.getElementById('ocScene');
    if(scene)scene.classList.toggle('motion-paused',!!snapshot?.simulation_paused);
  }
  const baseRenderSnapshot=window.renderSnapshot;
  if(typeof baseRenderSnapshot==='function'){
    window.renderSnapshot=function(snapshot,options){
      baseRenderSnapshot(snapshot,options);
      syncCockpitMotion(snapshot);
    };
  }
  if(window.displayed)syncCockpitMotion(window.displayed);
})();
"""
