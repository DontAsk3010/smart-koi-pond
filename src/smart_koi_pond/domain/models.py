from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import (
    AvailabilityState,
    CommandOwner,
    DataQuality,
    EventType,
    ExecutionMode,
    OperatingMode,
    SystemState,
    VerificationStatus,
)


@dataclass(slots=True)
class PondState:
    temperature_c: float
    dissolved_oxygen_mg_l: float
    ph: float
    water_level_pct: float
    circulation_flow_l_min: float = 0.0


@dataclass(slots=True, frozen=True)
class SensorSample:
    sensor_id: str
    parameter: str
    value: float | None
    timestamp: datetime
    availability: AvailabilityState = AvailabilityState.AVAILABLE


@dataclass(slots=True, frozen=True)
class ValidatedMeasurement:
    sensor_id: str
    parameter: str
    value: float | None
    timestamp: datetime
    availability: AvailabilityState
    quality: DataQuality
    reasons: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class StateEstimate:
    timestamp: datetime
    values: dict[str, float | None]
    quality: dict[str, DataQuality]


@dataclass(slots=True, frozen=True)
class Classification:
    state: SystemState
    reasons: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class CommandIntent:
    asset_id: str
    requested_on: bool
    owner: CommandOwner
    reason: str


@dataclass(slots=True, frozen=True)
class ArbitratedCommand:
    asset_id: str
    requested_on: bool
    final_on: bool
    owner: CommandOwner
    accepted: bool
    reason: str


@dataclass(slots=True, frozen=True)
class DeviceFeedback:
    asset_id: str
    commanded_on: bool
    feedback_on: bool
    availability: AvailabilityState
    timestamp: datetime


@dataclass(slots=True)
class VerificationTask:
    verification_id: str
    asset_id: str
    parameter: str
    baseline: float
    minimum_delta: float
    due_at: datetime
    status: VerificationStatus = VerificationStatus.PENDING
    observed_value: float | None = None


@dataclass(slots=True, frozen=True)
class EventRecord:
    sequence: int
    timestamp: datetime
    event_type: EventType
    code: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimeSnapshot:
    timestamp: datetime
    execution_mode: ExecutionMode
    operating_mode: OperatingMode
    pond_truth: PondState
    raw_samples: dict[str, SensorSample]
    validated: dict[str, ValidatedMeasurement]
    estimate: StateEstimate
    classification: Classification
    commands: dict[str, ArbitratedCommand]
    feedback: dict[str, DeviceFeedback]
    verification: list[VerificationTask]
