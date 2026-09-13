from datetime import datetime
from typing import Any

from smart_koi_pond.domain.enums import EventType
from smart_koi_pond.domain.models import EventRecord


class EventLog:
    def __init__(self) -> None:
        self._events: list[EventRecord] = []

    @property
    def events(self) -> tuple[EventRecord, ...]:
        return tuple(self._events)

    def append(
        self,
        timestamp: datetime,
        event_type: EventType,
        code: str,
        payload: dict[str, Any] | None = None,
    ) -> EventRecord:
        record = EventRecord(
            sequence=len(self._events) + 1,
            timestamp=timestamp,
            event_type=event_type,
            code=code,
            payload=payload or {},
        )
        self._events.append(record)
        return record
