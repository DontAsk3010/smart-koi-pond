from datetime import UTC, datetime  # noqa: I001
from types import SimpleNamespace

import pytest

from smart_koi_pond.control.ammonia import (
    UNIONIZED_AMMONIA_N_PARAMETER,
    UNIONIZED_AMMONIA_PARAMETER,
    calculate_unionized_ammonia_n,
)
from smart_koi_pond.control.engine import (
    SimulationControlPolicy,
    classify,
    decide,
    estimate_state,
)
from smart_koi_pond.control.water_quality import (
    WaterQualityRecoveryManager,
    WaterQualityRecoveryPolicy,
)
from smart_koi_pond.control.water_quality_config import (
    WaterQualityThresholdProfile,
    koi_freshwater_health_reference_v1,
)
from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    DataQuality,
    OperatingMode,
    SystemState,
)
from smart_koi_pond.domain.models import (
    Classification,
    StateEstimate,
    ValidatedMeasurement,
)


NOW = datetime(2026, 9, 15, tzinfo=UTC)


def _policy(**overrides):
    values = {
        "do_watch_below": 5.0,
        "do_emergency_below": 4.0,
        "do_recover_above": 5.5,
        "flow_watch_below": 8.0,
        "water_level_low_below": 70.0,
        "nh3_watch_above": 0.02,
        "nh3_emergency_above": 0.05,
    }
    values.update(overrides)
    return SimulationControlPolicy(**values)


def _measurement(parameter: str, value: float | None, quality=DataQuality.GOOD):
    return ValidatedMeasurement(
        sensor_id=f"sensor-{parameter}",
        parameter=parameter,
        value=value,
        timestamp=NOW,
        availability=AvailabilityState.AVAILABLE,
        quality=quality,
    )


def test_emerson_speciation_exposes_both_nitrogen_and_molecular_nh3_units():
    result = calculate_unionized_ammonia_n(
        tan_n_mg_l=1.0,
        ph=8.0,
        temperature_c=25.0,
    )
    assert result.pka == pytest.approx(9.2448413011)
    assert result.unionized_fraction == pytest.approx(0.0538421385)
    assert result.unionized_ammonia_n_mg_l == pytest.approx(0.0538421385)
    assert result.unionized_ammonia_nh3_mg_l == pytest.approx(0.0654657854)
    assert result.to_dict()["threshold_comparison_basis"] == "MOLECULAR_NH3_MG_L"


def test_same_tan_becomes_more_hazardous_when_ph_and_temperature_rise():
    cool_low_ph = calculate_unionized_ammonia_n(
        tan_n_mg_l=0.5,
        ph=7.5,
        temperature_c=20.0,
    )
    warm_high_ph = calculate_unionized_ammonia_n(
        tan_n_mg_l=0.5,
        ph=8.5,
        temperature_c=28.0,
    )
    assert warm_high_ph.unionized_ammonia_nh3_mg_l > (
        cool_low_ph.unionized_ammonia_nh3_mg_l
    )


def test_estimate_state_derives_nh3_only_from_validated_tan_ph_temperature():
    estimate = estimate_state(
        {
            "tan": _measurement("total_ammonia_nitrogen_mg_l", 1.0),
            "ph": _measurement("ph", 8.0),
            "temperature": _measurement("temperature_c", 25.0),
        }
    )
    assert estimate.values[UNIONIZED_AMMONIA_N_PARAMETER] == pytest.approx(
        0.0538421385
    )
    assert estimate.values[UNIONIZED_AMMONIA_PARAMETER] == pytest.approx(0.0654657854)
    assert estimate.provenance[UNIONIZED_AMMONIA_PARAMETER] == "CALCULATED"
    assert estimate.derivation[UNIONIZED_AMMONIA_PARAMETER]["fabricated"] is not True

    missing_temperature = estimate_state(
        {
            "tan": _measurement("total_ammonia_nitrogen_mg_l", 1.0),
            "ph": _measurement("ph", 8.0),
            "temperature": _measurement(
                "temperature_c",
                None,
                quality=DataQuality.INVALID,
            ),
        }
    )
    assert missing_temperature.values[UNIONIZED_AMMONIA_PARAMETER] is None
    assert missing_temperature.provenance[UNIONIZED_AMMONIA_PARAMETER] == "UNAVAILABLE"
    assert (
        missing_temperature.derivation[UNIONIZED_AMMONIA_PARAMETER]["status"]
        == "INPUT_REQUIRED"
    )


def test_koi_health_reference_matches_governed_freshwater_health_envelope():
    reference = koi_freshwater_health_reference_v1()
    assert reference.dissolved_oxygen_preferred_min_mg_l == pytest.approx(6.0)
    assert reference.dissolved_oxygen_warning_below_mg_l == pytest.approx(5.0)
    assert reference.dissolved_oxygen_emergency_at_or_below_mg_l == pytest.approx(4.0)
    assert reference.common_carp_growth_temperature_min_c == pytest.approx(23.0)
    assert reference.common_carp_growth_temperature_max_c == pytest.approx(30.0)
    assert reference.ph_min == pytest.approx(6.5)
    assert reference.ph_max == pytest.approx(9.0)
    assert reference.unionized_nh3_watch_mg_l == pytest.approx(0.02)
    assert reference.unionized_nh3_max_admissible_cyprinid_mg_l == pytest.approx(0.05)
    assert reference.nitrite_watch_mg_l == pytest.approx(0.1)
    assert reference.nitrate_upper_reference_mg_l == pytest.approx(20.0)
    assert reference.alkalinity_min_mg_l_as_caco3 == pytest.approx(100.0)
    assert reference.hardness_min_mg_l_as_caco3 == pytest.approx(20.0)
    assert reference.total_chlorine_target_mg_l == pytest.approx(0.0)

    profile = reference.threshold_profile()
    assert profile.nh3_watch_above == pytest.approx(0.02)
    assert profile.nh3_emergency_above == pytest.approx(0.05)
    assert profile.automatic_water_exchange_enabled is False
    assert profile.to_dict()["nh3_concentration_basis"] == "MOLECULAR_NH3_MG_L"


def test_classifier_uses_molecular_nh3_not_nh3_n_for_source_limits():
    estimate = StateEstimate(
        timestamp=NOW,
        values={
            "dissolved_oxygen_mg_l": 6.0,
            "circulation_flow_l_min": 10.0,
            "water_level_pct": 90.0,
            "temperature_c": 25.0,
            "ph": 7.5,
            "total_ammonia_nitrogen_mg_l": 1.0,
            UNIONIZED_AMMONIA_N_PARAMETER: 0.0177,
            UNIONIZED_AMMONIA_PARAMETER: 0.0215,
        },
        quality={
            "dissolved_oxygen_mg_l": DataQuality.GOOD,
            "circulation_flow_l_min": DataQuality.GOOD,
            "water_level_pct": DataQuality.GOOD,
            "temperature_c": DataQuality.GOOD,
            "ph": DataQuality.GOOD,
            "total_ammonia_nitrogen_mg_l": DataQuality.GOOD,
            UNIONIZED_AMMONIA_N_PARAMETER: DataQuality.GOOD,
            UNIONIZED_AMMONIA_PARAMETER: DataQuality.GOOD,
        },
    )
    classification = classify(
        estimate,
        _policy(tan_watch_above=None, tan_emergency_above=None),
    )
    assert classification.state == SystemState.WATCH
    assert "NH3_HIGH" in classification.reasons


def test_nh3_emergency_inhibits_feed_and_requests_available_life_support():
    estimate = StateEstimate(
        timestamp=NOW,
        values={
            "dissolved_oxygen_mg_l": 6.0,
            "circulation_flow_l_min": 10.0,
            "ph": 8.5,
            "total_ammonia_nitrogen_mg_l": 0.4,
            UNIONIZED_AMMONIA_PARAMETER: 0.083,
        },
        quality={},
    )
    intents = decide(
        estimate,
        Classification(SystemState.EMERGENCY, ("NH3_EMERGENCY",)),
        _policy(),
    )
    assert any(
        item.asset_id == "backup_aerator" and item.requested_on for item in intents
    )
    assert any(item.asset_id == "backup_pump" and item.requested_on for item in intents)
    feeder = next(item for item in intents if item.asset_id == "feeder")
    assert feeder.requested_on is False
    assert feeder.reason == "FEEDING_SAFETY_INHIBIT"


def test_nh3_water_exchange_requires_projected_post_mix_improvement():
    manager = WaterQualityRecoveryManager(
        WaterQualityRecoveryPolicy(
            enabled=True,
            exchange_fraction_pct=10.0,
            max_attempts=1,
            cooldown_seconds=0.0,
            nh3_recover_below=0.015,
        )
    )
    snapshot = SimpleNamespace(
        timestamp=NOW,
        operating_mode=OperatingMode.NORMAL_AUTO,
        classification=SimpleNamespace(reasons=("NH3_HIGH",)),
        estimate=SimpleNamespace(
            values={
                UNIONIZED_AMMONIA_PARAMETER: 0.0327328927,
                "water_level_pct": 85.0,
                "total_ammonia_nitrogen_mg_l": 0.5,
                "ph": 8.0,
                "temperature_c": 25.0,
                "alkalinity_mg_l_as_caco3": 100.0,
            }
        ),
    )
    unqualified_source = {
        "pond_use_qualified": False,
        "total_ammonia_nitrogen_mg_l": 0.0,
        "ph": 7.0,
        "temperature_c": 25.0,
        "alkalinity_mg_l_as_caco3": 100.0,
    }
    assert manager.observe(snapshot, unqualified_source) is None
    assert manager.last_outcome == "NO_SAFE_AUTOMATIC_WATER_EXCHANGE_PATH"

    high_buffer_high_ph_source = {
        "pond_use_qualified": True,
        "total_ammonia_nitrogen_mg_l": 0.01,
        "ph": 10.0,
        "temperature_c": 30.0,
        "alkalinity_mg_l_as_caco3": 5000.0,
    }
    standalone_source_nh3 = calculate_unionized_ammonia_n(
        tan_n_mg_l=0.01,
        ph=10.0,
        temperature_c=30.0,
    ).unionized_ammonia_nh3_mg_l
    assert standalone_source_nh3 < snapshot.estimate.values[UNIONIZED_AMMONIA_PARAMETER]
    assert manager.observe(snapshot, high_buffer_high_ph_source) is None
    assert manager.last_outcome == "NO_SAFE_AUTOMATIC_WATER_EXCHANGE_PATH"

    safe_source = {
        "pond_use_qualified": True,
        "total_ammonia_nitrogen_mg_l": 0.1,
        "ph": 7.5,
        "temperature_c": 25.0,
        "alkalinity_mg_l_as_caco3": 100.0,
    }
    request = manager.observe(snapshot, safe_source)
    assert request is not None
    assert request["parameter"] == UNIONIZED_AMMONIA_PARAMETER
    assert request["target_drain_level_pct"] == pytest.approx(75.0)
    assert request["target_refill_level_pct"] == pytest.approx(85.0)


def test_reference_profile_is_explicitly_applied_not_a_hidden_runtime_default():
    runtime = build_integrated_virtual_runtime()
    assert runtime.water_quality_threshold_snapshot()["configured"] is False

    reference_profile = koi_freshwater_health_reference_v1().threshold_profile()
    runtime.configure_water_quality_threshold_profile(reference_profile, actor="test")
    snapshot = runtime.water_quality_threshold_snapshot()
    assert snapshot["configured"] is True
    assert snapshot["profile_id"] == "KOI_FRESHWATER_HEALTH_REFERENCE_V1"
    assert snapshot["nh3_watch_above"] == pytest.approx(0.02)
    assert snapshot["nh3_emergency_above"] == pytest.approx(0.05)
    assert snapshot["nh3_concentration_basis"] == "MOLECULAR_NH3_MG_L"
    assert snapshot["automatic_water_exchange_enabled"] is False
    assert snapshot["automatic_chemical_dosing_authorized"] is False


def test_nh3_threshold_profile_round_trip_preserves_units_and_source():
    profile = koi_freshwater_health_reference_v1().threshold_profile()
    restored = WaterQualityThresholdProfile.from_dict(profile.to_dict())
    assert restored == profile
    assert restored.source_reference == profile.source_reference
    assert restored.nh3_watch_above == pytest.approx(0.02)
