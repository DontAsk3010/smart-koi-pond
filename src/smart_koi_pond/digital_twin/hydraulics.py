from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping


class EngineeringProvenance(StrEnum):
    DESIGN_ASSUMPTION = "DESIGN_ASSUMPTION"
    DATASHEET = "DATASHEET"
    CALCULATED = "CALCULATED"
    ESTIMATED = "ESTIMATED"
    MEASURED = "MEASURED"
    UNAVAILABLE = "UNAVAILABLE"


class HydraulicRouteRole(StrEnum):
    PRIMARY = "PRIMARY"
    BACKUP = "BACKUP"
    PARALLEL = "PARALLEL"


@dataclass(slots=True, frozen=True)
class HydraulicRouteSpec:
    route_id: str
    asset_id: str
    rated_flow_l_min: float
    role: HydraulicRouteRole = HydraulicRouteRole.PRIMARY
    base_throughput_factor: float = 1.0
    provenance: EngineeringProvenance = EngineeringProvenance.DESIGN_ASSUMPTION

    def __post_init__(self) -> None:
        if not self.route_id:
            raise ValueError("route_id is required")
        if not self.asset_id:
            raise ValueError("asset_id is required")
        if self.rated_flow_l_min < 0:
            raise ValueError("rated_flow_l_min must be non-negative")
        if not 0.0 <= self.base_throughput_factor <= 1.0:
            raise ValueError(
                "base_throughput_factor must be between 0.0 and 1.0"
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HydraulicRouteSpec":
        return cls(
            route_id=str(data["route_id"]),
            asset_id=str(data["asset_id"]),
            rated_flow_l_min=float(data["rated_flow_l_min"]),
            role=HydraulicRouteRole(
                data.get("role", HydraulicRouteRole.PRIMARY)
            ),
            base_throughput_factor=float(
                data.get("base_throughput_factor", 1.0)
            ),
            provenance=EngineeringProvenance(
                data.get(
                    "provenance",
                    EngineeringProvenance.DESIGN_ASSUMPTION,
                )
            ),
        )


@dataclass(slots=True, frozen=True)
class PondDesignProfile:
    profile_id: str
    revision: str
    effective_volume_l: float
    circulation_turnovers_per_hour_guide: float
    routes: tuple[HydraulicRouteSpec, ...]
    top_up_flow_l_min: float | None = None
    drain_flow_l_min: float | None = None
    biomass_kg: float | None = None
    feed_kg_per_day: float | None = None
    provenance: EngineeringProvenance = EngineeringProvenance.DESIGN_ASSUMPTION

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("profile_id is required")
        if not self.revision:
            raise ValueError("revision is required")
        if self.effective_volume_l <= 0:
            raise ValueError("effective_volume_l must be positive")
        if self.circulation_turnovers_per_hour_guide <= 0:
            raise ValueError(
                "circulation_turnovers_per_hour_guide must be positive"
            )
        if not self.routes:
            raise ValueError("at least one hydraulic route is required")
        route_ids = [route.route_id for route in self.routes]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("hydraulic route_id values must be unique")
        non_negative_fields = (
            "top_up_flow_l_min",
            "drain_flow_l_min",
            "biomass_kg",
            "feed_kg_per_day",
        )
        for field_name in non_negative_fields:
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(
                    f"{field_name} must be non-negative when provided"
                )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PondDesignProfile":
        return cls(
            profile_id=str(data["profile_id"]),
            revision=str(data["revision"]),
            effective_volume_l=float(data["effective_volume_l"]),
            circulation_turnovers_per_hour_guide=float(
                data["circulation_turnovers_per_hour_guide"]
            ),
            routes=tuple(
                HydraulicRouteSpec.from_dict(item) for item in data["routes"]
            ),
            top_up_flow_l_min=(
                float(data["top_up_flow_l_min"])
                if data.get("top_up_flow_l_min") is not None
                else None
            ),
            drain_flow_l_min=(
                float(data["drain_flow_l_min"])
                if data.get("drain_flow_l_min") is not None
                else None
            ),
            biomass_kg=(
                float(data["biomass_kg"])
                if data.get("biomass_kg") is not None
                else None
            ),
            feed_kg_per_day=(
                float(data["feed_kg_per_day"])
                if data.get("feed_kg_per_day") is not None
                else None
            ),
            provenance=EngineeringProvenance(
                data.get(
                    "provenance",
                    EngineeringProvenance.DESIGN_ASSUMPTION,
                )
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.value
        for route in payload["routes"]:
            route["role"] = route["role"].value
            route["provenance"] = route["provenance"].value
        return payload


class HydraulicNetworkModel:
    """Deterministic, reconfigurable hydraulic model for simulation.

    The model is profile-driven and gives process behavior plus capacity guidance
    without claiming site calibration or forcing an exact hardware size.
    """

    def __init__(self, profile: PondDesignProfile) -> None:
        self.profile = profile
        self._route_restrictions: dict[str, float] = {
            route.route_id: 1.0 for route in profile.routes
        }
        self._last_state = self.evaluate({})

    @staticmethod
    def _effect(
        actuator_effects: Mapping[str, float | bool],
        asset_id: str,
    ) -> float:
        value = actuator_effects.get(asset_id, 0.0)
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        return min(1.0, max(0.0, float(value)))

    @property
    def required_circulation_flow_l_min(self) -> float:
        return (
            self.profile.effective_volume_l
            * self.profile.circulation_turnovers_per_hour_guide
            / 60.0
        )

    def configure_profile(self, profile: PondDesignProfile) -> None:
        existing = self._route_restrictions
        self.profile = profile
        self._route_restrictions = {
            route.route_id: existing.get(route.route_id, 1.0)
            for route in profile.routes
        }
        self._last_state = self.evaluate({})

    def set_route_restriction(
        self,
        route_id: str,
        throughput_factor: float,
    ) -> None:
        if route_id not in {route.route_id for route in self.profile.routes}:
            raise KeyError(route_id)
        factor = float(throughput_factor)
        if not 0.0 <= factor <= 1.0:
            raise ValueError(
                "route throughput factor must be between 0.0 and 1.0"
            )
        self._route_restrictions[route_id] = factor

    def route_restriction(self, route_id: str) -> float:
        if route_id not in self._route_restrictions:
            raise KeyError(route_id)
        return self._route_restrictions[route_id]

    def _design_capacity(self, role: HydraulicRouteRole) -> float:
        return sum(
            route.rated_flow_l_min
            * route.base_throughput_factor
            * self._route_restrictions[route.route_id]
            for route in self.profile.routes
            if route.role == role
        )

    def _capacity_status(self, capacity_l_min: float) -> str:
        if capacity_l_min <= 0:
            return "NOT_CONFIGURED"
        if capacity_l_min < self.required_circulation_flow_l_min:
            return "BELOW_PROFILE_GUIDANCE"
        return "MEETS_OR_EXCEEDS_PROFILE_GUIDANCE"

    def evaluate(
        self,
        actuator_effects: Mapping[str, float | bool],
    ) -> dict[str, Any]:
        route_states: dict[str, dict[str, Any]] = {}
        total_flow = 0.0
        for route in self.profile.routes:
            runtime_factor = self._route_restrictions[route.route_id]
            active_effect = self._effect(actuator_effects, route.asset_id)
            effective_flow = (
                route.rated_flow_l_min
                * route.base_throughput_factor
                * runtime_factor
                * active_effect
            )
            total_flow += effective_flow
            route_states[route.route_id] = {
                "route_id": route.route_id,
                "asset_id": route.asset_id,
                "role": route.role.value,
                "rated_flow_l_min": route.rated_flow_l_min,
                "base_throughput_factor": route.base_throughput_factor,
                "runtime_throughput_factor": runtime_factor,
                "actuator_effectiveness": active_effect,
                "effective_flow_l_min": effective_flow,
                "provenance": route.provenance.value,
            }

        required = self.required_circulation_flow_l_min
        turnover = total_flow * 60.0 / self.profile.effective_volume_l
        active_status = (
            "BELOW_PROFILE_GUIDANCE"
            if total_flow < required
            else "MEETS_OR_EXCEEDS_PROFILE_GUIDANCE"
        )
        primary_capacity = self._design_capacity(HydraulicRouteRole.PRIMARY)
        backup_capacity = self._design_capacity(HydraulicRouteRole.BACKUP)
        parallel_capacity = self._design_capacity(HydraulicRouteRole.PARALLEL)
        state = {
            "profile_id": self.profile.profile_id,
            "profile_revision": self.profile.revision,
            "profile_provenance": self.profile.provenance.value,
            "effective_volume_l": self.profile.effective_volume_l,
            "circulation_turnovers_per_hour_guide": (
                self.profile.circulation_turnovers_per_hour_guide
            ),
            "required_circulation_flow_l_min": required,
            "total_effective_flow_l_min": total_flow,
            "achieved_turnovers_per_hour": turnover,
            "active_flow_status": active_status,
            "primary_design_capacity_l_min": primary_capacity,
            "backup_design_capacity_l_min": backup_capacity,
            "parallel_design_capacity_l_min": parallel_capacity,
            "primary_capacity_status": self._capacity_status(primary_capacity),
            "backup_capacity_status": self._capacity_status(backup_capacity),
            "parallel_capacity_status": self._capacity_status(
                parallel_capacity
            ),
            "sizing_advisory_is_mandatory_hardware_lock": False,
            "routes": route_states,
        }
        self._last_state = state
        return state

    def level_delta_pct_per_hour(
        self,
        *,
        top_up_effect: float,
        drain_effect: float,
    ) -> float | None:
        no_water_management_flow = (
            self.profile.top_up_flow_l_min is None
            and self.profile.drain_flow_l_min is None
        )
        if no_water_management_flow:
            return None
        top_up = (self.profile.top_up_flow_l_min or 0.0) * max(
            0.0,
            top_up_effect,
        )
        drain = (self.profile.drain_flow_l_min or 0.0) * max(
            0.0,
            drain_effect,
        )
        net_l_per_hour = (top_up - drain) * 60.0
        return net_l_per_hour / self.profile.effective_volume_l * 100.0

    def snapshot(self) -> dict[str, Any]:
        return dict(self._last_state)

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "route_restrictions": dict(self._route_restrictions),
        }

    @classmethod
    def from_checkpoint(
        cls,
        data: Mapping[str, Any],
    ) -> "HydraulicNetworkModel":
        network = cls(PondDesignProfile.from_dict(data["profile"]))
        for route_id, factor in data.get("route_restrictions", {}).items():
            if route_id in network._route_restrictions:
                network.set_route_restriction(route_id, float(factor))
        network._last_state = network.evaluate({})
        return network
