from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.governance_status_ui import GOVERNANCE_STATUS_SCRIPT
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def test_composed_browser_exposes_governed_change_and_recovery_state() -> None:
    assert "Governed Configuration / Update / Self-Recovery" in COMPOSED_INDEX_HTML
    assert "govConfig" in COMPOSED_INDEX_HTML
    assert "govSoftware" in COMPOSED_INDEX_HTML
    assert "govTransaction" in COMPOSED_INDEX_HTML
    assert "govRecovery" in COMPOSED_INDEX_HTML
    assert "HISTORIAN FRAME / READ ONLY" in COMPOSED_INDEX_HTML
    assert "s.configuration_control" in GOVERNANCE_STATUS_SCRIPT
    assert "s.recovery_control" in GOVERNANCE_STATUS_SCRIPT
    assert "LAST_GOOD" in GOVERNANCE_STATUS_SCRIPT
    assert "LOCKED_OUT" in GOVERNANCE_STATUS_SCRIPT
    assert "ESCALATED" in GOVERNANCE_STATUS_SCRIPT


def test_equipment_renderer_does_not_treat_feedback_on_as_unconditional_green() -> None:
    assert "failedAvailability.has(availability)" in GOVERNANCE_STATUS_SCRIPT
    assert "verification==='FAILED_RESPONSE'" in GOVERNANCE_STATUS_SCRIPT
    assert "a.feedback_on&&effect!==null&&effect<=0" in GOVERNANCE_STATUS_SCRIPT
    assert "a.feedback_on&&(effect===null||effect<1)" in GOVERNANCE_STATUS_SCRIPT
    assert "window.assetHtml=truthfulAssetHtml" in GOVERNANCE_STATUS_SCRIPT
    assert "window.updateAssets=function(s)" in GOVERNANCE_STATUS_SCRIPT


def test_governance_snapshot_state_is_preserved_in_historian_playback() -> None:
    runtime = build_integrated_virtual_runtime()
    service = RuntimeApplicationService(runtime)
    service.step(1.0)

    live = service.publication(after_sequence=0)["snapshot"]
    assert live["configuration_control"]["active_configuration_version"]
    assert live["configuration_control"]["last_good_configuration_version"]
    assert live["recovery_control"]["authority_escalation_allowed"] is False
    assert live["recovery_control"]["high_risk_chemical_dosing_allowed"] is False

    history = service.history(limit=20)
    assert history
    frame = history[-1]
    playback = service.playback(frame["frame_sequence"])["snapshot"]

    assert playback["configuration_control"] == frame["snapshot"]["configuration_control"]
    assert playback["recovery_control"] == frame["snapshot"]["recovery_control"]
    assert playback["configuration_control"] == live["configuration_control"]
