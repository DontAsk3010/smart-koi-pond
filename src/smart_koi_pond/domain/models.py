from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import (
    ActuatorSourceState,
    AlarmLifecycle,
    AvailabilityState,
    BaselineStatus,
    CommandOwner,
    ControlAuthorityState,
    DataQuality,
    EventType,
    ExecutionMode,
    IncidentLifecycle,
    ModuleInstallationState,
    ModuleOperationalState,
    OperatingMode,
    SensorSourceState,
    SystemState,
    ValidationPhase,
    VerificationStatus,
    WorkflowPhase,
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
    source_state: SensorSourceState = SensorSourceState.VIRTUAL_SOURCE
    adapter_id: str = "virtual-sensor-suite"
    device_id: str | None = None
    unit: str | None = None
    schema_version: int = 1


@dataclass(slots=True, frozen=True)
class ValidatedMeasurement:
    sensor_id: str
    parameter: str
    value: float | None
    timestamp: datetime
    availability: AvailabilityState
    quality: DataQuality
    reasons: tuple[str, ...] = ()
    source_state: SensorSourceState = SensorSourceState.VIRTUAL_SOURCE
    adapter_id: str = "virtual-sensor-suite"
    device_id: str | None = None
    unit: str | None = None
    schema_version: int = 1


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
    effectiveness: float = 1.0
    source_state: ActuatorSourceState = ActuatorSourceState.VIRTUAL_ACTUATOR
    authority_state: ControlAuthorityState = ControlAuthorityState.AUTHORIZED
    adapter_id: str = "virtual-actuator-bank"
    device_id: str | None = None
    schema_version: int = 1


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


@dataclass(slots=True, frozen=True)
class CapabilityProfile:
    profile_id: str
    package_label: str
    required_capabilities: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class ModuleStatus:
    module_id: str
    installation_state: ModuleInstallationState
    operational_state: ModuleOperationalState
    capabilities_provided: tuple[str, ...]
    reasons: tuple[str, ...] = ()
    sensor_ids: tuple[str, ...] = ()
    asset_ids: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class BaselineAssessment:
    status: BaselineStatus
    required_capabilities: tuple[str, ...]
    satisfied_capabilities: tuple[str, ...] = ()
    degraded_capabilities: tuple[str, ...] = ()
    missing_capabilities: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class CapabilityRegistrySnapshot:
    profile_id: str
    package_label: str
    available_capabilities: tuple[str, ...]
    modules: dict[str, ModuleStatus]
    baseline: BaselineAssessment


@dataclass(slots=True, frozen=True)
class CapabilitySummary:
    circulation_paths_available: int
    aeration_paths_available: int
    degraded_reasons: tuple[str, ...] = ()
    critical_capability_lost: bool = False
    registry: CapabilityRegistrySnapshot | None = None


@dataclass(slots=True, frozen=True)
class OperatingStatus:
    mode: OperatingMode
    phase: WorkflowPhase
    reason: str | None
    scope: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class AssetStatus:
    asset_id: str
    owner: CommandOwner
    availability: AvailabilityState
    feedback_on: bool
    effectiveness: float = 1.0
    source_state: ActuatorSourceState = ActuatorSourceState.VIRTUAL_ACTUATOR
    authority_state: ControlAuthorityState = ControlAuthorityState.AUTHORIZED
    adapter_id: str = "virtual-actuator-bank"
    device_id: str | None = None
    schema_version: int = 1


@dataclass(slots=True)
class AlarmRecord:
    alarm_id: str
    condition_key: str
    code: str
    opened_at: datetime
    lifecycle: AlarmLifecycle
    source_state: SystemState
    reasons: tuple[str, ...] = ()
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None


@dataclass(slots=True)
class IncidentRecord:
    incident_id: str
    opened_at: datetime
    trigger_alarm_id: str
    trigger_code: str
    trigger_state: SystemState
    start_event_sequence: int
    lifecycle: IncidentLifecycle = IncidentLifecycle.OPEN
    alarm_ids: tuple[str, ...] = ()
    resolved_at: datetime | None = None
    end_event_sequence: int | None = None


@dataclass(slots=True)
class RuntimeSnapshot:
    timestamp: datetime
    run_id: str
    config_version: str
    simulation_paused: bool
    simulation_acceleration: float
    execution_mode: ExecutionMode
    operating_mode: OperatingMode
    operating_status: OperatingStatus
    pond_truth: PondState
    raw_samples: dict[str, SensorSample]
    validated: dict[str, ValidatedMeasurement]
    estimate: StateEstimate
    classification: Classification
    capability: CapabilitySummary
    assets: dict[str, AssetStatus]
    commands: dict[str, ArbitratedCommand]
    feedback: dict[str, DeviceFeedback]
    verification: list[VerificationTask]
    validation_phase: ValidationPhase = ValidationPhase.SIMULATION
    io_contract_version: int = 1
    alarms: tuple[AlarmRecord, ...] = ()
    incidents: tuple[IncidentRecord, ...] = ()
    water_recovery: dict[str, Any] = field(default_factory=dict)
