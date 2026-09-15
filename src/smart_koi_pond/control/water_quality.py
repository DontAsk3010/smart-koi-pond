from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from math import log10
from typing import Any

from smart_koi_pond.control.ammonia import (
    UNIONIZED_AMMONIA_PARAMETER,
    calculate_unionized_ammonia_n,
)
from smart_koi_pond.domain.enums import OperatingMode


@dataclass(slots=True, frozen=True)
class WaterQualityRecoveryPolicy:
    """Bounded automatic water-exchange policy.

    Thresholds remain in SimulationControlPolicy. This policy only governs whether an
    already classified chemistry problem may use the existing governed WATER_CHANGE
    workflow and how retries/recovery verification are bounded. NH3 values are
    molecular un-ionized ammonia in mg/L, not NH3-N.
    """

    enabled: bool = False
    exchange_fraction_pct: float | None = None
    max_attempts: int = 1
    cooldown_seconds: float = 1800.0
    tan_recover_below: float | None = None
    nh3_recover_below: float | None = None
    nitrite_recover_below: float | None = None
    nitrate_recover_below: float | None = None
    ph_recover_low: float | None = None
    ph_recover_high: float | None = None

    def __post_init__(self) -> None:
        if self.enabled:
            if self.exchange_fraction_pct is None:
                raise ValueError(
                    "exchange_fraction_pct is required when recovery is enabled"
                )
            if not 0 < self.exchange_fraction_pct <= 30.0:
                raise ValueError("exchange_fraction_pct must be >0 and <=30")
        if self.max_attempts <= 0:
            raise ValueError("max_attempts must be positive")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative")
        if (
            self.ph_recover_low is not None
            and self.ph_recover_high is not None
            and self.ph_recover_low >= self.ph_recover_high
        ):
            raise ValueError("ph recovery low must be below high")


@dataclass(slots=True)
class WaterQualityRecoveryAttempt:
    parameter: str
    reason: str
    baseline: float
    started_at: datetime
    target_drain_level_pct: float
    target_refill_level_pct: float
    attempt_number: int
    workflow_seen_active: bool = False


class WaterQualityRecoveryManager:
    """Plans only safe, bounded use of the canonical WATER_CHANGE workflow."""

    _REASON_TO_PARAMETER = {
        "TAN_HIGH": "total_ammonia_nitrogen_mg_l",
        "TAN_EMERGENCY": "total_ammonia_nitrogen_mg_l",
        "NH3_HIGH": UNIONIZED_AMMONIA_PARAMETER,
        "NH3_EMERGENCY": UNIONIZED_AMMONIA_PARAMETER,
        "NITRITE_HIGH": "nitrite_mg_l",
        "NITRITE_EMERGENCY": "nitrite_mg_l",
        "NITRATE_HIGH": "nitrate_mg_l",
        "PH_OUT_OF_TARGET": "ph",
        "PH_EMERGENCY": "ph",
    }

    def __init__(self, policy: WaterQualityRecoveryPolicy | None = None) -> None:
        self.policy = policy or WaterQualityRecoveryPolicy()
        self.active: WaterQualityRecoveryAttempt | None = None
        self.attempt_counts: dict[str, int] = {}
        self.last_finished_at: datetime | None = None
        self.lockout_reason: str | None = None
        self.last_outcome: str | None = None
        self.last_reason: str | None = None

    @staticmethod
    def feed_inhibit_reason(snapshot: Any) -> str | None:
        reasons = set(snapshot.classification.reasons)
        for reason in (
            "NH3_EMERGENCY",
            "NH3_HIGH",
            "TAN_EMERGENCY",
            "TAN_HIGH",
            "NITRITE_EMERGENCY",
            "NITRITE_HIGH",
            "NITRATE_HIGH",
            "PH_EMERGENCY",
            "PH_OUT_OF_TARGET",
        ):
            if reason in reasons:
                return reason
        return None

    def _active_reason(self, snapshot: Any) -> tuple[str, str, float] | None:
        reasons = set(snapshot.classification.reasons)
        for reason in (
            "NH3_EMERGENCY",
            "TAN_EMERGENCY",
            "NITRITE_EMERGENCY",
            "PH_EMERGENCY",
            "NH3_HIGH",
            "TAN_HIGH",
            "NITRITE_HIGH",
            "NITRATE_HIGH",
            "PH_OUT_OF_TARGET",
        ):
            if reason not in reasons:
                continue
            parameter = self._REASON_TO_PARAMETER[reason]
            value = snapshot.estimate.values.get(parameter)
            if value is not None:
                return reason, parameter, float(value)
        return None

    def _projected_unionized_ammonia_after_exchange(
        self,
        *,
        snapshot: Any,
        source_water: dict[str, Any],
    ) -> float | None:
        """Project post-exchange molecular NH3 using the governed mixing basis.

        The recovery manager must not approve an NH3 water exchange merely because
        the source's standalone NH3 is lower. The final pond NH3 is recalculated from
        projected TAN, pH, and temperature after the configured drain/refill fraction.
        pH uses the same simplified buffer-weighted hydrogen-activity basis as the
        canonical water-exchange model. Missing required evidence fails closed.
        """
        if self.policy.exchange_fraction_pct is None:
            return None
        values = snapshot.estimate.values
        required_pond = {
            "water_level_pct": values.get("water_level_pct"),
            "total_ammonia_nitrogen_mg_l": values.get(
                "total_ammonia_nitrogen_mg_l"
            ),
            "ph": values.get("ph"),
            "temperature_c": values.get("temperature_c"),
            "alkalinity_mg_l_as_caco3": values.get("alkalinity_mg_l_as_caco3"),
        }
        required_source = {
            "total_ammonia_nitrogen_mg_l": source_water.get(
                "total_ammonia_nitrogen_mg_l"
            ),
            "ph": source_water.get("ph"),
            "temperature_c": source_water.get("temperature_c"),
            "alkalinity_mg_l_as_caco3": source_water.get(
                "alkalinity_mg_l_as_caco3"
            ),
        }
        if any(value is None for value in required_pond.values()) or any(
            value is None for value in required_source.values()
        ):
            return None

        level = float(required_pond["water_level_pct"])
        if level <= 0:
            return None
        refill_pct = min(float(self.policy.exchange_fraction_pct), level)
        source_fraction = refill_pct / level
        remaining_fraction = 1.0 - source_fraction

        pond_tan = float(required_pond["total_ammonia_nitrogen_mg_l"])
        source_tan = float(required_source["total_ammonia_nitrogen_mg_l"])
        projected_tan = pond_tan * remaining_fraction + source_tan * source_fraction

        pond_temperature = float(required_pond["temperature_c"])
        source_temperature = float(required_source["temperature_c"])
        projected_temperature = (
            pond_temperature * remaining_fraction
            + source_temperature * source_fraction
        )

        pond_alkalinity = max(
            float(required_pond["alkalinity_mg_l_as_caco3"]),
            1e-9,
        )
        source_alkalinity = max(
            float(required_source["alkalinity_mg_l_as_caco3"]),
            1e-9,
        )
        pond_weight = remaining_fraction * pond_alkalinity
        source_weight = source_fraction * source_alkalinity
        denominator = pond_weight + source_weight
        if denominator <= 0:
            return None
        pond_ph = float(required_pond["ph"])
        source_ph = float(required_source["ph"])
        hydrogen_activity = (
            10 ** (-pond_ph) * pond_weight
            + 10 ** (-source_ph) * source_weight
        ) / denominator
        projected_ph = -log10(max(hydrogen_activity, 1e-14))
        projected_ph = min(14.0, max(0.0, projected_ph))

        return calculate_unionized_ammonia_n(
            tan_n_mg_l=projected_tan,
            ph=projected_ph,
            temperature_c=projected_temperature,
        ).unionized_ammonia_nh3_mg_l

    def _source_supports_safer_direction(
        self,
        *,
        snapshot: Any,
        parameter: str,
        pond_value: float,
        source_water: dict[str, Any],
    ) -> bool:
        if not source_water.get("pond_use_qualified"):
            return False
        if parameter == UNIONIZED_AMMONIA_PARAMETER:
            projected_nh3 = self._projected_unionized_ammonia_after_exchange(
                snapshot=snapshot,
                source_water=source_water,
            )
            return projected_nh3 is not None and projected_nh3 < pond_value
        source_value = source_water.get(parameter)
        if source_value is None:
            return False
        source = float(source_value)
        if parameter in {
            "total_ammonia_nitrogen_mg_l",
            "nitrite_mg_l",
            "nitrate_mg_l",
        }:
            return source < pond_value
        if parameter == "ph":
            low = self.policy.ph_recover_low
            high = self.policy.ph_recover_high
            if low is None or high is None:
                return False
            center = (low + high) / 2.0
            return abs(source - center) < abs(pond_value - center)
        return False

    def _recovered(self, parameter: str, value: float) -> bool:
        if parameter == "total_ammonia_nitrogen_mg_l":
            return (
                self.policy.tan_recover_below is not None
                and value < self.policy.tan_recover_below
            )
        if parameter == UNIONIZED_AMMONIA_PARAMETER:
            return (
                self.policy.nh3_recover_below is not None
                and value < self.policy.nh3_recover_below
            )
        if parameter == "nitrite_mg_l":
            return (
                self.policy.nitrite_recover_below is not None
                and value < self.policy.nitrite_recover_below
            )
        if parameter == "nitrate_mg_l":
            return (
                self.policy.nitrate_recover_below is not None
                and value < self.policy.nitrate_recover_below
            )
        if parameter == "ph":
            return (
                self.policy.ph_recover_low is not None
                and self.policy.ph_recover_high is not None
                and self.policy.ph_recover_low < value < self.policy.ph_recover_high
            )
        return False

    def observe(self, snapshot: Any, source_water: dict[str, Any]) -> dict[str, Any] | None:
        now = snapshot.timestamp
        if self.active is not None:
            if snapshot.operating_mode == OperatingMode.WATER_CHANGE:
                self.active.workflow_seen_active = True
                return None
            if (
                self.active.workflow_seen_active
                and snapshot.operating_mode == OperatingMode.NORMAL_AUTO
            ):
                value = snapshot.estimate.values.get(self.active.parameter)
                if value is None:
                    self.last_outcome = "INSUFFICIENT_EVIDENCE"
                    self.lockout_reason = "RECOVERY_VERIFICATION_EVIDENCE_MISSING"
                elif self._recovered(self.active.parameter, float(value)):
                    self.last_outcome = "VERIFIED_SUCCESS"
                    self.lockout_reason = None
                    self.attempt_counts[self.active.parameter] = 0
                elif float(value) < self.active.baseline:
                    self.last_outcome = "IMPROVED_NOT_RECOVERED"
                else:
                    self.last_outcome = "FAILED_RESPONSE"
                self.last_reason = self.active.reason
                self.last_finished_at = now
                self.active = None
            return None

        if not self.policy.enabled or self.lockout_reason is not None:
            return None
        if snapshot.operating_mode != OperatingMode.NORMAL_AUTO:
            return None
        if (
            self.last_finished_at is not None
            and now
            < self.last_finished_at
            + timedelta(seconds=self.policy.cooldown_seconds)
        ):
            return None
        abnormal = self._active_reason(snapshot)
        if abnormal is None:
            return None
        reason, parameter, value = abnormal
        count = self.attempt_counts.get(parameter, 0)
        if count >= self.policy.max_attempts:
            self.lockout_reason = f"MAX_ATTEMPTS_EXHAUSTED:{parameter}"
            self.last_outcome = "LOCKED_OUT"
            self.last_reason = reason
            return None
        if not self._source_supports_safer_direction(
            snapshot=snapshot,
            parameter=parameter,
            pond_value=value,
            source_water=source_water,
        ):
            self.last_outcome = "NO_SAFE_AUTOMATIC_WATER_EXCHANGE_PATH"
            self.last_reason = reason
            return None
        level = snapshot.estimate.values.get("water_level_pct")
        if level is None or self.policy.exchange_fraction_pct is None:
            self.last_outcome = "WATER_LEVEL_EVIDENCE_REQUIRED"
            self.last_reason = reason
            return None
        target_refill = float(level)
        target_drain = max(0.0, target_refill - self.policy.exchange_fraction_pct)
        if target_drain >= target_refill:
            return None
        count += 1
        self.attempt_counts[parameter] = count
        self.active = WaterQualityRecoveryAttempt(
            parameter=parameter,
            reason=reason,
            baseline=value,
            started_at=now,
            target_drain_level_pct=target_drain,
            target_refill_level_pct=target_refill,
            attempt_number=count,
        )
        self.last_outcome = "REQUESTED"
        self.last_reason = reason
        return {
            "reason": f"WATER_QUALITY_RECOVERY:{reason}",
            "parameter": parameter,
            "baseline": value,
            "target_drain_level_pct": target_drain,
            "target_refill_level_pct": target_refill,
            "attempt_number": count,
        }

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "policy": asdict(self.policy),
            "enabled": self.policy.enabled,
            "active": (
                {
                    "parameter": self.active.parameter,
                    "reason": self.active.reason,
                    "baseline": self.active.baseline,
                    "started_at": self.active.started_at.isoformat(),
                    "target_drain_level_pct": self.active.target_drain_level_pct,
                    "target_refill_level_pct": self.active.target_refill_level_pct,
                    "attempt_number": self.active.attempt_number,
                    "workflow_seen_active": self.active.workflow_seen_active,
                }
                if self.active is not None
                else None
            ),
            "attempt_counts": dict(self.attempt_counts),
            "last_finished_at": (
                self.last_finished_at.isoformat()
                if self.last_finished_at is not None
                else None
            ),
            "last_outcome": self.last_outcome,
            "last_reason": self.last_reason,
            "lockout_reason": self.lockout_reason,
            "nh3_concentration_basis": "MOLECULAR_NH3_MG_L",
            "automatic_chemical_dosing_authorized": False,
        }
