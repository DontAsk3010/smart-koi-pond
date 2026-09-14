from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.filtration import MechanicalFiltrationProfile
from smart_koi_pond.digital_twin.hydraulics import (
    EngineeringProvenance,
    HydraulicRouteRole,
    HydraulicRouteSpec,
    PondDesignProfile,
)
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.digital_twin.scenario_control import VirtualScenarioController
from smart_koi_pond.domain.enums import OperatingMode
from smart_koi_pond.domain.models import PondState

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
)


def design_profile() -> PondDesignProfile:
    return PondDesignProfile(
        profile_id="mechanical-test-pond",
        revision="pond-r1",
        effective_volume_l=20_000.0,
        circulation_turnovers_per_hour_guide=1.0,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
        routes=(
            HydraulicRouteSpec(
                route_id="main-route",
                asset_id="main_pump",
                rated_flow_l_min=400.0,
                role=HydraulicRouteRole.PRIMARY,
            ),
            HydraulicRouteSpec(
                route_id="backup-route",
                asset_id="backup_pump",
                rated_flow_l_min=400.0,
                role=HydraulicRouteRole.BACKUP,
            ),
        ),
    )


def filtration_profile(
    *,
    discharge_flow_l_min: float | None = 100.0,
    turbidity_factor: float | None = None,
    revision: str = "filter-r1",
) -> MechanicalFiltrationProfile:
    return MechanicalFiltrationProfile(
        profile_id="mechanical-filter-a",
        revision=revision,
        source_reference="TEST_EXPLICIT_INPUT_NOT_PRODUCTION_RATING",
        filtered_route_id="main-route",
        capture_efficiency_per_pass=0.5,
        max_captured_solids_g=500.0,
        minimum_route_throughput_factor_at_capacity=0.5,
        backwash_solids_removal_g_per_min=50.0,
        backwash_discharge_flow_l_min=discharge_flow_l_min,
        turbidity_ntu_per_mg_l_tss=turbidity_factor,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
    )


def make_model(*, waste_solids_g: float | None = 100.0) -> PondModel:
    model = PondModel(
        PondState(
            27.0,
            6.0,
            7.2,
            85.0,
            waste_solids_g=waste_solids_g,
        ),
        EnvironmentInputs(27.0, 0.0),
    )
    model.configure_design_profile(design_profile())
    return model


def make_runtime(*, configure_filter: bool = True) -> DigitalTwinRuntime:
    model = make_model(waste_solids_g=200.0)
    if configure_filter:
        model.configure_mechanical_filtration_profile(filtration_profile())
    runtime = DigitalTwinRuntime(
        model,
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        config_version="mechanical-filtration-test-v1",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_flow_dependent_capture_conserves_suspended_plus_captured_mass() -> None:
    model = make_model(waste_solids_g=100.0)
    model.configure_mechanical_filtration_profile(filtration_profile())

    model.step(3600.0, {"main_pump": 1.0})
    state = model.mechanical_filtration_snapshot()

    assert state["last_route_flow_l_min"] == pytest.approx(400.0)
    assert state["last_captured_g"] > 0.0
    assert state["captured_solids_g"] > 0.0
    assert model.state.waste_solids_g is not None
    assert model.state.waste_solids_g + state["captured_solids_g"] == pytest.approx(100.0)


def test_zero_flow_captures_nothing_and_unknown_solids_remain_unknown() -> None:
    known = make_model(waste_solids_g=100.0)
    known.configure_mechanical_filtration_profile(filtration_profile())
    known.step(3600.0, {})
    assert known.state.waste_solids_g == pytest.approx(100.0)
    assert known.mechanical_filtration_snapshot()["last_captured_g"] == pytest.approx(0.0)

    unknown = make_model(waste_solids_g=None)
    unknown.configure_mechanical_filtration_profile(filtration_profile())
    unknown.step(3600.0, {"main_pump": 1.0})
    snapshot = unknown.mechanical_filtration_snapshot()
    assert unknown.state.waste_solids_g is None
    assert snapshot["last_captured_g"] is None
    assert snapshot["tss_mg_l"] is None


def test_filter_loading_restriction_composes_with_independent_route_restriction() -> None:
    model = make_model(waste_solids_g=300.0)
    model.configure_mechanical_filtration_profile(filtration_profile())
    model.set_hydraulic_restriction("main-route", 0.5)

    model.step(3600.0, {"main_pump": 1.0})
    route = model.hydraulic_snapshot()["routes"]["main-route"]

    assert route["independent_restriction_factor"] == pytest.approx(0.5)
    assert route["process_throughput_factor"] < 1.0
    assert route["runtime_throughput_factor"] == pytest.approx(
        route["independent_restriction_factor"]
        * route["process_throughput_factor"]
    )
    assert model.hydraulics is not None
    assert model.hydraulics.route_restriction("main-route") == pytest.approx(0.5)


def test_governed_backwash_reduces_load_recovers_process_factor_and_known_discharge_level() -> None:
    model = make_model(waste_solids_g=400.0)
    model.configure_mechanical_filtration_profile(filtration_profile())
    model.step(3600.0, {"main_pump": 1.0})
    before = model.mechanical_filtration_snapshot()
    before_level = model.state.water_level_pct

    model.step(60.0, {"main_pump": 1.0, "backwash_valve": 1.0})
    after = model.mechanical_filtration_snapshot()

    assert after["captured_solids_g"] < before["captured_solids_g"]
    assert after["process_throughput_factor"] > before["process_throughput_factor"]
    assert after["last_backwash_removed_g"] > 0.0
    assert after["last_backwash_discharge_l"] == pytest.approx(100.0)
    assert model.state.water_level_pct == pytest.approx(before_level - 0.5)


def test_unknown_backwash_discharge_does_not_fabricate_water_level_change() -> None:
    model = make_model(waste_solids_g=400.0)
    model.configure_mechanical_filtration_profile(
        filtration_profile(discharge_flow_l_min=None)
    )
    model.step(3600.0, {"main_pump": 1.0})
    before_level = model.state.water_level_pct

    model.step(60.0, {"main_pump": 1.0, "backwash_valve": 1.0})
    state = model.mechanical_filtration_snapshot()

    assert state["last_backwash_removed_g"] > 0.0
    assert state["last_backwash_discharge_l"] is None
    assert state["cumulative_backwash_discharge_l"] is None
    assert model.state.water_level_pct == pytest.approx(before_level)


def test_tss_is_calculated_but_turbidity_and_clarity_require_separate_basis() -> None:
    model = make_model(waste_solids_g=100.0)
    model.configure_mechanical_filtration_profile(
        filtration_profile(discharge_flow_l_min=None, turbidity_factor=None)
    )
    first = model.mechanical_filtration_snapshot()

    assert first["tss_mg_l"] == pytest.approx(5.0)
    assert first["tss_provenance"] == "CALCULATED"
    assert first["turbidity_ntu"] is None
    assert first["turbidity_provenance"] == "UNAVAILABLE"
    assert first["water_clarity_conclusion"] == "NOT_ESTABLISHED"

    model.configure_mechanical_filtration_profile(
        filtration_profile(
            discharge_flow_l_min=None,
            turbidity_factor=2.0,
            revision="filter-r2",
        )
    )
    second = model.mechanical_filtration_snapshot()
    assert second["turbidity_ntu"] == pytest.approx(10.0)
    assert second["water_clarity_conclusion"] == "NOT_ESTABLISHED"


def test_safe_runtime_reset_preserves_filter_load_and_deenergizes_outputs() -> None:
    runtime = make_runtime()
    runtime.tick(3600.0)
    before = runtime.model.mechanical_filtration_snapshot()
    assert before["captured_solids_g"] > 0.0

    VirtualScenarioController(runtime).safe_runtime_reset()
    after = runtime.model.mechanical_filtration_snapshot()

    assert after["captured_solids_g"] == pytest.approx(before["captured_solids_g"])
    assert after["cumulative_backwash_removed_g"] == pytest.approx(
        before["cumulative_backwash_removed_g"]
    )
    assert runtime.operating_mode == OperatingMode.RECOVERY_SYNC
    assert all(not asset.feedback_on for asset in runtime.actuators.assets.values())


def test_service_configuration_is_engineering_gated_audited_and_published() -> None:
    service = RuntimeApplicationService(make_runtime(configure_filter=False))
    payload = {"profile": filtration_profile().to_dict()}

    with pytest.raises(PermissionError):
        service.command(
            "configure_mechanical_filtration_profile",
            payload,
            role="operator",
        )

    snapshot = service.command(
        "configure_mechanical_filtration_profile",
        payload,
        role="engineering",
    )
    publication = service.publication()
    mechanical = snapshot.hydraulics["mechanical_filtration"]

    assert mechanical["configured"] is True
    assert mechanical["filtered_route_id"] == "main-route"
    assert publication["snapshot"]["hydraulics"]["mechanical_filtration"] == mechanical
    assert publication["mechanical_filtration_schema_version"] == 1
    assert any(
        event.code == "MECHANICAL_FILTRATION_PROFILE_CONFIGURED"
        for event in service.runtime.events.events
    )


def test_historian_playback_preserves_mechanical_state_without_mutation() -> None:
    service = RuntimeApplicationService(make_runtime())
    service.step(600.0)
    history = service.history(limit=20)
    frame = history[-1]
    playback = service.playback(frame["frame_sequence"])
    before = service.runtime.model.mechanical_filtration_snapshot()

    assert playback["snapshot"]["hydraulics"]["mechanical_filtration"] == frame[
        "snapshot"
    ]["hydraulics"]["mechanical_filtration"]
    assert playback["snapshot"]["process_visual"]["mechanical_filtration"][
        "water_clarity_conclusion"
    ] == "NOT_ESTABLISHED"
    assert service.runtime.model.mechanical_filtration_snapshot() == before
