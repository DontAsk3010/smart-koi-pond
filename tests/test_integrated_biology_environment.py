from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.digital_twin.biology import BiologicalProcessProfile
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.hydraulics import (
    EngineeringProvenance,
    HydraulicRouteRole,
    HydraulicRouteSpec,
    PondDesignProfile,
)
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.digital_twin.scenario_control import (
    ScenarioTrigger,
    VirtualScenarioController,
)
from smart_koi_pond.domain.enums import OperatingMode, SystemState
from smart_koi_pond.domain.models import PondState

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    tan_watch_above=0.4,
    tan_emergency_above=1.5,
    nitrite_watch_above=0.4,
    nitrite_emergency_above=1.5,
    nitrate_watch_above=20.0,
    ph_watch_below=6.8,
    ph_watch_above=8.2,
    ph_emergency_below=6.0,
    ph_emergency_above=9.0,
)


def design_profile(
    *,
    volume_l: float = 20_000.0,
    biomass_kg: float | None = 50.0,
    feed_kg_per_day: float | None = 1.0,
    revision: str = "pond-r1",
) -> PondDesignProfile:
    return PondDesignProfile(
        profile_id="explicit-test-pond",
        revision=revision,
        effective_volume_l=volume_l,
        circulation_turnovers_per_hour_guide=1.0,
        biomass_kg=biomass_kg,
        feed_kg_per_day=feed_kg_per_day,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
        routes=(
            HydraulicRouteSpec(
                route_id="main-route",
                asset_id="main_pump",
                rated_flow_l_min=400.0,
                role=HydraulicRouteRole.PRIMARY,
                provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
            ),
            HydraulicRouteSpec(
                route_id="backup-route",
                asset_id="backup_pump",
                rated_flow_l_min=400.0,
                role=HydraulicRouteRole.BACKUP,
                provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
            ),
        ),
    )


def biological_profile(revision: str = "bio-r1") -> BiologicalProcessProfile:
    return BiologicalProcessProfile(
        profile_id="explicit-test-biology",
        revision=revision,
        source_reference="TEST_FIXTURE_EXPLICIT_INPUT_NOT_PRODUCTION_SETPOINT",
        biofilter_ammonia_capacity_g_n_per_day=20.0,
        biofilter_nitrite_capacity_g_n_per_day=10.0,
        fish_oxygen_demand_g_o2_per_kg_hour=0.01,
        feed_oxygen_demand_g_o2_per_kg_feed=2.0,
        ammonia_n_generation_g_per_kg_feed=30.0,
        solid_waste_g_per_kg_feed=200.0,
        nitrification_oxygen_g_o2_per_g_n=1.0,
        alkalinity_consumption_g_caco3_per_g_n=2.0,
        nitrification_do_reference_mg_l=5.0,
        ph_drop_per_100_mg_l_alkalinity_loss=0.1,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
    )


def pond_state(*, chemistry: bool = True) -> PondState:
    return PondState(
        27.0,
        6.0,
        7.4,
        85.0,
        total_ammonia_nitrogen_mg_l=0.0 if chemistry else None,
        nitrite_mg_l=0.0 if chemistry else None,
        nitrate_mg_l=0.0 if chemistry else None,
        alkalinity_mg_l_as_caco3=150.0 if chemistry else None,
        waste_solids_g=0.0 if chemistry else None,
    )


def configured_model(
    *,
    profile: PondDesignProfile | None = None,
    state: PondState | None = None,
) -> PondModel:
    model = PondModel(
        state or pond_state(),
        EnvironmentInputs(ambient_temperature_c=27.0, oxygen_demand_mg_l_per_hour=0.0),
    )
    model.configure_design_profile(profile or design_profile())
    model.configure_biological_profile(biological_profile())
    return model


def configured_runtime() -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        configured_model(),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        config_version="integrated-biology-test-v1",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_missing_biological_inputs_remain_input_required_without_fabrication() -> None:
    model = configured_model(
        profile=design_profile(biomass_kg=None, feed_kg_per_day=None),
        state=pond_state(chemistry=False),
    )

    model.step(3600.0, {"main_pump": 1.0})
    biology = model.biological_snapshot()

    assert biology["status"] == "INPUT_REQUIRED"
    assert set(biology["missing_inputs"]) == {"biomass_kg", "feed_kg_per_day"}
    assert biology["chemistry_evolution_active"] is False
    assert model.state.total_ammonia_nitrogen_mg_l is None
    assert model.state.nitrite_mg_l is None
    assert model.state.nitrate_mg_l is None


def test_metric_units_and_explicit_provenance_are_canonical() -> None:
    model = configured_model()
    model.step(0.0, {"main_pump": 1.0})
    biology = model.biological_snapshot()

    assert biology["units"] == {
        "volume": "L",
        "biomass": "kg",
        "feed": "kg/day",
        "oxygen_demand": "mg/L/hour",
        "tan": "mg/L",
        "nitrite": "mg/L",
        "nitrate": "mg/L",
        "alkalinity": "mg/L as CaCO3",
        "waste_solids": "g",
    }
    assert biology["provenance"] == "USER_CONFIGURED_SCENARIO"
    assert "DESIGN_ASSUMPTION" not in str(biology)


def test_feed_and_biomass_drive_oxygen_demand_waste_and_nitrogen_cycle() -> None:
    model = configured_model()
    before_ph = model.state.ph
    before_alkalinity = model.state.alkalinity_mg_l_as_caco3

    model.step(86_400.0, {"main_pump": 1.0})
    biology = model.biological_snapshot()

    assert biology["biological_oxygen_demand_mg_l_per_hour"] > 0.0
    assert model.state.total_ammonia_nitrogen_mg_l == pytest.approx(0.5)
    assert model.state.nitrite_mg_l == pytest.approx(0.5)
    assert model.state.nitrate_mg_l == pytest.approx(0.5)
    assert model.state.waste_solids_g == pytest.approx(200.0)
    assert model.state.alkalinity_mg_l_as_caco3 < before_alkalinity
    assert model.state.ph < before_ph


def test_low_do_or_low_flow_constrains_biofilter_conversion() -> None:
    low_do = configured_model(
        state=PondState(
            27.0,
            0.0,
            7.4,
            85.0,
            total_ammonia_nitrogen_mg_l=0.0,
            nitrite_mg_l=0.0,
            nitrate_mg_l=0.0,
            alkalinity_mg_l_as_caco3=150.0,
            waste_solids_g=0.0,
        )
    )
    low_do.step(86_400.0, {"main_pump": 1.0})
    assert low_do.state.total_ammonia_nitrogen_mg_l == pytest.approx(1.5)
    assert low_do.state.nitrite_mg_l == pytest.approx(0.0)
    assert low_do.state.nitrate_mg_l == pytest.approx(0.0)

    no_flow = configured_model()
    no_flow.step(86_400.0, {})
    assert no_flow.state.total_ammonia_nitrogen_mg_l == pytest.approx(1.5)
    assert no_flow.state.nitrite_mg_l == pytest.approx(0.0)
    assert no_flow.state.nitrate_mg_l == pytest.approx(0.0)


def test_high_tan_uses_safe_support_and_feed_inhibit_without_chemical_dosing() -> None:
    service = RuntimeApplicationService(configured_runtime())

    snapshot = service.command(
        "set_environment_state",
        {"parameter": "tan", "value": 0.8},
        role="engineering",
    )

    assert "TAN_HIGH" in snapshot.classification.reasons
    assert snapshot.classification.state == SystemState.CORRECTING
    assert snapshot.commands["backup_aerator"].final_on is True
    assert snapshot.commands["backup_pump"].final_on is True
    assert snapshot.commands["feeder"].final_on is False
    assert all("dos" not in asset_id.lower() for asset_id in snapshot.commands)


def test_environment_disturbance_is_role_gated_audited_and_publishable() -> None:
    service = RuntimeApplicationService(configured_runtime())

    with pytest.raises(PermissionError):
        service.command(
            "set_environment_state",
            {"parameter": "nitrate", "value": 25.0},
            role="operator",
        )

    snapshot = service.command(
        "set_environment_state",
        {"parameter": "nitrate", "value": 25.0},
        role="engineering",
    )
    publication = service.publication()

    assert snapshot.pond_truth.nitrate_mg_l == pytest.approx(25.0)
    assert publication["snapshot"]["biology"]["configured"] is True
    assert publication["snapshot"]["pond_truth"]["nitrate_mg_l"] == pytest.approx(25.0)
    assert any(
        event.code == "SIMULATION_ENVIRONMENT_STATE_CHANGED"
        for event in service.runtime.events.events
    )


def test_automatic_environment_trigger_uses_same_scenario_authority() -> None:
    service = RuntimeApplicationService(configured_runtime())
    service.scenarios.schedule(
        ScenarioTrigger(
            action="set_environment_state",
            payload={"parameter": "ph", "value": 6.5},
            after_seconds=60.0,
        )
    )

    snapshot = service.step(60.0)

    assert snapshot.pond_truth.ph == pytest.approx(6.5)
    assert "PH_OUT_OF_TARGET" in snapshot.classification.reasons
    assert any(
        event.code == "SIMULATION_TRIGGER_FIRED"
        for event in service.runtime.events.events
    )


def test_safe_runtime_reset_preserves_biology_and_chemistry_but_deenergizes_outputs() -> None:
    runtime = configured_runtime()
    scenarios = VirtualScenarioController(runtime)
    scenarios.set_environment_state("tan", 0.9)
    scenarios.set_environment_state("nitrite", 0.7)
    scenarios.set_environment_state("nitrate", 24.0)
    scenarios.safe_runtime_reset()

    assert runtime.model.state.total_ammonia_nitrogen_mg_l == pytest.approx(0.9)
    assert runtime.model.state.nitrite_mg_l == pytest.approx(0.7)
    assert runtime.model.state.nitrate_mg_l == pytest.approx(24.0)
    assert runtime.model.biology is not None
    assert runtime.model.biology.profile.profile_id == "explicit-test-biology"
    assert runtime.operating_mode == OperatingMode.RECOVERY_SYNC
    assert all(not asset.feedback_on for asset in runtime.actuators.assets.values())


def test_volume_biomass_and_feed_revision_recalculates_oxygen_load() -> None:
    service = RuntimeApplicationService(configured_runtime())
    first = service.publication()["snapshot"]["biology"][
        "biological_oxygen_demand_mg_l_per_hour"
    ]

    service.command(
        "configure_design_profile",
        {
            "profile": design_profile(
                volume_l=40_000.0,
                biomass_kg=100.0,
                feed_kg_per_day=2.0,
                revision="pond-r2",
            ).to_dict()
        },
        role="engineering",
    )
    second = service.publication()["snapshot"]["biology"][
        "biological_oxygen_demand_mg_l_per_hour"
    ]

    assert first is not None
    assert second is not None
    assert second == pytest.approx(first)
    assert service.publication()["snapshot"]["design_profile"]["revision"] == "pond-r2"
