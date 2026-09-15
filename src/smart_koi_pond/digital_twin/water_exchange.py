from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .hydraulics import EngineeringProvenance
from .model import PondModel


SOURCE_WATER_QUALIFICATION_INPUT_REQUIRED = "INPUT_REQUIRED"
SOURCE_WATER_QUALIFICATION_NOT_QUALIFIED = "NOT_QUALIFIED"
SOURCE_WATER_QUALIFICATION_QUALIFIED = "QUALIFIED"
_SOURCE_WATER_QUALIFICATION_STATES = {
    SOURCE_WATER_QUALIFICATION_INPUT_REQUIRED,
    SOURCE_WATER_QUALIFICATION_NOT_QUALIFIED,
    SOURCE_WATER_QUALIFICATION_QUALIFIED,
}


@dataclass(slots=True, frozen=True)
class SourceWaterProfile:
    """Explicit source-water evidence used for virtual refill/mixing.

    Disinfectant residuals are evidence about the source water as presented to the
    pond after any external/manual conditioning. Qualification is explicit; source
    type never implies safe chemistry.
    """

    profile_id: str
    revision: str
    source_reference: str
    source_type: str
    temperature_c: float | None = None
    dissolved_oxygen_mg_l: float | None = None
    ph: float | None = None
    total_ammonia_nitrogen_mg_l: float | None = None
    nitrite_mg_l: float | None = None
    nitrate_mg_l: float | None = None
    alkalinity_mg_l_as_caco3: float | None = None
    free_chlorine_residual_mg_l: float | None = None
    chloramine_residual_mg_l: float | None = None
    pond_use_qualification: str = SOURCE_WATER_QUALIFICATION_INPUT_REQUIRED
    qualification_basis: str | None = None
    qualification_reference: str | None = None
    conditioning_method: str | None = None
    conditioning_reference: str | None = None
    provenance: EngineeringProvenance = EngineeringProvenance.USER_CONFIGURED_SCENARIO

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("profile_id is required")
        if not self.revision:
            raise ValueError("revision is required")
        if not self.source_reference:
            raise ValueError("source_reference is required")
        if not self.source_type:
            raise ValueError("source_type is required")
        for field_name in (
            "dissolved_oxygen_mg_l",
            "total_ammonia_nitrogen_mg_l",
            "nitrite_mg_l",
            "nitrate_mg_l",
            "alkalinity_mg_l_as_caco3",
            "free_chlorine_residual_mg_l",
            "chloramine_residual_mg_l",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be non-negative when provided")
        if self.ph is not None and not 0.0 <= self.ph <= 14.0:
            raise ValueError("ph must be between 0 and 14 when provided")
        qualification = str(self.pond_use_qualification).upper()
        if qualification not in _SOURCE_WATER_QUALIFICATION_STATES:
            raise ValueError(
                "pond_use_qualification must be INPUT_REQUIRED, NOT_QUALIFIED, or QUALIFIED"
            )
        object.__setattr__(self, "pond_use_qualification", qualification)
        if qualification == SOURCE_WATER_QUALIFICATION_QUALIFIED:
            if not self.qualification_basis:
                raise ValueError("QUALIFIED source water requires qualification_basis")
            if not self.qualification_reference:
                raise ValueError("QUALIFIED source water requires qualification_reference")
        if self.conditioning_method and not self.conditioning_reference:
            raise ValueError(
                "conditioning_reference is required when conditioning_method is provided"
            )
        if self.provenance == EngineeringProvenance.UNAVAILABLE:
            raise ValueError("configured source-water profile cannot be UNAVAILABLE")

    @property
    def pond_use_qualified(self) -> bool:
        return self.pond_use_qualification == SOURCE_WATER_QUALIFICATION_QUALIFIED

    def qualification_snapshot(self) -> dict[str, Any]:
        if self.pond_use_qualified:
            reason = "EXPLICIT_GOVERNED_QUALIFICATION_EVIDENCE"
        elif self.pond_use_qualification == SOURCE_WATER_QUALIFICATION_NOT_QUALIFIED:
            reason = "SOURCE_WATER_EXPLICITLY_NOT_QUALIFIED"
        else:
            reason = "SOURCE_WATER_QUALIFICATION_INPUT_REQUIRED"
        return {
            "state": self.pond_use_qualification,
            "pond_use_qualified": self.pond_use_qualified,
            "basis": self.qualification_basis,
            "reference": self.qualification_reference,
            "conditioning_method": self.conditioning_method,
            "conditioning_reference": self.conditioning_reference,
            "reason": reason,
            "source_type_implies_safe_chemistry": False,
            "automatic_chemical_dosing_authorized": False,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.value
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SourceWaterProfile:
        def optional_float(name: str) -> float | None:
            value = data.get(name)
            return float(value) if value is not None else None

        def optional_text(name: str) -> str | None:
            value = data.get(name)
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        return cls(
            profile_id=str(data["profile_id"]),
            revision=str(data["revision"]),
            source_reference=str(data["source_reference"]),
            source_type=str(data["source_type"]),
            temperature_c=optional_float("temperature_c"),
            dissolved_oxygen_mg_l=optional_float("dissolved_oxygen_mg_l"),
            ph=optional_float("ph"),
            total_ammonia_nitrogen_mg_l=optional_float(
                "total_ammonia_nitrogen_mg_l"
            ),
            nitrite_mg_l=optional_float("nitrite_mg_l"),
            nitrate_mg_l=optional_float("nitrate_mg_l"),
            alkalinity_mg_l_as_caco3=optional_float(
                "alkalinity_mg_l_as_caco3"
            ),
            free_chlorine_residual_mg_l=optional_float(
                "free_chlorine_residual_mg_l"
            ),
            chloramine_residual_mg_l=optional_float("chloramine_residual_mg_l"),
            pond_use_qualification=str(
                data.get(
                    "pond_use_qualification",
                    SOURCE_WATER_QUALIFICATION_INPUT_REQUIRED,
                )
            ),
            qualification_basis=optional_text("qualification_basis"),
            qualification_reference=optional_text("qualification_reference"),
            conditioning_method=optional_text("conditioning_method"),
            conditioning_reference=optional_text("conditioning_reference"),
            provenance=EngineeringProvenance.normalize(
                data.get("provenance", EngineeringProvenance.USER_CONFIGURED_SCENARIO)
            ),
        )


class WaterExchangePondModel(PondModel):
    """Pond model with governed discharge/refill and source-water mixing fidelity."""

    _CONCENTRATION_FIELDS = (
        "total_ammonia_nitrogen_mg_l",
        "nitrite_mg_l",
        "nitrate_mg_l",
        "alkalinity_mg_l_as_caco3",
    )

    def __init__(
        self,
        *args: Any,
        source_water: SourceWaterProfile | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.source_water = source_water
        self.cumulative_discharge_l = 0.0
        self.cumulative_refill_l = 0.0
        self._last_exchange: dict[str, Any] | None = None

    def configure_source_water_profile(self, profile: SourceWaterProfile) -> None:
        self.source_water = profile

    def source_water_is_qualified(self) -> bool:
        return self.source_water is not None and self.source_water.pond_use_qualified

    def source_water_qualification_snapshot(self) -> dict[str, Any]:
        if self.source_water is None:
            return {
                "state": SOURCE_WATER_QUALIFICATION_INPUT_REQUIRED,
                "pond_use_qualified": False,
                "basis": None,
                "reference": None,
                "conditioning_method": None,
                "conditioning_reference": None,
                "reason": "SOURCE_WATER_PROFILE_INPUT_REQUIRED",
                "source_type_implies_safe_chemistry": False,
                "automatic_chemical_dosing_authorized": False,
            }
        return self.source_water.qualification_snapshot()

    def source_water_snapshot(self) -> dict[str, Any]:
        qualification = self.source_water_qualification_snapshot()
        if self.source_water is None:
            return {
                "configured": False,
                "status": "INPUT_REQUIRED",
                "provenance": EngineeringProvenance.UNAVAILABLE.value,
                "qualification": qualification,
                "pond_use_qualified": False,
            }
        return {
            "configured": True,
            **self.source_water.to_dict(),
            "qualification": qualification,
            "pond_use_qualified": qualification["pond_use_qualified"],
        }

    def water_exchange_snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "model": "WELL_MIXED_DISCHARGE_PLUS_SOURCE_WATER_MIXING_V1",
            "source_water": self.source_water_snapshot(),
            "cumulative_discharge_l": self.cumulative_discharge_l,
            "cumulative_refill_l": self.cumulative_refill_l,
            "last_exchange": self._last_exchange,
            "discharge_only_concentration_change": (
                "NONE_UNDER_WELL_MIXED_ASSUMPTION"
            ),
            "ph_mixing_model": "BUFFER_WEIGHTED_HYDROGEN_ACTIVITY_SIMPLIFIED_V1",
            "ph_model_is_laboratory_equilibrium": False,
            "unknown_source_values_are_fabricated": False,
            "source_type_implies_disinfectant_absence": False,
            "automatic_chemical_dosing_authorized": False,
        }

    def hydraulic_snapshot(self) -> dict[str, Any]:
        snapshot = super().hydraulic_snapshot()
        snapshot["water_exchange"] = self.water_exchange_snapshot()
        return snapshot

    def checkpoint_state(self) -> dict[str, Any]:
        payload = super().checkpoint_state()
        payload["water_exchange"] = {
            "source_water": (
                self.source_water.to_dict() if self.source_water is not None else None
            ),
            "cumulative_discharge_l": self.cumulative_discharge_l,
            "cumulative_refill_l": self.cumulative_refill_l,
            "last_exchange": self._last_exchange,
        }
        return payload

    def restore_engineering_state(self, state: Mapping[str, Any] | None) -> None:
        super().restore_engineering_state(state)
        exchange = state.get("water_exchange") if state else None
        if not exchange:
            self.source_water = None
            self.cumulative_discharge_l = 0.0
            self.cumulative_refill_l = 0.0
            self._last_exchange = None
            return
        source = exchange.get("source_water")
        self.source_water = SourceWaterProfile.from_dict(source) if source else None
        self.cumulative_discharge_l = max(
            0.0,
            float(exchange.get("cumulative_discharge_l", 0.0)),
        )
        self.cumulative_refill_l = max(
            0.0,
            float(exchange.get("cumulative_refill_l", 0.0)),
        )
        last_exchange = exchange.get("last_exchange")
        self._last_exchange = dict(last_exchange) if last_exchange else None

    @staticmethod
    def _mixed_value(
        pond_value: float,
        source_value: float,
        remaining_volume_l: float,
        refill_l: float,
    ) -> float:
        final_volume_l = remaining_volume_l + refill_l
        if final_volume_l <= 0:
            return pond_value
        return (
            pond_value * remaining_volume_l + source_value * refill_l
        ) / final_volume_l

    def _mix_concentration(
        self,
        field_name: str,
        *,
        remaining_volume_l: float,
        refill_l: float,
        before_value: float | None,
    ) -> dict[str, Any]:
        source_value = (
            getattr(self.source_water, field_name)
            if self.source_water is not None
            else None
        )
        if before_value is None:
            return {
                "before": None,
                "source": source_value,
                "after": None,
                "status": "POND_VALUE_UNKNOWN",
            }
        if source_value is None:
            setattr(self.state, field_name, None)
            return {
                "before": before_value,
                "source": None,
                "after": None,
                "status": "SOURCE_VALUE_UNKNOWN_POST_MIX_NOT_ESTABLISHED",
            }
        after = self._mixed_value(
            before_value,
            source_value,
            remaining_volume_l,
            refill_l,
        )
        setattr(self.state, field_name, after)
        return {
            "before": before_value,
            "source": source_value,
            "after": after,
            "status": "CALCULATED_CONSERVED_MASS_MIXING",
        }

    def _mix_temperature_or_do(
        self,
        field_name: str,
        source_field: str,
        *,
        remaining_volume_l: float,
        refill_l: float,
    ) -> dict[str, Any]:
        before = float(getattr(self.state, field_name))
        source_value = (
            getattr(self.source_water, source_field)
            if self.source_water is not None
            else None
        )
        if source_value is None:
            return {
                "before": before,
                "source": None,
                "after": before,
                "status": "SOURCE_VALUE_UNKNOWN_NOT_APPLIED",
            }
        after = self._mixed_value(before, source_value, remaining_volume_l, refill_l)
        setattr(self.state, field_name, after)
        return {
            "before": before,
            "source": source_value,
            "after": after,
            "status": "CALCULATED_VOLUME_WEIGHTED_MIXING",
        }

    def _mix_ph(
        self,
        *,
        remaining_volume_l: float,
        refill_l: float,
        pond_alkalinity_before: float | None,
    ) -> dict[str, Any]:
        before = float(self.state.ph)
        source_ph = self.source_water.ph if self.source_water is not None else None
        source_alkalinity = (
            self.source_water.alkalinity_mg_l_as_caco3
            if self.source_water is not None
            else None
        )
        if (
            source_ph is None
            or source_alkalinity is None
            or pond_alkalinity_before is None
        ):
            return {
                "before": before,
                "source": source_ph,
                "after": before,
                "status": "PARTIAL_BUFFER_CONTEXT_REQUIRED_NOT_APPLIED",
                "model": "BUFFER_WEIGHTED_HYDROGEN_ACTIVITY_SIMPLIFIED_V1",
            }
        pond_weight = remaining_volume_l * max(pond_alkalinity_before, 1e-9)
        source_weight = refill_l * max(source_alkalinity, 1e-9)
        denominator = pond_weight + source_weight
        if denominator <= 0:
            return {
                "before": before,
                "source": source_ph,
                "after": before,
                "status": "PARTIAL_ZERO_BUFFER_WEIGHT_NOT_APPLIED",
                "model": "BUFFER_WEIGHTED_HYDROGEN_ACTIVITY_SIMPLIFIED_V1",
            }
        hydrogen_activity = (
            10 ** (-before) * pond_weight
            + 10 ** (-source_ph) * source_weight
        ) / denominator
        after = -math.log10(max(hydrogen_activity, 1e-14))
        self.state.ph = min(14.0, max(0.0, after))
        return {
            "before": before,
            "source": source_ph,
            "after": self.state.ph,
            "status": "MODELED_SIMPLIFIED_BUFFER_WEIGHTED_H_ACTIVITY",
            "model": "BUFFER_WEIGHTED_HYDROGEN_ACTIVITY_SIMPLIFIED_V1",
            "laboratory_equilibrium_claim": False,
        }

    def step(
        self,
        seconds: float,
        actuator_effects: dict[str, float | bool],
    ):
        if self.hydraulics is None or seconds <= 0:
            return super().step(seconds, actuator_effects)

        design_volume_l = self.hydraulics.profile.effective_volume_l
        starting_volume_l = (
            design_volume_l
            * min(100.0, max(0.0, float(self.state.water_level_pct)))
            / 100.0
        )

        state = super().step(seconds, actuator_effects)

        minutes = seconds / 60.0
        hours = seconds / 3600.0
        top_up_effect = self._effect(actuator_effects, "top_up_valve")
        drain_effect = self._effect(actuator_effects, "drain_valve")
        top_up_requested_l = (
            (self.hydraulics.profile.top_up_flow_l_min or 0.0)
            * minutes
            * top_up_effect
        )
        drain_requested_l = (
            (self.hydraulics.profile.drain_flow_l_min or 0.0)
            * minutes
            * drain_effect
        )
        leak_requested_l = (
            design_volume_l
            * max(0.0, self.environment.leak_pct_per_hour)
            * hours
            / 100.0
        )
        backwash_discharge_l = 0.0
        if self.filtration is not None:
            last_discharge = self.filtration.snapshot(
                suspended_solids_g=self.state.waste_solids_g,
                volume_l=design_volume_l,
            ).get("last_backwash_discharge_l")
            backwash_discharge_l = max(0.0, float(last_discharge or 0.0))

        discharge_l = min(
            starting_volume_l,
            drain_requested_l + leak_requested_l + backwash_discharge_l,
        )
        remaining_volume_l = max(0.0, starting_volume_l - discharge_l)
        refill_l = min(
            top_up_requested_l,
            max(0.0, design_volume_l - remaining_volume_l),
        )
        final_volume_l = remaining_volume_l + refill_l
        self.state.water_level_pct = (
            min(100.0, max(0.0, final_volume_l / design_volume_l * 100.0))
            if design_volume_l > 0
            else 0.0
        )

        if discharge_l <= 0 and refill_l <= 0:
            return state

        parameter_results: dict[str, Any] = {
            field_name: {
                "before": getattr(self.state, field_name),
                "source": None,
                "after": getattr(self.state, field_name),
                "status": "DISCHARGE_ONLY_CONCENTRATION_INVARIANT",
            }
            for field_name in self._CONCENTRATION_FIELDS
        }

        if refill_l > 0:
            before_concentrations = {
                field_name: getattr(self.state, field_name)
                for field_name in self._CONCENTRATION_FIELDS
            }
            pond_alkalinity_before = before_concentrations[
                "alkalinity_mg_l_as_caco3"
            ]
            for field_name, before_value in before_concentrations.items():
                parameter_results[field_name] = self._mix_concentration(
                    field_name,
                    remaining_volume_l=remaining_volume_l,
                    refill_l=refill_l,
                    before_value=before_value,
                )
            parameter_results["temperature_c"] = self._mix_temperature_or_do(
                "temperature_c",
                "temperature_c",
                remaining_volume_l=remaining_volume_l,
                refill_l=refill_l,
            )
            parameter_results[
                "dissolved_oxygen_mg_l"
            ] = self._mix_temperature_or_do(
                "dissolved_oxygen_mg_l",
                "dissolved_oxygen_mg_l",
                remaining_volume_l=remaining_volume_l,
                refill_l=refill_l,
            )
            parameter_results["ph"] = self._mix_ph(
                remaining_volume_l=remaining_volume_l,
                refill_l=refill_l,
                pond_alkalinity_before=pond_alkalinity_before,
            )

        self.cumulative_discharge_l += discharge_l
        self.cumulative_refill_l += refill_l
        qualification = self.source_water_qualification_snapshot()
        self._last_exchange = {
            "starting_volume_l": starting_volume_l,
            "discharge_l": discharge_l,
            "discharge_breakdown_l": {
                "backwash": min(backwash_discharge_l, discharge_l),
                "drain_requested": drain_requested_l,
                "leak_requested": leak_requested_l,
            },
            "remaining_volume_l": remaining_volume_l,
            "refill_l": refill_l,
            "final_volume_l": final_volume_l,
            "source_profile_id": (
                self.source_water.profile_id if self.source_water is not None else None
            ),
            "source_profile_revision": (
                self.source_water.revision if self.source_water is not None else None
            ),
            "source_provenance": (
                self.source_water.provenance.value
                if self.source_water is not None
                else EngineeringProvenance.UNAVAILABLE.value
            ),
            "source_water_qualification": qualification,
            "parameter_results": parameter_results,
            "well_mixed_discharge_assumption": True,
        }
        return state
