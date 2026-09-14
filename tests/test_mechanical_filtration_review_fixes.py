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
from smart_koi_pond.domain.models import PondState


POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
)


def _design_profile() -> PondDesignProfile:
    return PondDesignProfile(
        profile_id="review-fix-pond",
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


def _filtration_profile() -> MechanicalFiltrationProfile:
    return MechanicalFiltrationProfile(
        profile_id="review-fix-filter",
        revision="r1",
        source_reference="TEST_EXPLICIT_INPUT_NOT_PRODUCTION_RATING",
        filtered_route_id="main-route",
        capture_efficiency_per_pass=0.5,
        max_captured_solids_g=500.0,
        minimum_route_throughput_factor_at_capacity=0.5,
        backwash_solids_removal_g_per_min=50.0,
        backwash_discharge_flow_l_min=100.0,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
    )


def _model(*, water_level_pct: float = 85.0) -> PondModel:
    model = PondModel(
        PondState(
            temperature_c=27.0,
            dissolved_oxygen_mg_l=6.0,
            ph=7.2,
            water_level_pct=water_level_pct,
            waste_solids_g=100.0,
        ),
        EnvironmentInputs(ambient_temperature_c=27.0, oxygen_demand_mg_l_per_hour=0.0),
    )
    model.configure_design_profile(_design_profile())
    model.configure_mechanical_filtration_profile(_filtration_profile())
    return model


def test_publication_process_visual_schema_marker_matches_payload() -> None:
    runtime = DigitalTwinRuntime(
        _model(),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    service = RuntimeApplicationService(runtime)

    publication = service.publication()

    assert publication["process_visual_schema_version"] == 2
    assert publication["snapshot"]["process_visual"]["schema_version"] == 2


def test_backwash_discharge_stops_when_simulated_pond_is_empty() -> None:
    model = _model(water_level_pct=1.0)

    model.step(600.0, {"backwash_valve": 1.0})
    first = model.mechanical_filtration_snapshot()

    assert first["last_backwash_discharge_l"] == pytest.approx(200.0)
    assert first["cumulative_backwash_discharge_l"] == pytest.approx(200.0)
    assert model.state.water_level_pct == pytest.approx(0.0)

    model.step(60.0, {"backwash_valve": 1.0})
    second = model.mechanical_filtration_snapshot()

    assert second["last_backwash_discharge_l"] == pytest.approx(0.0)
    assert second["cumulative_backwash_discharge_l"] == pytest.approx(200.0)
    assert model.state.water_level_pct == pytest.approx(0.0)
