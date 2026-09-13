import json
import os
from pathlib import Path
from typing import Any

from smart_koi_pond.events.publication import _wire_value


class RuntimeHistorian:
    """Append-only runtime snapshot historian with optional JSONL durability."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_in_memory: int = 20_000,
    ) -> None:
        if max_in_memory <= 0:
            raise ValueError("max_in_memory must be positive")
        self.path = Path(path) if path is not None else None
        self.max_in_memory = max_in_memory
        self._frames: list[dict[str, Any]] = []
        self._next_sequence = 1
        if self.path is not None and self.path.exists():
            self._load_existing()

    @property
    def latest_sequence(self) -> int:
        return self._next_sequence - 1

    def _validate_frame(self, frame: dict[str, Any], expected_sequence: int) -> None:
        if frame.get("schema_version") != self.SCHEMA_VERSION:
            raise ValueError("unsupported historian schema version")
        if int(frame.get("frame_sequence", 0)) != expected_sequence:
            raise ValueError("historian frame sequence must be contiguous")

    def _load_existing(self) -> None:
        assert self.path is not None
        loaded: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for expected, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                frame = json.loads(line)
                if not isinstance(frame, dict):
                    raise ValueError("historian frame must be a JSON object")
                self._validate_frame(frame, expected)
                loaded.append(frame)
        self._next_sequence = len(loaded) + 1
        self._frames = loaded[-self.max_in_memory :]

    def append(
        self,
        *,
        run_id: str,
        event_sequence: int,
        snapshot: Any,
    ) -> dict[str, Any]:
        frame = {
            "schema_version": self.SCHEMA_VERSION,
            "frame_sequence": self._next_sequence,
            "run_id": run_id,
            "timestamp": snapshot.timestamp.isoformat(),
            "event_sequence": int(event_sequence),
            "snapshot": _wire_value(snapshot),
        }
        self._next_sequence += 1
        self._frames.append(frame)
        if len(self._frames) > self.max_in_memory:
            self._frames = self._frames[-self.max_in_memory :]

        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(frame, separators=(",", ":")))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        return frame

    def recent(
        self,
        *,
        limit: int = 100,
        run_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        frames = self._frames
        if run_id is not None:
            frames = [frame for frame in frames if frame["run_id"] == run_id]
        return tuple(frames[-limit:])

    def by_sequence(
        self,
        frame_sequence: int,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        if frame_sequence <= 0:
            raise ValueError("frame_sequence must be positive")
        for frame in reversed(self._frames):
            if int(frame["frame_sequence"]) != frame_sequence:
                continue
            if run_id is not None and frame["run_id"] != run_id:
                continue
            return frame
        raise KeyError(frame_sequence)

    def at_or_before(
        self,
        timestamp: str,
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        candidates = [
            frame
            for frame in self._frames
            if frame["timestamp"] <= timestamp
            and (run_id is None or frame["run_id"] == run_id)
        ]
        if not candidates:
            raise KeyError(timestamp)
        return candidates[-1]
