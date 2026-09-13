from collections.abc import Iterable
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

    def restore(self, records: Iterable[EventRecord]) -> None:
        restored = list(records)
        expected = list(range(1, len(restored) + 1))
        actual = [record.sequence for record in restored]
        if actual != expected:
            raise ValueError("event sequence must be contiguous and start at 1")
        self._events = restored

    def after(self, sequence: int) -> tuple[EventRecord, ...]:
        if sequence < 0:
            raise ValueError("sequence must be non-negative")
        return tuple(record for record in self._events if record.sequence > sequence)
