from __future__ import annotations

from typing import Any

from smart_koi_pond.control.water_quality_config import WaterQualityThresholdProfile
from smart_koi_pond.dashboard.source_water_service import (
    SourceWaterQualifiedRuntimeApplicationService,
)
from smart_koi_pond.digital_twin.koi_stock import FeedingPolicy, KoiStockProfile
from smart_koi_pond.domain.enums import EventType


class KoiStockRuntimeApplicationService(SourceWaterQualifiedRuntimeApplicationService):
    """Application boundary for koi-stock/feeding/water-quality configuration.

    These are configuration operations only. They mutate the same canonical runtime
    through its governed configuration transaction boundary; they do not create a
    second calculation or control engine in the browser/application layer.
    """

    _ENGINEERING_ACTIONS = {
        "configure_koi_stock_profile",
        "configure_feeding_policy",
        "configure_water_quality_threshold_profile",
    }

    def _require_engineering(self, action: str, role: str) -> None:
        if role == "engineering":
            return
        self.runtime.events.append(
            self.runtime.clock.current,
            EventType.CONFIGURATION,
            "CONFIGURATION_COMMAND_REJECTED",
            {
                "action": action,
                "role": role,
                "reason": "ENGINEERING_ROLE_REQUIRED",
            },
        )
        raise PermissionError(f"role {role} is not authorized for {action}")

    def command(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        *,
        role: str = "viewer",
    ):
        if action not in self._ENGINEERING_ACTIONS:
            return super().command(action, payload, role=role)

        data = payload or {}
        with self._lock:
            self._require_engineering(action, role)
            if action == "configure_koi_stock_profile":
                profile = KoiStockProfile.from_dict(data["profile"])
                configure = getattr(self.runtime, "configure_koi_stock_profile", None)
                if configure is None:
                    raise RuntimeError(
                        "runtime does not support governed koi-stock configuration"
                    )
                configure(profile, actor=str(data.get("actor", role)))
            elif action == "configure_feeding_policy":
                policy = FeedingPolicy.from_dict(data["policy"])
                configure = getattr(self.runtime, "configure_feeding_policy", None)
                if configure is None:
                    raise RuntimeError(
                        "runtime does not support governed feeding-policy configuration"
                    )
                configure(policy, actor=str(data.get("actor", role)))
            elif action == "configure_water_quality_threshold_profile":
                profile = WaterQualityThresholdProfile.from_dict(data["profile"])
                configure = getattr(
                    self.runtime,
                    "configure_water_quality_threshold_profile",
                    None,
                )
                if configure is None:
                    raise RuntimeError(
                        "runtime does not support governed water-quality thresholds"
                    )
                configure(profile, actor=str(data.get("actor", role)))

            self._last_snapshot = self._tick_and_evaluate(0.0)
            return self._last_snapshot

    def publication(self, *, after_sequence: int = 0):
        publication = super().publication(after_sequence=after_sequence)
        publication["koi_stock_feeding_schema_version"] = 1
        publication["water_quality_recovery_schema_version"] = 1
        publication["automatic_chemical_dosing_authorized"] = False
        return publication
