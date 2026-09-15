from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy, decide
from smart_koi_pond.control.water_quality import (
    WaterQualityRecoveryManager,
    WaterQualityRecoveryPolicy,
)
from smart_koi_pond.control.water_quality_config import (
    WaterQualityThresholdProfile,
)
from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.koi_stock_service import KoiStockRuntimeApplicationService
from smart_koi_pond.digital_twin.biology import (
    BiologicalProcessModel,
    BiologicalProcessProfile,
)
from smart_koi_pond.digital_twin.hydraulics import (
    EngineeringProvenance,
    HydraulicNetworkModel,
    HydraulicRouteSpec,
    PondDesignProfile,
)
from smart_koi_pond.digital_twin.koi_stock import (
    FeedingPolicy,
    KoiStockGroup,
    KoiStockProfile,
    indonesia_juvenile_koi_estimator_v1,
)
from smart_koi_pond.digital_twin.koi_stock_model import KoiStockWaterExchangePondModel
from smart_koi_pond.digital_twin.model import EnvironmentInputs
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    DataQuality,
    OperatingMode,
    SystemState,
)
from smart_koi_pond.domain.models import Classification, PondState, StateEstimate
from smart_koi_pond.sensors.real import BufferedRealSensorSuite


NOW = datetime(2026, 9, 15, tzinfo=UTC)


def _stock(*, length_cm=None, weight_g=None, count=10):
    return KoiStockProfile(
        profile_id="owner-stock",
        revision="r1",
        groups=(
            KoiStockGroup(
                group_id="g1",
                count=count,
                average_length_cm=length_cm,
                average_weight_g=weight_g,
                weight_provenance=EngineeringProvenance.MEASURED,
            ),
        ),
        source_reference="owner-stock-record",
        estimator=indonesia_juvenile_koi_estimator_v1(),
        provenance=EngineeringProvenance.USER_CONFIGURED,
    )


def _feeding(rate=0.02, meals=4):
    return FeedingPolicy(
        policy_id="owner-feeding",
        revision="r1",
        source_reference="owner-configured-feeding-policy",
        body_weight_fraction_per_day=rate,
        meals_per_day=meals,
        provenance=EngineeringProvenance.USER_CONFIGURED,
    )


def test_length_weight_estimator_is_bounded_and_does_not_extrapolate():
    estimator = indonesia_juvenile_koi_estimator_v1()
    assert estimator.estimate_weight_g(16.0) == pytest.approx(79.321)

    unresolved = _stock(length_cm=25.0, count=5).evaluate_biomass()
    assert unresolved["status"] == "INPUT_REQUIRED"
    assert unresolved["biomass_kg"] is None
    assert unresolved["groups"][0]["status"] == "OUTSIDE_ESTIMATOR_DOMAIN"
    assert unresolved["estimator_extrapolation_allowed"] is False


def test_measured_weight_overrides_length_estimator_domain():
    snapshot = _stock(length_cm=50.0, weight_g=500.0, count=5).evaluate_biomass()
    assert snapshot["status"] == "READY"
    assert snapshot["biomass_kg"] == pytest.approx(2.5)
    assert snapshot["groups"][0]["weight_basis"] == "ENTERED_WEIGHT"
    assert snapshot["groups"][0]["weight_provenance"] == "MEASURED"


def test_feeding_plan_is_derived_from_biomass_and_meals():
    biomass = _stock(weight_g=100.0, count=10).evaluate_biomass()
    plan = _feeding(rate=0.02, meals=4).evaluate(
        biomass_snapshot=biomass,
        temperature_c=27.0,
    )
    assert plan["planned_feed_kg_per_day"] == pytest.approx(0.02)
    assert plan["planned_feed_per_meal_g"] == pytest.approx(5.0)
    assert plan["meals_per_day"] == 4


def _biological_model(*, inhibited: bool):
    pond_profile = PondDesignProfile(
        profile_id="pond",
        revision="r1",
        effective_volume_l=1000.0,
        circulation_turnovers_per_hour_guide=1.0,
        routes=(
            HydraulicRouteSpec(
                route_id="main-circulation",
                asset_id="main_pump",
                rated_flow_l_min=20.0,
            ),
        ),
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
    )
    biology_profile = BiologicalProcessProfile(
        profile_id="biology",
        revision="r1",
        source_reference="test-explicit-coefficients",
        biofilter_ammonia_capacity_g_n_per_day=0.0,
        biofilter_nitrite_capacity_g_n_per_day=0.0,
        fish_oxygen_demand_g_o2_per_kg_hour=0.0,
        feed_oxygen_demand_g_o2_per_kg_feed=0.0,
        ammonia_n_generation_g_per_kg_feed=100.0,
        solid_waste_g_per_kg_feed=0.0,
        nitrification_oxygen_g_o2_per_g_n=0.0,
        alkalinity_consumption_g_caco3_per_g_n=0.0,
        nitrification_do_reference_mg_l=5.0,
        ph_drop_per_100_mg_l_alkalinity_loss=0.0,
        provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
    )
    model = KoiStockWaterExchangePondModel(
        PondState(
            temperature_c=27.0,
            dissolved_oxygen_mg_l=6.0,
            ph=7.2,
            water_level_pct=100.0,
            total_ammonia_nitrogen_mg_l=0.0,
            nitrite_mg_l=0.0,
            nitrate_mg_l=0.0,
            alkalinity_mg_l_as_caco3=100.0,
            waste_solids_g=0.0,
        ),
        EnvironmentInputs(
            ambient_temperature_c=27.0,
            oxygen_demand_mg_l_per_hour=0.0,
        ),
        hydraulics=HydraulicNetworkModel(pond_profile),
        biology=BiologicalProcessModel(biology_profile),
        koi_stock=_stock(weight_g=100.0, count=10),
        feeding_policy=_feeding(rate=0.02, meals=4),
    )
    model.set_water_quality_feed_inhibited(
        inhibited,
        "NITRITE_HIGH" if inhibited else None,
    )
    return model


def test_feed_inhibit_removes_future_feed_load_from_biology():
    feeding = _biological_model(inhibited=False)
    feeding.step(86400.0, {"main_pump": 1.0})
    assert feeding.state.total_ammonia_nitrogen_mg_l == pytest.approx(2.0)

    inhibited = _biological_model(inhibited=True)
    inhibited.step(86400.0, {"main_pump": 1.0})
    assert inhibited.state.total_ammonia_nitrogen_mg_l == pytest.approx(0.0)
    plan = inhibited.feeding_plan_snapshot()
    assert plan["planned_feed_kg_per_day"] == pytest.approx(0.02)
    assert plan["effective_feed_kg_per_day"] == pytest.approx(0.0)
    assert plan["water_quality_feed_inhibited"] is True


def _policy():
    return SimulationControlPolicy(
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


def test_nitrate_high_inhibits_feeding_without_fabricating_acute_support():
    values = {
        "dissolved_oxygen_mg_l": 5.2,
        "circulation_flow_l_min": 10.0,
        "total_ammonia_nitrogen_mg_l": 0.0,
        "nitrite_mg_l": 0.0,
        "nitrate_mg_l": 30.0,
        "ph": 7.2,
    }
    estimate = StateEstimate(
        timestamp=NOW,
        values=values,
        quality={name: DataQuality.GOOD for name in values},
    )
    intents = decide(
        estimate,
        Classification(SystemState.WATCH, ("NITRATE_HIGH",)),
        _policy(),
    )
    feeder = next(item for item in intents if item.asset_id == "feeder")
    assert feeder.requested_on is False
    assert feeder.reason == "WATER_QUALITY_FEED_INHIBIT"
    assert not any(
        item.asset_id in {"backup_pump", "backup_aerator"} and item.requested_on
        for item in intents
    )


def test_real_sensor_adapter_accepts_chemistry_without_inventing_samples():
    suite = BufferedRealSensorSuite(
        device_bindings={
            "tan": "tan-01",
            "nitrite": "nitrite-01",
            "nitrate": "nitrate-01",
            "alkalinity": "alk-01",
        }
    )
    suite.ingest("nitrite", device_id="nitrite-01", value=0.6, timestamp=NOW)
    state = PondState(27.0, 6.0, 7.2, 85.0)
    samples = suite.sample(state, NOW)
    assert samples["nitrite"].value == pytest.approx(0.6)
    assert samples["nitrite"].source_state.value == "REAL_SOURCE"
    assert samples["tan"].value is None
    assert samples["tan"].availability == AvailabilityState.UNKNOWN


def _snapshot(reason, parameter, value, *, mode=OperatingMode.NORMAL_AUTO):
    return SimpleNamespace(
        timestamp=NOW,
        operating_mode=mode,
        classification=SimpleNamespace(reasons=(reason,)),
        estimate=SimpleNamespace(
            values={parameter: value, "water_level_pct": 85.0}
        ),
    )


def test_nitrite_recovery_requests_only_qualified_safer_water_exchange():
    manager = WaterQualityRecoveryManager(
        WaterQualityRecoveryPolicy(
            enabled=True,
            exchange_fraction_pct=10.0,
            max_attempts=2,
            cooldown_seconds=0.0,
            nitrite_recover_below=0.3,
        )
    )
    snap = _snapshot("NITRITE_HIGH", "nitrite_mg_l", 0.8)
    unqualified = {
        "pond_use_qualified": False,
        "nitrite_mg_l": 0.0,
    }
    assert manager.observe(snap, unqualified) is None
    assert manager.last_outcome == "NO_SAFE_AUTOMATIC_WATER_EXCHANGE_PATH"

    manager.last_outcome = None
    qualified = {
        "pond_use_qualified": True,
        "nitrite_mg_l": 0.05,
    }
    request = manager.observe(snap, qualified)
    assert request is not None
    assert request["parameter"] == "nitrite_mg_l"
    assert request["target_drain_level_pct"] == pytest.approx(75.0)
    assert request["target_refill_level_pct"] == pytest.approx(85.0)


def test_ph_recovery_refuses_source_that_moves_away_from_recovery_band():
    manager = WaterQualityRecoveryManager(
        WaterQualityRecoveryPolicy(
            enabled=True,
            exchange_fraction_pct=10.0,
            ph_recover_low=6.9,
            ph_recover_high=8.1,
        )
    )
    snap = _snapshot("PH_OUT_OF_TARGET", "ph", 8.6)
    source = {"pond_use_qualified": True, "ph": 9.0}
    assert manager.observe(snap, source) is None
    assert manager.last_outcome == "NO_SAFE_AUTOMATIC_WATER_EXCHANGE_PATH"


def test_water_quality_thresholds_are_governed_reconfigurable_not_hidden_defaults():
    runtime = build_integrated_virtual_runtime()
    profile = WaterQualityThresholdProfile(
        profile_id="owner-water-policy",
        revision="r1",
        source_reference="commissioning-policy-reference",
        tan_watch_above=0.25,
        tan_emergency_above=0.8,
        tan_recover_below=0.15,
        nitrite_watch_above=0.2,
        nitrite_emergency_above=0.6,
        nitrite_recover_below=0.1,
        nitrate_watch_above=25.0,
        nitrate_recover_below=15.0,
        ph_watch_below=6.9,
        ph_watch_above=8.1,
        ph_emergency_below=6.2,
        ph_emergency_above=8.8,
        ph_recover_low=7.0,
        ph_recover_high=8.0,
        automatic_water_exchange_enabled=True,
        exchange_fraction_pct=10.0,
        max_recovery_attempts=2,
        recovery_cooldown_seconds=600.0,
        provenance=EngineeringProvenance.USER_CONFIGURED,
    )
    runtime.configure_water_quality_threshold_profile(profile, actor="test")
    assert runtime.policy.nitrite_watch_above == pytest.approx(0.2)
    assert runtime.policy.ph_emergency_above == pytest.approx(8.8)
    assert runtime.water_quality_recovery.policy.max_attempts == 2
    assert runtime.water_quality_threshold_snapshot()["profile_id"] == (
        "owner-water-policy"
    )


def test_application_service_keeps_configuration_engineering_role_gated():
    service = KoiStockRuntimeApplicationService(build_integrated_virtual_runtime())
    payload = {
        "profile": _stock(weight_g=100.0, count=10).to_dict(),
    }
    with pytest.raises(PermissionError):
        service.command("configure_koi_stock_profile", payload, role="operator")
    snapshot = service.command(
        "configure_koi_stock_profile",
        payload,
        role="engineering",
    )
    assert snapshot.biology["koi_stock"]["biomass_kg"] == pytest.approx(1.0)
