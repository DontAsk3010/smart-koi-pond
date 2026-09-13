MODULAR_UI_SCRIPT = r"""
(function(){
  const previousRenderSnapshot = renderSnapshot;

  function ensureBaselineBadge() {
    let badge = document.getElementById('baselineBadge');
    if (badge) return badge;
    badge = document.createElement('div');
    badge.id = 'baselineBadge';
    badge.className = 'pill';
    badge.innerHTML = 'Baseline: <b id="baselineState">—</b>';
    const top = document.querySelector('header .top');
    if (top) top.appendChild(badge);
    return badge;
  }

  function renderModularState(snapshot) {
    ensureBaselineBadge();
    const registry = snapshot.capability && snapshot.capability.registry;
    const baseline = registry && registry.baseline;
    const baselineState = baseline ? baseline.status : '—';
    text('baselineState', baselineState);

    const badge = document.getElementById('baselineBadge');
    if (badge) {
      badge.title = baseline
        ? [
            ...(baseline.missing_capabilities || []),
            ...(baseline.degraded_capabilities || [])
          ].join(', ')
        : 'Capability registry unavailable';
    }

    const cap = snapshot.capability || {};
    const summary = [
      baselineState,
      `Circulation paths: ${cap.circulation_paths_available ?? '—'}`,
      `Aeration paths: ${cap.aeration_paths_available ?? '—'}`
    ];
    if (registry) summary.push(`Profile: ${registry.profile_id} / ${registry.package_label}`);
    const reasons = cap.degraded_reasons || [];
    if (reasons.length) summary.push(reasons.join(' · '));
    text('capability', summary.join(' · '));

    document.querySelectorAll('[data-asset]').forEach(node => {
      const asset = snapshot.assets && snapshot.assets[node.dataset.asset];
      node.style.display = asset && asset.availability === 'UNSUPPORTED' ? 'none' : '';
    });
  }

  renderSnapshot = function(snapshot, options) {
    previousRenderSnapshot(snapshot, options);
    renderModularState(snapshot);
  };

  ensureBaselineBadge();
})();
"""
