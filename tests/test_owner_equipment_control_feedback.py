from pathlib import Path


def test_owner_equipment_controls_expose_canonical_state_and_feedback() -> None:
    source = Path("src/smart_koi_pond/dashboard/integrated_control_ui.py").read_text(
        encoding="utf-8"
    )

    assert "Actual canonical equipment state" in source
    assert "ivpEquipmentControlFeedback" in source
    assert "MANUAL CONTROL ACTIVE" in source
    assert "COMMAND ACCEPTED" in source
    assert "COMMAND REJECTED" in source
    assert "canonical feedback" in source


def test_manual_on_off_buttons_follow_runtime_ownership_and_feedback() -> None:
    source = Path("src/smart_koi_pond/dashboard/integrated_control_ui.py").read_text(
        encoding="utf-8"
    )

    assert "node.disabled=!enabled" in source
    assert "owner==='MANUAL'||owner==='MAINTENANCE'" in source
    assert "ivpMainPumpOnButton" in source
    assert "ivpMainPumpOffButton" in source
    assert "ivpAeratorOnButton" in source
    assert "ivpAeratorOffButton" in source
    assert "main?.feedback_on===true" in source
    assert "aerator?.feedback_on===true" in source
