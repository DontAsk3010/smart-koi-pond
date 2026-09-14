from smart_koi_pond.dashboard.animated_pond_ui import ANIMATED_POND_SCRIPT
from smart_koi_pond.domain.process_visual import project_process_visual


def test_process_visual_preserves_unavailable_core_values_instead_of_false_zero() -> None:
    state = project_process_visual(
        {
            "run_id": "unavailable-visual-test",
            "classification": {"state": "UNKNOWN"},
            "operating_mode": "NORMAL_AUTO",
            "operating_status": {"phase": "ACTIVE"},
            "pond_truth": {},
            "assets": {},
            "verification": [],
            "hydraulics": {},
        }
    )

    assert state.dissolved_oxygen_mg_l is None
    assert state.circulation.measured_total_flow_l_min is None
    assert state.circulation.flow_motion_active is False
    assert state.water_management.water_level_pct is None
    assert "DISSOLVED_OXYGEN_UNAVAILABLE" in state.limitations
    assert "CIRCULATION_FLOW_UNAVAILABLE" in state.limitations
    assert "WATER_LEVEL_UNAVAILABLE" in state.limitations


def test_unknown_asset_effectiveness_cannot_animate_process_success() -> None:
    state = project_process_visual(
        {
            "run_id": "unknown-effectiveness-test",
            "classification": {"state": "NORMAL"},
            "operating_mode": "NORMAL_AUTO",
            "operating_status": {"phase": "ACTIVE"},
            "pond_truth": {
                "circulation_flow_l_min": 12.0,
                "dissolved_oxygen_mg_l": 6.0,
                "water_level_pct": 85.0,
            },
            "assets": {
                "main_pump": {
                    "feedback_on": True,
                    "availability": "AVAILABLE",
                    # Deliberately no effectiveness evidence.
                }
            },
            "verification": [],
            "hydraulics": {},
        }
    )

    assert state.circulation.measured_total_flow_l_min == 12.0
    assert state.circulation.primary.feedback_on is True
    assert state.circulation.primary.effectiveness is None
    assert state.circulation.primary.motion_active is False
    assert state.circulation.flow_motion_active is False


def test_animated_renderer_uses_explicit_unavailable_labels_not_numeric_fallbacks() -> None:
    assert "Level UNAVAILABLE" in ANIMATED_POND_SCRIPT
    assert "DO UNAVAILABLE" in ANIMATED_POND_SCRIPT
    assert "Flow UNAVAILABLE" in ANIMATED_POND_SCRIPT
    assert "effect ${effectLabel}" in ANIMATED_POND_SCRIPT
    assert "Number(circ.measured_total_flow_l_min)||0" not in ANIMATED_POND_SCRIPT
    assert "Number(pv.dissolved_oxygen_mg_l)||0" not in ANIMATED_POND_SCRIPT
    assert "clamp(wm.water_level_pct,0,100)" not in ANIMATED_POND_SCRIPT
