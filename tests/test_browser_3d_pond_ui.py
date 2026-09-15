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
    assert "data-smart-koi-babylon" in BROWSER_3D_POND_SCRIPT
    assert "window.BABYLON" in BROWSER_3D_POND_SCRIPT


def test_3d_renderer_reads_canonical_process_visual_without_second_transport() -> None:
    script = BROWSER_3D_POND_SCRIPT
    assert "snapshot?.process_visual" in script
    assert "pv.circulation?.primary?.motion_active===true" in script
    assert "pv.circulation?.backup?.motion_active===true" in script
    assert "pv.aeration?.primary?.motion_active===true" in script
    assert "pv.aeration?.backup?.motion_active===true" in script
    assert "pv?.water_management?.water_level_pct" in script
    assert "pv.simulation_paused===true" in script
    assert "fetch('/api/runtime'" not in script
    assert 'fetch("/api/runtime"' not in script
    assert "/api/command" not in script
    assert "sendCommand(" not in script


def test_3d_flow_requires_canonical_flow_evidence_and_motion_state() -> None:
    script = BROWSER_3D_POND_SCRIPT
    assert "measured_total_flow_l_min" in script
    assert "flowKnown&&pv.circulation?.flow_motion_active===true" in script
    assert "primary?.motion_active===true" in script
    assert "backup?.motion_active===true" in script
    assert "flow===null?0" in script
    assert "flow===null?'UNAVAILABLE'" in script


def test_3d_renderer_fails_soft_to_existing_2d_cockpit() -> None:
    script = BROWSER_3D_POND_SCRIPT
    style = BROWSER_3D_POND_STYLE
    assert "3D UNAVAILABLE · 2D CANONICAL COCKPIT REMAINS ACTIVE" in script
    assert "host.classList.add('three-ready')" in script
    assert "host.classList.remove('three-ready')" in script
    assert ".oc-scene.three-ready .oc-process-svg" in style
    assert "catch(err=>fallback(host,err))" in script


def test_3d_renderer_supports_pointer_touch_and_existing_drilldown() -> None:
    script = BROWSER_3D_POND_SCRIPT
    assert "camera.attachControl(canvas,true)" in script
    assert "touch-action:none" in BROWSER_3D_POND_STYLE
    assert "window.openEquipmentDetail" in script
    assert "PointerEventTypes.POINTERPICK" in script
