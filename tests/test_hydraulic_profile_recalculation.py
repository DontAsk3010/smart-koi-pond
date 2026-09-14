from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.hydraulics import (
    EngineeringProvenance,
    HydraulicRouteRole,
    HydraulicRouteSpec,
    PondDesignProfile,
)
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import OperatingMode
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


def profile(
    volume_l: float,
    *,
    revision: str = "r1",
    main_flow: float = 400.0,
    backup_flow: float = 400.0,
    top_up_flow: float | None = 100.0,
    drain_flow: float | None = 100.0,
) -> PondDesignProfile:
    return PondDesignProfile(
        profile_id="pond-design-a",
        revision=revision,
        effective_volume_l=volume_l,
        circulation_turnovers_per_hour_guide=1.0,
        biomass_kg=60.0,
        feed_kg_per_day=1.2,
        top_up_flow_l_min=top_up_flow,
        drain_flow_l_min=drain_flow,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
        routes=(
            HydraulicRouteSpec(
                route_id="main-circulation",
                asset_id="main_pump",
                rated_flow_l_min=main_flow,
                role=HydraulicRouteRole.PRIMARY,
            ),
            HydraulicRouteSpec(
                route_id="backup-circulation",
                asset_id="backup_pump",
                rated_flow_l_min=backup_flow,
                role=HydraulicRouteRole.BACKUP,
            ),
        ),
    )


def make_runtime() -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, 6.0, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        config_version="hydraulic-profile-test-v1",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_volume_change_recalculates_required_flow_without_hardware_rewrite() -> None:
    runtime = make_runtime()
    runtime.configure_design_profile(profile(20_000.0, revision="r1"))
    first = runtime.tick(0.0)

    assert first.hydraulics["required_circulation_flow_l_min"] == pytest.approx(333.333333)
    assert first.hydraulics["total_effective_flow_l_min"] == pytest.approx(400.0)
    assert first.hydraulics["achieved_turnovers_per_hour"] == pytest.approx(1.2)
    assert first.hydraulics["active_flow_status"] == "FLOW_AT_OR_ABOVE_CALCULATED_REQUIREMENT"

    runtime.configure_design_profile(profile(40_000.0, revision="r2"))
    second = runtime.tick(0.0)

    assert second.hydraulics["required_circulation_flow_l_min"] == pytest.approx(666.666667)
    assert second.hydraulics["total_effective_flow_l_min"] == pytest.approx(400.0)
    assert second.hydraulics["achieved_turnovers_per_hour"] == pytest.approx(0.6)
    assert second.hydraulics["active_flow_status"] == "FLOW_BELOW_CALCULATED_REQUIREMENT"
    assert second.design_profile["revision"] == "r2"
    assert any(
        event.code == "POND_DESIGN_PROFILE_RECALCULATED"
        for event in runtime.events.events
    )


def test_larger_candidate_pump_is_guidance_not_a_hardware_lock() -> None:
    runtime = make_runtime()
    runtime.configure_design_profile(profile(20_000.0, main_flow=800.0))
    state = runtime.tick(0.0).hydraulics

    assert state["primary_design_capacity_l_min"] == pytest.approx(800.0)
    assert (
        state["primary_capacity_status"]
        == "DECLARED_CAPACITY_AT_OR_ABOVE_CALCULATED_REQUIREMENT"
    )
    assert state["hardware_fault_conclusion"] == "NOT_ESTABLISHED"
    assert state["hardware_upgrade_required"] is False
    assert state["hardware_assessment_requires_evidence"] is True
    assert state["sizing_advisory_is_mandatory_hardware_lock"] is False


def test_route_restriction_changes_effective_flow_and_turnover() -> None:
    runtime = make_runtime()
    runtime.configure_design_profile(profile(20_000.0))
    runtime.set_hydraulic_restriction("main-circulation", 0.5)

    snapshot = runtime.tick(0.0)
    route = snapshot.hydraulics["routes"]["main-circulation"]
    assert route["runtime_throughput_factor"] == pytest.approx(0.5)
    assert route["effective_flow_l_min"] == pytest.approx(200.0)
    assert snapshot.hydraulics["total_effective_flow_l_min"] == pytest.approx(200.0)
    assert snapshot.hydraulics["achieved_turnovers_per_hour"] == pytest.approx(0.6)


def test_water_management_rate_recalculates_from_effective_volume() -> None:
    small = PondModel(
        PondState(27.0, 6.0, 7.2, 10.0),
        EnvironmentInputs(28.0, 0.0),
    )
    small.configure_design_profile(profile(10_000.0))
    small.step(3600.0, {"top_up_valve": 1.0})

    large = PondModel(
        PondState(27.0, 6.0, 7.2, 10.0),
        EnvironmentInputs(28.0, 0.0),
    )
    large.configure_design_profile(profile(20_000.0))
    large.step(3600.0, {"top_up_valve": 1.0})

    assert small.state.water_level_pct == pytest.approx(70.0)
    assert large.state.water_level_pct == pytest.approx(40.0)


def test_checkpoint_preserves_profile_and_restriction_but_deenergizes_outputs() -> None:
    runtime = make_runtime()
    runtime.configure_design_profile(profile(25_000.0, revision="checkpoint-r1"))
    runtime.set_hydraulic_restriction("main-circulation", 0.6)
    checkpoint = runtime.capture_checkpoint()

    restored = make_runtime()
    restored.restore_checkpoint(checkpoint)

    assert restored.model.design_profile_snapshot()["effective_volume_l"] == pytest.approx(
        25_000.0
    )
    assert restored.model.hydraulics is not None
    assert restored.model.hydraulics.route_restriction("main-circulation") == pytest.approx(
        0.6
    )
    assert all(not asset.feedback_on for asset in restored.actuators.assets.values())
    assert restored.operating_mode == OperatingMode.RECOVERY_SYNC


def test_engineering_service_can_reconfigure_profile_and_publish_state() -> None:
    service = RuntimeApplicationService(make_runtime())
    payload = {"profile": profile(30_000.0, revision="service-r1").to_dict()}

    with pytest.raises(PermissionError):
        service.command("configure_design_profile", payload, role="operator")

    snapshot = service.command("configure_design_profile", payload, role="engineering")
    publication = service.publication()

    assert snapshot.design_profile["revision"] == "service-r1"
    assert publication["snapshot"]["design_profile"]["effective_volume_l"] == pytest.approx(
        30_000.0
    )
    assert publication["snapshot"]["hydraulics"][
        "required_circulation_flow_l_min"
    ] == pytest.approx(500.0)


def test_profile_uses_explicit_user_configured_provenance_not_design_assumption() -> None:
    runtime = make_runtime()
    runtime.configure_design_profile(profile(20_000.0))
    snapshot = runtime.tick(0.0)

    assert snapshot.design_profile["provenance"] == "USER_CONFIGURED_SCENARIO"
    assert snapshot.hydraulics["profile_provenance"] == "USER_CONFIGURED_SCENARIO"
    assert (
        snapshot.hydraulics["routes"]["main-circulation"]["provenance"]
        == "USER_CONFIGURED_SCENARIO"
    )
