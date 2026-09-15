from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from smart_koi_pond.digital_twin.hydraulics import EngineeringProvenance


INDONESIA_JUVENILE_KOI_ESTIMATOR_ID = "INDONESIA_KOI_LENGTH_WEIGHT_2026_V1"
JUVENILE_KOI_FEEDING_REFERENCE_ID = "JUVENILE_KOI_FEEDING_2025_V1"


@dataclass(slots=True, frozen=True)
class LengthWeightEstimator:
    estimator_id: str
    revision: str
    source_reference: str
    min_length_cm: float
    max_length_cm: float
    intercept_g: float
    slope_g_per_cm: float
    r_squared: float | None = None
    standard_error_g: float | None = None
    provenance: EngineeringProvenance = EngineeringProvenance.EXPERT_REFERENCE_PROFILE

    def __post_init__(self) -> None:
        if not self.estimator_id or not self.revision or not self.source_reference:
            raise ValueError("estimator identity/revision/source are required")
        if self.min_length_cm <= 0 or self.max_length_cm <= self.min_length_cm:
            raise ValueError("estimator length domain is invalid")
        if self.provenance == EngineeringProvenance.UNAVAILABLE:
            raise ValueError("configured estimator cannot use UNAVAILABLE provenance")

    def estimate_weight_g(self, length_cm: float) -> float | None:
        length = float(length_cm)
        if not self.min_length_cm <= length <= self.max_length_cm:
            return None
        estimated = self.intercept_g + self.slope_g_per_cm * length
        return max(0.0, estimated)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.value
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LengthWeightEstimator:
        return cls(
            estimator_id=str(data["estimator_id"]),
            revision=str(data["revision"]),
            source_reference=str(data["source_reference"]),
            min_length_cm=float(data["min_length_cm"]),
            max_length_cm=float(data["max_length_cm"]),
            intercept_g=float(data["intercept_g"]),
            slope_g_per_cm=float(data["slope_g_per_cm"]),
            r_squared=(float(data["r_squared"]) if data.get("r_squared") is not None else None),
            standard_error_g=(
                float(data["standard_error_g"])
                if data.get("standard_error_g") is not None
                else None
            ),
            provenance=EngineeringProvenance.normalize(
                data.get("provenance", EngineeringProvenance.EXPERT_REFERENCE_PROFILE)
            ),
        )


def indonesia_juvenile_koi_estimator_v1() -> LengthWeightEstimator:
    """Published koi estimator; deliberately refuses extrapolation outside 11.27-20.12 cm."""
    return LengthWeightEstimator(
        estimator_id=INDONESIA_JUVENILE_KOI_ESTIMATOR_ID,
        revision="1",
        source_reference="DOI:10.1051/bioconf/202622904002",
        min_length_cm=11.27,
        max_length_cm=20.12,
        intercept_g=-142.663,
        slope_g_per_cm=13.874,
        r_squared=0.774,
        standard_error_g=17.090,
        provenance=EngineeringProvenance.EXPERT_REFERENCE_PROFILE,
    )


@dataclass(slots=True, frozen=True)
class KoiStockGroup:
    group_id: str
    count: int
    average_length_cm: float | None = None
    average_weight_g: float | None = None
    weight_provenance: EngineeringProvenance = EngineeringProvenance.MANUAL_REFERENCE

    def __post_init__(self) -> None:
        if not self.group_id:
            raise ValueError("group_id is required")
        if self.count <= 0:
            raise ValueError("count must be positive")
        if self.average_length_cm is not None and self.average_length_cm <= 0:
            raise ValueError("average_length_cm must be positive")
        if self.average_weight_g is not None and self.average_weight_g <= 0:
            raise ValueError("average_weight_g must be positive")
        if self.average_length_cm is None and self.average_weight_g is None:
            raise ValueError("average_length_cm or average_weight_g is required")
        if self.average_weight_g is not None and self.weight_provenance == EngineeringProvenance.UNAVAILABLE:
            raise ValueError("entered weight cannot use UNAVAILABLE provenance")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["weight_provenance"] = self.weight_provenance.value
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KoiStockGroup:
        return cls(
            group_id=str(data["group_id"]),
            count=int(data["count"]),
            average_length_cm=(
                float(data["average_length_cm"])
                if data.get("average_length_cm") is not None
                else None
            ),
            average_weight_g=(
                float(data["average_weight_g"])
                if data.get("average_weight_g") is not None
                else None
            ),
            weight_provenance=EngineeringProvenance.normalize(
                data.get("weight_provenance", EngineeringProvenance.MANUAL_REFERENCE)
            ),
        )


@dataclass(slots=True, frozen=True)
class KoiStockProfile:
    profile_id: str
    revision: str
    groups: tuple[KoiStockGroup, ...]
    source_reference: str
    estimator: LengthWeightEstimator | None = None
    provenance: EngineeringProvenance = EngineeringProvenance.USER_CONFIGURED

    def __post_init__(self) -> None:
        if not self.profile_id or not self.revision or not self.source_reference:
            raise ValueError("profile identity/revision/source are required")
        if not self.groups:
            raise ValueError("at least one koi stock group is required")
        ids = [group.group_id for group in self.groups]
        if len(ids) != len(set(ids)):
            raise ValueError("koi group ids must be unique")
        if self.provenance == EngineeringProvenance.UNAVAILABLE:
            raise ValueError("configured koi stock cannot use UNAVAILABLE provenance")

    def evaluate_biomass(self) -> dict[str, Any]:
        total_count = 0
        total_weight_g = 0.0
        group_results: list[dict[str, Any]] = []
        unresolved: list[str] = []
        for group in self.groups:
            total_count += group.count
            if group.average_weight_g is not None:
                avg_weight = group.average_weight_g
                basis = "ENTERED_WEIGHT"
                provenance = group.weight_provenance.value
            elif group.average_length_cm is not None and self.estimator is not None:
                avg_weight = self.estimator.estimate_weight_g(group.average_length_cm)
                if avg_weight is None:
                    unresolved.append(group.group_id)
                    group_results.append(
                        {
                            "group_id": group.group_id,
                            "count": group.count,
                            "average_length_cm": group.average_length_cm,
                            "average_weight_g": None,
                            "biomass_kg": None,
                            "status": "OUTSIDE_ESTIMATOR_DOMAIN",
                            "estimator_id": self.estimator.estimator_id,
                        }
                    )
                    continue
                basis = "LENGTH_WEIGHT_ESTIMATOR"
                provenance = self.estimator.provenance.value
            else:
                unresolved.append(group.group_id)
                group_results.append(
                    {
                        "group_id": group.group_id,
                        "count": group.count,
                        "average_length_cm": group.average_length_cm,
                        "average_weight_g": None,
                        "biomass_kg": None,
                        "status": "INPUT_REQUIRED",
                    }
                )
                continue

            group_weight_g = avg_weight * group.count
            total_weight_g += group_weight_g
            group_results.append(
                {
                    "group_id": group.group_id,
                    "count": group.count,
                    "average_length_cm": group.average_length_cm,
                    "average_weight_g": avg_weight,
                    "biomass_kg": group_weight_g / 1000.0,
                    "weight_basis": basis,
                    "weight_provenance": provenance,
                    "status": "RESOLVED",
                }
            )

        complete = not unresolved
        return {
            "configured": True,
            "profile_id": self.profile_id,
            "revision": self.revision,
            "source_reference": self.source_reference,
            "provenance": self.provenance.value,
            "total_count": total_count,
            "biomass_kg": total_weight_g / 1000.0 if complete else None,
            "status": "READY" if complete else "INPUT_REQUIRED",
            "unresolved_groups": unresolved,
            "groups": group_results,
            "estimator": self.estimator.to_dict() if self.estimator is not None else None,
            "estimator_extrapolation_allowed": False,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "revision": self.revision,
            "groups": [group.to_dict() for group in self.groups],
            "source_reference": self.source_reference,
            "estimator": self.estimator.to_dict() if self.estimator is not None else None,
            "provenance": self.provenance.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> KoiStockProfile:
        estimator = data.get("estimator")
        return cls(
            profile_id=str(data["profile_id"]),
            revision=str(data["revision"]),
            groups=tuple(KoiStockGroup.from_dict(item) for item in data["groups"]),
            source_reference=str(data["source_reference"]),
            estimator=LengthWeightEstimator.from_dict(estimator) if estimator else None,
            provenance=EngineeringProvenance.normalize(
                data.get("provenance", EngineeringProvenance.USER_CONFIGURED)
            ),
        )


@dataclass(slots=True, frozen=True)
class FeedingPolicy:
    policy_id: str
    revision: str
    source_reference: str
    body_weight_fraction_per_day: float
    meals_per_day: int
    min_average_weight_g: float | None = None
    max_average_weight_g: float | None = None
    min_temperature_c: float | None = None
    max_temperature_c: float | None = None
    provenance: EngineeringProvenance = EngineeringProvenance.USER_CONFIGURED

    def __post_init__(self) -> None:
        if not self.policy_id or not self.revision or not self.source_reference:
            raise ValueError("feeding policy identity/revision/source are required")
        if not 0 < self.body_weight_fraction_per_day <= 0.20:
            raise ValueError("body_weight_fraction_per_day must be >0 and <=0.20")
        if self.meals_per_day <= 0:
            raise ValueError("meals_per_day must be positive")
        if self.provenance == EngineeringProvenance.UNAVAILABLE:
            raise ValueError("configured feeding policy cannot use UNAVAILABLE provenance")

    def evaluate(
        self,
        *,
        biomass_snapshot: Mapping[str, Any],
        temperature_c: float | None,
    ) -> dict[str, Any]:
        biomass = biomass_snapshot.get("biomass_kg")
        if biomass is None:
            return self._unavailable("BIOMASS_INPUT_REQUIRED")
        groups = biomass_snapshot.get("groups") or []
        total_count = int(biomass_snapshot.get("total_count") or 0)
        weighted_g = float(biomass) * 1000.0
        avg_weight_g = weighted_g / total_count if total_count > 0 else None
        if (
            avg_weight_g is not None
            and self.min_average_weight_g is not None
            and avg_weight_g < self.min_average_weight_g
        ):
            return self._unavailable("OUTSIDE_POLICY_WEIGHT_DOMAIN")
        if (
            avg_weight_g is not None
            and self.max_average_weight_g is not None
            and avg_weight_g > self.max_average_weight_g
        ):
            return self._unavailable("OUTSIDE_POLICY_WEIGHT_DOMAIN")
        if temperature_c is None and (
            self.min_temperature_c is not None or self.max_temperature_c is not None
        ):
            return self._unavailable("TEMPERATURE_INPUT_REQUIRED")
        if (
            temperature_c is not None
            and self.min_temperature_c is not None
            and temperature_c < self.min_temperature_c
        ) or (
            temperature_c is not None
            and self.max_temperature_c is not None
            and temperature_c > self.max_temperature_c
        ):
            return self._unavailable("OUTSIDE_POLICY_TEMPERATURE_DOMAIN")
        feed_kg_per_day = float(biomass) * self.body_weight_fraction_per_day
        return {
            "configured": True,
            "status": "READY",
            "policy_id": self.policy_id,
            "revision": self.revision,
            "source_reference": self.source_reference,
            "provenance": self.provenance.value,
            "biomass_kg": float(biomass),
            "average_weight_g": avg_weight_g,
            "temperature_c": temperature_c,
            "body_weight_fraction_per_day": self.body_weight_fraction_per_day,
            "planned_feed_kg_per_day": feed_kg_per_day,
            "meals_per_day": self.meals_per_day,
            "planned_feed_per_meal_g": feed_kg_per_day * 1000.0 / self.meals_per_day,
            "groups_considered": len(groups),
        }

    def _unavailable(self, reason: str) -> dict[str, Any]:
        return {
            "configured": True,
            "status": "INPUT_REQUIRED",
            "reason": reason,
            "policy_id": self.policy_id,
            "revision": self.revision,
            "source_reference": self.source_reference,
            "provenance": self.provenance.value,
            "planned_feed_kg_per_day": None,
            "planned_feed_per_meal_g": None,
            "meals_per_day": self.meals_per_day,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.value
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FeedingPolicy:
        return cls(
            policy_id=str(data["policy_id"]),
            revision=str(data["revision"]),
            source_reference=str(data["source_reference"]),
            body_weight_fraction_per_day=float(data["body_weight_fraction_per_day"]),
            meals_per_day=int(data["meals_per_day"]),
            min_average_weight_g=(
                float(data["min_average_weight_g"])
                if data.get("min_average_weight_g") is not None
                else None
            ),
            max_average_weight_g=(
                float(data["max_average_weight_g"])
                if data.get("max_average_weight_g") is not None
                else None
            ),
            min_temperature_c=(
                float(data["min_temperature_c"])
                if data.get("min_temperature_c") is not None
                else None
            ),
            max_temperature_c=(
                float(data["max_temperature_c"])
                if data.get("max_temperature_c") is not None
                else None
            ),
            provenance=EngineeringProvenance.normalize(
                data.get("provenance", EngineeringProvenance.USER_CONFIGURED)
            ),
        )


def juvenile_koi_feeding_reference_2025_v1(*, rate_fraction: float = 0.035) -> FeedingPolicy:
    """Bounded reference midpoint from a 3-4% BW/day juvenile-koi study.

    It is intentionally not a universal/adult-koi production default.
    """
    if not 0.03 <= rate_fraction <= 0.04:
        raise ValueError("reference rate must remain within the published 3-4% BW/day range")
    return FeedingPolicy(
        policy_id=JUVENILE_KOI_FEEDING_REFERENCE_ID,
        revision="1",
        source_reference="DOI:10.3390/fishes10040181; 3-4% BW/day juvenile koi reference",
        body_weight_fraction_per_day=rate_fraction,
        meals_per_day=3,
        min_average_weight_g=5.0,
        max_average_weight_g=20.0,
        min_temperature_c=23.0,
        max_temperature_c=27.0,
        provenance=EngineeringProvenance.EXPERT_REFERENCE_PROFILE,
    )
