from __future__ import annotations

from typing import Any

from smart_koi_pond.digital_twin.owner_integrated_runtime import (
    OwnerIntegratedProductionRuntime,
)


class OwnerIntegratedReportingProductionRuntime(OwnerIntegratedProductionRuntime):
    """Add one canonical owner-facing journey record across backwash and refill."""

    def start_integrated_backwash_restore(self, reason: str) -> None:
        filtration = getattr(self.model, "filtration", None)
        cumulative_before = (
            float(filtration.cumulative_backwash_discharge_l)
            if filtration is not None
            else None
        )
        super().start_integrated_backwash_restore(reason)
        if self._owner_backwash_active is not None:
            self._owner_backwash_active["cumulative_backwash_discharge_l_before"] = (
                cumulative_before
            )

    def _finish_owner_backwash(
        self,
        snapshot: Any,
        outcome: str,
        detail: str,
    ) -> None:
        session = self._owner_backwash_active or {}
        before = session.get("cumulative_backwash_discharge_l_before")
        filtration = getattr(self.model, "filtration", None)
        cumulative_after = (
            float(filtration.cumulative_backwash_discharge_l)
            if filtration is not None
            else None
        )
        backwash_discharge_l = None
        if before is not None and cumulative_after is not None:
            backwash_discharge_l = max(0.0, cumulative_after - float(before))

        super()._finish_owner_backwash(snapshot, outcome, detail)
        if self._owner_backwash_last is None:
            return

        last_exchange = self._owner_backwash_last.get("last_exchange") or {}
        refill_l = last_exchange.get("refill_l")
        starting = self._owner_backwash_last.get("starting_chemistry") or {}
        final = self._owner_backwash_last.get("final_chemistry") or {}
        changed = {
            parameter: {
                "before": starting.get(parameter),
                "after": final.get(parameter),
            }
            for parameter in (
                "ph",
                "temperature_c",
                "dissolved_oxygen_mg_l",
                "total_ammonia_nitrogen_mg_l",
                "nitrite_mg_l",
                "nitrate_mg_l",
                "alkalinity_mg_l_as_caco3",
            )
        }
        self._owner_backwash_last["integrated_water_journey"] = {
            "backwash_discharge_l": backwash_discharge_l,
            "refill_l": refill_l,
            "source_water_mixing_applied": bool(refill_l and float(refill_l) > 0.0),
            "chemistry_before_after": changed,
            "single_owner_journey": True,
        }
