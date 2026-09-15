from smart_koi_pond.dashboard.browser_3d_pond_ui import (
    BABYLON_JS_URL,
    BROWSER_3D_POND_SCRIPT,
    BROWSER_3D_POND_STYLE,
)
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def test_browser_native_3d_renderer_is_composed_into_owner_cockpit() -> None:
    html = COMPOSED_INDEX_HTML
    assert 'id="browser-3d-pond-style"' in html
    assert "pond3dCanvas" in html
    assert "3D · CANONICAL PROCESS VISUAL" in html
    assert "REFERENCE VISUAL LAYOUT · NOT SITE MEASUREMENT" in html


def test_babylon_dependency_is_pinned_and_presentation_only() -> None:
    assert BABYLON_JS_URL == (
        "https://cdn.jsdelivr.net/npm/babylonjs@9.26.1/babylon.min.js"
    )
    assert "smartKoiBabylon" in BROWSER_3D_POND_SCRIPT
    assert "window.BABYLON" in BROWSER_3D_POND_SCRIPT


def test_3d_renderer_reads_canonical_process_visual_without_second_transport() -> None:
    script = BROWSER_3D_POND_SCRIPT
    assert "process_visual" in script
    assert "circulation?.primary" in script
    assert "circulation?.backup" in script
    assert "aeration?.primary" in script
    assert "aeration?.backup" in script
    assert "water_level_pct" in script
    assert "simulation_paused===true" in script
    assert "fetch('/api/runtime'" not in script
    assert 'fetch("/api/runtime"' not in script
    assert "/api/command" not in script
    assert "sendCommand(" not in script


def test_3d_flow_requires_canonical_flow_evidence_and_motion_state() -> None:
    script = BROWSER_3D_POND_SCRIPT
    assert "measured_total_flow_l_min" in script
    assert "flow_motion_active===true" in script
    assert "circulation?.primary?.motion_active===true" in script
    assert "circulation?.backup?.motion_active===true" in script
    assert "flow===null?'UNAVAILABLE'" in script


def test_primary_backup_pumps_and_aerators_have_independent_state_materials() -> None:
    script = BROWSER_3D_POND_SCRIPT
    assert "mainPump:mat(" in script
    assert "backupPump:mat(" in script
    assert "primaryAerator:mat(" in script
    assert "backupAerator:mat(" in script
    assert "tint(B,M.mainPump,ps)" in script
    assert "tint(B,M.backupPump,qs)" in script
    assert "tint(B,M.primaryAerator,pathState(pv.aeration?.primary))" in script
    assert "tint(B,M.backupAerator,pathState(pv.aeration?.backup))" in script


def test_3d_renderer_fails_soft_to_existing_2d_cockpit() -> None:
    script = BROWSER_3D_POND_SCRIPT
    style = BROWSER_3D_POND_STYLE
    assert "3D UNAVAILABLE · 2D CANONICAL COCKPIT REMAINS ACTIVE" in script
    assert "host.classList.add('three-ready')" in script
    assert "host.classList.remove('three-ready')" in script
    assert ".oc-scene.three-ready .oc-process-svg" in style
    assert ".catch(e=>fallback(host,e))" in script


def test_3d_renderer_supports_pointer_touch_and_existing_drilldown() -> None:
    script = BROWSER_3D_POND_SCRIPT
    assert "camera.attachControl(canvas,true)" in script
    assert "touch-action:none" in BROWSER_3D_POND_STYLE
    assert "window.openEquipmentDetail" in script
    assert "PointerEventTypes.POINTERPICK" in script
