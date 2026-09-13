from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.modular_ui import MODULAR_UI_SCRIPT
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    BaselineStatus,
    ModuleInstallationState,
    ModuleOperationalState,
    SystemState,
)
from smart_koi_pond.domain.models import CapabilityProfile, PondState

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
)


def make_runtime(
    *,
    module_installation=None,
    profile: CapabilityProfile | None = None,
    policy: SimulationControlPolicy = POLICY,
) -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(
                temperature_c=27.0,
                dissolved_oxygen_mg_l=6.0,
                ph=7.2,
                water_level_pct=85.0,
            ),
            EnvironmentInputs(
                ambient_temperature_c=28.0,
                oxygen_demand_mg_l_per_hour=0.2,
            ),
        ),
        policy,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        config_version="modular-platform-test-v1",
        capability_profile=profile,
        module_installation=module_installation,
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_default_simulation_profile_satisfies_mandatory_baseline() -> None:
    runtime = make_runtime()
    snapshot = runtime.tick(0.0)

    registry = snapshot.capability.registry
    assert registry is not None
    assert registry.baseline.status == BaselineStatus.SATISFIED
    assert registry.baseline.missing_capabilities == ()
    assert snapshot.classification.state == SystemState.NORMAL


def test_optional_module_absence_is_not_failure_or_baseline_degradation() -> None:
    runtime = make_runtime(
        module_installation={
            "uv_treatment": ModuleInstallationState.NOT_INSTALLED,
        }
    )
    snapshot = runtime.tick(0.0)

    registry = snapshot.capability.registry
    assert registry is not None
    assert registry.baseline.status == BaselineStatus.SATISFIED
    assert snapshot.classification.state == SystemState.NORMAL
    assert registry.modules["uv_treatment"].installation_state == (
        ModuleInstallationState.NOT_INSTALLED
    )
    assert snapshot.assets["uv_lamp"].availability == AvailabilityState.UNSUPPORTED


def test_missing_mandatory_baseline_capability_prevents_false_normal() -> None:
    runtime = make_runtime(
        module_installation={
            "ph_monitoring": ModuleInstallationState.NOT_INSTALLED,
        }
    )
    snapshot = runtime.tick(0.0)

    registry = snapshot.capability.registry
    assert registry is not None
    assert registry.baseline.status == BaselineStatus.NOT_MET
    assert "measurement.ph" in registry.baseline.missing_capabilities
    assert snapshot.classification.state == SystemState.DEGRADED
    assert snapshot.validated["ph"].availability == AvailabilityState.UNSUPPORTED


def test_missing_dependency_disables_only_dependent_automation() -> None:
    low_water_policy = SimulationControlPolicy(
        do_watch_below=5.0,
        do_emergency_below=4.0,
        do_recover_above=5.5,
        flow_watch_below=8.0,
        water_level_low_below=70.0,
        low_water_auto_recovery_enabled=True,
        water_level_recover_target=85.0,
        water_level_hard_high_cutoff=95.0,
    )
    runtime = make_runtime(
        policy=low_water_policy,
        module_installation={
            "top_up_hardware": ModuleInstallationState.NOT_INSTALLED,
        },
    )
    snapshot = runtime.tick(0.0)

    registry = snapshot.capability.registry
    assert registry is not None
    auto_top_up = registry.modules["auto_top_up"]
    assert auto_top_up.operational_state == ModuleOperationalState.NOT_AVAILABLE
    assert any("actuator.top_up" in reason for reason in auto_top_up.reasons)
    assert registry.baseline.status == BaselineStatus.SATISFIED
    assert "life_support.primary_aeration" in registry.available_capabilities
    assert snapshot.assets["top_up_valve"].availability == AvailabilityState.UNSUPPORTED

    with pytest.raises(RuntimeError, match="automation.water_change"):
        runtime.start_water_change(
            "DEPENDENCY_TEST",
            target_drain_level_pct=75.0,
            target_refill_level_pct=85.0,
        )


def test_package_label_does_not_change_control_or_capability_meaning() -> None:
    required = make_runtime().capability_registry.profile.required_capabilities
    base = make_runtime(
        profile=CapabilityProfile(
            profile_id="POND_PROFILE_A",
            package_label="BASE",
            required_capabilities=required,
        )
    ).tick(0.0)
    professional = make_runtime(
        profile=CapabilityProfile(
            profile_id="POND_PROFILE_A",
            package_label="PROFESSIONAL",
            required_capabilities=required,
        )
    ).tick(0.0)

    assert base.classification == professional.classification
    assert base.capability.registry is not None
    assert professional.capability.registry is not None
    assert (
        base.capability.registry.available_capabilities
        == professional.capability.registry.available_capabilities
    )
    assert base.capability.registry.package_label == "BASE"
    assert professional.capability.registry.package_label == "PROFESSIONAL"


def test_module_configuration_survives_checkpoint_and_restart() -> None:
    source = make_runtime()
    source.configure_module(
        "uv_treatment",
        installation_state=ModuleInstallationState.NOT_INSTALLED,
    )
    source.tick(0.0)
    checkpoint = source.capture_checkpoint()

    restored = make_runtime()
    restored.restore_checkpoint(checkpoint)
    snapshot = restored.tick(0.0)

    registry = snapshot.capability.registry
    assert registry is not None
    assert registry.modules["uv_treatment"].installation_state == (
        ModuleInstallationState.NOT_INSTALLED
    )
    assert snapshot.assets["uv_lamp"].availability == AvailabilityState.UNSUPPORTED
    assert any(
        event.code == "RUNTIME_RESTART_RECONCILIATION_REQUIRED"
        for event in restored.events.events
    )


def test_running_asset_cannot_be_removed_as_module() -> None:
    runtime = make_runtime()
    with pytest.raises(RuntimeError, match="safely OFF"):
        runtime.configure_module(
            "primary_circulation",
            installation_state=ModuleInstallationState.NOT_INSTALLED,
        )


def test_capability_registry_is_published_and_modular_ui_exposes_baseline() -> None:
    runtime = make_runtime(
        module_installation={"uv_treatment": ModuleInstallationState.NOT_INSTALLED}
    )
    snapshot = runtime.tick(0.0)
    publication = runtime.publish(snapshot)
    registry = publication["snapshot"]["capability"]["registry"]

    assert registry["baseline"]["status"] == BaselineStatus.SATISFIED.value
    assert registry["modules"]["uv_treatment"]["installation_state"] == (
        ModuleInstallationState.NOT_INSTALLED.value
    )
    assert "baselineBadge" in MODULAR_UI_SCRIPT
    assert "baseline" in MODULAR_UI_SCRIPT.lower()
