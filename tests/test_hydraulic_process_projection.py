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
