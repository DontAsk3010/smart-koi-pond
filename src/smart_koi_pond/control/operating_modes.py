from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from smart_koi_pond.actuators.virtual import VirtualActuatorBank
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    CommandOwner,
    DataQuality,
    EventType,
    OperatingMode,
    WorkflowPhase,
)
from smart_koi_pond.domain.models import (
    CapabilitySummary,
    CommandIntent,
    OperatingStatus,
    ValidatedMeasurement,
)
from smart_koi_pond.events.log import EventLog
from smart_koi_pond.sensors.virtual import VirtualSensorSuite

_CAPABILITY_AVAILABLE = {
    AvailabilityState.AVAILABLE,
    AvailabilityState.STANDBY,
    AvailabilityState.MANUAL,
}


@dataclass(slots=True, frozen=True)
class _AssetRestoreState:
    owner: CommandOwner
    availability: AvailabilityState


@dataclass(slots=True)
class _OperatingSession:
    origin_mode: OperatingMode
    phase: WorkflowPhase
    reason: str
    scope: tuple[str, ...]
    started_at: datetime
    asset_restore: dict[str, _AssetRestoreState] = field(default_factory=dict)
    sensor_restore: dict[str, AvailabilityState | None] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class OperatingModeManager:
    """Governed operating-mode ownership and transition coordinator."""

    def __init__(
        self,
        actuators: VirtualActuatorBank,
        sensors: VirtualSensorSuite,
        events: EventLog,
    ) -> None:
        self.actuators = actuators
        self.sensors = sensors
        self.events = events
        self.mode = OperatingMode.NORMAL_AUTO
        self.phase = WorkflowPhase.IDLE
        self._session: _OperatingSession | None = None

    @property
    def status(self) -> OperatingStatus:
        session = self._session
        return OperatingStatus(
            mode=self.mode,
            phase=self.phase,
            reason=session.reason if session else None,
            scope=session.scope if session else (),
        )

    def _ensure_idle(self) -> None:
        if self.mode != OperatingMode.NORMAL_AUTO or self._session is not None:
            raise RuntimeError(f"operating mode already active: {self.mode}")

    def _validate_assets(self, asset_ids: Iterable[str]) -> tuple[str, ...]:
        scope = tuple(dict.fromkeys(asset_ids))
        unknown = [asset_id for asset_id in scope if asset_id not in self.actuators.assets]
        if unknown:
            raise KeyError(f"unknown asset(s): {', '.join(unknown)}")
        return scope

    def _validate_sensors(self, sensor_ids: Iterable[str]) -> tuple[str, ...]:
        scope = tuple(dict.fromkeys(sensor_ids))
        unknown = [sensor_id for sensor_id in scope if sensor_id not in self.sensors.PARAMETER_MAP]
        if unknown:
            raise KeyError(f"unknown sensor(s): {', '.join(unknown)}")
        return scope

    def _remember_assets(self, asset_ids: Iterable[str]) -> dict[str, _AssetRestoreState]:
        return {
            asset_id: _AssetRestoreState(
                owner=self.actuators.assets[asset_id].owner,
                availability=self.actuators.assets[asset_id].availability,
            )
            for asset_id in asset_ids
        }

    def _remember_sensors(
        self, sensor_ids: Iterable[str]
    ) -> dict[str, AvailabilityState | None]:
        return {
            sensor_id: self.sensors.availability_override(sensor_id)
            for sensor_id in sensor_ids
        }

    def _start(
        self,
        mode: OperatingMode,
        phase: WorkflowPhase,
        reason: str,
        now: datetime,
        *,
        scope: tuple[str, ...] = (),
        asset_restore: dict[str, _AssetRestoreState] | None = None,
        sensor_restore: dict[str, AvailabilityState | None] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.mode = mode
        self.phase = phase
        self._session = _OperatingSession(
            origin_mode=mode,
            phase=phase,
            reason=reason,
            scope=scope,
            started_at=now,
            asset_restore=asset_restore or {},
            sensor_restore=sensor_restore or {},
            metadata=metadata or {},
        )
        self.events.append(
            now,
            EventType.MODE,
            "OPERATING_MODE_ENTERED",
            {
                "mode": mode,
                "phase": phase,
                "reason": reason,
                "scope": scope,
            },
        )

    def _set_phase(self, phase: WorkflowPhase, now: datetime, code: str) -> None:
        self.phase = phase
        if self._session is not None:
            self._session.phase = phase
        self.events.append(
            now,
            EventType.MODE,
            code,
            {"mode": self.mode, "phase": phase},
        )

    def start_manual_maintenance(
        self,
        scope: Iterable[str],
        reason: str,
        now: datetime,
        *,
        service_locked: Iterable[str] = (),
    ) -> None:
        self._ensure_idle()
        scope_tuple = self._validate_assets(scope)
        locked = self._validate_assets(service_locked)
        if not set(locked).issubset(scope_tuple):
            raise ValueError("service_locked assets must be inside maintenance scope")
        restore = self._remember_assets(scope_tuple)
        for asset_id in scope_tuple:
            self.actuators.set_owner(asset_id, CommandOwner.MAINTENANCE)
        for asset_id in locked:
            self.actuators.set_availability(
                asset_id, AvailabilityState.MAINTENANCE_UNAVAILABLE
            )
        self._start(
            OperatingMode.MANUAL_MAINTENANCE,
            WorkflowPhase.ACTIVE,
            reason,
            now,
            scope=scope_tuple,
            asset_restore=restore,
            metadata={"service_locked": locked},
        )

    def start_sensor_calibration(
        self,
        sensor_ids: Iterable[str],
        reason: str,
        now: datetime,
    ) -> None:
        self._ensure_idle()
        scope = self._validate_sensors(sensor_ids)
        restore = self._remember_sensors(scope)
        for sensor_id in scope:
            self.sensors.set_availability(sensor_id, AvailabilityState.CALIBRATION)
        self._start(
            OperatingMode.SENSOR_CALIBRATION,
            WorkflowPhase.CALIBRATING,
            reason,
            now,
            scope=scope,
            sensor_restore=restore,
        )

    def start_partial_shutdown(
        self,
        asset_ids: Iterable[str],
        reason: str,
        now: datetime,
    ) -> None:
        self._ensure_idle()
        scope = self._validate_assets(asset_ids)
        restore = self._remember_assets(scope)
        for asset_id in scope:
            self.actuators.set_owner(asset_id, CommandOwner.SHUTDOWN)
            self.actuators.set_availability(asset_id, AvailabilityState.PLANNED_OFF)
        self._start(
            OperatingMode.PARTIAL_SHUTDOWN,
            WorkflowPhase.SHUTDOWN,
            reason,
            now,
            scope=scope,
            asset_restore=restore,
        )

    def start_safe_total_shutdown(
        self,
        reason: str,
        now: datetime,
        *,
        fish_present: bool = True,
    ) -> None:
        self._ensure_idle()
        scope = tuple(self.actuators.assets)
        restore = self._remember_assets(scope)
        minimum_safe = {"main_pump", "primary_aerator"} if fish_present else set()
        for asset_id in scope:
            self.actuators.set_owner(asset_id, CommandOwner.SHUTDOWN)
            if asset_id in minimum_safe:
                self.actuators.set_availability(asset_id, AvailabilityState.AVAILABLE)
            else:
                self.actuators.set_availability(asset_id, AvailabilityState.PLANNED_OFF)
        self._start(
            OperatingMode.SAFE_TOTAL_SHUTDOWN,
            WorkflowPhase.SHUTDOWN,
            reason,
            now,
            scope=scope,
            asset_restore=restore,
            metadata={
                "fish_present": fish_present,
                "minimum_safe_assets": tuple(sorted(minimum_safe)),
            },
        )

    def start_water_change(
        self,
        reason: str,
        now: datetime,
        *,
        target_drain_level_pct: float,
        target_refill_level_pct: float,
    ) -> None:
        self._ensure_idle()
        if not 0.0 <= target_drain_level_pct < target_refill_level_pct <= 100.0:
            raise ValueError("water-change targets must satisfy 0 <= drain < refill <= 100")
        scope = self._validate_assets(("drain_valve", "top_up_valve", "feeder"))
        restore = self._remember_assets(scope)
        self.actuators.set_owner("drain_valve", CommandOwner.WORKFLOW)
        self.actuators.set_owner("top_up_valve", CommandOwner.WORKFLOW)
        self.actuators.set_owner("feeder", CommandOwner.SHUTDOWN)
        self._start(
            OperatingMode.WATER_CHANGE,
            WorkflowPhase.DRAINING,
            reason,
            now,
            scope=scope,
            asset_restore=restore,
            metadata={
                "target_drain_level_pct": target_drain_level_pct,
                "target_refill_level_pct": target_refill_level_pct,
            },
        )

    def start_filter_clean(
        self,
        service_scope: Iterable[str],
        reason: str,
        now: datetime,
    ) -> None:
        self._ensure_idle()
        service_assets = self._validate_assets(service_scope)
        scope = tuple(dict.fromkeys((*service_assets, "backwash_valve")))
        restore = self._remember_assets(scope)
        for asset_id in service_assets:
            self.actuators.set_owner(asset_id, CommandOwner.MAINTENANCE)
            self.actuators.set_availability(
                asset_id, AvailabilityState.MAINTENANCE_UNAVAILABLE
            )
        self.actuators.set_owner("backwash_valve", CommandOwner.WORKFLOW)
        self._start(
            OperatingMode.FILTER_CLEAN,
            WorkflowPhase.BACKWASHING,
            reason,
            now,
            scope=scope,
            asset_restore=restore,
            metadata={"service_scope": service_assets},
        )

    def start_blackout(self, reason: str, now: datetime) -> None:
        self._ensure_idle()
        scope = tuple(self.actuators.assets)
        restore = self._remember_assets(scope)
        for asset_id in scope:
            self.actuators.set_owner(asset_id, CommandOwner.SHUTDOWN)
            self.actuators.set_availability(asset_id, AvailabilityState.UNAVAILABLE)
        self._start(
            OperatingMode.BLACKOUT_RECOVERY,
            WorkflowPhase.BLACKOUT,
            reason,
            now,
            scope=scope,
            asset_restore=restore,
            metadata={"power_restored": False, "requires_life_support_restart": True},
        )

    def restore_power(self, now: datetime) -> None:
        session = self._session
        if (
            session is None
            or session.origin_mode != OperatingMode.BLACKOUT_RECOVERY
            or self.phase != WorkflowPhase.BLACKOUT
        ):
            raise RuntimeError("no blackout is awaiting power restoration")
        for asset_id, prior in session.asset_restore.items():
            self.actuators.set_availability(asset_id, prior.availability)
            self.actuators.set_owner(asset_id, CommandOwner.SHUTDOWN)
        session.metadata["power_restored"] = True
        self.mode = OperatingMode.RECOVERY_SYNC
        self._set_phase(WorkflowPhase.RECOVERY_SYNC, now, "BLACKOUT_POWER_RESTORED")

    def request_return_to_auto(self, now: datetime) -> None:
        session = self._session
        if session is None:
            return
        if self.phase == WorkflowPhase.BLACKOUT:
            raise RuntimeError("restore power before recovery sync")
        for sensor_id, availability in session.sensor_restore.items():
            self.sensors.set_availability(sensor_id, availability)
        for asset_id, prior in session.asset_restore.items():
            self.actuators.set_availability(asset_id, prior.availability)
        self.mode = OperatingMode.RECOVERY_SYNC
        self._set_phase(WorkflowPhase.RECOVERY_SYNC, now, "RECOVERY_SYNC_REQUESTED")

    def _recovery_inputs_good(
        self, validated: dict[str, ValidatedMeasurement]
    ) -> bool:
        required = ("do", "water_level", "flow")
        return all(
            sensor_id in validated
            and validated[sensor_id].quality == DataQuality.GOOD
            for sensor_id in required
        )

    def _blackout_restart_verified(self) -> bool:
        session = self._session
        if session is None:
            return False
        if not session.metadata.get("requires_life_support_restart", False):
            return True
        return (
            self.actuators.assets["main_pump"].feedback_on
            and self.actuators.assets["primary_aerator"].feedback_on
        )

    def _complete_recovery(self, now: datetime) -> None:
        session = self._session
        if session is None:
            return
        for asset_id, prior in session.asset_restore.items():
            self.actuators.set_owner(asset_id, prior.owner)
            self.actuators.set_availability(asset_id, prior.availability)
        for sensor_id, availability in session.sensor_restore.items():
            self.sensors.set_availability(sensor_id, availability)
        origin = session.origin_mode
        self.events.append(
            now,
            EventType.MODE,
            "RETURN_TO_AUTO_COMPLETE",
            {"origin_mode": origin},
        )
        self.mode = OperatingMode.NORMAL_AUTO
        self.phase = WorkflowPhase.IDLE
        self._session = None

    def advance_phase(
        self,
        now: datetime,
        validated: dict[str, ValidatedMeasurement],
    ) -> None:
        session = self._session
        if session is None:
            return

        if session.origin_mode == OperatingMode.WATER_CHANGE:
            level = validated.get("water_level")
            if level and level.value is not None:
                if (
                    self.phase == WorkflowPhase.DRAINING
                    and level.value <= session.metadata["target_drain_level_pct"]
                ):
                    self._set_phase(
                        WorkflowPhase.REFILLING,
                        now,
                        "WATER_CHANGE_DRAIN_TARGET_REACHED",
                    )
                elif (
                    self.phase == WorkflowPhase.REFILLING
                    and level.value >= session.metadata["target_refill_level_pct"]
                ):
                    self._set_phase(
                        WorkflowPhase.VERIFYING,
                        now,
                        "WATER_CHANGE_REFILL_TARGET_REACHED",
                    )
                    self.request_return_to_auto(now)

    def complete_recovery_if_ready(
        self,
        now: datetime,
        validated: dict[str, ValidatedMeasurement],
    ) -> bool:
        if self.phase != WorkflowPhase.RECOVERY_SYNC or self._session is None:
            return False
        if not self._recovery_inputs_good(validated):
            return False
        if not self._blackout_restart_verified():
            return False
        self._complete_recovery(now)
        return True

    def command_intents(self) -> list[CommandIntent]:
        session = self._session
        if session is None:
            return []

        if session.origin_mode == OperatingMode.WATER_CHANGE:
            if self.phase == WorkflowPhase.DRAINING:
                return [
                    CommandIntent(
                        "drain_valve",
                        True,
                        CommandOwner.WORKFLOW,
                        "WATER_CHANGE_DRAIN",
                    ),
                    CommandIntent(
                        "top_up_valve",
                        False,
                        CommandOwner.WORKFLOW,
                        "WATER_CHANGE_DRAIN_INHIBIT_REFILL",
                    ),
                    CommandIntent(
                        "feeder",
                        False,
                        CommandOwner.SHUTDOWN,
                        "WATER_CHANGE_FEED_INHIBIT",
                    ),
                ]
            if self.phase == WorkflowPhase.REFILLING:
                return [
                    CommandIntent(
                        "drain_valve",
                        False,
                        CommandOwner.WORKFLOW,
                        "WATER_CHANGE_CLOSE_DRAIN",
                    ),
                    CommandIntent(
                        "top_up_valve",
                        True,
                        CommandOwner.WORKFLOW,
                        "WATER_CHANGE_REFILL",
                    ),
                    CommandIntent(
                        "feeder",
                        False,
                        CommandOwner.SHUTDOWN,
                        "WATER_CHANGE_FEED_INHIBIT",
                    ),
                ]
            if self.phase == WorkflowPhase.RECOVERY_SYNC:
                return [
                    CommandIntent(
                        "drain_valve",
                        False,
                        CommandOwner.WORKFLOW,
                        "WATER_CHANGE_RECOVERY_CLOSE_DRAIN",
                    ),
                    CommandIntent(
                        "top_up_valve",
                        False,
                        CommandOwner.WORKFLOW,
                        "WATER_CHANGE_RECOVERY_CLOSE_REFILL",
                    ),
                    CommandIntent(
                        "feeder",
                        False,
                        CommandOwner.SHUTDOWN,
                        "WATER_CHANGE_FEED_INHIBIT",
                    ),
                ]

        if session.origin_mode == OperatingMode.FILTER_CLEAN:
            if self.phase == WorkflowPhase.BACKWASHING:
                return [
                    CommandIntent(
                        "backwash_valve",
                        True,
                        CommandOwner.WORKFLOW,
                        "FILTER_BACKWASH_ACTIVE",
                    )
                ]
            if self.phase == WorkflowPhase.RECOVERY_SYNC:
                return [
                    CommandIntent(
                        "backwash_valve",
                        False,
                        CommandOwner.WORKFLOW,
                        "FILTER_BACKWASH_STOP",
                    )
                ]

        if session.origin_mode == OperatingMode.PARTIAL_SHUTDOWN:
            return [
                CommandIntent(
                    asset_id,
                    False,
                    CommandOwner.SHUTDOWN,
                    "PLANNED_PARTIAL_SHUTDOWN",
                )
                for asset_id in session.scope
            ]

        if session.origin_mode == OperatingMode.SAFE_TOTAL_SHUTDOWN:
            minimum_safe = set(session.metadata["minimum_safe_assets"])
            return [
                CommandIntent(
                    asset_id,
                    asset_id in minimum_safe,
                    CommandOwner.SHUTDOWN,
                    (
                        "MINIMUM_SAFE_LIFE_SUPPORT"
                        if asset_id in minimum_safe
                        else "SAFE_TOTAL_SHUTDOWN"
                    ),
                )
                for asset_id in session.scope
            ]

        if (
            session.origin_mode == OperatingMode.BLACKOUT_RECOVERY
            and self.phase == WorkflowPhase.RECOVERY_SYNC
        ):
            return [
                CommandIntent(
                    "main_pump",
                    True,
                    CommandOwner.SHUTDOWN,
                    "RECOVERY_RESTART_CIRCULATION",
                ),
                CommandIntent(
                    "primary_aerator",
                    True,
                    CommandOwner.SHUTDOWN,
                    "RECOVERY_RESTART_AERATION",
                ),
                CommandIntent(
                    "feeder",
                    False,
                    CommandOwner.SHUTDOWN,
                    "RECOVERY_FEED_INHIBIT",
                ),
            ]
        return []


def assess_capability(actuators: VirtualActuatorBank) -> CapabilitySummary:
    circulation_ids = ("main_pump", "backup_pump")
    aeration_ids = ("primary_aerator", "backup_aerator")
    circulation = sum(
        actuators.assets[asset_id].availability in _CAPABILITY_AVAILABLE
        for asset_id in circulation_ids
    )
    aeration = sum(
        actuators.assets[asset_id].availability in _CAPABILITY_AVAILABLE
        for asset_id in aeration_ids
    )
    reasons: list[str] = []
    if circulation == 0:
        reasons.append("CRITICAL_CAPABILITY_LOST:CIRCULATION")
    elif circulation == 1:
        reasons.append("REDUNDANCY_REDUCED:CIRCULATION")
    if aeration == 0:
        reasons.append("CRITICAL_CAPABILITY_LOST:AERATION")
    elif aeration == 1:
        reasons.append("REDUNDANCY_REDUCED:AERATION")
    return CapabilitySummary(
        circulation_paths_available=circulation,
        aeration_paths_available=aeration,
        degraded_reasons=tuple(reasons),
        critical_capability_lost=circulation == 0 or aeration == 0,
    )
