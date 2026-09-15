from __future__ import annotations

from datetime import datetime
from typing import Any

from smart_koi_pond.control.water_management import LowWaterRecoveryManager
from smart_koi_pond.digital_twin.governed_runtime import ProductionDigitalTwinRuntime
from smart_koi_pond.domain.enums import EventType
from smart_koi_pond.domain.models import ArbitratedCommand, CommandIntent, DeviceFeedback


class SourceWaterAwareLowWaterRecoveryManager(LowWaterRecoveryManager):
    """Retain the accepted low-water controller while exposing source-water gating.

    The source-water interlock itself lives at the runtime command boundary. This
    manager only preserves the exact reason in the bounded recovery/lockout state.
    """

    def __init__(self, qualification_provider) -> None:
        super().__init__()
        self._qualification_provider = qualification_provider

    def _clear_lockout_if_recovered(self, **kwargs) -> None:
        if self.lockout_reason == "SOURCE_WATER_NOT_QUALIFIED":
            qualification = self._qualification_provider()
            if not qualification["pond_use_qualified"]:
                return
            events = kwargs["events"]
            now = kwargs["now"]
            previous_attempt = self.lockout_attempt_id
            self.lockout_reason = None
            self.lockout_attempt_id = None
            self._append(
                events,
                now,
                "LOW_WATER_RECOVERY_LOCKOUT_CLEARED",
                {
                    "previous_attempt_id": previous_attempt,
                    "previous_reason": "SOURCE_WATER_NOT_QUALIFIED",
                    "qualification_state": qualification["state"],
                    "qualification_reference": qualification.get("reference"),
                },
            )
            return
        super()._clear_lockout_if_recovered(**kwargs)

    def observe_command(
        self,
        command: ArbitratedCommand,
        feedback: DeviceFeedback,
        now: datetime,
        events,
    ) -> None:
        attempt = self.active
        if (
            attempt is not None
            and command.asset_id == self.ASSET_ID
            and command.requested_on
            and not command.accepted
            and command.reason.startswith("SOURCE_WATER_NOT_QUALIFIED")
        ):
            attempt.outcome = "ABORTED"
            attempt.terminal_reason = "SOURCE_WATER_NOT_QUALIFIED"
            self.lockout_reason = attempt.terminal_reason
            self.lockout_attempt_id = attempt.attempt_id
            qualification = self._qualification_provider()
            self._append(
                events,
                now,
                "LOW_WATER_RECOVERY_ABORTED",
                {
                    "attempt_id": attempt.attempt_id,
                    "reason": attempt.terminal_reason,
                    "command_accepted": False,
                    "feedback_on": feedback.feedback_on,
                    "qualification_state": qualification["state"],
                    "qualification_reference": qualification.get("reference"),
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
        super().observe_command(command, feedback, now, events)

    def status(self, policy) -> dict[str, Any]:
        status = super().status(policy)
        qualification = self._qualification_provider()
        status["source_water_qualification_required"] = True
        status["source_water_qualified"] = qualification["pond_use_qualified"]
        status["source_water_qualification_state"] = qualification["state"]
        status["source_water_qualification_reason"] = qualification["reason"]
        status["source_water_qualification_reference"] = qualification.get("reference")
        status["auto_top_up_source_water_dependency_satisfied"] = qualification[
            "pond_use_qualified"
        ]
        return status


class SourceWaterQualifiedProductionRuntime(ProductionDigitalTwinRuntime):
    """Production runtime with one fail-closed source-water actuation interlock.

    This class reuses the accepted production runtime/control brain. It does not add
    a parallel controller: it adds a pre-arbitration safety dependency for every
    request that would energize the canonical top-up valve.
    """

    TOP_UP_ASSET_ID = "top_up_valve"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.low_water_recovery = SourceWaterAwareLowWaterRecoveryManager(
            self._source_water_qualification_snapshot
        )

    def _source_water_qualification_snapshot(self) -> dict[str, Any]:
        snapshot = getattr(self.model, "source_water_qualification_snapshot", None)
        if snapshot is None:
            return {
                "state": "NOT_APPLICABLE",
                "pond_use_qualified": True,
                "reference": None,
                "reason": "MODEL_DOES_NOT_REQUIRE_SOURCE_WATER_QUALIFICATION",
            }
        return dict(snapshot())

    def _require_source_water_qualified(self, operation: str) -> None:
        qualification = self._source_water_qualification_snapshot()
        if qualification["pond_use_qualified"]:
            return
        self.events.append(
            self.clock.current,
            EventType.CONFIGURATION,
            "SOURCE_WATER_OPERATION_INHIBITED",
            {
                "operation": operation,
                "reason": "SOURCE_WATER_NOT_QUALIFIED",
                "qualification_state": qualification["state"],
                "qualification_reference": qualification.get("reference"),
                "drain_started": False if operation == "WATER_CHANGE" else None,
                "automatic_chemical_dosing_authorized": False,
            },
        )
        raise RuntimeError(
            f"SOURCE_WATER_NOT_QUALIFIED:{qualification['state']}:{operation}"
        )

    def _execute_intent(self, intent: CommandIntent, now: datetime):
        if intent.asset_id == self.TOP_UP_ASSET_ID and intent.requested_on:
            qualification = self._source_water_qualification_snapshot()
            if not qualification["pond_use_qualified"]:
                command = ArbitratedCommand(
                    asset_id=intent.asset_id,
                    requested_on=True,
                    final_on=False,
                    owner=intent.owner,
                    accepted=False,
                    reason=f"SOURCE_WATER_NOT_QUALIFIED:{qualification['state']}",
                )
                feedback = self.actuators.execute(command, now)
                self.events.append(
                    now,
                    EventType.COMMAND,
                    "SOURCE_WATER_TOP_UP_INHIBITED",
                    {
                        "asset_id": intent.asset_id,
                        "owner": intent.owner,
                        "requested_on": True,
                        "accepted": False,
                        "final_on": False,
                        "qualification_state": qualification["state"],
                        "qualification_reference": qualification.get("reference"),
                        "source_type_implies_safe_chemistry": False,
                        "automatic_chemical_dosing_authorized": False,
                    },
                )
                self.events.append(
                    now,
                    EventType.COMMAND,
                    "COMMAND_ARBITRATED",
                    {
                        "asset_id": command.asset_id,
                        "owner": command.owner,
                        "accepted": command.accepted,
                        "final_on": command.final_on,
                        "reason": command.reason,
                        "source_state": self.actuators.source_for(command.asset_id),
                        "authority_state": self.actuators.authority_for(command.asset_id),
                        "adapter_id": self.actuators.adapter_id,
                        "device_id": self.actuators.device_id_for(command.asset_id),
                    },
                )
                return command, feedback
        return super()._execute_intent(intent, now)

    def start_water_change(
        self,
        reason: str,
        *,
        target_drain_level_pct: float,
        target_refill_level_pct: float,
    ) -> None:
        self._require_source_water_qualified("WATER_CHANGE")
        super().start_water_change(
            reason,
            target_drain_level_pct=target_drain_level_pct,
            target_refill_level_pct=target_refill_level_pct,
        )
