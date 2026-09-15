from smart_koi_pond.dashboard.owner_cockpit_motion_guard_ui import (
    OWNER_COCKPIT_MOTION_GUARD_SCRIPT,
    OWNER_COCKPIT_MOTION_GUARD_STYLE,
)
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def test_owner_test_controls_stay_with_live_pond_cockpit() -> None:
    script = OWNER_COCKPIT_MOTION_GUARD_SCRIPT
    assert "ocOwnerTestDock" in script
    assert "#ownerOperationalCockpit .oc-center .oc-card" in script
    assert "takeover.insertAdjacentElement('afterend',dock)" in script
    assert "Test & Response" in script
    assert "Condition" in script
    assert "Action" in script
    assert "Result" in script


def test_owner_test_dock_reuses_existing_governed_acceptance_controls() -> None:
    script = OWNER_COCKPIT_MOTION_GUARD_SCRIPT
    for target in (
        "faNitriteHigh",
        "faNitriteEmergency",
        "faNitrateHigh",
        "faLowDo",
        "faPhHigh",
        "faPhLow",
        "faPumpFail",
        "faPumpRepair",
        "faRestoreBaseline",
        "faApplyChemistry",
        "faUnsafeSource",
        "faSafeSource",
        "faAttemptWaterChange",
    ):
        assert target in script
    assert "fetch('/api/command'" not in script
    assert "new WebSocket" not in script


def test_owner_surface_uses_progressive_disclosure_instead_of_static_warning_prose() -> None:
    style = OWNER_COCKPIT_MOTION_GUARD_STYLE
    script = OWNER_COCKPIT_MOTION_GUARD_SCRIPT
    assert "#functionalAcceptanceHarness .fa-warning" in style
    assert "display:none!important" in style
    assert "Technical evidence" in script
    assert "Chemistry & water-change controls" in script
    assert "oc-test-more" in style
    assert "More tests" in script


def test_owner_test_result_is_read_from_canonical_snapshot_evidence() -> None:
    script = OWNER_COCKPIT_MOTION_GUARD_SCRIPT
    assert "snapshot.classification?.state" in script
    assert "snapshot.classification?.reasons" in script
    assert "snapshot.commands||{}" in script
    assert "snapshot.verification||[]" in script
    assert "snapshot.water_recovery?.water_quality" in script
    assert "snapshot.process_visual?.circulation?.measured_total_flow_l_min" in script


def test_clean_test_cockpit_is_packaged_into_composed_ui() -> None:
    html = COMPOSED_INDEX_HTML
    assert "owner-cockpit-motion-guard-style" in html
    assert "ocOwnerTestDock" in html
    assert "fa-compact-details" in html
