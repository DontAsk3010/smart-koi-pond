from __future__ import annotations

import pytest

from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.digital_twin.hydraulics import HydraulicRouteSpec, PondDesignProfile
from smart_koi_pond.digital_twin.water_exchange import SourceWaterProfile, WaterExchangePondModel
from smart_koi_pond.domain.enums import OperatingMode


def _design() -> PondDesignProfile:
    return PondDesignProfile(
        profile_id="mass-audit-pond",
        revision="r1",
        effective_volume_l=1000.0,
        circulation_turnovers_per_hour_guide=1.0,
        routes=(
            HydraulicRouteSpec(
                route_id="main-circulation",
                asset_id="main_pump",
                rated_flow_l_min=100.0,
            ),
        ),
        top_up_flow_l_min=100.0,
        drain_flow_l_min=100.0,
    )


def _source(*, nitrate_mg_l: float = 10.0) -> SourceWaterProfile:
    return SourceWaterProfile(
        profile_id="mass-audit-source",
        revision="r1",
        source_reference="mass-balance-audit-input",
        source_type="WELL",
        temperature_c=27.0,
        dissolved_oxygen_mg_l=6.0,
        ph=7.2,
        total_ammonia_nitrogen_mg_l=0.0,
        nitrite_mg_l=0.0,
        nitrate_mg_l=nitrate_mg_l,
        alkalinity_mg_l_as_caco3=100.0,
    )


def test_explicit_nitrate_mass_is_conserved_across_discharge_and_refill() -> None:
    runtime = build_integrated_virtual_runtime()
    runtime.configure_design_profile(_design())
    assert isinstance(runtime.model, WaterExchangePondModel)
    runtime.model.configure_source_water_profile(_source(nitrate_mg_l=10.0))
    runtime.model.set_truth("nitrate_mg_l", 40.0)
    runtime.model.state.water_level_pct = 100.0

    initial_mass_mg = 40.0 * 1000.0
    runtime.model.step(60.0, {"drain_valve": 1.0})

    assert runtime.model.state.water_level_pct == pytest.approx(90.0)
    assert runtime.model.state.nitrate_mg_l == pytest.approx(40.0)
    remaining_mass_mg = runtime.model.state.nitrate_mg_l * 900.0
    removed_mass_mg = 40.0 * 100.0
    assert remaining_mass_mg + removed_mass_mg == pytest.approx(initial_mass_mg)

    runtime.model.step(60.0, {"top_up_valve": 1.0})

    expected_final_mass_mg = remaining_mass_mg + 10.0 * 100.0
    actual_final_mass_mg = runtime.model.state.nitrate_mg_l * 1000.0
    assert actual_final_mass_mg == pytest.approx(expected_final_mass_mg)
    assert runtime.model.state.nitrate_mg_l == pytest.approx(37.0)


def test_governed_water_change_workflow_drives_real_mass_balance_path() -> None:
    runtime = build_integrated_virtual_runtime()
    runtime.configure_design_profile(_design())
    assert isinstance(runtime.model, WaterExchangePondModel)
    runtime.model.configure_source_water_profile(_source(nitrate_mg_l=0.0))
    runtime.model.set_truth("nitrate_mg_l", 40.0)
    runtime.model.state.water_level_pct = 100.0

    runtime.start_water_change(
        "MASS_BALANCE_AUDIT",
        target_drain_level_pct=80.0,
        target_refill_level_pct=100.0,
    )

    runtime.tick(0.0)  # acquire workflow ownership and energize drain path
    runtime.tick(60.0)
    runtime.tick(60.0)  # reaches 80%, closes drain and opens refill
    runtime.tick(60.0)
    runtime.tick(60.0)  # returns to 100% and enters recovery/return-to-auto path
    runtime.tick(0.0)

    assert runtime.model.state.water_level_pct == pytest.approx(100.0)
    assert runtime.model.state.nitrate_mg_l == pytest.approx(32.0)
    assert runtime.operating_mode == OperatingMode.NORMAL_AUTO
    exchange = runtime.model.water_exchange_snapshot()
    assert exchange["cumulative_discharge_l"] == pytest.approx(200.0)
    assert exchange["cumulative_refill_l"] == pytest.approx(200.0)
    assert exchange["last_exchange"]["source_profile_id"] == "mass-audit-source"
