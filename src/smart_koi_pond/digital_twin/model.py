from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from smart_koi_pond.digital_twin.hydraulics import HydraulicNetworkModel, PondDesignProfile
from smart_koi_pond.domain.models import PondState


@dataclass(slots=True, frozen=True)
class EnvironmentInputs:
    ambient_temperature_c: float
    oxygen_demand_mg_l_per_hour: float
    leak_pct_per_hour: float = 0.0


@dataclass(slots=True, frozen=True)
class ActuatorEffects:
    main_pump_flow_l_min: float = 12.0
    backup_pump_flow_l_min: float = 10.0
    primary_aerator_gain_mg_l_per_hour: float = 0.55
    backup_aerator_gain_mg_l_per_hour: float = 0.75
    top_up_gain_pct_per_hour: float = 12.0
    drain_loss_pct_per_hour: float = 18.0
    temperature_exchange_per_hour: float = 0.08


class PondModel:
    """Deterministic production-lineage pond model.

    Without a PondDesignProfile the model preserves the accepted V1 control-test behavior.
    Once a profile is configured, hydraulic flow and optional water-management rates become
    volume-aware and route-aware while retaining explicit design provenance.
    """

    def __init__(
        self,
        state: PondState,
        environment: EnvironmentInputs,
        effects: ActuatorEffects | None = None,
        *,
        hydraulics: HydraulicNetworkModel | None = None,
    ) -> None:
        self.state = state
        self.environment = environment
        self.effects = effects or ActuatorEffects()
        self.hydraulics = hydraulics

    def set_truth(self, parameter: str, value: float) -> None:
        if parameter == "temperature_c":
            self.state.temperature_c = value
        elif parameter == "dissolved_oxygen_mg_l":
            self.state.dissolved_oxygen_mg_l = value
        elif parameter == "ph":
            self.state.ph = value
        elif parameter == "water_level_pct":
            self.state.water_level_pct = value
        else:
            raise KeyError(parameter)

    def configure_design_profile(self, profile: PondDesignProfile) -> None:
        if self.hydraulics is None:
            self.hydraulics = HydraulicNetworkModel(profile)
        else:
            self.hydraulics.configure_profile(profile)

    def set_hydraulic_restriction(self, route_id: str, throughput_factor: float) -> None:
        if self.hydraulics is None:
            raise RuntimeError("hydraulic profile is not configured")
        self.hydraulics.set_route_restriction(route_id, throughput_factor)

    def design_profile_snapshot(self) -> dict[str, Any]:
        if self.hydraulics is None:
            return {
                "configured": False,
                "provenance": "UNAVAILABLE",
            }
        return {
            "configured": True,
            **self.hydraulics.profile.to_dict(),
        }

    def hydraulic_snapshot(self) -> dict[str, Any]:
        if self.hydraulics is None:
            return {
                "configured": False,
                "provenance": "UNAVAILABLE",
                "per_route_flow_modeled": False,
            }
        return {
            "configured": True,
            "per_route_flow_modeled": True,
            **self.hydraulics.snapshot(),
        }

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "hydraulics": (
                self.hydraulics.checkpoint_state() if self.hydraulics is not None else None
            )
        }

    def restore_engineering_state(self, state: Mapping[str, Any] | None) -> None:
        if not state or state.get("hydraulics") is None:
            self.hydraulics = None
            return
        self.hydraulics = HydraulicNetworkModel.from_checkpoint(state["hydraulics"])

    @staticmethod
    def _effect(actuator_effects: dict[str, float | bool], asset_id: str) -> float:
        value = actuator_effects.get(asset_id, 0.0)
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        return min(1.0, max(0.0, float(value)))

    def step(
        self,
        seconds: float,
        actuator_effects: dict[str, float | bool],
    ) -> PondState:
        hours = seconds / 3600.0
        e = self.effects

        main_pump_effect = self._effect(actuator_effects, "main_pump")
        backup_pump_effect = self._effect(actuator_effects, "backup_pump")
        primary_aerator_effect = self._effect(actuator_effects, "primary_aerator")
        backup_aerator_effect = self._effect(actuator_effects, "backup_aerator")
        top_up_effect = self._effect(actuator_effects, "top_up_valve")
        drain_effect = self._effect(actuator_effects, "drain_valve")

        if self.hydraulics is None:
            self.state.circulation_flow_l_min = (
                e.main_pump_flow_l_min * main_pump_effect
                + e.backup_pump_flow_l_min * backup_pump_effect
            )
        else:
            hydraulic_state = self.hydraulics.evaluate(actuator_effects)
            self.state.circulation_flow_l_min = float(
                hydraulic_state["total_effective_flow_l_min"]
            )

        do_delta = -self.environment.oxygen_demand_mg_l_per_hour
        do_delta += e.primary_aerator_gain_mg_l_per_hour * primary_aerator_effect
        do_delta += e.backup_aerator_gain_mg_l_per_hour * backup_aerator_effect
        self.state.dissolved_oxygen_mg_l = max(
            0.0, self.state.dissolved_oxygen_mg_l + do_delta * hours
        )

        temp_delta = (
            self.environment.ambient_temperature_c - self.state.temperature_c
        ) * e.temperature_exchange_per_hour
        self.state.temperature_c += temp_delta * hours

        level_delta = -self.environment.leak_pct_per_hour
        volume_aware_delta = (
            self.hydraulics.level_delta_pct_per_hour(
                top_up_effect=top_up_effect,
                drain_effect=drain_effect,
            )
            if self.hydraulics is not None
            else None
        )
        if volume_aware_delta is None:
            level_delta += e.top_up_gain_pct_per_hour * top_up_effect
            level_delta -= e.drain_loss_pct_per_hour * drain_effect
        else:
            level_delta += volume_aware_delta
        next_level = self.state.water_level_pct + level_delta * hours
        self.state.water_level_pct = min(100.0, max(0.0, next_level))
        return self.state
