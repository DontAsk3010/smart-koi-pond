from __future__ import annotations

from datetime import datetime
from typing import Any

from smart_koi_pond.control.water_quality import (
    WaterQualityRecoveryAttempt,
    WaterQualityRecoveryManager,
    WaterQualityRecoveryPolicy,
)
from smart_koi_pond.digital_twin.koi_stock import FeedingPolicy, KoiStockProfile
from smart_koi_pond.digital_twin.source_water_runtime import (
    SourceWaterQualifiedProductionRuntime,
)
from smart_koi_pond.domain.enums import EventType


class WaterQualityRegulatingProductionRuntime(SourceWaterQualifiedProductionRuntime):
    """Canonical production runtime with bounded non-chemical water-quality recovery.

    It reuses the accepted command, arbitration, operating-mode, water-change,
    source-water qualification, verification, historian and adapter paths. No second
    controller or direct actuator output path is introduced.
    """

    def __init__(
        self,
        *args: Any,
        water_quality_recovery_policy: WaterQualityRecoveryPolicy | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.water_quality_recovery = WaterQualityRecoveryManager(
            water_quality_recovery_policy
        )

    def configure_koi_stock_profile(
        self,
        profile: KoiStockProfile,
        *,
        actor: str = "engineering",
    ) -> None:
        configure = getattr(self.model, "configure_koi_stock_profile", None)
        if configure is None:
            raise RuntimeError("runtime model does not support koi-stock configuration")
        before_fn = getattr(self.model, "koi_stock_snapshot", None)
        before = before_fn() if before_fn is not None else {"configured": False}
        self._apply_governed_configuration(
            scope="KOI_STOCK_PROFILE",
            actor=actor,
            reason="KOI_STOCK_PROFILE_CHANGE",
            before=before,
            after=profile.to_dict(),
            preflight=lambda: (),
            apply=lambda: configure(profile),
        )
        after = self.model.koi_stock_snapshot()
        self.events.append(
            self.clock.current,
            EventType.CONFIGURATION,
            "KOI_STOCK_BIOMASS_RECALCULATED",
            {
                "actor": actor,
                "profile_id": profile.profile_id,
                "revision": profile.revision,
                "total_count": after.get("total_count"),
                "biomass_kg": after.get("biomass_kg"),
                "status": after.get("status"),
                "unresolved_groups": after.get("unresolved_groups", []),
                "estimator_extrapolation_allowed": False,
            },
        )

    def configure_feeding_policy(
        self,
        policy: FeedingPolicy,
        *,
        actor: str = "engineering",
    ) -> None:
        configure = getattr(self.model, "configure_feeding_policy", None)
        if configure is None:
            raise RuntimeError("runtime model does not support feeding-policy configuration")
        before_fn = getattr(self.model, "feeding_plan_snapshot", None)
        before = before_fn() if before_fn is not None else {"configured": False}
        self._apply_governed_configuration(
            scope="FEEDING_POLICY",
            actor=actor,
            reason="FEEDING_POLICY_CHANGE",
            before=before,
            after=policy.to_dict(),
            preflight=lambda: (),
            apply=lambda: configure(policy),
        )
        after = self.model.feeding_plan_snapshot()
        self.events.append(
            self.clock.current,
            EventType.CONFIGURATION,
            "FEEDING_PLAN_RECALCULATED",
            {
                "actor": actor,
                "policy_id": policy.policy_id,
                "revision": policy.revision,
                "status": after.get("status"),
                "planned_feed_kg_per_day": after.get("planned_feed_kg_per_day"),
                "planned_feed_per_meal_g": after.get("planned_feed_per_meal_g"),
                "meals_per_day": after.get("meals_per_day"),
                "verified_mass_dispense_claimed": False,
            },
        )

    def _source_water_snapshot_for_recovery(self) -> dict[str, Any]:
        snapshot = getattr(self.model, "source_water_snapshot", None)
        if snapshot is None:
            return {
                "configured": False,
                "pond_use_qualified": False,
            }
        return dict(snapshot())

    def _apply_feed_inhibit_for_next_step(self, snapshot: Any) -> None:
        setter = getattr(self.model, "set_water_quality_feed_inhibited", None)
        if setter is None:
            return
        reason = self.water_quality_recovery.feed_inhibit_reason(snapshot)
        setter(reason is not None, reason)

    def _process_water_quality_recovery(self, snapshot: Any) -> bool:
        before = self.water_quality_recovery.status()
        request = self.water_quality_recovery.observe(
            snapshot,
            self._source_water_snapshot_for_recovery(),
        )
        if request is not None:
            self.events.append(
                snapshot.timestamp,
                EventType.RECOVERY,
                "WATER_QUALITY_RECOVERY_REQUESTED",
                {
                    **request,
                    "automatic_chemical_dosing_authorized": False,
                    "uses_existing_water_change_workflow": True,
                },
            )
            try:
                self.start_water_change(
                    request["reason"],
                    target_drain_level_pct=request["target_drain_level_pct"],
                    target_refill_level_pct=request["target_refill_level_pct"],
                )
            except Exception as exc:
                active = self.water_quality_recovery.active
                if active is not None:
                    self.water_quality_recovery.last_outcome = "REQUEST_REJECTED"
                    self.water_quality_recovery.last_reason = active.reason
                    self.water_quality_recovery.last_finished_at = snapshot.timestamp
                    self.water_quality_recovery.active = None
                self.events.append(
                    snapshot.timestamp,
                    EventType.RECOVERY,
                    "WATER_QUALITY_RECOVERY_REQUEST_REJECTED",
                    {
                        "reason": request["reason"],
                        "error": str(exc),
                        "automatic_chemical_dosing_authorized": False,
                    },
                )
        after = self.water_quality_recovery.status()
        return before != after

    def tick(self, seconds: float):
        snapshot = super().tick(seconds)
        self._apply_feed_inhibit_for_next_step(snapshot)
        recovery_changed = self._process_water_quality_recovery(snapshot)
        snapshot.biology = self.model.biological_snapshot()
        snapshot.water_recovery = dict(snapshot.water_recovery)
        snapshot.water_recovery["water_quality"] = self.water_quality_recovery.status()
        if recovery_changed:
            latest_event = self.events.events[-1].sequence if self.events.events else 0
            self.historian.append(
                run_id=self.run_id,
                event_sequence=latest_event,
                snapshot=snapshot,
            )
        return snapshot

    def capture_checkpoint(self):
        checkpoint = super().capture_checkpoint()
        checkpoint["water_quality_recovery_state"] = self.water_quality_recovery.status()
        return checkpoint

    def restore_checkpoint(self, checkpoint) -> None:
        super().restore_checkpoint(checkpoint)
        saved = checkpoint.get("water_quality_recovery_state")
        if not saved:
            return
        manager = self.water_quality_recovery
        manager.attempt_counts = {
            str(key): int(value)
            for key, value in saved.get("attempt_counts", {}).items()
        }
        manager.last_outcome = saved.get("last_outcome")
        manager.last_reason = saved.get("last_reason")
        manager.lockout_reason = saved.get("lockout_reason")
        last_finished = saved.get("last_finished_at")
        manager.last_finished_at = (
            datetime.fromisoformat(str(last_finished)) if last_finished else None
        )
        active = saved.get("active")
        if active:
            manager.active = WaterQualityRecoveryAttempt(
                parameter=str(active["parameter"]),
                reason=str(active["reason"]),
                baseline=float(active["baseline"]),
                started_at=datetime.fromisoformat(str(active["started_at"])),
                target_drain_level_pct=float(active["target_drain_level_pct"]),
                target_refill_level_pct=float(active["target_refill_level_pct"]),
                attempt_number=int(active["attempt_number"]),
                workflow_seen_active=bool(active.get("workflow_seen_active", False)),
            )
        else:
            manager.active = None

    def publish(self, snapshot, *, after_sequence: int = 0):
        snapshot.biology = self.model.biological_snapshot()
        snapshot.water_recovery = dict(snapshot.water_recovery)
        snapshot.water_recovery["water_quality"] = self.water_quality_recovery.status()
        publication = super().publish(snapshot, after_sequence=after_sequence)
        publication["water_quality_recovery_schema_version"] = 1
        publication["koi_stock_feeding_schema_version"] = 1
        publication["automatic_chemical_dosing_authorized"] = False
        return publication
