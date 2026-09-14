from __future__ import annotations

from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.filtration import MechanicalFiltrationProfile
from smart_koi_pond.digital_twin.hydraulics import (
    HydraulicRouteSpec,
    PondDesignProfile,
)
from smart_koi_pond.digital_twin.model import EnvironmentInputs
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.digital_twin.water_exchange import (
    SourceWaterProfile,
    WaterExchangePondModel,
)
from smart_koi_pond.domain.models import PondState


def _design(
    *,
    top_up_flow_l_min: float | None = 100.0,
    drain_flow_l_min: float | None = 100.0,
) -> PondDesignProfile:
    return PondDesignProfile(
        profile_id="pond",
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
        top_up_flow_l_min=top_up_flow_l_min,
        drain_flow_l_min=drain_flow_l_min,
    )


def _source(**overrides: float | str | None) -> SourceWaterProfile:
    values = {
        "profile_id": "source",
        "revision": "r1",
        "source_reference": "owner-water-test",
        "source_type": "WELL",
        "temperature_c": 25.0,
        "dissolved_oxygen_mg_l": 7.0,
        "ph": 7.8,
        "total_ammonia_nitrogen_mg_l": 0.0,
        "nitrite_mg_l": 0.0,
        "nitrate_mg_l": 0.0,
        "alkalinity_mg_l_as_caco3": 80.0,
    }
    values.update(overrides)
    return SourceWaterProfile(**values)


def _model(*, level: float = 100.0, source: SourceWaterProfile | None = None):
    model = WaterExchangePondModel(
        PondState(
            temperature_c=28.0,
            dissolved_oxygen_mg_l=6.0,
            ph=7.0,
            water_level_pct=level,
            total_ammonia_nitrogen_mg_l=1.0,
            nitrite_mg_l=2.0,
            nitrate_mg_l=40.0,
            alkalinity_mg_l_as_caco3=100.0,
            waste_solids_g=50.0,
        ),
        EnvironmentInputs(
            ambient_temperature_c=28.0,
            oxygen_demand_mg_l_per_hour=0.0,
        ),
        source_water=source,
    )
    model.configure_design_profile(_design())
    return model


def test_discharge_only_preserves_well_mixed_dissolved_concentrations() -> None:
    model = _model(source=_source())
    before = (
        model.state.total_ammonia_nitrogen_mg_l,
        model.state.nitrite_mg_l,
        model.state.nitrate_mg_l,
        model.state.alkalinity_mg_l_as_caco3,
    )

    model.step(60.0, {"drain_valve": 1.0})

    after = (
        model.state.total_ammonia_nitrogen_mg_l,
        model.state.nitrite_mg_l,
        model.state.nitrate_mg_l,
        model.state.alkalinity_mg_l_as_caco3,
    )
    assert after == before
    assert model.state.water_level_pct == pytest.approx(90.0)
    exchange = model.water_exchange_snapshot()["last_exchange"]
    assert exchange["discharge_l"] == pytest.approx(100.0)
    assert exchange["refill_l"] == 0.0
    assert exchange["parameter_results"]["nitrate_mg_l"]["status"] == (
        "DISCHARGE_ONLY_CONCENTRATION_INVARIANT"
    )


def test_lower_nitrate_source_water_dilutes_pond_nitrate() -> None:
    model = _model(level=80.0, source=_source(nitrate_mg_l=0.0))

    model.step(60.0, {"top_up_valve": 1.0})

    assert model.state.water_level_pct == pytest.approx(90.0)
    assert model.state.nitrate_mg_l == pytest.approx(40.0 * 800.0 / 900.0)
    evidence = model.water_exchange_snapshot()["last_exchange"]["parameter_results"]
    assert evidence["nitrate_mg_l"]["status"] == "CALCULATED_CONSERVED_MASS_MIXING"


def test_higher_nitrate_source_water_can_raise_pond_nitrate() -> None:
    model = _model(level=80.0, source=_source(nitrate_mg_l=100.0))

    model.step(60.0, {"top_up_valve": 1.0})

    expected = (40.0 * 800.0 + 100.0 * 100.0) / 900.0
    assert model.state.nitrate_mg_l == pytest.approx(expected)
    assert model.state.nitrate_mg_l > 40.0


def test_unknown_source_chemistry_is_not_fabricated_after_refill() -> None:
    model = _model(level=80.0, source=_source(nitrate_mg_l=None))

    model.step(60.0, {"top_up_valve": 1.0})

    assert model.state.nitrate_mg_l is None
    evidence = model.water_exchange_snapshot()["last_exchange"]["parameter_results"]
    assert evidence["nitrate_mg_l"]["after"] is None
    assert evidence["nitrate_mg_l"]["status"] == (
        "SOURCE_VALUE_UNKNOWN_POST_MIX_NOT_ESTABLISHED"
    )


def test_temperature_do_kh_and_tan_follow_supported_source_water_mixing() -> None:
    model = _model(
        level=80.0,
        source=_source(
            temperature_c=24.0,
            dissolved_oxygen_mg_l=8.0,
            total_ammonia_nitrogen_mg_l=0.0,
            alkalinity_mg_l_as_caco3=50.0,
        ),
    )

    model.step(60.0, {"top_up_valve": 1.0})

    assert model.state.temperature_c == pytest.approx(
        (28.0 * 800.0 + 24.0 * 100.0) / 900.0
    )
    assert model.state.dissolved_oxygen_mg_l == pytest.approx(
        (6.0 * 800.0 + 8.0 * 100.0) / 900.0
    )
    assert model.state.total_ammonia_nitrogen_mg_l == pytest.approx(
        1.0 * 800.0 / 900.0
    )
    assert model.state.alkalinity_mg_l_as_caco3 == pytest.approx(
        (100.0 * 800.0 + 50.0 * 100.0) / 900.0
    )


def test_ph_uses_explicit_simplified_buffer_model_not_linear_average() -> None:
    model = _model(
        level=80.0,
        source=_source(ph=8.0, alkalinity_mg_l_as_caco3=50.0),
    )

    model.step(60.0, {"top_up_valve": 1.0})

    linear_average = (7.0 * 800.0 + 8.0 * 100.0) / 900.0
    assert model.state.ph != pytest.approx(linear_average)
    assert 7.0 < model.state.ph < 8.0
    ph_evidence = model.water_exchange_snapshot()["last_exchange"][
        "parameter_results"
    ]["ph"]
    assert ph_evidence["status"] == "MODELED_SIMPLIFIED_BUFFER_WEIGHTED_H_ACTIVITY"
    assert ph_evidence["laboratory_equilibrium_claim"] is False


def test_backwash_discharge_plus_refill_changes_nitrate_by_source_mix() -> None:
    model = _model(source=_source(nitrate_mg_l=0.0))
    model.configure_mechanical_filtration_profile(
        MechanicalFiltrationProfile(
            profile_id="filter",
            revision="r1",
            source_reference="filter-manual",
            filtered_route_id="main-circulation",
            capture_efficiency_per_pass=0.5,
            max_captured_solids_g=1000.0,
            minimum_route_throughput_factor_at_capacity=0.5,
            backwash_solids_removal_g_per_min=100.0,
            backwash_discharge_flow_l_min=100.0,
        )
    )

    model.step(60.0, {"backwash_valve": 1.0, "top_up_valve": 1.0})

    assert model.state.water_level_pct == pytest.approx(100.0)
    assert model.state.nitrate_mg_l == pytest.approx(36.0)
    exchange = model.water_exchange_snapshot()["last_exchange"]
    assert exchange["discharge_l"] == pytest.approx(100.0)
    assert exchange["refill_l"] == pytest.approx(100.0)
    assert exchange["discharge_breakdown_l"]["backwash"] == pytest.approx(100.0)


def test_source_water_profile_survives_runtime_checkpoint_restart() -> None:
    runtime = build_integrated_virtual_runtime()
    runtime.configure_design_profile(_design())
    assert isinstance(runtime.model, WaterExchangePondModel)
    runtime.model.configure_source_water_profile(_source())
    checkpoint = runtime.capture_checkpoint()

    restored = build_integrated_virtual_runtime()
    restored.restore_checkpoint(checkpoint)

    assert isinstance(restored.model, WaterExchangePondModel)
    source = restored.model.source_water_snapshot()
    assert source["configured"] is True
    assert source["profile_id"] == "source"
    assert source["nitrate_mg_l"] == 0.0


def test_service_configuration_is_role_gated_audited_and_published() -> None:
    runtime = build_integrated_virtual_runtime()
    service = RuntimeApplicationService(runtime)
    payload = {"profile": _source().to_dict(), "actor": "owner-test"}

    with pytest.raises(PermissionError):
        service.command("configure_source_water_profile", payload, role="operator")

    service.command("configure_source_water_profile", payload, role="engineering")
    publication = service.publication()
    source = publication["snapshot"]["hydraulics"]["water_exchange"]["source_water"]
    assert source["configured"] is True
    assert source["source_type"] == "WELL"
    assert publication["source_water_exchange_schema_version"] == 1
    assert any(
        event.code == "SOURCE_WATER_PROFILE_CONFIGURED"
        for event in runtime.events.events
    )


def test_historian_playback_and_browser_surface_use_canonical_exchange_state() -> None:
    runtime = DigitalTwinRuntime(
        WaterExchangePondModel(
            PondState(
                temperature_c=28.0,
                dissolved_oxygen_mg_l=6.0,
                ph=7.0,
                water_level_pct=80.0,
                total_ammonia_nitrogen_mg_l=1.0,
                nitrite_mg_l=2.0,
                nitrate_mg_l=40.0,
                alkalinity_mg_l_as_caco3=100.0,
                waste_solids_g=50.0,
            ),
            EnvironmentInputs(
                ambient_temperature_c=28.0,
                oxygen_demand_mg_l_per_hour=0.0,
            ),
            source_water=_source(nitrate_mg_l=0.0),
        ),
        SimulationControlPolicy(
            do_watch_below=5.0,
            do_emergency_below=4.0,
            do_recover_above=5.5,
            flow_watch_below=8.0,
            water_level_low_below=70.0,
            verification_delay_seconds=120.0,
            do_verification_min_delta=0.01,
        ),
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        config_version="source-water-test",
    )
    runtime.configure_design_profile(_design())
    runtime.model.step(60.0, {"top_up_valve": 1.0})
    snapshot = runtime.tick(0.0)
    assert snapshot.hydraulics["water_exchange"]["last_exchange"]["refill_l"] == 100.0
    frame = runtime.playback_frame(runtime.historian.latest_sequence)
    assert frame["snapshot"]["hydraulics"]["water_exchange"]["last_exchange"][
        "refill_l"
    ] == 100.0
    assert "Source Water & Water Exchange" in COMPOSED_INDEX_HTML
    assert "configure_source_water_profile" in COMPOSED_INDEX_HTML
