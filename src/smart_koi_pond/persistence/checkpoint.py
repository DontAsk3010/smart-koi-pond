import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from smart_koi_pond.control.operating_modes import _AssetRestoreState, _OperatingSession
from smart_koi_pond.domain.enums import (
    ActuatorSourceState,
    AvailabilityState,
    CommandOwner,
    EventType,
    ExecutionMode,
    OperatingMode,
    ValidationPhase,
    VerificationStatus,
    WorkflowPhase,
)
from smart_koi_pond.domain.models import EventRecord, VerificationTask

if TYPE_CHECKING:
    from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime

CHECKPOINT_SCHEMA_VERSION = 1


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _capture_mode_session(runtime: "DigitalTwinRuntime") -> dict[str, Any] | None:
    session = runtime.modes._session
    if session is None:
        return None
    return {
        "origin_mode": session.origin_mode.value,
        "phase": session.phase.value,
        "reason": session.reason,
        "scope": list(session.scope),
        "started_at": session.started_at.isoformat(),
        "asset_restore": {
            asset_id: {
                "owner": state.owner.value,
                "availability": state.availability.value,
            }
            for asset_id, state in session.asset_restore.items()
        },
        "sensor_restore": {
            sensor_id: availability.value if availability is not None else None
            for sensor_id, availability in session.sensor_restore.items()
        },
        "metadata": _jsonable(session.metadata),
    }


def _legacy_virtual_sensor_fields(runtime: "DigitalTwinRuntime") -> dict[str, Any]:
    faults = getattr(runtime.sensors, "_faults", None)
    stuck = getattr(runtime.sensors, "_stuck_values", None)
    if faults is None or stuck is None:
        return {}
    return {
        "sensor_availability": {
            sensor_id: (
                runtime.sensors.availability_override(sensor_id).value
                if runtime.sensors.availability_override(sensor_id) is not None
                else None
            )
            for sensor_id in runtime.sensors.PARAMETER_MAP
        },
        "sensor_faults": {
            sensor_id: {"mode": fault.mode, "value": fault.value}
            for sensor_id, fault in faults.items()
        },
        "sensor_stuck_values": dict(stuck),
    }


def capture_checkpoint(runtime: "DigitalTwinRuntime") -> dict[str, Any]:
    checkpoint = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "run_id": runtime.run_id,
        "config_version": runtime.config_version,
        "saved_at": runtime.clock.current.isoformat(),
        "execution_mode": runtime.execution_mode.value,
        "validation_phase": runtime.validation_phase.value,
        "sensor_adapter_id": runtime.sensors.adapter_id,
        "actuator_adapter_id": runtime.actuators.adapter_id,
        "sensor_adapter_state": _jsonable(runtime.sensors.checkpoint_state()),
        "actuator_adapter_state": _jsonable(runtime.actuators.checkpoint_state()),
        "clock": {
            "current": runtime.clock.current.isoformat(),
            "acceleration": runtime.clock.acceleration,
            "paused": runtime.clock.paused,
        },
        "pond_truth": {
            "temperature_c": runtime.model.state.temperature_c,
            "dissolved_oxygen_mg_l": runtime.model.state.dissolved_oxygen_mg_l,
            "ph": runtime.model.state.ph,
            "water_level_pct": runtime.model.state.water_level_pct,
            "circulation_flow_l_min": runtime.model.state.circulation_flow_l_min,
        },
        "assets": {
            asset_id: {
                "owner": asset.owner.value,
                "availability": asset.availability.value,
                "feedback_on": asset.feedback_on,
                "effectiveness": asset.effectiveness,
                "source_state": runtime.actuators.source_for(asset_id).value,
                "authority_state": runtime.actuators.authority_for(asset_id).value,
                "device_id": runtime.actuators.device_id_for(asset_id),
            }
            for asset_id, asset in runtime.actuators.assets.items()
        },
        "operating_mode": runtime.modes.mode.value,
        "operating_phase": runtime.modes.phase.value,
        "operating_session": _capture_mode_session(runtime),
        "verification": [
            {
                "verification_id": task.verification_id,
                "asset_id": task.asset_id,
                "parameter": task.parameter,
                "baseline": task.baseline,
                "minimum_delta": task.minimum_delta,
                "due_at": task.due_at.isoformat(),
                "status": task.status.value,
                "observed_value": task.observed_value,
            }
            for task in runtime.verification.tasks
        ],
        "events": [
            {
                "sequence": event.sequence,
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type.value,
                "code": event.code,
                "payload": _jsonable(event.payload),
            }
            for event in runtime.events.events
        ],
    }
    checkpoint.update(_legacy_virtual_sensor_fields(runtime))
    return checkpoint


def _restore_event_log(runtime: "DigitalTwinRuntime", data: dict[str, Any]) -> None:
    records = [
        EventRecord(
            sequence=int(item["sequence"]),
            timestamp=datetime.fromisoformat(item["timestamp"]),
            event_type=EventType(item["event_type"]),
            code=str(item["code"]),
            payload=dict(item.get("payload", {})),
        )
        for item in data.get("events", [])
    ]
    runtime.events.restore(records)


def _restore_verification(runtime: "DigitalTwinRuntime", data: dict[str, Any]) -> None:
    tasks: list[VerificationTask] = []
    aborted_ids: list[str] = []
    for item in data.get("verification", []):
        status = VerificationStatus(item["status"])
        if status == VerificationStatus.PENDING:
            status = VerificationStatus.ABORTED_BY_MODE_CHANGE
            aborted_ids.append(str(item["verification_id"]))
        tasks.append(
            VerificationTask(
                verification_id=str(item["verification_id"]),
                asset_id=str(item["asset_id"]),
                parameter=str(item["parameter"]),
                baseline=float(item["baseline"]),
                minimum_delta=float(item["minimum_delta"]),
                due_at=datetime.fromisoformat(item["due_at"]),
                status=status,
                observed_value=item.get("observed_value"),
            )
        )
    runtime.verification.restore(tasks)
    for verification_id in aborted_ids:
        runtime.events.append(
            runtime.clock.current,
            EventType.VERIFICATION,
            "VERIFICATION_ABORTED_ON_RESTART",
            {"verification_id": verification_id},
        )


def _restore_session(data: dict[str, Any] | None) -> _OperatingSession | None:
    if data is None:
        return None
    return _OperatingSession(
        origin_mode=OperatingMode(data["origin_mode"]),
        phase=WorkflowPhase(data["phase"]),
        reason=str(data["reason"]),
        scope=tuple(data.get("scope", [])),
        started_at=datetime.fromisoformat(data["started_at"]),
        asset_restore={
            asset_id: _AssetRestoreState(
                owner=CommandOwner(state["owner"]),
                availability=AvailabilityState(state["availability"]),
            )
            for asset_id, state in data.get("asset_restore", {}).items()
        },
        sensor_restore={
            sensor_id: AvailabilityState(availability) if availability is not None else None
            for sensor_id, availability in data.get("sensor_restore", {}).items()
        },
        metadata=dict(data.get("metadata", {})),
    )


def _safe_restart_availability(
    runtime: "DigitalTwinRuntime",
    asset_id: str,
    requested: AvailabilityState,
) -> AvailabilityState:
    source = ActuatorSourceState(runtime.actuators.source_for(asset_id))
    if source == ActuatorSourceState.REAL_ACTUATOR:
        return AvailabilityState.UNKNOWN
    return requested


def _safe_session_restore(
    runtime: "DigitalTwinRuntime",
    session: _OperatingSession,
) -> _OperatingSession:
    session.asset_restore = {
        asset_id: _AssetRestoreState(
            owner=state.owner,
            availability=_safe_restart_availability(
                runtime,
                asset_id,
                state.availability,
            ),
        )
        for asset_id, state in session.asset_restore.items()
    }
    return session


def _enter_restart_gate(
    runtime: "DigitalTwinRuntime",
    saved_session: _OperatingSession | None,
    saved_assets: dict[str, dict[str, Any]],
) -> None:
    now = runtime.clock.current
    if saved_session is None:
        restore = {
            asset_id: _AssetRestoreState(
                owner=CommandOwner(state["owner"]),
                availability=_safe_restart_availability(
                    runtime,
                    asset_id,
                    AvailabilityState(state["availability"]),
                ),
            )
            for asset_id, state in saved_assets.items()
        }
        for asset_id, state in restore.items():
            runtime.actuators.set_availability(asset_id, state.availability)
            runtime.actuators.set_owner(asset_id, CommandOwner.SHUTDOWN)
        runtime.modes.mode = OperatingMode.RECOVERY_SYNC
        runtime.modes.phase = WorkflowPhase.RECOVERY_SYNC
        runtime.modes._session = _OperatingSession(
            origin_mode=OperatingMode.BLACKOUT_RECOVERY,
            phase=WorkflowPhase.RECOVERY_SYNC,
            reason="RUNTIME_RESTART_RECONCILIATION",
            scope=tuple(saved_assets),
            started_at=now,
            asset_restore=restore,
            metadata={
                "power_restored": True,
                "requires_life_support_restart": True,
                "restart_reconciliation": True,
            },
        )
        return

    saved_session = _safe_session_restore(runtime, saved_session)
    if saved_session.origin_mode == OperatingMode.BLACKOUT_RECOVERY:
        for asset_id, state in saved_session.asset_restore.items():
            runtime.actuators.set_availability(asset_id, state.availability)
            runtime.actuators.set_owner(asset_id, CommandOwner.SHUTDOWN)
        saved_session.phase = WorkflowPhase.RECOVERY_SYNC
        saved_session.metadata["power_restored"] = True
        saved_session.metadata["requires_life_support_restart"] = True
        saved_session.metadata["restart_reconciliation"] = True
        runtime.modes.mode = OperatingMode.RECOVERY_SYNC
        runtime.modes.phase = WorkflowPhase.RECOVERY_SYNC
        runtime.modes._session = saved_session
        return

    saved_session.phase = WorkflowPhase.HOLD
    saved_session.metadata["restart_hold"] = True
    runtime.modes.mode = OperatingMode.HOLD
    runtime.modes.phase = WorkflowPhase.HOLD
    runtime.modes._session = saved_session


def _legacy_sensor_state(checkpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        "availability": {
            sensor_id: availability
            for sensor_id, availability in checkpoint.get("sensor_availability", {}).items()
            if availability is not None
        },
        "faults": dict(checkpoint.get("sensor_faults", {})),
        "stuck_values": dict(checkpoint.get("sensor_stuck_values", {})),
    }


def _restore_adapter_state(
    runtime: "DigitalTwinRuntime",
    checkpoint: dict[str, Any],
) -> None:
    saved_sensor_adapter = checkpoint.get("sensor_adapter_id")
    saved_actuator_adapter = checkpoint.get("actuator_adapter_id")
    if saved_sensor_adapter is not None and saved_sensor_adapter != runtime.sensors.adapter_id:
        raise ValueError(
            "checkpoint sensor adapter identity does not match runtime: "
            f"{saved_sensor_adapter} != {runtime.sensors.adapter_id}"
        )
    if (
        saved_actuator_adapter is not None
        and saved_actuator_adapter != runtime.actuators.adapter_id
    ):
        raise ValueError(
            "checkpoint actuator adapter identity does not match runtime: "
            f"{saved_actuator_adapter} != {runtime.actuators.adapter_id}"
        )

    sensor_state = checkpoint.get("sensor_adapter_state")
    if sensor_state is None and hasattr(runtime.sensors, "_faults"):
        sensor_state = _legacy_sensor_state(checkpoint)
    runtime.sensors.restore_state(sensor_state)
    runtime.actuators.restore_state(checkpoint.get("actuator_adapter_state"))


def restore_checkpoint(
    runtime: "DigitalTwinRuntime",
    checkpoint: dict[str, Any],
) -> None:
    if checkpoint.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError("unsupported checkpoint schema version")
    if checkpoint.get("config_version") != runtime.config_version:
        raise ValueError("checkpoint config_version does not match runtime config_version")

    _restore_adapter_state(runtime, checkpoint)
    runtime.run_id = str(checkpoint["run_id"])
    runtime.execution_mode = ExecutionMode(checkpoint["execution_mode"])
    runtime.validation_phase = ValidationPhase(
        checkpoint.get("validation_phase", ValidationPhase.SIMULATION.value)
    )

    clock = checkpoint["clock"]
    runtime.clock.current = datetime.fromisoformat(clock["current"])
    runtime.clock.acceleration = float(clock["acceleration"])
    runtime.clock.paused = bool(clock["paused"])

    truth = checkpoint["pond_truth"]
    runtime.model.state.temperature_c = float(truth["temperature_c"])
    runtime.model.state.dissolved_oxygen_mg_l = float(truth["dissolved_oxygen_mg_l"])
    runtime.model.state.ph = float(truth["ph"])
    runtime.model.state.water_level_pct = float(truth["water_level_pct"])
    runtime.model.state.circulation_flow_l_min = float(truth["circulation_flow_l_min"])

    saved_assets = checkpoint["assets"]
    for asset_id, state in saved_assets.items():
        if asset_id not in runtime.actuators.assets:
            continue
        requested = AvailabilityState(state["availability"])
        runtime.actuators.set_availability(
            asset_id,
            _safe_restart_availability(runtime, asset_id, requested),
        )
        runtime.actuators.set_owner(asset_id, CommandOwner(state["owner"]))
        runtime.actuators.set_effectiveness(asset_id, float(state.get("effectiveness", 1.0)))
        runtime.actuators.assets[asset_id].feedback_on = False

    _restore_event_log(runtime, checkpoint)
    _restore_verification(runtime, checkpoint)
    saved_session = _restore_session(checkpoint.get("operating_session"))
    _enter_restart_gate(runtime, saved_session, saved_assets)

    runtime._last_feedback = runtime.actuators.feedback_map()
    runtime.events.append(
        runtime.clock.current,
        EventType.MODE,
        "RUNTIME_RESTART_RECONCILIATION_REQUIRED",
        {
            "saved_operating_mode": checkpoint.get("operating_mode"),
            "restored_operating_mode": runtime.modes.mode,
            "execution_mode": runtime.execution_mode,
            "validation_phase": runtime.validation_phase,
            "sensor_adapter_id": runtime.sensors.adapter_id,
            "actuator_adapter_id": runtime.actuators.adapter_id,
            "stale_command_replay": False,
            "stale_real_sample_replay": False,
            "stale_real_feedback_replay": False,
        },
    )


class JsonCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, checkpoint: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(checkpoint, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    def read(self) -> dict[str, Any]:
        loaded = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("checkpoint file must contain a JSON object")
        return loaded
