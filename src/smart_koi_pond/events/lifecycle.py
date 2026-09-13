from dataclasses import replace
from datetime import datetime
from typing import Any

from smart_koi_pond.domain.enums import (
    AlarmLifecycle,
    EventType,
    IncidentLifecycle,
    SystemState,
    VerificationStatus,
)
from smart_koi_pond.domain.models import (
    AlarmRecord,
    Classification,
    EventRecord,
    IncidentRecord,
    VerificationTask,
)
from smart_koi_pond.events.log import EventLog


class AlarmIncidentManager:
    """Governed alarm and incident lifecycle coordinator.

    Acknowledgement is metadata, never resolution. Resolution requires a recovery
    transition and a subsequent still-healthy observation.
    """

    _SYSTEM_KEY = "SYSTEM_STATE"

    def __init__(self, events: EventLog) -> None:
        self.events = events
        self.alarms: list[AlarmRecord] = []
        self.incidents: list[IncidentRecord] = []
        self._alarm_counter = 0
        self._incident_counter = 0

    @property
    def active_alarms(self) -> tuple[AlarmRecord, ...]:
        return tuple(
            alarm
            for alarm in self.alarms
            if alarm.lifecycle != AlarmLifecycle.RESOLVED
        )

    @property
    def active_incident(self) -> IncidentRecord | None:
        for incident in reversed(self.incidents):
            if incident.lifecycle != IncidentLifecycle.RESOLVED:
                return incident
        return None

    def _next_alarm_id(self) -> str:
        self._alarm_counter += 1
        return f"alarm-{self._alarm_counter}"

    def _next_incident_id(self) -> str:
        self._incident_counter += 1
        return f"incident-{self._incident_counter}"

    def _alarm_for_key(self, condition_key: str) -> AlarmRecord | None:
        for alarm in reversed(self.alarms):
            if (
                alarm.condition_key == condition_key
                and alarm.lifecycle != AlarmLifecycle.RESOLVED
            ):
                return alarm
        return None

    @staticmethod
    def _lifecycle_for_state(state: SystemState) -> AlarmLifecycle:
        if state in {SystemState.EMERGENCY, SystemState.FAILSAFE}:
            return AlarmLifecycle.ESCALATED
        if state == SystemState.CORRECTING:
            return AlarmLifecycle.CORRECTIVE_ACTIVE
        return AlarmLifecycle.OPEN

    def _open_alarm(
        self,
        *,
        condition_key: str,
        code: str,
        now: datetime,
        source_state: SystemState,
        reasons: tuple[str, ...],
        lifecycle: AlarmLifecycle,
    ) -> AlarmRecord:
        alarm = AlarmRecord(
            alarm_id=self._next_alarm_id(),
            condition_key=condition_key,
            code=code,
            opened_at=now,
            lifecycle=lifecycle,
            source_state=source_state,
            reasons=reasons,
        )
        self.alarms.append(alarm)
        event = self.events.append(
            now,
            EventType.ALARM,
            "ALARM_OPENED",
            {
                "alarm_id": alarm.alarm_id,
                "condition_key": condition_key,
                "code": code,
                "lifecycle": lifecycle,
                "source_state": source_state,
                "reasons": reasons,
            },
        )
        self._attach_alarm_to_incident(alarm, event)
        return alarm

    def _attach_alarm_to_incident(
        self,
        alarm: AlarmRecord,
        alarm_event: EventRecord,
    ) -> None:
        incident = self.active_incident
        if incident is None:
            incident = IncidentRecord(
                incident_id=self._next_incident_id(),
                opened_at=alarm.opened_at,
                trigger_alarm_id=alarm.alarm_id,
                trigger_code=alarm.code,
                trigger_state=alarm.source_state,
                start_event_sequence=alarm_event.sequence,
                alarm_ids=(alarm.alarm_id,),
            )
            self.incidents.append(incident)
            self.events.append(
                alarm.opened_at,
                EventType.INCIDENT,
                "INCIDENT_OPENED",
                {
                    "incident_id": incident.incident_id,
                    "trigger_alarm_id": alarm.alarm_id,
                    "trigger_code": alarm.code,
                    "trigger_state": alarm.source_state,
                },
            )
            return

        if alarm.alarm_id not in incident.alarm_ids:
            incident.alarm_ids = (*incident.alarm_ids, alarm.alarm_id)
            incident.lifecycle = IncidentLifecycle.OPEN
            self.events.append(
                alarm.opened_at,
                EventType.INCIDENT,
                "INCIDENT_ALARM_ATTACHED",
                {
                    "incident_id": incident.incident_id,
                    "alarm_id": alarm.alarm_id,
                },
            )

    def _set_alarm_lifecycle(
        self,
        alarm: AlarmRecord,
        lifecycle: AlarmLifecycle,
        now: datetime,
        *,
        reasons: tuple[str, ...] | None = None,
        source_state: SystemState | None = None,
    ) -> None:
        if reasons is not None:
            alarm.reasons = reasons
        if source_state is not None:
            alarm.source_state = source_state
        if alarm.lifecycle == lifecycle:
            return
        previous = alarm.lifecycle
        alarm.lifecycle = lifecycle
        if lifecycle == AlarmLifecycle.RESOLVED:
            alarm.resolved_at = now
        else:
            alarm.resolved_at = None
        self.events.append(
            now,
            EventType.ALARM,
            f"ALARM_{lifecycle.value}",
            {
                "alarm_id": alarm.alarm_id,
                "from": previous,
                "to": lifecycle,
            },
        )

    def _update_system_alarm(
        self,
        now: datetime,
        classification: Classification,
        touched: set[str],
    ) -> None:
        existing = self._alarm_for_key(self._SYSTEM_KEY)
        if classification.state == SystemState.NORMAL:
            return

        touched.add(self._SYSTEM_KEY)
        target = self._lifecycle_for_state(classification.state)
        code = f"SYSTEM_{classification.state.value}"
        if existing is None:
            self._open_alarm(
                condition_key=self._SYSTEM_KEY,
                code=code,
                now=now,
                source_state=classification.state,
                reasons=classification.reasons,
                lifecycle=target,
            )
            return

        existing.code = code
        self._set_alarm_lifecycle(
            existing,
            target,
            now,
            reasons=classification.reasons,
            source_state=classification.state,
        )

    def _update_verification_alarms(
        self,
        now: datetime,
        classification: Classification,
        completed: list[VerificationTask],
        touched: set[str],
    ) -> None:
        for task in completed:
            if task.status not in {
                VerificationStatus.FAILED_RESPONSE,
                VerificationStatus.INSUFFICIENT_EVIDENCE,
            }:
                continue
            key = f"VERIFICATION:{task.verification_id}"
            touched.add(key)
            existing = self._alarm_for_key(key)
            lifecycle = (
                AlarmLifecycle.ESCALATED
                if task.status == VerificationStatus.FAILED_RESPONSE
                else AlarmLifecycle.OPEN
            )
            reasons = (
                task.status.value,
                f"ASSET:{task.asset_id}",
                f"PARAMETER:{task.parameter}",
            )
            if existing is None:
                self._open_alarm(
                    condition_key=key,
                    code=task.status.value,
                    now=now,
                    source_state=classification.state,
                    reasons=reasons,
                    lifecycle=lifecycle,
                )
            else:
                self._set_alarm_lifecycle(
                    existing,
                    lifecycle,
                    now,
                    reasons=reasons,
                    source_state=classification.state,
                )

    def _advance_recovery(
        self,
        now: datetime,
        classification: Classification,
        touched: set[str],
    ) -> None:
        if classification.state != SystemState.NORMAL:
            return
        for alarm in self.active_alarms:
            if alarm.condition_key in touched:
                continue
            if alarm.lifecycle == AlarmLifecycle.RECOVERING:
                self._set_alarm_lifecycle(alarm, AlarmLifecycle.RESOLVED, now)
            else:
                self._set_alarm_lifecycle(alarm, AlarmLifecycle.RECOVERING, now)

    def _update_incident(self, now: datetime) -> None:
        incident = self.active_incident
        if incident is None:
            return

        active = [
            alarm
            for alarm in self.alarms
            if alarm.alarm_id in incident.alarm_ids
            and alarm.lifecycle != AlarmLifecycle.RESOLVED
        ]
        if not active:
            previous = incident.lifecycle
            incident.lifecycle = IncidentLifecycle.RESOLVED
            incident.resolved_at = now
            event = self.events.append(
                now,
                EventType.INCIDENT,
                "INCIDENT_RESOLVED",
                {
                    "incident_id": incident.incident_id,
                    "from": previous,
                    "to": IncidentLifecycle.RESOLVED,
                },
            )
            incident.end_event_sequence = event.sequence
            return

        target = (
            IncidentLifecycle.RECOVERING
            if all(alarm.lifecycle == AlarmLifecycle.RECOVERING for alarm in active)
            else IncidentLifecycle.OPEN
        )
        if target != incident.lifecycle:
            previous = incident.lifecycle
            incident.lifecycle = target
            self.events.append(
                now,
                EventType.INCIDENT,
                f"INCIDENT_{target.value}",
                {
                    "incident_id": incident.incident_id,
                    "from": previous,
                    "to": target,
                },
            )

    def update(
        self,
        now: datetime,
        classification: Classification,
        completed_verifications: list[VerificationTask],
    ) -> None:
        touched: set[str] = set()
        self._update_system_alarm(now, classification, touched)
        self._update_verification_alarms(
            now,
            classification,
            completed_verifications,
            touched,
        )
        self._advance_recovery(now, classification, touched)
        self._update_incident(now)

    def acknowledge(self, alarm_id: str, actor: str, now: datetime) -> AlarmRecord:
        alarm = next((item for item in self.alarms if item.alarm_id == alarm_id), None)
        if alarm is None:
            raise KeyError(alarm_id)
        if alarm.lifecycle == AlarmLifecycle.RESOLVED:
            raise ValueError("resolved alarm cannot be acknowledged")
        if alarm.acknowledged_at is None:
            alarm.acknowledged_at = now
            alarm.acknowledged_by = actor
            self.events.append(
                now,
                EventType.ALARM,
                "ALARM_ACKNOWLEDGED",
                {
                    "alarm_id": alarm.alarm_id,
                    "actor": actor,
                    "lifecycle": alarm.lifecycle,
                },
            )
        return alarm

    def evidence_for_incident(self, incident_id: str) -> tuple[EventRecord, ...]:
        incident = next(
            (item for item in self.incidents if item.incident_id == incident_id),
            None,
        )
        if incident is None:
            raise KeyError(incident_id)
        end = incident.end_event_sequence
        return tuple(
            event
            for event in self.events.events
            if event.sequence >= incident.start_event_sequence
            and (end is None or event.sequence <= end)
        )

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "alarms": [
                {
                    "alarm_id": alarm.alarm_id,
                    "condition_key": alarm.condition_key,
                    "code": alarm.code,
                    "opened_at": alarm.opened_at.isoformat(),
                    "lifecycle": alarm.lifecycle.value,
                    "source_state": alarm.source_state.value,
                    "reasons": list(alarm.reasons),
                    "acknowledged_at": (
                        alarm.acknowledged_at.isoformat()
                        if alarm.acknowledged_at is not None
                        else None
                    ),
                    "acknowledged_by": alarm.acknowledged_by,
                    "resolved_at": (
                        alarm.resolved_at.isoformat()
                        if alarm.resolved_at is not None
                        else None
                    ),
                }
                for alarm in self.alarms
            ],
            "incidents": [
                {
                    "incident_id": incident.incident_id,
                    "opened_at": incident.opened_at.isoformat(),
                    "trigger_alarm_id": incident.trigger_alarm_id,
                    "trigger_code": incident.trigger_code,
                    "trigger_state": incident.trigger_state.value,
                    "start_event_sequence": incident.start_event_sequence,
                    "lifecycle": incident.lifecycle.value,
                    "alarm_ids": list(incident.alarm_ids),
                    "resolved_at": (
                        incident.resolved_at.isoformat()
                        if incident.resolved_at is not None
                        else None
                    ),
                    "end_event_sequence": incident.end_event_sequence,
                }
                for incident in self.incidents
            ],
        }

    def restore_checkpoint_state(self, data: dict[str, Any] | None) -> None:
        if not data:
            self.alarms = []
            self.incidents = []
            self._alarm_counter = 0
            self._incident_counter = 0
            return

        self.alarms = [
            AlarmRecord(
                alarm_id=str(item["alarm_id"]),
                condition_key=str(item["condition_key"]),
                code=str(item["code"]),
                opened_at=datetime.fromisoformat(item["opened_at"]),
                lifecycle=AlarmLifecycle(item["lifecycle"]),
                source_state=SystemState(item["source_state"]),
                reasons=tuple(item.get("reasons", [])),
                acknowledged_at=(
                    datetime.fromisoformat(item["acknowledged_at"])
                    if item.get("acknowledged_at")
                    else None
                ),
                acknowledged_by=item.get("acknowledged_by"),
                resolved_at=(
                    datetime.fromisoformat(item["resolved_at"])
                    if item.get("resolved_at")
                    else None
                ),
            )
            for item in data.get("alarms", [])
        ]
        self.incidents = [
            IncidentRecord(
                incident_id=str(item["incident_id"]),
                opened_at=datetime.fromisoformat(item["opened_at"]),
                trigger_alarm_id=str(item["trigger_alarm_id"]),
                trigger_code=str(item["trigger_code"]),
                trigger_state=SystemState(item["trigger_state"]),
                start_event_sequence=int(item["start_event_sequence"]),
                lifecycle=IncidentLifecycle(item["lifecycle"]),
                alarm_ids=tuple(item.get("alarm_ids", [])),
                resolved_at=(
                    datetime.fromisoformat(item["resolved_at"])
                    if item.get("resolved_at")
                    else None
                ),
                end_event_sequence=(
                    int(item["end_event_sequence"])
                    if item.get("end_event_sequence") is not None
                    else None
                ),
            )
            for item in data.get("incidents", [])
        ]

        self._alarm_counter = max(
            (
                int(alarm.alarm_id.rsplit("-", 1)[1])
                for alarm in self.alarms
                if alarm.alarm_id.rsplit("-", 1)[-1].isdigit()
            ),
            default=0,
        )
        self._incident_counter = max(
            (
                int(incident.incident_id.rsplit("-", 1)[1])
                for incident in self.incidents
                if incident.incident_id.rsplit("-", 1)[-1].isdigit()
            ),
            default=0,
        )

    def snapshot_alarms(self) -> tuple[AlarmRecord, ...]:
        return tuple(replace(alarm) for alarm in self.alarms)

    def snapshot_incidents(self) -> tuple[IncidentRecord, ...]:
        return tuple(replace(incident) for incident in self.incidents)
