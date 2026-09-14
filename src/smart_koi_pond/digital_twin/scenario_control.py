from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from smart_koi_pond.actuators.virtual import ActuatorFault
from smart_koi_pond.control.validation import PLAUSIBILITY_BOUNDS
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    ActuatorSourceState,
    EventType,
    ExecutionMode,
    SensorSourceState,
    SystemState,
)
from smart_koi_pond.domain.models import RuntimeSnapshot
from smart_koi_pond.sensors.virtual import SensorFault


@dataclass(slots=True)
class ScenarioTrigger:
    action: str
    payload: dict[str, Any]
    trigger_id: str = field(default_factory=lambda: str(uuid4()))
    after_seconds: float | None = None
    sensor_id: str | None = None
    comparison: str | None = None
    threshold: float | None = None
    system_state: SystemState | str | None = None
    one_shot: bool = True
    enabled: bool = True
    fired_count: int = 0


class VirtualScenarioController:
    """Manual and automatic fault/recovery orchestration for the Digital Twin.

    The controller only injects faults/disturbances into simulation state. Real I/O is
    never modified by simulation actions. Runtime reset reuses the governed checkpoint/
    restart path, which starts outputs de-energized and requires recovery reconciliation
    instead of replaying stale commands.
    """

    ENVIRONMENT_ALIASES = {
        "temperature": "temperature_c",
        "do": "dissolved_oxygen_mg_l",
        "ph": "ph",
        "water_level": "water_level_pct",
        "tan": "total_ammonia_nitrogen_mg_l",
        "ammonia": "total_ammonia_nitrogen_mg_l",
        "nitrite": "nitrite_mg_l",
        "nitrate": "nitrate_mg_l",
        "alkalinity": "alkalinity_mg_l_as_caco3",
        "waste_solids": "waste_solids_g",
    }

    def __init__(self, runtime: DigitalTwinRuntime) -> None:
        self.runtime = runtime
        self.started_at = runtime.clock.current
        self._triggers: dict[str, ScenarioTrigger] = {}

    @property
    def triggers(self) -> tuple[ScenarioTrigger, ...]:
        return tuple(self._triggers.values())

    def _event(self, code: str, payload: dict[str, Any]) -> None:
        self.runtime.events.append(
            self.runtime.clock.current,
            EventType.SCENARIO,
            code,
            payload,
        )

    def inject_sensor_fault(
        self,
        sensor_id: str,
        mode: str,
        value: float | None = None,
        *,
        origin: str = "MANUAL",
    ) -> None:
        if self.runtime.sensors.source_for(sensor_id) != SensorSourceState.VIRTUAL_SOURCE:
            raise RuntimeError("simulation sensor faults require a VIRTUAL_SOURCE")
        setter = getattr(self.runtime.sensors, "set_fault", None)
        if setter is None:
            raise RuntimeError("configured sensor adapter does not support fault injection")
        if mode not in {"dropout", "stuck", "drift"}:
            raise ValueError("sensor fault mode must be dropout, stuck, or drift")
        setter(sensor_id, SensorFault(mode, value))
        self._event(
            "SIMULATION_SENSOR_FAULT_INJECTED",
            {
                "sensor_id": sensor_id,
                "mode": mode,
                "value": value,
                "origin": origin,
            },
        )

    def clear_sensor_fault(self, sensor_id: str, *, origin: str = "MANUAL") -> None:
        if self.runtime.sensors.source_for(sensor_id) != SensorSourceState.VIRTUAL_SOURCE:
            raise RuntimeError("simulation sensor repair requires a VIRTUAL_SOURCE")
        setter = getattr(self.runtime.sensors, "set_fault", None)
        if setter is None:
            raise RuntimeError("configured sensor adapter does not support fault injection")
        setter(sensor_id, None)
        self._event(
            "SIMULATION_SENSOR_FAULT_CLEARED",
            {"sensor_id": sensor_id, "origin": origin},
        )

    def inject_actuator_fault(
        self,
        asset_id: str,
        mode: str,
        value: float | None = None,
        *,
        origin: str = "MANUAL",
    ) -> None:
        if self.runtime.actuators.source_for(asset_id) != ActuatorSourceState.VIRTUAL_ACTUATOR:
            raise RuntimeError("simulation actuator faults require a VIRTUAL_ACTUATOR")
        setter = getattr(self.runtime.actuators, "set_fault", None)
        if setter is None:
            raise RuntimeError("configured actuator adapter does not support fault injection")
        setter(asset_id, ActuatorFault(mode, value))
        self.runtime._last_feedback = self.runtime.actuators.feedback_map()
        self._event(
            "SIMULATION_ACTUATOR_FAULT_INJECTED",
            {
                "asset_id": asset_id,
                "mode": mode,
                "value": value,
                "origin": origin,
            },
        )

    def clear_actuator_fault(self, asset_id: str, *, origin: str = "MANUAL") -> None:
        if self.runtime.actuators.source_for(asset_id) != ActuatorSourceState.VIRTUAL_ACTUATOR:
            raise RuntimeError("simulation actuator repair requires a VIRTUAL_ACTUATOR")
        setter = getattr(self.runtime.actuators, "set_fault", None)
        if setter is None:
            raise RuntimeError("configured actuator adapter does not support fault injection")
        setter(asset_id, None)
        self.runtime._last_feedback = self.runtime.actuators.feedback_map()
        self._event(
            "SIMULATION_ACTUATOR_FAULT_CLEARED",
            {"asset_id": asset_id, "origin": origin, "restart_required": False},
        )

    def set_environment_state(
        self,
        parameter: str,
        value: float,
        *,
        origin: str = "MANUAL",
    ) -> None:
        if self.runtime.execution_mode != ExecutionMode.SIMULATION:
            raise RuntimeError("environment disturbance injection requires SIMULATION mode")
        canonical = self.ENVIRONMENT_ALIASES.get(parameter, parameter)
        numeric = float(value)
        if canonical == "waste_solids_g":
            if numeric < 0:
                raise ValueError("waste_solids_g must be non-negative")
        else:
            bounds = PLAUSIBILITY_BOUNDS.get(canonical)
            if bounds is None:
                raise KeyError(parameter)
            if not bounds[0] <= numeric <= bounds[1]:
                raise ValueError(
                    f"{canonical} disturbance must remain within modeled plausibility bounds"
                )
        before = getattr(self.runtime.model.state, canonical)
        self.runtime.model.set_truth(canonical, numeric)
        self._event(
            "SIMULATION_ENVIRONMENT_STATE_CHANGED",
            {
                "parameter": canonical,
                "before": before,
                "after": numeric,
                "origin": origin,
                "authority": "SIMULATION_ENGINEERING_ONLY",
            },
        )

    def safe_runtime_reset(self, *, origin: str = "MANUAL") -> None:
        self._event(
            "SAFE_RUNTIME_RESET_REQUESTED",
            {"origin": origin, "stale_command_replay": False},
        )
        checkpoint = self.runtime.capture_checkpoint()
        self.runtime.restore_checkpoint(checkpoint)
        self._event(
            "SAFE_RUNTIME_RESET_COMPLETE",
            {
                "origin": origin,
                "operating_mode": self.runtime.operating_mode,
                "stale_command_replay": False,
                "faults_preserved": True,
            },
        )

    def schedule(self, trigger: ScenarioTrigger) -> str:
        if trigger.trigger_id in self._triggers:
            raise ValueError(f"duplicate trigger_id: {trigger.trigger_id}")
        if trigger.after_seconds is not None and trigger.after_seconds < 0:
            raise ValueError("after_seconds must be non-negative")
        if trigger.comparison not in {None, "below", "above"}:
            raise ValueError("comparison must be below or above")
        if trigger.sensor_id is not None:
            if trigger.comparison is None or trigger.threshold is None:
                raise ValueError("sensor trigger requires comparison and threshold")
        if trigger.system_state is not None:
            trigger.system_state = SystemState(trigger.system_state)
        self._triggers[trigger.trigger_id] = trigger
        self._event(
            "SIMULATION_TRIGGER_ARMED",
            {
                "trigger_id": trigger.trigger_id,
                "action": trigger.action,
                "after_seconds": trigger.after_seconds,
                "sensor_id": trigger.sensor_id,
                "comparison": trigger.comparison,
                "threshold": trigger.threshold,
                "system_state": trigger.system_state,
            },
        )
        return trigger.trigger_id

    def cancel(self, trigger_id: str) -> None:
        trigger = self._triggers.pop(trigger_id)
        self._event(
            "SIMULATION_TRIGGER_CANCELLED",
            {"trigger_id": trigger.trigger_id, "action": trigger.action},
        )

    def _elapsed_seconds(self, now: datetime) -> float:
        return max(0.0, (now - self.started_at).total_seconds())

    def _trigger_matches(self, trigger: ScenarioTrigger, snapshot: RuntimeSnapshot) -> bool:
        if not trigger.enabled or (trigger.one_shot and trigger.fired_count > 0):
            return False
        checks: list[bool] = []
        if trigger.after_seconds is not None:
            checks.append(self._elapsed_seconds(snapshot.timestamp) >= trigger.after_seconds)
        if trigger.sensor_id is not None:
            measurement = snapshot.validated.get(trigger.sensor_id)
            if measurement is None or measurement.value is None:
                return False
            if trigger.comparison == "below":
                checks.append(measurement.value < float(trigger.threshold))
            else:
                checks.append(measurement.value > float(trigger.threshold))
        if trigger.system_state is not None:
            checks.append(snapshot.classification.state == SystemState(trigger.system_state))
        return bool(checks) and all(checks)

    def _execute_action(self, trigger: ScenarioTrigger) -> None:
        action = trigger.action
        payload = trigger.payload
        if action == "inject_sensor_fault":
            self.inject_sensor_fault(
                str(payload["sensor_id"]),
                str(payload["mode"]),
                payload.get("value"),
                origin="AUTOMATIC",
            )
        elif action == "clear_sensor_fault":
            self.clear_sensor_fault(str(payload["sensor_id"]), origin="AUTOMATIC")
        elif action == "inject_actuator_fault":
            self.inject_actuator_fault(
                str(payload["asset_id"]),
                str(payload["mode"]),
                payload.get("value"),
                origin="AUTOMATIC",
            )
        elif action == "clear_actuator_fault":
            self.clear_actuator_fault(str(payload["asset_id"]), origin="AUTOMATIC")
        elif action == "set_environment_state":
            self.set_environment_state(
                str(payload["parameter"]),
                float(payload["value"]),
                origin="AUTOMATIC",
            )
        elif action == "start_blackout":
            self.runtime.start_blackout(str(payload.get("reason", "AUTOMATIC_POWER_LOSS")))
        elif action == "restore_power":
            self.runtime.restore_power()
        elif action == "safe_runtime_reset":
            self.safe_runtime_reset(origin="AUTOMATIC")
        else:
            raise ValueError(f"unsupported automatic scenario action: {action}")

    def evaluate(self, snapshot: RuntimeSnapshot) -> tuple[str, ...]:
        fired: list[str] = []
        for trigger in tuple(self._triggers.values()):
            if not self._trigger_matches(trigger, snapshot):
                continue
            self._execute_action(trigger)
            trigger.fired_count += 1
            fired.append(trigger.trigger_id)
            self._event(
                "SIMULATION_TRIGGER_FIRED",
                {
                    "trigger_id": trigger.trigger_id,
                    "action": trigger.action,
                    "fired_count": trigger.fired_count,
                },
            )
        return tuple(fired)
