from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from smart_koi_pond.domain.models import RuntimeSnapshot
from smart_koi_pond.events.log import EventLog


def _wire_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _wire_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _wire_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire_value(item) for item in value]
    return value


class CanonicalRuntimePublisher:
    SCHEMA_VERSION = 1

    def publish(
        self,
        *,
        run_id: str,
        snapshot: RuntimeSnapshot,
        event_log: EventLog,
        after_sequence: int = 0,
    ) -> dict[str, Any]:
        events = event_log.after(after_sequence)
        latest_sequence = event_log.events[-1].sequence if event_log.events else 0
        return {
            "schema_version": self.SCHEMA_VERSION,
            "run_id": run_id,
            "published_at": snapshot.timestamp.isoformat(),
            "snapshot_sequence": latest_sequence,
            "snapshot": _wire_value(snapshot),
            "events": [_wire_value(event) for event in events],
            "next_event_sequence": latest_sequence,
        }
