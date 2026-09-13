from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from smart_koi_pond.digital_twin.hydraulics import EngineeringProvenance
from smart_koi_pond.domain.models import PondState


@dataclass(slots=True, frozen=True)
class BiologicalProcessProfile:
    """Explicit biological-process configuration.

    The profile intentionally has no hidden engineering defaults. Coefficients must be
    supplied from a governed source, user-configured scenario, datasheet/reference,
    calculation, or measured/calibrated evidence.
    """

    profile_id: str
    revision: str
    source_reference: str
    biofilter_ammonia_capacity_g_n_per_day: float
    biofilter_nitrite_capacity_g_n_per_day: float
    fish_oxygen_demand_g_o2_per_kg_hour: float
    feed_oxygen_demand_g_o2_per_kg_feed: float
    ammonia_n_generation_g_per_kg_feed: float
    solid_waste_g_per_kg_feed: float
    nitrification_oxygen_g_o2_per_g_n: float
    alkalinity_consumption_g_caco3_per_g_n: float
    nitrification_do_reference_mg_l: float
    ph_drop_per_100_mg_l_alkalinity_loss: float
    provenance: EngineeringProvenance

    def __post_init__(self) -> None:
        if not self.profile_id:
            raise ValueError("profile_id is required")
        if not self.revision:
            raise ValueError("revision is required")
        if not self.source_reference:
            raise ValueError("source_reference is required")
        non_negative = (
            "biofilter_ammonia_capacity_g_n_per_day",
            "biofilter_nitrite_capacity_g_n_per_day",
            "fish_oxygen_demand_g_o2_per_kg_hour",
            "feed_oxygen_demand_g_o2_per_kg_feed",
            "ammonia_n_generation_g_per_kg_feed",
            "solid_waste_g_per_kg_feed",
            "nitrification_oxygen_g_o2_per_g_n",
            "alkalinity_consumption_g_caco3_per_g_n",
            "ph_drop_per_100_mg_l_alkalinity_loss",
        )
        for field_name in non_negative:
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if self.nitrification_do_reference_mg_l <= 0:
            raise ValueError("nitrification_do_reference_mg_l must be positive")
        if self.provenance == EngineeringProvenance.UNAVAILABLE:
            raise ValueError("configured biological profile cannot use UNAVAILABLE provenance")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BiologicalProcessProfile":
        return cls(
            profile_id=str(data["profile_id"]),
            revision=str(data["revision"]),
            source_reference=str(data["source_reference"]),
            biofilter_ammonia_capacity_g_n_per_day=float(
                data["biofilter_ammonia_capacity_g_n_per_day"]
            ),
            biofilter_nitrite_capacity_g_n_per_day=float(
                data["biofilter_nitrite_capacity_g_n_per_day"]
            ),
            fish_oxygen_demand_g_o2_per_kg_hour=float(
                data["fish_oxygen_demand_g_o2_per_kg_hour"]
            ),
            feed_oxygen_demand_g_o2_per_kg_feed=float(
                data["feed_oxygen_demand_g_o2_per_kg_feed"]
            ),
            ammonia_n_generation_g_per_kg_feed=float(
                data["ammonia_n_generation_g_per_kg_feed"]
            ),
            solid_waste_g_per_kg_feed=float(data["solid_waste_g_per_kg_feed"]),
            nitrification_oxygen_g_o2_per_g_n=float(
                data["nitrification_oxygen_g_o2_per_g_n"]
            ),
            alkalinity_consumption_g_caco3_per_g_n=float(
                data["alkalinity_consumption_g_caco3_per_g_n"]
            ),
            nitrification_do_reference_mg_l=float(
                data["nitrification_do_reference_mg_l"]
            ),
            ph_drop_per_100_mg_l_alkalinity_loss=float(
                data["ph_drop_per_100_mg_l_alkalinity_loss"]
            ),
            provenance=EngineeringProvenance.normalize(data["provenance"]),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.value
        return payload


class BiologicalProcessModel:
    """Deterministic feed/biomass → oxygen/waste → nitrogen-cycle model.

    The process uses only explicit Pond Profile inputs and explicit configured
    coefficients. Missing input remains visible and prevents unsupported chemistry
    evolution instead of being replaced by a synthetic value.
    """

    def __init__(self, profile: BiologicalProcessProfile) -> None:
        self.profile = profile
        self._last_snapshot: dict[str, Any] = self._empty_snapshot("NOT_EVALUATED")

    def configure_profile(self, profile: BiologicalProcessProfile) -> None:
        self.profile = profile
        self._last_snapshot = self._empty_snapshot("PROFILE_RECONFIGURED")

    def _empty_snapshot(self, status: str) -> dict[str, Any]:
        return {
            "configured": True,
            "status": status,
            "profile_id": self.profile.profile_id,
            "profile_revision": self.profile.revision,
            "source_reference": self.profile.source_reference,
            "provenance": self.profile.provenance.value,
            "units": {
                "volume": "L",
                "biomass": "kg",
                "feed": "kg/day",
                "oxygen_demand": "mg/L/hour",
                "tan": "mg/L",
                "nitrite": "mg/L",
                "nitrate": "mg/L",
                "alkalinity": "mg/L as CaCO3",
                "waste_solids": "g",
            },
        }

    @staticmethod
    def _mg_l_to_g(value_mg_l: float, volume_l: float) -> float:
        return value_mg_l * volume_l / 1000.0

    @staticmethod
    def _g_to_mg_l(value_g: float, volume_l: float) -> float:
        return value_g * 1000.0 / volume_l

    def evaluate_oxygen_demand_mg_l_per_hour(
        self,
        *,
        volume_l: float,
        biomass_kg: float | None,
        feed_kg_per_day: float | None,
        nitrified_n_g_per_hour: float = 0.0,
    ) -> float | None:
        if biomass_kg is None or feed_kg_per_day is None:
            return None
        p = self.profile
        oxygen_g_per_hour = (
            biomass_kg * p.fish_oxygen_demand_g_o2_per_kg_hour
            + feed_kg_per_day * p.feed_oxygen_demand_g_o2_per_kg_feed / 24.0
            + nitrified_n_g_per_hour * p.nitrification_oxygen_g_o2_per_g_n
        )
        return oxygen_g_per_hour * 1000.0 / volume_l

    def step(
        self,
        state: PondState,
        *,
        seconds: float,
        volume_l: float,
        biomass_kg: float | None,
        feed_kg_per_day: float | None,
        circulation_flow_l_min: float,
        required_circulation_flow_l_min: float,
    ) -> float:
        if seconds < 0:
            raise ValueError("seconds cannot be negative")
        missing_profile_inputs = []
        if biomass_kg is None:
            missing_profile_inputs.append("biomass_kg")
        if feed_kg_per_day is None:
            missing_profile_inputs.append("feed_kg_per_day")
        chemistry_values = {
            "total_ammonia_nitrogen_mg_l": state.total_ammonia_nitrogen_mg_l,
            "nitrite_mg_l": state.nitrite_mg_l,
            "nitrate_mg_l": state.nitrate_mg_l,
            "alkalinity_mg_l_as_caco3": state.alkalinity_mg_l_as_caco3,
            "waste_solids_g": state.waste_solids_g,
        }
        missing_chemistry = [name for name, value in chemistry_values.items() if value is None]

        base_demand = self.evaluate_oxygen_demand_mg_l_per_hour(
            volume_l=volume_l,
            biomass_kg=biomass_kg,
            feed_kg_per_day=feed_kg_per_day,
        )
        if missing_profile_inputs:
            self._last_snapshot = {
                **self._empty_snapshot("INPUT_REQUIRED"),
                "missing_inputs": tuple(missing_profile_inputs),
                "chemistry_evolution_active": False,
                "biological_oxygen_demand_mg_l_per_hour": None,
            }
            return 0.0

        if missing_chemistry:
            self._last_snapshot = {
                **self._empty_snapshot("CHEMISTRY_INPUT_REQUIRED"),
                "missing_inputs": tuple(missing_chemistry),
                "chemistry_evolution_active": False,
                "biological_oxygen_demand_mg_l_per_hour": base_demand,
            }
            return float(base_demand or 0.0)

        if seconds == 0:
            self._last_snapshot = {
                **self._empty_snapshot("READY"),
                "missing_inputs": (),
                "chemistry_evolution_active": True,
                "biological_oxygen_demand_mg_l_per_hour": base_demand,
                "flow_support_factor": self._flow_factor(
                    circulation_flow_l_min,
                    required_circulation_flow_l_min,
                ),
                "do_support_factor": self._do_factor(state.dissolved_oxygen_mg_l),
            }
            return float(base_demand or 0.0)

        assert biomass_kg is not None
        assert feed_kg_per_day is not None
        assert state.total_ammonia_nitrogen_mg_l is not None
        assert state.nitrite_mg_l is not None
        assert state.nitrate_mg_l is not None
        assert state.alkalinity_mg_l_as_caco3 is not None
        assert state.waste_solids_g is not None

        p = self.profile
        days = seconds / 86400.0
        hours = seconds / 3600.0
        flow_factor = self._flow_factor(
            circulation_flow_l_min,
            required_circulation_flow_l_min,
        )
        do_factor = self._do_factor(state.dissolved_oxygen_mg_l)
        support_factor = min(flow_factor, do_factor)

        ammonia_mass_g = self._mg_l_to_g(
            state.total_ammonia_nitrogen_mg_l,
            volume_l,
        )
        nitrite_mass_g = self._mg_l_to_g(state.nitrite_mg_l, volume_l)
        nitrate_mass_g = self._mg_l_to_g(state.nitrate_mg_l, volume_l)

        generated_ammonia_g = (
            feed_kg_per_day * p.ammonia_n_generation_g_per_kg_feed * days
        )
        ammonia_mass_g += generated_ammonia_g
        ammonia_capacity_g = (
            p.biofilter_ammonia_capacity_g_n_per_day * days * support_factor
        )
        ammonia_oxidized_g = min(ammonia_mass_g, ammonia_capacity_g)
        ammonia_mass_g -= ammonia_oxidized_g
        nitrite_mass_g += ammonia_oxidized_g

        nitrite_capacity_g = (
            p.biofilter_nitrite_capacity_g_n_per_day * days * support_factor
        )
        nitrite_oxidized_g = min(nitrite_mass_g, nitrite_capacity_g)
        nitrite_mass_g -= nitrite_oxidized_g
        nitrate_mass_g += nitrite_oxidized_g

        total_nitrified_g = ammonia_oxidized_g + nitrite_oxidized_g
        alkalinity_consumed_g = (
            total_nitrified_g * p.alkalinity_consumption_g_caco3_per_g_n
        )
        alkalinity_loss_mg_l = self._g_to_mg_l(alkalinity_consumed_g, volume_l)
        prior_alkalinity = state.alkalinity_mg_l_as_caco3
        state.alkalinity_mg_l_as_caco3 = max(0.0, prior_alkalinity - alkalinity_loss_mg_l)
        if alkalinity_loss_mg_l > 0:
            state.ph = max(
                0.0,
                state.ph
                - alkalinity_loss_mg_l
                / 100.0
                * p.ph_drop_per_100_mg_l_alkalinity_loss,
            )

        generated_solids_g = feed_kg_per_day * p.solid_waste_g_per_kg_feed * days
        state.waste_solids_g += generated_solids_g
        state.total_ammonia_nitrogen_mg_l = self._g_to_mg_l(ammonia_mass_g, volume_l)
        state.nitrite_mg_l = self._g_to_mg_l(nitrite_mass_g, volume_l)
        state.nitrate_mg_l = self._g_to_mg_l(nitrate_mass_g, volume_l)

        nitrified_n_g_per_hour = total_nitrified_g / hours if hours > 0 else 0.0
        oxygen_demand = self.evaluate_oxygen_demand_mg_l_per_hour(
            volume_l=volume_l,
            biomass_kg=biomass_kg,
            feed_kg_per_day=feed_kg_per_day,
            nitrified_n_g_per_hour=nitrified_n_g_per_hour,
        )
        self._last_snapshot = {
            **self._empty_snapshot("READY"),
            "missing_inputs": (),
            "chemistry_evolution_active": True,
            "biomass_kg": biomass_kg,
            "feed_kg_per_day": feed_kg_per_day,
            "flow_support_factor": flow_factor,
            "do_support_factor": do_factor,
            "ammonia_generated_g_n": generated_ammonia_g,
            "ammonia_oxidized_g_n": ammonia_oxidized_g,
            "nitrite_oxidized_g_n": nitrite_oxidized_g,
            "alkalinity_consumed_g_caco3": alkalinity_consumed_g,
            "solid_waste_generated_g": generated_solids_g,
            "biological_oxygen_demand_mg_l_per_hour": oxygen_demand,
        }
        return float(oxygen_demand or 0.0)

    def _do_factor(self, dissolved_oxygen_mg_l: float) -> float:
        return min(
            1.0,
            max(0.0, dissolved_oxygen_mg_l / self.profile.nitrification_do_reference_mg_l),
        )

    @staticmethod
    def _flow_factor(flow_l_min: float, required_flow_l_min: float) -> float:
        if required_flow_l_min <= 0:
            return 0.0
        return min(1.0, max(0.0, flow_l_min / required_flow_l_min))

    def snapshot(self) -> dict[str, Any]:
        return dict(self._last_snapshot)

    def checkpoint_state(self) -> dict[str, Any]:
        return {"profile": self.profile.to_dict()}

    @classmethod
    def from_checkpoint(cls, data: Mapping[str, Any]) -> "BiologicalProcessModel":
        return cls(BiologicalProcessProfile.from_dict(data["profile"]))
