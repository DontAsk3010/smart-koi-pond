from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.models import PondState

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
)


def make_service() -> RuntimeApplicationService:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, 6.0, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="animated-pond-test",
        config_version="animated-pond-v1",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return RuntimeApplicationService(runtime)


def visual(service: RuntimeApplicationService) -> dict:
    return service.publication(after_sequence=0)["snapshot"]["process_visual"]


def test_process_visual_projection_is_published_from_canonical_runtime() -> None:
    service = make_service()
    state = visual(service)

    assert state["source"] == "CANONICAL_RUNTIME_SNAPSHOT"
    assert state["run_id"] == "animated-pond-test"
    assert state["circulation"]["measured_total_flow_l_min"] == pytest.approx(12.0)
    assert state["circulation"]["primary"]["motion_active"] is True
    assert state["circulation"]["active_route_ids"] == ["main_pump"]
    assert state["aeration"]["primary"]["motion_active"] is True
    assert state["water_management"]["quantitative_discharge_rate_l_min"] is None
    assert "NO_QUANTITATIVE_WASTE_OR_SLUDGE_MODEL" in state["limitations"]


def test_zero_effectiveness_never_animates_false_flow_success() -> None:
    service = make_service()
    service.runtime.actuators.set_effectiveness("main_pump", 0.0)
    service.step(0)
    state = visual(service)

    assert state["circulation"]["measured_total_flow_l_min"] == pytest.approx(0.0)
    assert state["circulation"]["flow_motion_active"] is False
    assert state["circulation"]["primary"]["feedback_on"] is True
    assert state["circulation"]["primary"]["motion_active"] is False


def test_backup_takeover_switches_the_animated_hydraulic_route() -> None:
    service = make_service()
    runtime = service.runtime
    runtime.actuators.assets["main_pump"].feedback_on = False
    runtime.actuators.assets["backup_pump"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    service.step(0)
    state = visual(service)

    assert state["circulation"]["measured_total_flow_l_min"] == pytest.approx(10.0)
    assert state["circulation"]["primary"]["motion_active"] is False
    assert state["circulation"]["backup"]["motion_active"] is True
    assert state["circulation"]["active_route_ids"] == ["backup_pump"]


def test_water_change_projects_drain_then_refill_without_frontend_logic() -> None:
    service = make_service()
    service.command(
        "start_water_change",
        {"target_drain_level_pct": 80.0, "target_refill_level_pct": 85.0},
        role="engineering",
    )
    draining = visual(service)

    assert draining["water_management"]["drain"]["motion_active"] is True
    assert draining["water_management"]["top_up"]["motion_active"] is False
    assert draining["water_management"]["discharge_kind"] == "DRAIN"
    assert draining["water_management"]["expected_level_direction"] == "FALLING_EXPECTED"

    service.runtime.model.set_truth("water_level_pct", 80.0)
    service.step(0)
    refilling = visual(service)

    assert refilling["operating_phase"] == "REFILLING"
    assert refilling["water_management"]["drain"]["motion_active"] is False
    assert refilling["water_management"]["top_up"]["motion_active"] is True
    assert refilling["water_management"]["expected_level_direction"] == "RISING_EXPECTED"


def test_backwash_is_visible_but_quantitative_waste_is_not_fabricated() -> None:
    service = make_service()
    service.command(
        "start_filter_clean",
        {"service_scope": [], "reason": "TEST_BACKWASH"},
        role="engineering",
    )
    state = visual(service)

    assert state["water_management"]["backwash"]["motion_active"] is True
    assert state["water_management"]["discharge_kind"] == "BACKWASH"
    assert state["water_management"]["quantitative_discharge_rate_l_min"] is None


def test_historian_playback_carries_the_same_process_visual_contract() -> None:
    service = make_service()
    service.step(30)
    history = service.history(limit=10)
    frame = history[-1]
    playback = service.playback(frame["frame_sequence"])

    assert playback["snapshot"]["process_visual"] == frame["snapshot"]["process_visual"]
    assert playback["snapshot"]["process_visual"]["source"] == "CANONICAL_RUNTIME_SNAPSHOT"


def test_paused_single_step_advances_process_once_and_stays_paused() -> None:
    service = make_service()
    service.command("pause", role="operator")
    before = service.last_snapshot
    before_time = before.timestamp
    before_do = before.pond_truth.dissolved_oxygen_mg_l

    stepped = service.command("step", {"seconds": 60.0}, role="operator")

    assert stepped.simulation_paused is True
    assert (stepped.timestamp - before_time).total_seconds() == pytest.approx(60.0)
    assert stepped.pond_truth.dissolved_oxygen_mg_l != pytest.approx(before_do)


def test_composed_ui_contains_state_bound_renderer_and_step_control() -> None:
    assert "LIVE POND PROCESS — STATE-BOUND RENDERER" in COMPOSED_INDEX_HTML
    assert "mainFlowPath" in COMPOSED_INDEX_HTML
    assert "backupFlowPath" in COMPOSED_INDEX_HTML
    assert "topUpPath" in COMPOSED_INDEX_HTML
    assert "drainPath" in COMPOSED_INDEX_HTML
    assert "backwashPath" in COMPOSED_INDEX_HTML
    assert "Step +1s" in COMPOSED_INDEX_HTML
    assert "Waste/sludge quantity: NOT MODELED" in COMPOSED_INDEX_HTML
