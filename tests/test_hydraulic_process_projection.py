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
from smart_koi_pond.domain.models import PondState
from smart_koi_pond.domain.process_visual import project_process_visual

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
)


def test_modeled_route_flow_reaches_canonical_process_projection() -> None:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, 6.0, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        config_version="hydraulic-projection-test-v1",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    runtime.configure_design_profile(
        PondDesignProfile(
            profile_id="projection-pond",
            revision="r1",
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
            ),
        )
    )
    service = RuntimeApplicationService(runtime)

    process = service.publication()["snapshot"]["process_visual"]
    circulation = process["circulation"]

    assert circulation["modeled_route_flows_l_min"]["main-route"] == pytest.approx(400.0)
    assert circulation["route_flow_provenance"] == "USER_CONFIGURED_SCENARIO"
    assert "PER_ROUTE_FLOW_MODELED_NOT_PHYSICALLY_METERED" in process["limitations"]
    assert "NO_PER_ROUTE_FLOW_METERING" not in process["limitations"]


def test_missing_modeled_route_flow_remains_unavailable_not_false_zero() -> None:
    state = project_process_visual(
        {
            "run_id": "missing-route-flow-test",
            "classification": {"state": "UNKNOWN"},
            "operating_mode": "NORMAL_AUTO",
            "operating_status": {"phase": "ACTIVE"},
            "pond_truth": {
                "circulation_flow_l_min": None,
                "dissolved_oxygen_mg_l": 6.0,
                "water_level_pct": 85.0,
            },
            "assets": {},
            "verification": [],
            "hydraulics": {
                "per_route_flow_modeled": True,
                "profile_provenance": "USER_CONFIGURED_SCENARIO",
                "routes": {"main-route": {"effective_flow_l_min": None}},
            },
        }
    )

    assert state.circulation.modeled_route_flows_l_min["main-route"] is None
    assert "MODELED_ROUTE_FLOW_VALUE_UNAVAILABLE" in state.limitations
