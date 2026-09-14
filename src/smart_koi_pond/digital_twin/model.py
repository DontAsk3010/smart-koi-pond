from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from smart_koi_pond.digital_twin.biology import (
    BiologicalProcessModel,
    BiologicalProcessProfile,
)
from smart_koi_pond.digital_twin.filtration import (
    MechanicalFiltrationModel,
    MechanicalFiltrationProfile,
)
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
    """Deterministic production-lineage pond model."""

    def __init__(
        self,
        state: PondState,
        environment: EnvironmentInputs,
        effects: ActuatorEffects | None = None,
        *,
        hydraulics: HydraulicNetworkModel | None = None,
        biology: BiologicalProcessModel | None = None,
        filtration: MechanicalFiltrationModel | None = None,
    ) -> None:
        self.state = state
        self.environment = environment
        self.effects = effects or ActuatorEffects()
        self.hydraulics = hydraulics
        self.biology = biology
        self.filtration = filtration
        self._validate_filtration_route()
        self._sync_filtration_process_factor()

    def set_truth(self, parameter: str, value: float) -> None:
        attributes = {
            "temperature_c": "temperature_c",
            "dissolved_oxygen_mg_l": "dissolved_oxygen_mg_l",
            "ph": "ph",
            "water_level_pct": "water_level_pct",
            "total_ammonia_nitrogen_mg_l": "total_ammonia_nitrogen_mg_l",
            "nitrite_mg_l": "nitrite_mg_l",
            "nitrate_mg_l": "nitrate_mg_l",
            "alkalinity_mg_l_as_caco3": "alkalinity_mg_l_as_caco3",
            "waste_solids_g": "waste_solids_g",
        }
        attribute = attributes.get(parameter)
        if attribute is None:
            raise KeyError(parameter)
        setattr(self.state, attribute, float(value))

    def actual_water_volume_l(self) -> float | None:
        """Return current modeled pond-water volume from profile volume and water level."""
        if self.hydraulics is None:
            return None
        level_fraction = min(
            1.0,
            max(0.0, float(self.state.water_level_pct) / 100.0),
        )
        return self.hydraulics.profile.effective_volume_l * level_fraction

    def _validate_filtration_route(self) -> None:
        if self.filtration is None:
            return
        if self.hydraulics is None:
            raise RuntimeError(
                "hydraulic Pond Profile must be configured before mechanical filtration"
            )
        route_id = self.filtration.profile.filtered_route_id
        if not self.hydraulics.has_route(route_id):
            raise ValueError(f"mechanical filtration route is not configured: {route_id}")

    def _sync_filtration_process_factor(self) -> None:
        if self.filtration is None or self.hydraulics is None:
            return
        self.hydraulics.set_route_process_factor(
            self.filtration.profile.filtered_route_id,
            self.filtration.process_throughput_factor,
        )

    def configure_design_profile(self, profile: PondDesignProfile) -> None:
        if self.filtration is not None:
            route_ids = {route.route_id for route in profile.routes}
            if self.filtration.profile.filtered_route_id not in route_ids:
                raise ValueError(
                    "updated Pond Profile removes the route bound to mechanical filtration"
                )
        if self.hydraulics is None:
            self.hydraulics = HydraulicNetworkModel(profile)
        else:
            self.hydraulics.configure_profile(profile)
        self._sync_filtration_process_factor()

    def configure_biological_profile(self, profile: BiologicalProcessProfile) -> None:
        if self.hydraulics is None:
            raise RuntimeError(
                "hydraulic Pond Profile must be configured before biological process profile"
            )
        if self.biology is None:
            self.biology = BiologicalProcessModel(profile)
        else:
            self.biology.configure_profile(profile)

    def configure_mechanical_filtration_profile(
        self,
        profile: MechanicalFiltrationProfile,
    ) -> None:
        if self.hydraulics is None:
            raise RuntimeError(
                "hydraulic Pond Profile must be configured before mechanical filtration"
            )
        if not self.hydraulics.has_route(profile.filtered_route_id):
            raise ValueError(
                f"mechanical filtration route is not configured: {profile.filtered_route_id}"
            )
        if self.filtration is None:
            self.filtration = MechanicalFiltrationModel(profile)
        else:
            previous_route = self.filtration.profile.filtered_route_id
            self.filtration.configure_profile(profile)
            if previous_route != profile.filtered_route_id and self.hydraulics.has_route(
                previous_route
            ):
                self.hydraulics.set_route_process_factor(previous_route, 1.0)
        self._sync_filtration_process_factor()

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
                "actual_water_volume_l": None,
                "actual_water_volume_provenance": "UNAVAILABLE",
                "mechanical_filtration": self.mechanical_filtration_snapshot(),
            }
        return {
            "configured": True,
            "per_route_flow_modeled": True,
            **self.hydraulics.snapshot(),
            "actual_water_volume_l": self.actual_water_volume_l(),
            "actual_water_volume_provenance": "CALCULATED",
            "actual_water_volume_basis": "EFFECTIVE_VOLUME_X_WATER_LEVEL",
            "process_volume_integration_basis": "ACTUAL_MODELED_VOLUME_AT_STEP_START",
            "mechanical_filtration": self.mechanical_filtration_snapshot(),
        }

    def biological_snapshot(self) -> dict[str, Any]:
        if self.biology is None:
            return {
                "configured": False,
                "status": "NOT_CONFIGURED",
                "provenance": "UNAVAILABLE",
            }
        return self.biology.snapshot()

    def mechanical_filtration_snapshot(self) -> dict[str, Any]:
        if self.filtration is None:
            return {
                "configured": False,
                "status": "NOT_CONFIGURED",
                "provenance": "UNAVAILABLE",
                "captured_solids_g": None,
                "tss_mg_l": None,
                "turbidity_ntu": None,
                "water_clarity_conclusion": "NOT_ESTABLISHED",
            }
        return self.filtration.snapshot(
            suspended_solids_g=self.state.waste_solids_g,
            volume_l=self.actual_water_volume_l(),
        )

    def _biological_truth_snapshot(self) -> dict[str, float | None]:
        return {
            "total_ammonia_nitrogen_mg_l": self.state.total_ammonia_nitrogen_mg_l,
            "nitrite_mg_l": self.state.nitrite_mg_l,
            "nitrate_mg_l": self.state.nitrate_mg_l,
            "alkalinity_mg_l_as_caco3": self.state.alkalinity_mg_l_as_caco3,
            "waste_solids_g": self.state.waste_solids_g,
        }

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "hydraulics": (
                self.hydraulics.checkpoint_state() if self.hydraulics is not None else None
            ),
            "biology": self.biology.checkpoint_state() if self.biology is not None else None,
            "filtration": (
                self.filtration.checkpoint_state() if self.filtration is not None else None
            ),
            "biological_truth": self._biological_truth_snapshot(),
        }

    def restore_engineering_state(self, state: Mapping[str, Any] | None) -> None:
        if not state:
            self.hydraulics = None
            self.biology = None
            self.filtration = None
            return
        hydraulic_state = state.get("hydraulics")
        biology_state = state.get("biology")
        filtration_state = state.get("filtration")
        self.hydraulics = (
            HydraulicNetworkModel.from_checkpoint(hydraulic_state)
            if hydraulic_state is not None
            else None
        )
        self.biology = (
            BiologicalProcessModel.from_checkpoint(biology_state)
            if biology_state is not None
            else None
        )
        self.filtration = (
            MechanicalFiltrationModel.from_checkpoint(filtration_state)
            if filtration_state is not None
            else None
        )
        self._validate_filtration_route()
        self._sync_filtration_process_factor()
        for parameter, value in state.get("biological_truth", {}).items():
            if value is not None:
                self.set_truth(parameter, float(value))
            elif hasattr(self.state, parameter):
                setattr(self.state, parameter, None)

    @staticmethod
    def _effect(actuator_effects: dict[str, float | bool], asset_id: str) -> float:
        value = actuator_effects.get(asset_id, 0.0)
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        return min(1.0, max(0.0, float(value)))

    def _biological_oxygen_demand(self, seconds: float) -> float:
        if self.biology is None or self.hydraulics is None:
            return 0.0
        profile = self.hydraulics.profile
        actual_volume_l = self.actual_water_volume_l()
        return self.biology.step(
            self.state,
            seconds=seconds,
            volume_l=float(actual_volume_l or 0.0),
            biomass_kg=profile.biomass_kg,
            feed_kg_per_day=profile.feed_kg_per_day,
            circulation_flow_l_min=self.state.circulation_flow_l_min,
            required_circulation_flow_l_min=(
                self.hydraulics.required_circulation_flow_l_min
            ),
        )

    def _mechanical_filtration_step(
        self,
        seconds: float,
        actuator_effects: dict[str, float | bool],
        hydraulic_state: dict[str, Any] | None,
    ) -> float | None:
        if self.filtration is None or self.hydraulics is None or hydraulic_state is None:
            return None
        route_id = self.filtration.profile.filtered_route_id
        route_state = hydraulic_state["routes"][route_id]
        actual_volume_l = self.actual_water_volume_l()
        result = self.filtration.step(
            self.state,
            seconds=seconds,
            volume_l=float(actual_volume_l or 0.0),
            route_flow_l_min=float(route_state["effective_flow_l_min"]),
            backwash_effect=self._effect(actuator_effects, "backwash_valve"),
        )
        self._sync_filtration_process_factor()
        refreshed = self.hydraulics.evaluate(actuator_effects)
        self.state.circulation_flow_l_min = float(
            refreshed["total_effective_flow_l_min"]
        )
        return result["backwash_discharge_l"]

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

        hydraulic_state: dict[str, Any] | None = None
        if self.hydraulics is None:
            self.state.circulation_flow_l_min = (
                e.main_pump_flow_l_min * main_pump_effect
                + e.backup_pump_flow_l_min * backup_pump_effect
            )
        else:
            self._sync_filtration_process_factor()
            hydraulic_state = self.hydraulics.evaluate(actuator_effects)
            self.state.circulation_flow_l_min = float(
                hydraulic_state["total_effective_flow_l_min"]
            )

        biological_oxygen_demand = self._biological_oxygen_demand(seconds)
        backwash_discharge_l = self._mechanical_filtration_step(
            seconds, actuator_effects, hydraulic_state
        )

        do_delta = -self.environment.oxygen_demand_mg_l_per_hour
        do_delta -= biological_oxygen_demand
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
        if (
            backwash_discharge_l is not None
            and self.hydraulics is not None
            and self.hydraulics.profile.effective_volume_l > 0
        ):
            next_level -= (
                backwash_discharge_l
                / self.hydraulics.profile.effective_volume_l
                * 100.0
            )
        self.state.water_level_pct = min(100.0, max(0.0, next_level))
        return self.state
