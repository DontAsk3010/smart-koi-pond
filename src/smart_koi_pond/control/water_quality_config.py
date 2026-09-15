from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from smart_koi_pond.digital_twin.hydraulics import EngineeringProvenance


@dataclass(slots=True, frozen=True)
class WaterQualityThresholdProfile:
    """Versioned water-quality classification and recovery thresholds.

    Values are explicit governed configuration. This class deliberately does not
    provide hidden universal biological defaults. ``nh3_*`` fields are molecular
    un-ionized ammonia NH3 in mg/L, not NH3-N in mg N/L.
    """

    profile_id: str
    revision: str
    source_reference: str
    tan_watch_above: float | None = None
    tan_emergency_above: float | None = None
    tan_recover_below: float | None = None
    nh3_watch_above: float | None = None
    nh3_emergency_above: float | None = None
    nh3_recover_below: float | None = None
    nitrite_watch_above: float | None = None
    nitrite_emergency_above: float | None = None
    nitrite_recover_below: float | None = None
    nitrate_watch_above: float | None = None
    nitrate_recover_below: float | None = None
    ph_watch_below: float | None = None
    ph_watch_above: float | None = None
    ph_emergency_below: float | None = None
    ph_emergency_above: float | None = None
    ph_recover_low: float | None = None
    ph_recover_high: float | None = None
    automatic_water_exchange_enabled: bool = False
    exchange_fraction_pct: float | None = None
    max_recovery_attempts: int = 1
    recovery_cooldown_seconds: float = 1800.0
    provenance: EngineeringProvenance = EngineeringProvenance.USER_CONFIGURED

    def __post_init__(self) -> None:
        if not self.profile_id or not self.revision or not self.source_reference:
            raise ValueError("profile identity/revision/source are required")
        for name in (
            "tan_watch_above",
            "tan_emergency_above",
            "tan_recover_below",
            "nh3_watch_above",
            "nh3_emergency_above",
            "nh3_recover_below",
            "nitrite_watch_above",
            "nitrite_emergency_above",
            "nitrite_recover_below",
            "nitrate_watch_above",
            "nitrate_recover_below",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if (
            self.tan_watch_above is not None
            and self.tan_emergency_above is not None
            and self.tan_emergency_above <= self.tan_watch_above
        ):
            raise ValueError("TAN emergency must be above TAN watch")
        if (
            self.nh3_watch_above is not None
            and self.nh3_emergency_above is not None
            and self.nh3_emergency_above <= self.nh3_watch_above
        ):
            raise ValueError("NH3 emergency must be above NH3 watch")
        if (
            self.nitrite_watch_above is not None
            and self.nitrite_emergency_above is not None
            and self.nitrite_emergency_above <= self.nitrite_watch_above
        ):
            raise ValueError("nitrite emergency must be above nitrite watch")
        if (
            self.tan_recover_below is not None
            and self.tan_watch_above is not None
            and self.tan_recover_below >= self.tan_watch_above
        ):
            raise ValueError("TAN recovery must be below TAN watch")
        if (
            self.nh3_recover_below is not None
            and self.nh3_watch_above is not None
            and self.nh3_recover_below >= self.nh3_watch_above
        ):
            raise ValueError("NH3 recovery must be below NH3 watch")
        if (
            self.nitrite_recover_below is not None
            and self.nitrite_watch_above is not None
            and self.nitrite_recover_below >= self.nitrite_watch_above
        ):
            raise ValueError("nitrite recovery must be below nitrite watch")
        if (
            self.nitrate_recover_below is not None
            and self.nitrate_watch_above is not None
            and self.nitrate_recover_below >= self.nitrate_watch_above
        ):
            raise ValueError("nitrate recovery must be below nitrate watch")
        if (
            self.ph_watch_below is not None
            and self.ph_emergency_below is not None
            and self.ph_emergency_below >= self.ph_watch_below
        ):
            raise ValueError("pH low emergency must be below pH low watch")
        if (
            self.ph_watch_above is not None
            and self.ph_emergency_above is not None
            and self.ph_emergency_above <= self.ph_watch_above
        ):
            raise ValueError("pH high emergency must be above pH high watch")
        if (
            self.ph_recover_low is not None
            and self.ph_recover_high is not None
            and self.ph_recover_low >= self.ph_recover_high
        ):
            raise ValueError("pH recovery low must be below recovery high")
        if self.automatic_water_exchange_enabled:
            if self.exchange_fraction_pct is None:
                raise ValueError(
                    "exchange_fraction_pct required when automatic recovery is enabled"
                )
            if not 0 < self.exchange_fraction_pct <= 30.0:
                raise ValueError("exchange_fraction_pct must be >0 and <=30")
        if self.max_recovery_attempts <= 0:
            raise ValueError("max_recovery_attempts must be positive")
        if self.recovery_cooldown_seconds < 0:
            raise ValueError("recovery_cooldown_seconds cannot be negative")
        if self.provenance == EngineeringProvenance.UNAVAILABLE:
            raise ValueError(
                "configured threshold profile cannot use UNAVAILABLE provenance"
            )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.value
        payload["nh3_concentration_basis"] = "MOLECULAR_NH3_MG_L"
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WaterQualityThresholdProfile:
        def opt(name: str) -> float | None:
            value = data.get(name)
            return float(value) if value is not None else None

        return cls(
            profile_id=str(data["profile_id"]),
            revision=str(data["revision"]),
            source_reference=str(data["source_reference"]),
            tan_watch_above=opt("tan_watch_above"),
            tan_emergency_above=opt("tan_emergency_above"),
            tan_recover_below=opt("tan_recover_below"),
            nh3_watch_above=opt("nh3_watch_above"),
            nh3_emergency_above=opt("nh3_emergency_above"),
            nh3_recover_below=opt("nh3_recover_below"),
            nitrite_watch_above=opt("nitrite_watch_above"),
            nitrite_emergency_above=opt("nitrite_emergency_above"),
            nitrite_recover_below=opt("nitrite_recover_below"),
            nitrate_watch_above=opt("nitrate_watch_above"),
            nitrate_recover_below=opt("nitrate_recover_below"),
            ph_watch_below=opt("ph_watch_below"),
            ph_watch_above=opt("ph_watch_above"),
            ph_emergency_below=opt("ph_emergency_below"),
            ph_emergency_above=opt("ph_emergency_above"),
            ph_recover_low=opt("ph_recover_low"),
            ph_recover_high=opt("ph_recover_high"),
            automatic_water_exchange_enabled=bool(
                data.get("automatic_water_exchange_enabled", False)
            ),
            exchange_fraction_pct=opt("exchange_fraction_pct"),
            max_recovery_attempts=int(data.get("max_recovery_attempts", 1)),
            recovery_cooldown_seconds=float(
                data.get("recovery_cooldown_seconds", 1800.0)
            ),
            provenance=EngineeringProvenance.normalize(
                data.get("provenance", EngineeringProvenance.USER_CONFIGURED)
            ),
        )


@dataclass(slots=True, frozen=True)
class KoiFreshwaterHealthReference:
    """Source-backed koi/common-carp freshwater reference, not site commissioning.

    This registry exposes health-oriented reference values without silently making
    them production setpoints. A commissioned pond may intentionally use a narrower
    operating band, but shall not weaken the biological-safety envelope without
    governed evidence.
    """

    reference_id: str = "KOI_FRESHWATER_HEALTH_REFERENCE_V1"
    dissolved_oxygen_preferred_min_mg_l: float = 6.0
    dissolved_oxygen_preferred_max_mg_l: float = 8.0
    dissolved_oxygen_warning_below_mg_l: float = 5.0
    dissolved_oxygen_emergency_at_or_below_mg_l: float = 4.0
    common_carp_growth_temperature_min_c: float = 23.0
    common_carp_growth_temperature_max_c: float = 30.0
    ph_min: float = 6.5
    ph_max: float = 9.0
    tan_target_mg_n_l: float = 0.0
    tan_general_freshwater_upper_tolerance_mg_n_l: float = 1.0
    unionized_nh3_target_mg_l: float = 0.0
    unionized_nh3_watch_mg_l: float = 0.02
    unionized_nh3_max_admissible_cyprinid_mg_l: float = 0.05
    nitrite_target_mg_l: float = 0.0
    nitrite_watch_mg_l: float = 0.1
    nitrate_upper_reference_mg_l: float = 20.0
    alkalinity_min_mg_l_as_caco3: float = 100.0
    hardness_min_mg_l_as_caco3: float = 20.0
    total_chlorine_target_mg_l: float = 0.0
    free_chlorine_target_mg_l: float = 0.0
    provenance: EngineeringProvenance = EngineeringProvenance.EXPERT_REFERENCE_PROFILE

    @property
    def source_reference(self) -> str:
        return (
            "SMART_KOI_POND Handbook V0.17; Merck Veterinary Manual freshwater "
            "water-quality reference ranges; FAO Cyprinus carpio cultured-species "
            "profile; FAO fish-health unionized-ammonia guidance; US EPA 2013 "
            "freshwater ammonia speciation"
        )

    def threshold_profile(self) -> WaterQualityThresholdProfile:
        """Return an explicit reference profile; automatic recovery stays disabled.

        TAN's general freshwater tolerance boundary is used only as a secondary
        WATCH. Toxicity is primarily relationship-aware through molecular NH3 from
        validated TAN-N + pH + temperature. No unsourced emergency or recovery
        threshold is invented for nitrite, nitrate or pH.
        """
        return WaterQualityThresholdProfile(
            profile_id=self.reference_id,
            revision="1",
            source_reference=self.source_reference,
            tan_watch_above=self.tan_general_freshwater_upper_tolerance_mg_n_l,
            nh3_watch_above=self.unionized_nh3_watch_mg_l,
            nh3_emergency_above=self.unionized_nh3_max_admissible_cyprinid_mg_l,
            nitrite_watch_above=self.nitrite_watch_mg_l,
            nitrate_watch_above=self.nitrate_upper_reference_mg_l,
            ph_watch_below=self.ph_min,
            ph_watch_above=self.ph_max,
            automatic_water_exchange_enabled=False,
            provenance=self.provenance,
        )


def koi_freshwater_health_reference_v1() -> KoiFreshwaterHealthReference:
    """Return the governed, source-backed reference without auto-applying it."""
    return KoiFreshwaterHealthReference()
