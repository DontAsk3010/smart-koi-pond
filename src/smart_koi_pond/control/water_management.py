from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    CommandOwner,
    DataQuality,
    EventType,
    OperatingMode,
    VerificationStatus,
)
from smart_koi_pond.domain.models import (
    ArbitratedCommand,
    CommandIntent,
    DeviceFeedback,
    StateEstimate,
    VerificationTask,
)
from smart_koi_pond.events.log import EventLog


@dataclass(slots=True)
class LowWaterRecoveryAttempt:
    attempt_id: str
    started_at: datetime
    baseline_level_pct: float
    target_level_pct: float
    hard_high_cutoff_pct: float
    max_runtime_seconds: float
    max_level_gain_pct: float
    response_verified: bool = False
    target_reached: bool = False
    safe_off_confirmed: bool = False
    outcome: str | None = None
    terminal_reason: str | None = None


class LowWaterRecoveryManager:
    """Single-attempt autonomous top-up coordinator for simulation/SIL.

    The manager never commands drain. Any terminal or unsafe path requests a
    non-overridable SAFETY OFF command for the top-up valve. Failed attempts
    enter lockout and cannot silently retry while the low-water condition remains.
    """

    ASSET_ID = "top_up_valve"

    def __init__(self) -> None:
        self.active: LowWaterRecoveryAttempt | None = None
        self._counter = 0
        self.lockout_reason: str | None = None
        self.lockout_attempt_id: str | None = None

    def _append(
        self,
        events: EventLog,
        now: datetime,
        code: str,
        payload: dict[str, Any],
    ) -> None:
        events.append(now, EventType.RECOVERY, code, payload)

    def _safety_off(self, reason: str) -> CommandIntent:
        return CommandIntent(
            self.ASSET_ID,
            False,
            CommandOwner.SAFETY,
            f"LOW_WATER_SAFETY_OFF:{reason}",
        )

    def _abort(
        self,
        *,
        reason: str,
        now: datetime,
        level: float | None,
        events: EventLog,
    ) -> CommandIntent:
        attempt = self.active
        if attempt is None:
            return self._safety_off(reason)
        if attempt.outcome != "ABORTED":
            attempt.outcome = "ABORTED"
            attempt.terminal_reason = reason
            self.lockout_reason = reason
            self.lockout_attempt_id = attempt.attempt_id
            self._append(
                events,
                now,
                "LOW_WATER_RECOVERY_ABORTED",
                {
                    "attempt_id": attempt.attempt_id,
                    "reason": reason,
                    "level_pct": level,
                    "baseline_level_pct": attempt.baseline_level_pct,
                    "response_verified": attempt.response_verified,
                },
            )
        return self._safety_off(reason)

    def _clear_lockout_if_recovered(
        self,
        *,
        level: float | None,
        quality: DataQuality | None,
        policy: SimulationControlPolicy,
        now: datetime,
        events: EventLog,
    ) -> None:
        if self.lockout_reason is None:
            return
        target = policy.water_level_recover_target
        if quality != DataQuality.GOOD or level is None or target is None or level < target:
            return
        previous_reason = self.lockout_reason
        previous_attempt = self.lockout_attempt_id
        self.lockout_reason = None
        self.lockout_attempt_id = None
        self._append(
            events,
            now,
            "LOW_WATER_RECOVERY_LOCKOUT_CLEARED",
            {
                "previous_attempt_id": previous_attempt,
                "previous_reason": previous_reason,
                "level_pct": level,
            },
        )

    def plan(
        self,
        *,
        now: datetime,
        estimate: StateEstimate,
        operating_mode: OperatingMode,
        actuators,
        completed_verifications: list[VerificationTask],
        policy: SimulationControlPolicy,
        events: EventLog,
    ) -> list[CommandIntent]:
        level = estimate.values.get("water_level_pct")
        quality = estimate.quality.get("water_level_pct")
        asset = actuators.assets[self.ASSET_ID]

        self._clear_lockout_if_recovered(
            level=level,
            quality=quality,
            policy=policy,
            now=now,
            events=events,
        )

        if self.active is None:
            if self.lockout_reason is not None:
                if asset.feedback_on:
                    return [self._safety_off(f"LOCKOUT:{self.lockout_reason}")]
                return []
            if not policy.low_water_auto_recovery_enabled:
                return []
            if quality != DataQuality.GOOD or level is None:
                return []
            if level >= policy.water_level_low_below:
                return []
            if operating_mode != OperatingMode.NORMAL_AUTO:
                return []
            if asset.availability != AvailabilityState.AVAILABLE:
                return []
            if asset.owner != CommandOwner.AUTO:
                return []

            target = policy.water_level_recover_target
            cutoff = policy.water_level_hard_high_cutoff
            if target is None or cutoff is None:
                return []
            self._counter += 1
            self.active = LowWaterRecoveryAttempt(
                attempt_id=f"low-water-{self._counter}",
                started_at=now,
                baseline_level_pct=level,
                target_level_pct=target,
                hard_high_cutoff_pct=cutoff,
                max_runtime_seconds=policy.low_water_max_runtime_seconds,
                max_level_gain_pct=policy.low_water_max_level_gain_pct,
            )
            self._append(
                events,
                now,
                "LOW_WATER_RECOVERY_STARTED",
                {
                    "attempt_id": self.active.attempt_id,
                    "baseline_level_pct": level,
                    "target_level_pct": target,
                    "hard_high_cutoff_pct": cutoff,
                    "max_runtime_seconds": policy.low_water_max_runtime_seconds,
                    "max_level_gain_pct": policy.low_water_max_level_gain_pct,
                },
            )
            return [
                CommandIntent(
                    self.ASSET_ID,
                    True,
                    CommandOwner.AUTO,
                    "LOW_WATER_AUTO_RECOVERY_START",
                )
            ]

        attempt = self.active

        for task in completed_verifications:
            if task.asset_id != self.ASSET_ID:
                continue
            if task.status == VerificationStatus.VERIFIED_SUCCESS:
                if not attempt.response_verified:
                    attempt.response_verified = True
                    self._append(
                        events,
                        now,
                        "LOW_WATER_RESPONSE_VERIFIED",
                        {
                            "attempt_id": attempt.attempt_id,
                            "verification_id": task.verification_id,
                            "baseline": task.baseline,
                            "observed": task.observed_value,
                        },
                    )
            elif task.status in {
                VerificationStatus.FAILED_RESPONSE,
                VerificationStatus.INSUFFICIENT_EVIDENCE,
                VerificationStatus.ABORTED_BY_MODE_CHANGE,
            }:
                return [
                    self._abort(
                        reason=f"VERIFICATION_{task.status.value}",
                        now=now,
                        level=level,
                        events=events,
                    )
                ]

        if attempt.outcome == "ABORTED":
            return [self._safety_off(attempt.terminal_reason or "ABORTED")]

        if attempt.target_reached:
            if attempt.response_verified:
                return [self._safety_off("TARGET_REACHED")]
            return [self._safety_off("TARGET_REACHED_WAITING_VERIFICATION")]

        if not policy.low_water_auto_recovery_enabled:
            return [
                self._abort(
                    reason="FEATURE_DISABLED_DURING_ATTEMPT",
                    now=now,
                    level=level,
                    events=events,
                )
            ]
        if operating_mode != OperatingMode.NORMAL_AUTO:
            return [
                self._abort(
                    reason=f"UNSAFE_OPERATING_MODE:{operating_mode.value}",
                    now=now,
                    level=level,
                    events=events,
                )
            ]
        if quality != DataQuality.GOOD or level is None:
            return [
                self._abort(
                    reason="INVALID_WATER_LEVEL_EVIDENCE",
                    now=now,
                    level=level,
                    events=events,
                )
            ]
        if asset.availability != AvailabilityState.AVAILABLE:
            return [
                self._abort(
                    reason=f"TOP_UP_VALVE_NOT_AVAILABLE:{asset.availability.value}",
                    now=now,
                    level=level,
                    events=events,
                )
            ]
        if asset.owner != CommandOwner.AUTO:
            return [
                self._abort(
                    reason=f"TOP_UP_VALVE_OWNER_CHANGED:{asset.owner.value}",
                    now=now,
                    level=level,
                    events=events,
                )
            ]

        if level >= attempt.hard_high_cutoff_pct:
            return [
                self._abort(
                    reason="HARD_HIGH_LEVEL_CUTOFF",
                    now=now,
                    level=level,
                    events=events,
                )
            ]

        elapsed = (now - attempt.started_at).total_seconds()
        if elapsed >= attempt.max_runtime_seconds:
            return [
                self._abort(
                    reason="MAX_RUNTIME_EXCEEDED",
                    now=now,
                    level=level,
                    events=events,
                )
            ]

        level_gain = level - attempt.baseline_level_pct
        if level_gain >= attempt.max_level_gain_pct:
            return [
                self._abort(
                    reason="MAX_LEVEL_GAIN_EXCEEDED",
                    now=now,
                    level=level,
                    events=events,
                )
            ]

        if level >= attempt.target_level_pct:
            attempt.target_reached = True
            self._append(
                events,
                now,
                "LOW_WATER_RECOVERY_TARGET_REACHED",
                {
                    "attempt_id": attempt.attempt_id,
                    "level_pct": level,
                    "response_verified": attempt.response_verified,
                },
            )
            return [self._safety_off("TARGET_REACHED")]

        return [
            CommandIntent(
                self.ASSET_ID,
                True,
                CommandOwner.AUTO,
                "LOW_WATER_AUTO_RECOVERY_CONTINUE",
            )
        ]

    def observe_command(
        self,
        command: ArbitratedCommand,
        feedback: DeviceFeedback,
        now: datetime,
        events: EventLog,
    ) -> None:
        attempt = self.active
        if attempt is None or command.asset_id != self.ASSET_ID:
            return

        if command.requested_on:
            if not command.accepted or not feedback.feedback_on:
                attempt.outcome = "ABORTED"
                attempt.terminal_reason = "TOP_UP_COMMAND_NOT_EFFECTIVE"
                self.lockout_reason = attempt.terminal_reason
                self.lockout_attempt_id = attempt.attempt_id
                self._append(
                    events,
                    now,
                    "LOW_WATER_RECOVERY_ABORTED",
                    {
                        "attempt_id": attempt.attempt_id,
                        "reason": attempt.terminal_reason,
                        "command_accepted": command.accepted,
                        "feedback_on": feedback.feedback_on,
                    },
                )
                if not feedback.feedback_on:
                    attempt.safe_off_confirmed = True
                    self._append(
                        events,
                        now,
                        "LOW_WATER_RECOVERY_SAFE_OFF_CONFIRMED",
                        {
                            "attempt_id": attempt.attempt_id,
                            "outcome": attempt.outcome,
                        },
                    )
                    self.active = None
            return

        if feedback.feedback_on:
            return

        if not attempt.safe_off_confirmed:
            attempt.safe_off_confirmed = True
            self._append(
                events,
                now,
                "LOW_WATER_RECOVERY_SAFE_OFF_CONFIRMED",
                {
                    "attempt_id": attempt.attempt_id,
                    "outcome": attempt.outcome,
                    "target_reached": attempt.target_reached,
                    "response_verified": attempt.response_verified,
                },
            )

        if attempt.outcome == "ABORTED":
            self.active = None
            return

        if attempt.target_reached and attempt.response_verified:
            attempt.outcome = "VERIFIED_SUCCESS"
            self._append(
                events,
                now,
                "LOW_WATER_RECOVERY_COMPLETED",
                {
                    "attempt_id": attempt.attempt_id,
                    "outcome": attempt.outcome,
                },
            )
            self.active = None

    def checkpoint_state(self) -> dict[str, Any]:
        active = None
        if self.active is not None:
            active = asdict(self.active)
            active["started_at"] = self.active.started_at.isoformat()
        return {
            "counter": self._counter,
            "lockout_reason": self.lockout_reason,
            "lockout_attempt_id": self.lockout_attempt_id,
            "active_attempt": active,
        }

    def restore_after_restart(
        self,
        data: dict[str, Any] | None,
        *,
        now: datetime,
        events: EventLog,
    ) -> None:
        if not data:
            return
        self._counter = int(data.get("counter", 0))
        self.lockout_reason = data.get("lockout_reason")
        self.lockout_attempt_id = data.get("lockout_attempt_id")
        active = data.get("active_attempt")
        self.active = None
        if active:
            attempt_id = str(active["attempt_id"])
            self.lockout_reason = "RUNTIME_RESTART_ABORT"
            self.lockout_attempt_id = attempt_id
            self._append(
                events,
                now,
                "LOW_WATER_RECOVERY_ABORTED_ON_RESTART",
                {
                    "attempt_id": attempt_id,
                    "stale_command_replay": False,
                },
            )

    def status(self, policy: SimulationControlPolicy) -> dict[str, Any]:
        attempt = self.active
        return {
            "enabled": policy.low_water_auto_recovery_enabled,
            "active_attempt_id": attempt.attempt_id if attempt else None,
            "started_at": attempt.started_at.isoformat() if attempt else None,
            "baseline_level_pct": attempt.baseline_level_pct if attempt else None,
            "target_level_pct": (
                attempt.target_level_pct
                if attempt
                else policy.water_level_recover_target
            ),
            "hard_high_cutoff_pct": (
                attempt.hard_high_cutoff_pct
                if attempt
                else policy.water_level_hard_high_cutoff
            ),
            "response_verified": attempt.response_verified if attempt else False,
            "target_reached": attempt.target_reached if attempt else False,
            "safe_off_confirmed": attempt.safe_off_confirmed if attempt else True,
            "lockout_reason": self.lockout_reason,
            "lockout_attempt_id": self.lockout_attempt_id,
        }
