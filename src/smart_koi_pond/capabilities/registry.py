from dataclasses import dataclass
from typing import Any

from smart_koi_pond.actuators.virtual import VirtualActuatorBank
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    BaselineStatus,
    DataQuality,
    ModuleInstallationState,
    ModuleOperationalState,
)
from smart_koi_pond.domain.models import (
    BaselineAssessment,
    CapabilityProfile,
    CapabilityRegistrySnapshot,
    ModuleStatus,
    ValidatedMeasurement,
)

_CAPABILITY_ASSET_AVAILABLE = {
    AvailabilityState.AVAILABLE,
    AvailabilityState.STANDBY,
    AvailabilityState.MANUAL,
}

DEFAULT_SIMULATION_BASELINE = (
    "core.local_control",
    "core.safe_restart",
    "core.alarm_history",
    "core.manual_intervention",
    "measurement.temperature",
    "measurement.do",
    "measurement.ph",
    "measurement.water_level",
    "measurement.circulation_flow",
    "life_support.primary_circulation",
    "life_support.primary_aeration",
    "life_support.emergency_aeration",
)


@dataclass(slots=True, frozen=True)
class ModuleManifest:
    module_id: str
    capabilities_provided: tuple[str, ...]
    required_capabilities: tuple[str, ...] = ()
    optional_capabilities: tuple[str, ...] = ()
    sensor_ids: tuple[str, ...] = ()
    asset_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class _ModuleConfiguration:
    installation_state: ModuleInstallationState = ModuleInstallationState.INSTALLED
    enabled: bool = True


DEFAULT_MODULE_MANIFESTS = (
    ModuleManifest(
        "core_runtime",
        (
            "core.local_control",
            "core.safe_restart",
            "core.alarm_history",
            "core.manual_intervention",
            "core.response_verification",
            "safety.low_water_interlocks",
        ),
    ),
    ModuleManifest(
        "temperature_monitoring",
        ("measurement.temperature",),
        sensor_ids=("temperature",),
    ),
    ModuleManifest(
        "do_monitoring",
        ("measurement.do",),
        sensor_ids=("do",),
    ),
    ModuleManifest(
        "ph_monitoring",
        ("measurement.ph",),
        sensor_ids=("ph",),
    ),
    ModuleManifest(
        "water_level_monitoring",
        ("measurement.water_level",),
        sensor_ids=("water_level",),
    ),
    ModuleManifest(
        "flow_monitoring",
        ("measurement.circulation_flow",),
        sensor_ids=("flow",),
    ),
    ModuleManifest(
        "primary_circulation",
        ("life_support.primary_circulation",),
        asset_ids=("main_pump",),
    ),
    ModuleManifest(
        "backup_circulation",
        ("life_support.backup_circulation",),
        asset_ids=("backup_pump",),
    ),
    ModuleManifest(
        "primary_aeration",
        ("life_support.primary_aeration",),
        asset_ids=("primary_aerator",),
    ),
    ModuleManifest(
        "emergency_aeration",
        ("life_support.emergency_aeration",),
        asset_ids=("backup_aerator",),
    ),
    ModuleManifest(
        "top_up_hardware",
        ("actuator.top_up",),
        asset_ids=("top_up_valve",),
    ),
    ModuleManifest(
        "drain_hardware",
        ("actuator.drain",),
        asset_ids=("drain_valve",),
    ),
    ModuleManifest(
        "backwash_hardware",
        ("actuator.backwash",),
        asset_ids=("backwash_valve",),
    ),
    ModuleManifest(
        "feeder_hardware",
        ("actuator.feeder",),
        asset_ids=("feeder",),
    ),
    ModuleManifest(
        "uv_treatment",
        ("treatment.uv",),
        asset_ids=("uv_lamp",),
    ),
    ModuleManifest(
        "auto_top_up",
        ("automation.auto_top_up",),
        required_capabilities=(
            "measurement.water_level",
            "actuator.top_up",
            "core.response_verification",
            "safety.low_water_interlocks",
        ),
    ),
    ModuleManifest(
        "water_change_automation",
        ("automation.water_change",),
        required_capabilities=(
            "measurement.water_level",
            "actuator.top_up",
            "actuator.drain",
            "core.response_verification",
        ),
    ),
    ModuleManifest(
        "filter_clean_automation",
        ("automation.filter_clean",),
        required_capabilities=("actuator.backwash",),
    ),
    ModuleManifest(
        "feeding_control",
        ("automation.feeding",),
        required_capabilities=("actuator.feeder", "core.local_control"),
    ),
)


class CapabilityRegistry:
    """Canonical module/capability registry and Pond-Profile baseline evaluator."""

    def __init__(
        self,
        *,
        profile: CapabilityProfile | None = None,
        manifests: tuple[ModuleManifest, ...] = DEFAULT_MODULE_MANIFESTS,
        module_installation: dict[str, ModuleInstallationState | str] | None = None,
        module_enabled: dict[str, bool] | None = None,
    ) -> None:
        self.manifests = {manifest.module_id: manifest for manifest in manifests}
        self.profile = profile or CapabilityProfile(
            profile_id="DIGITAL_TWIN_V1",
            package_label="SIMULATION_FULL",
            required_capabilities=DEFAULT_SIMULATION_BASELINE,
        )
        self._configuration = {
            module_id: _ModuleConfiguration() for module_id in self.manifests
        }
        for module_id, state in (module_installation or {}).items():
            self.configure(module_id, installation_state=state)
        for module_id, enabled in (module_enabled or {}).items():
            self.configure(module_id, enabled=enabled)

    def configure(
        self,
        module_id: str,
        *,
        installation_state: ModuleInstallationState | str | None = None,
        enabled: bool | None = None,
    ) -> None:
        if module_id not in self.manifests:
            raise KeyError(f"unknown module: {module_id}")
        config = self._configuration[module_id]
        if installation_state is not None:
            config.installation_state = ModuleInstallationState(installation_state)
        if enabled is not None:
            config.enabled = bool(enabled)

    def set_profile(self, profile: CapabilityProfile) -> None:
        self.profile = profile

    def configuration_for(self, module_id: str) -> dict[str, Any]:
        if module_id not in self.manifests:
            raise KeyError(f"unknown module: {module_id}")
        config = self._configuration[module_id]
        return {
            "installation_state": config.installation_state,
            "enabled": config.enabled,
        }

    def _direct_state(
        self,
        manifest: ModuleManifest,
        validated: dict[str, ValidatedMeasurement],
        actuators: VirtualActuatorBank,
        feature_flags: dict[str, bool],
    ) -> tuple[ModuleOperationalState, tuple[str, ...]]:
        config = self._configuration[manifest.module_id]
        if config.installation_state != ModuleInstallationState.INSTALLED:
            return (
                ModuleOperationalState.NOT_AVAILABLE,
                (config.installation_state.value,),
            )
        if not config.enabled or not feature_flags.get(manifest.module_id, True):
            return ModuleOperationalState.DISABLED, ("DISABLED_BY_CONFIGURATION",)

        reasons: list[str] = []
        for sensor_id in manifest.sensor_ids:
            measurement = validated.get(sensor_id)
            if measurement is None:
                reasons.append(f"SENSOR_MISSING:{sensor_id}")
            elif measurement.quality != DataQuality.GOOD:
                reasons.append(f"SENSOR_NOT_GOOD:{sensor_id}:{measurement.quality.value}")
            elif measurement.availability != AvailabilityState.AVAILABLE:
                reasons.append(
                    f"SENSOR_UNAVAILABLE:{sensor_id}:{measurement.availability.value}"
                )
        for asset_id in manifest.asset_ids:
            asset = actuators.assets.get(asset_id)
            if asset is None:
                reasons.append(f"ASSET_MISSING:{asset_id}")
            elif asset.availability not in _CAPABILITY_ASSET_AVAILABLE:
                reasons.append(f"ASSET_UNAVAILABLE:{asset_id}:{asset.availability.value}")

        if reasons:
            return ModuleOperationalState.DEGRADED, tuple(reasons)
        return ModuleOperationalState.AVAILABLE, ()

    def evaluate(
        self,
        *,
        validated: dict[str, ValidatedMeasurement],
        actuators: VirtualActuatorBank,
        feature_flags: dict[str, bool] | None = None,
    ) -> CapabilityRegistrySnapshot:
        flags = feature_flags or {}
        direct = {
            module_id: self._direct_state(manifest, validated, actuators, flags)
            for module_id, manifest in self.manifests.items()
        }

        available: set[str] = set()
        changed = True
        while changed:
            changed = False
            for module_id, manifest in self.manifests.items():
                state, _ = direct[module_id]
                if state != ModuleOperationalState.AVAILABLE:
                    continue
                if not all(dep in available for dep in manifest.required_capabilities):
                    continue
                before = len(available)
                available.update(manifest.capabilities_provided)
                changed = changed or len(available) != before

        statuses: dict[str, ModuleStatus] = {}
        for module_id, manifest in self.manifests.items():
            state, reasons = direct[module_id]
            if state == ModuleOperationalState.AVAILABLE:
                missing_dependencies = tuple(
                    dep for dep in manifest.required_capabilities if dep not in available
                )
                if missing_dependencies:
                    state = ModuleOperationalState.NOT_AVAILABLE
                    reasons = tuple(
                        f"DEPENDENCY_UNSATISFIED:{dep}" for dep in missing_dependencies
                    )
            config = self._configuration[module_id]
            statuses[module_id] = ModuleStatus(
                module_id=module_id,
                installation_state=config.installation_state,
                operational_state=state,
                capabilities_provided=manifest.capabilities_provided,
                reasons=reasons,
                sensor_ids=manifest.sensor_ids,
                asset_ids=manifest.asset_ids,
            )

        required = self.profile.required_capabilities
        satisfied: list[str] = []
        degraded: list[str] = []
        missing: list[str] = []
        reasons: list[str] = []
        for capability in required:
            if capability in available:
                satisfied.append(capability)
                continue
            providers = [
                manifest
                for manifest in self.manifests.values()
                if capability in manifest.capabilities_provided
            ]
            structurally_present = any(
                self._configuration[provider.module_id].installation_state
                == ModuleInstallationState.INSTALLED
                and self._configuration[provider.module_id].enabled
                for provider in providers
            )
            if providers and structurally_present:
                degraded.append(capability)
                reasons.append(f"BASELINE_CAPABILITY_DEGRADED:{capability}")
            else:
                missing.append(capability)
                reasons.append(f"BASELINE_CAPABILITY_MISSING:{capability}")

        if missing:
            baseline_status = BaselineStatus.NOT_MET
        elif degraded:
            baseline_status = BaselineStatus.DEGRADED
        else:
            baseline_status = BaselineStatus.SATISFIED

        baseline = BaselineAssessment(
            status=baseline_status,
            required_capabilities=required,
            satisfied_capabilities=tuple(sorted(satisfied)),
            degraded_capabilities=tuple(sorted(degraded)),
            missing_capabilities=tuple(sorted(missing)),
            reasons=tuple(reasons),
        )
        return CapabilityRegistrySnapshot(
            profile_id=self.profile.profile_id,
            package_label=self.profile.package_label,
            available_capabilities=tuple(sorted(available)),
            modules=statuses,
            baseline=baseline,
        )

    def structurally_enabled(self, module_id: str) -> bool:
        if module_id not in self.manifests:
            raise KeyError(f"unknown module: {module_id}")
        config = self._configuration[module_id]
        return (
            config.installation_state == ModuleInstallationState.INSTALLED
            and config.enabled
        )

    def asset_is_configured(self, asset_id: str) -> bool:
        providers = [
            manifest
            for manifest in self.manifests.values()
            if asset_id in manifest.asset_ids
        ]
        if not providers:
            return True
        return any(self.structurally_enabled(provider.module_id) for provider in providers)

    def structural_capabilities(self) -> tuple[str, ...]:
        available: set[str] = set()
        changed = True
        while changed:
            changed = False
            for module_id, manifest in self.manifests.items():
                if not self.structurally_enabled(module_id):
                    continue
                if not all(dep in available for dep in manifest.required_capabilities):
                    continue
                before = len(available)
                available.update(manifest.capabilities_provided)
                changed = changed or len(available) != before
        return tuple(sorted(available))

    def capability_structurally_enabled(self, capability: str) -> bool:
        return capability in self.structural_capabilities()

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "profile": {
                "profile_id": self.profile.profile_id,
                "package_label": self.profile.package_label,
                "required_capabilities": list(self.profile.required_capabilities),
            },
            "modules": {
                module_id: {
                    "installation_state": config.installation_state.value,
                    "enabled": config.enabled,
                }
                for module_id, config in self._configuration.items()
            },
        }

    def restore_state(self, state: dict[str, Any] | None) -> None:
        if not state:
            return
        profile = state.get("profile")
        if profile:
            self.profile = CapabilityProfile(
                profile_id=str(profile["profile_id"]),
                package_label=str(profile["package_label"]),
                required_capabilities=tuple(profile.get("required_capabilities", ())),
            )
        for module_id, config in state.get("modules", {}).items():
            if module_id not in self.manifests:
                continue
            self.configure(
                module_id,
                installation_state=config.get(
                    "installation_state", ModuleInstallationState.INSTALLED
                ),
                enabled=bool(config.get("enabled", True)),
            )
