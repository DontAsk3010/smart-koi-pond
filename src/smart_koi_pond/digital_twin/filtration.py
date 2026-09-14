from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from smart_koi_pond.digital_twin.hydraulics import EngineeringProvenance
from smart_koi_pond.domain.models import PondState


@dataclass(slots=True, frozen=True)
class MechanicalFiltrationProfile:
    """Explicit-input mechanical-filtration process configuration."""

    profile_id: str
    revision: str
    source_reference: str
    filtered_route_id: str
    capture_efficiency_per_pass: float
    max_captured_solids_g: float
    minimum_route_throughput_factor_at_capacity: float
    backwash_solids_removal_g_per_min: float
    backwash_discharge_flow_l_min: float | None = None
    turbidity_ntu_per_mg_l_tss: float | None = None
    provenance: EngineeringProvenance = EngineeringProvenance.USER_CONFIGURED_SCENARIO

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("profile_id is required")
        if not self.revision:
            raise ValueError("revision is required")
        if not self.source_reference:
            raise ValueError("source_reference is required")
        if not self.filtered_route_id:
            raise ValueError("filtered_route_id is required")
        if not 0.0 <= self.capture_efficiency_per_pass <= 1.0:
            raise ValueError("capture_efficiency_per_pass must be between 0.0 and 1.0")
        if self.max_captured_solids_g <= 0:
            raise ValueError("max_captured_solids_g must be positive")
        if not 0.0 <= self.minimum_route_throughput_factor_at_capacity <= 1.0:
            raise ValueError(
                "minimum_route_throughput_factor_at_capacity must be between 0.0 and 1.0"
            )
        if self.backwash_solids_removal_g_per_min < 0:
            raise ValueError("backwash_solids_removal_g_per_min must be non-negative")
        if (
            self.backwash_discharge_flow_l_min is not None
            and self.backwash_discharge_flow_l_min < 0
        ):
            raise ValueError("backwash_discharge_flow_l_min must be non-negative")
        if (
            self.turbidity_ntu_per_mg_l_tss is not None
            and self.turbidity_ntu_per_mg_l_tss < 0
        ):
            raise ValueError("turbidity_ntu_per_mg_l_tss must be non-negative")
        if self.provenance == EngineeringProvenance.UNAVAILABLE:
            raise ValueError("configured mechanical-filtration profile cannot be UNAVAILABLE")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.value
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MechanicalFiltrationProfile:
        return cls(
            profile_id=str(data["profile_id"]),
            revision=str(data["revision"]),
            source_reference=str(data["source_reference"]),
            filtered_route_id=str(data["filtered_route_id"]),
            capture_efficiency_per_pass=float(data["capture_efficiency_per_pass"]),
            max_captured_solids_g=float(data["max_captured_solids_g"]),
            minimum_route_throughput_factor_at_capacity=float(
                data["minimum_route_throughput_factor_at_capacity"]
            ),
            backwash_solids_removal_g_per_min=float(
                data["backwash_solids_removal_g_per_min"]
            ),
            backwash_discharge_flow_l_min=(
                float(data["backwash_discharge_flow_l_min"])
                if data.get("backwash_discharge_flow_l_min") is not None
                else None
            ),
            turbidity_ntu_per_mg_l_tss=(
                float(data["turbidity_ntu_per_mg_l_tss"])
                if data.get("turbidity_ntu_per_mg_l_tss") is not None
                else None
            ),
            provenance=EngineeringProvenance.normalize(data["provenance"]),
        )


class MechanicalFiltrationModel:
    """Mass-conserving mechanical capture, loading and governed backwash model."""

    def __init__(self, profile: MechanicalFiltrationProfile) -> None:
        self.profile = profile
        self.captured_solids_g = 0.0
        self.cumulative_backwash_removed_g = 0.0
        self.cumulative_backwash_discharge_l = 0.0
        self._last_captured_g: float | None = None
        self._last_backwash_removed_g = 0.0
        self._last_backwash_discharge_l: float | None = None
        self._last_route_flow_l_min = 0.0

    def configure_profile(self, profile: MechanicalFiltrationProfile) -> None:
        self.profile = profile

    @property
    def loading_fraction(self) -> float:
        return self.captured_solids_g / self.profile.max_captured_solids_g

    @property
    def process_throughput_factor(self) -> float:
        bounded_loading = min(1.0, max(0.0, self.loading_fraction))
        minimum = self.profile.minimum_route_throughput_factor_at_capacity
        return 1.0 - (1.0 - minimum) * bounded_loading

    def step(
        self,
        state: PondState,
        *,
        seconds: float,
        volume_l: float,
        route_flow_l_min: float,
        backwash_effect: float,
    ) -> dict[str, float | None]:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        if volume_l <= 0:
            raise ValueError("volume_l must be positive")
        if route_flow_l_min < 0:
            raise ValueError("route_flow_l_min must be non-negative")

        minutes = seconds / 60.0
        captured_g: float | None = None
        if state.waste_solids_g is not None:
            suspended_g = max(0.0, float(state.waste_solids_g))
            processed_turnovers = route_flow_l_min * minutes / volume_l
            capture_fraction = 0.0
            if route_flow_l_min > 0 and processed_turnovers > 0:
                capture_fraction = 1.0 - (
                    1.0 - self.profile.capture_efficiency_per_pass
                ) ** processed_turnovers
            captured_g = min(suspended_g, suspended_g * capture_fraction)
            state.waste_solids_g = suspended_g - captured_g
            self.captured_solids_g += captured_g

        bounded_backwash = min(1.0, max(0.0, float(backwash_effect)))
        removed_g = min(
            self.captured_solids_g,
            self.profile.backwash_solids_removal_g_per_min * minutes * bounded_backwash,
        )
        self.captured_solids_g -= removed_g
        self.cumulative_backwash_removed_g += removed_g

        discharge_l: float | None = None
        if self.profile.backwash_discharge_flow_l_min is not None:
            requested_discharge_l = (
                self.profile.backwash_discharge_flow_l_min
                * minutes
                * bounded_backwash
            )
            available_water_l = volume_l * min(
                100.0,
                max(0.0, float(state.water_level_pct)),
            ) / 100.0
            discharge_l = min(requested_discharge_l, available_water_l)
            self.cumulative_backwash_discharge_l += discharge_l

        self._last_captured_g = captured_g
        self._last_backwash_removed_g = removed_g
        self._last_backwash_discharge_l = discharge_l
        self._last_route_flow_l_min = route_flow_l_min
        return {
            "captured_g": captured_g,
            "backwash_removed_g": removed_g,
            "backwash_discharge_l": discharge_l,
        }

    def snapshot(
        self,
        *,
        suspended_solids_g: float | None,
        volume_l: float | None,
    ) -> dict[str, Any]:
        tss_mg_l: float | None = None
        turbidity_ntu: float | None = None
        if suspended_solids_g is not None and volume_l is not None and volume_l > 0:
            tss_mg_l = max(0.0, suspended_solids_g) * 1000.0 / volume_l
            if self.profile.turbidity_ntu_per_mg_l_tss is not None:
                turbidity_ntu = tss_mg_l * self.profile.turbidity_ntu_per_mg_l_tss

        loading = self.loading_fraction
        return {
            "configured": True,
            "profile_id": self.profile.profile_id,
            "profile_revision": self.profile.revision,
            "source_reference": self.profile.source_reference,
            "provenance": self.profile.provenance.value,
            "filtered_route_id": self.profile.filtered_route_id,
            "capture_efficiency_per_pass": self.profile.capture_efficiency_per_pass,
            "captured_solids_g": self.captured_solids_g,
            "suspended_solids_g": suspended_solids_g,
            "max_captured_solids_g": self.profile.max_captured_solids_g,
            "loading_fraction": loading,
            "loading_status": (
                "AT_OR_ABOVE_CONFIGURED_CAPACITY"
                if loading >= 1.0
                else "BELOW_CONFIGURED_CAPACITY"
            ),
            "process_throughput_factor": self.process_throughput_factor,
            "last_route_flow_l_min": self._last_route_flow_l_min,
            "last_captured_g": self._last_captured_g,
            "last_backwash_removed_g": self._last_backwash_removed_g,
            "cumulative_backwash_removed_g": self.cumulative_backwash_removed_g,
            "backwash_discharge_flow_l_min": self.profile.backwash_discharge_flow_l_min,
            "last_backwash_discharge_l": self._last_backwash_discharge_l,
            "cumulative_backwash_discharge_l": (
                self.cumulative_backwash_discharge_l
                if self.profile.backwash_discharge_flow_l_min is not None
                else None
            ),
            "tss_mg_l": tss_mg_l,
            "tss_provenance": (
                EngineeringProvenance.CALCULATED.value
                if tss_mg_l is not None
                else EngineeringProvenance.UNAVAILABLE.value
            ),
            "turbidity_ntu": turbidity_ntu,
            "turbidity_provenance": (
                EngineeringProvenance.CALCULATED.value
                if turbidity_ntu is not None
                else EngineeringProvenance.UNAVAILABLE.value
            ),
            "water_clarity_conclusion": "NOT_ESTABLISHED",
            "hardware_fault_conclusion": "NOT_ESTABLISHED",
            "hardware_upgrade_required": False,
            "hardware_assessment_requires_evidence": True,
        }

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "captured_solids_g": self.captured_solids_g,
            "cumulative_backwash_removed_g": self.cumulative_backwash_removed_g,
            "cumulative_backwash_discharge_l": self.cumulative_backwash_discharge_l,
            "last_captured_g": self._last_captured_g,
            "last_backwash_removed_g": self._last_backwash_removed_g,
            "last_backwash_discharge_l": self._last_backwash_discharge_l,
            "last_route_flow_l_min": self._last_route_flow_l_min,
        }

    @classmethod
    def from_checkpoint(
        cls,
        data: Mapping[str, Any],
    ) -> MechanicalFiltrationModel:
        model = cls(MechanicalFiltrationProfile.from_dict(data["profile"]))
        model.captured_solids_g = max(0.0, float(data.get("captured_solids_g", 0.0)))
        model.cumulative_backwash_removed_g = max(
            0.0, float(data.get("cumulative_backwash_removed_g", 0.0))
        )
        model.cumulative_backwash_discharge_l = max(
            0.0, float(data.get("cumulative_backwash_discharge_l", 0.0))
        )
        last_captured = data.get("last_captured_g")
        model._last_captured_g = (
            float(last_captured) if last_captured is not None else None
        )
        model._last_backwash_removed_g = max(
            0.0, float(data.get("last_backwash_removed_g", 0.0))
        )
        last_discharge = data.get("last_backwash_discharge_l")
        model._last_backwash_discharge_l = (
            float(last_discharge) if last_discharge is not None else None
        )
        model._last_route_flow_l_min = max(
            0.0, float(data.get("last_route_flow_l_min", 0.0))
        )
        return model
