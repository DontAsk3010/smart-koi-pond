from __future__ import annotations

import pytest

from smart_koi_pond.digital_twin.biology import BiologicalProcessProfile
from smart_koi_pond.digital_twin.filtration import MechanicalFiltrationProfile
from smart_koi_pond.digital_twin.hydraulics import (
    EngineeringProvenance,
    HydraulicRouteSpec,
    PondDesignProfile,
)
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.water_exchange import WaterExchangePondModel
from smart_koi_pond.domain.models import PondState


def _design(*, top_up: float | None = None, drain: float | None = None) -> PondDesignProfile:
    return PondDesignProfile(
        profile_id="actual-volume-test-pond",
        revision="r1",
        effective_volume_l=1000.0,
        circulation_turnovers_per_hour_guide=1.0,
        routes=(
            HydraulicRouteSpec(
                route_id="main-route",
                asset_id="main_pump",
                rated_flow_l_min=100.0,
            ),
        ),
        top_up_flow_l_min=top_up,
        drain_flow_l_min=drain,
        biomass_kg=0.0,
        feed_kg_per_day=1.0,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
    )


def _biology() -> BiologicalProcessProfile:
    return BiologicalProcessProfile(
        profile_id="actual-volume-test-biology",
        revision="r1",
        source_reference="TEST_EXPLICIT_INPUT_NOT_PRODUCTION_SETPOINT",
        biofilter_ammonia_capacity_g_n_per_day=0.0,
        biofilter_nitrite_capacity_g_n_per_day=0.0,
        fish_oxygen_demand_g_o2_per_kg_hour=0.0,
        feed_oxygen_demand_g_o2_per_kg_feed=0.0,
        ammonia_n_generation_g_per_kg_feed=10.0,
        solid_waste_g_per_kg_feed=0.0,
        nitrification_oxygen_g_o2_per_g_n=0.0,
        alkalinity_consumption_g_caco3_per_g_n=0.0,
        nitrification_do_reference_mg_l=5.0,
        ph_drop_per_100_mg_l_alkalinity_loss=0.0,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
    )


def _filter(*, backwash_flow: float | None = 100.0) -> MechanicalFiltrationProfile:
    return MechanicalFiltrationProfile(
        profile_id="actual-volume-test-filter",
        revision="r1",
        source_reference="TEST_EXPLICIT_INPUT_NOT_PRODUCTION_RATING",
        filtered_route_id="main-route",
        capture_efficiency_per_pass=0.5,
        max_captured_solids_g=1000.0,
        minimum_route_throughput_factor_at_capacity=1.0,
        backwash_solids_removal_g_per_min=0.0,
        backwash_discharge_flow_l_min=backwash_flow,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
    )


def _state(*, level: float, waste: float = 100.0) -> PondState:
    return PondState(
        temperature_c=27.0,
        dissolved_oxygen_mg_l=6.0,
        ph=7.4,
        water_level_pct=level,
        total_ammonia_nitrogen_mg_l=0.0,
        nitrite_mg_l=0.0,
        nitrate_mg_l=0.0,
        alkalinity_mg_l_as_caco3=100.0,
        waste_solids_g=waste,
    )


def test_hydraulic_snapshot_exposes_actual_volume_from_water_level() -> None:
    model = PondModel(_state(level=80.0), EnvironmentInputs(27.0, 0.0))
    model.configure_design_profile(_design())

    hydraulic = model.hydraulic_snapshot()

    assert model.actual_water_volume_l() == pytest.approx(800.0)
    assert hydraulic["actual_water_volume_l"] == pytest.approx(800.0)
    assert hydraulic["actual_water_volume_provenance"] == "CALCULATED"
    assert hydraulic["actual_water_volume_basis"] == "EFFECTIVE_VOLUME_X_WATER_LEVEL"
    assert hydraulic["process_volume_integration_basis"] == (
        "ACTUAL_MODELED_VOLUME_AT_STEP_START"
    )


def test_biology_uses_actual_partial_volume_for_mass_to_concentration() -> None:
    model = PondModel(_state(level=50.0, waste=0.0), EnvironmentInputs(27.0, 0.0))
    model.configure_design_profile(_design())
    model.configure_biological_profile(_biology())

    model.step(86_400.0, {})
    biology = model.biological_snapshot()

    assert biology["water_volume_l"] == pytest.approx(500.0)
    assert biology["water_volume_basis"] == "ACTUAL_MODELED_VOLUME_AT_STEP_START"
    assert model.state.total_ammonia_nitrogen_mg_l == pytest.approx(20.0)


def test_mechanical_capture_and_tss_use_actual_partial_volume() -> None:
    model = PondModel(_state(level=50.0), EnvironmentInputs(27.0, 0.0))
    model.configure_design_profile(_design())
    model.configure_mechanical_filtration_profile(_filter(backwash_flow=None))

    model.step(60.0, {"main_pump": 1.0})
    mechanical = model.mechanical_filtration_snapshot()
    expected_capture_fraction = 1.0 - 0.5 ** (100.0 / 500.0)
    expected_remaining = 100.0 * (1.0 - expected_capture_fraction)

    assert mechanical["last_process_water_volume_l"] == pytest.approx(500.0)
    assert mechanical["last_captured_g"] == pytest.approx(100.0 * expected_capture_fraction)
    assert mechanical["tss_mg_l"] == pytest.approx(expected_remaining * 1000.0 / 500.0)


def test_backwash_available_water_is_actual_volume_not_level_applied_twice() -> None:
    model = PondModel(_state(level=50.0), EnvironmentInputs(27.0, 0.0))
    model.configure_design_profile(_design())
    model.configure_mechanical_filtration_profile(_filter(backwash_flow=600.0))

    model.step(60.0, {"backwash_valve": 1.0})
    mechanical = model.mechanical_filtration_snapshot()

    assert mechanical["last_process_water_volume_l"] == pytest.approx(500.0)
    assert mechanical["last_backwash_discharge_l"] == pytest.approx(500.0)
    assert model.state.water_level_pct == pytest.approx(0.0)


def test_zero_actual_water_volume_stops_aqueous_processes_without_division() -> None:
    model = PondModel(_state(level=0.0), EnvironmentInputs(27.0, 0.0))
    model.configure_design_profile(_design())
    model.configure_biological_profile(_biology())
    model.configure_mechanical_filtration_profile(_filter())

    model.step(60.0, {"main_pump": 1.0, "backwash_valve": 1.0})

    biology = model.biological_snapshot()
    mechanical = model.mechanical_filtration_snapshot()
    assert biology["status"] == "NO_WATER_VOLUME"
    assert biology["chemistry_evolution_active"] is False
    assert biology["biological_oxygen_demand_mg_l_per_hour"] is None
    assert mechanical["last_process_water_volume_l"] == 0.0
    assert mechanical["last_captured_g"] == 0.0
    assert mechanical["last_backwash_discharge_l"] == 0.0
    assert mechanical["tss_mg_l"] is None


def test_partial_drain_updates_process_volume_on_following_integration_step() -> None:
    model = WaterExchangePondModel(
        _state(level=100.0, waste=0.0),
        EnvironmentInputs(27.0, 0.0),
    )
    model.configure_design_profile(_design(drain=500.0))
    model.configure_biological_profile(_biology())

    model.step(60.0, {"drain_valve": 1.0})
    assert model.state.water_level_pct == pytest.approx(50.0)

    model.state.total_ammonia_nitrogen_mg_l = 0.0
    model.step(86_400.0, {})

    assert model.biological_snapshot()["water_volume_l"] == pytest.approx(500.0)
    assert model.state.total_ammonia_nitrogen_mg_l == pytest.approx(20.0)
