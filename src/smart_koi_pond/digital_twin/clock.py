from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(slots=True)
class SimulationClock:
    current: datetime
    acceleration: float = 1.0
    paused: bool = False

    @classmethod
    def start(cls, start_at: datetime | None = None) -> "SimulationClock":
        if start_at is None:
            start_at = datetime(2026, 1, 1, tzinfo=UTC)
        if start_at.tzinfo is None:
            raise ValueError("SimulationClock requires timezone-aware datetime")
        return cls(current=start_at)

    def advance(self, real_seconds: float, *, force: bool = False) -> datetime:
        if real_seconds < 0:
            raise ValueError("real_seconds must be non-negative")
        if not self.paused or force:
            self.current += timedelta(seconds=real_seconds * self.acceleration)
        return self.current

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False
