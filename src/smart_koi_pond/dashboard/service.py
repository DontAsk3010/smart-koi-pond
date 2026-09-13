import math
import threading
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from smart_koi_pond.digital_twin.hydraulics import PondDesignProfile
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.digital_twin.scenario_control import ScenarioTrigger, VirtualScenarioController
from smart_koi_pond.domain.enums import EventType
from smart_koi_pond.domain.models import RuntimeSnapshot
from smart_koi_pond.domain.process_visual import project_process_visual

_ROLE_LEVEL = {"viewer": 0, "operator": 1, "engineering": 2}
_ACTION_LEVEL = {
    "pause": 1,
    "resume": 1,
    "step": 1,
    "return_to_auto": 1,
    "restore_power": 1,
    "acknowledge_alarm": 1,
    "set_acceleration": 2,
    "start_blackout": 2,
    "start_manual_maintenance": 2,
    "start_sensor_calibration": 2,
    "start_partial_shutdown": 2,
    "start_safe_total_shutdown": 2,
    "start_water_change": 2,
    "start_filter_clean": 2,
    "manual_command": 2,
    "inject_sensor_fault": 2,
    "clear_sensor_fault": 2,
    "inject_actuator_fault": 2,
    "clear_actuator_fault": 2,
    "safe_runtime_reset": 2,
    "schedule_scenario_trigger": 2,
    "cancel_scenario_trigger": 2,
    "configure_module": 2,
    "configure_design_profile": 2,
    "set_hydraulic_restriction": 2,
}


def _wire(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _wire(asdict(value))
    if isinstance(value, dict):
        return {str(key): _wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(item) for item in value]
    return value


def _with_process_visual(snapshot: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(snapshot)
    enriched["process_visual"] = _wire(project_process_visual(snapshot))
    return enriched


class RuntimeApplicationService:
    """Thread-safe application boundary around the canonical Digital Twin runtime."""

    def __init__(self, runtime: DigitalTwinRuntime, *, step_seconds: float = 1.0) -> None:
        if step_seconds <= 0:
            raise ValueError("step_seconds must be positive")
        self.runtime = runtime
        self.step_seconds = step_seconds
        self.scenarios = VirtualScenarioController(runtime)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_snapshot = runtime.tick(0.0)

    @property
    def last_snapshot(self) -> RuntimeSnapshot:
        with self._lock:
            return self._last_snapshot

    def _tick_and_evaluate(self, seconds: float) -> RuntimeSnapshot:
        snapshot = self.runtime.tick(seconds)
        if self.scenarios.evaluate(snapshot):
            snapshot = self.runtime.tick(0.0)
        return snapshot

    def step(self, seconds: float | None = None) -> RuntimeSnapshot:
        with self._lock:
            self._last_snapshot = self._tick_and_evaluate(
                self.step_seconds if seconds is None else seconds
            )
            return self._last_snapshot

    def publication(self, *, after_sequence: int = 0) -> dict[str, Any]:
        with self._lock:
            publication = self.runtime.publish(
                self._last_snapshot,
                after_sequence=after_sequence,
            )
            publication["snapshot"]["process_visual"] = _wire(
                project_process_visual(self._last_snapshot)
            )
            publication["process_visual_schema_version"] = 1
            publication["scenario_triggers"] = _wire(self.scenarios.triggers)
            return publication

    def history(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            frames = []
            for frame in self.runtime.recent_history(limit):
                wired = _wire(frame)
                wired["snapshot"] = _with_process_visual(wired["snapshot"])
                frames.append(wired)
            return frames

    def playback(self, frame_sequence: int) -> dict[str, Any]:
        with self._lock:
            frame = _wire(self.runtime.playback_frame(frame_sequence))
            frame["snapshot"] = _with_process_visual(frame["snapshot"])
            return frame

    def incident_evidence(self, incident_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [_wire(event) for event in self.runtime.incident_evidence(incident_id)]

    def _require_role(self, action: str, role: str) -> None:
        required = _ACTION_LEVEL.get(action)
        if required is None:
            raise ValueError(f"unsupported command action: {action}")
        actual = _ROLE_LEVEL.get(role)
        if actual is None:
            raise PermissionError(f"unknown role: {role}")
        if actual < required:
            self.runtime.events.append(
                self.runtime.clock.current,
                EventType.SCENARIO,
                "UI_COMMAND_REJECTED",
                {"action": action, "role": role, "reason": "INSUFFICIENT_ROLE"},
            )
            raise PermissionError(f"role {role} is not authorized for {action}")

    def _single_step_while_paused(self, simulation_seconds: float) -> None:
        if not math.isfinite(simulation_seconds) or simulation_seconds <= 0:
            raise ValueError("step seconds must be a positive finite number")
        if not self.runtime.clock.paused:
            raise RuntimeError("single-step requires the simulation to be paused")
        acceleration = self.runtime.clock.acceleration
        self.runtime.clock.advance(simulation_seconds / acceleration, force=True)
        self.runtime.model.step(
            simulation_seconds,
            self.runtime.actuators.process_effect_map(),
        )

    def command(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        *,
        role: str = "viewer",
    ) -> RuntimeSnapshot:
        data = payload or {}
        with self._lock:
            self._require_role(action, role)

            if action == "pause":
                self.runtime.clock.pause()
            elif action == "resume":
                self.runtime.clock.resume()
            elif action == "step":
                self._single_step_while_paused(
                    float(data.get("seconds", self.step_seconds))
                )
            elif action == "set_acceleration":
                value = float(data["value"])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError("acceleration must be a positive finite number")
                self.runtime.clock.acceleration = value
            elif action == "return_to_auto":
                self.runtime.request_return_to_auto()
            elif action == "restore_power":
                self.runtime.restore_power()
            elif action == "acknowledge_alarm":
                actor = str(data.get("actor", role))
                self.runtime.acknowledge_alarm(str(data["alarm_id"]), actor)
            elif action == "start_blackout":
                self.runtime.start_blackout(str(data.get("reason", "SIMULATED_POWER_LOSS")))
            elif action == "start_manual_maintenance":
                self.runtime.start_manual_maintenance(
                    data.get("scope", []),
                    str(data.get("reason", "UI_MAINTENANCE")),
                    service_locked=data.get("service_locked", []),
                )
            elif action == "start_sensor_calibration":
                self.runtime.start_sensor_calibration(
                    data.get("sensor_ids", []),
                    str(data.get("reason", "UI_SENSOR_CALIBRATION")),
                )
            elif action == "start_partial_shutdown":
                self.runtime.start_partial_shutdown(
                    data.get("asset_ids", []),
                    str(data.get("reason", "UI_PARTIAL_SHUTDOWN")),
                )
            elif action == "start_safe_total_shutdown":
                self.runtime.start_safe_total_shutdown(
                    str(data.get("reason", "UI_SAFE_TOTAL_SHUTDOWN")),
                    fish_present=bool(data.get("fish_present", True)),
                )
            elif action == "start_water_change":
                self.runtime.start_water_change(
                    str(data.get("reason", "UI_WATER_CHANGE")),
                    target_drain_level_pct=float(data["target_drain_level_pct"]),
                    target_refill_level_pct=float(data["target_refill_level_pct"]),
                )
            elif action == "start_filter_clean":
                self.runtime.start_filter_clean(
                    data.get("service_scope", []),
                    str(data.get("reason", "UI_FILTER_CLEAN")),
                )
            elif action == "manual_command":
                self.runtime.manual_command(
                    str(data["asset_id"]),
                    bool(data["on"]),
                    str(data.get("reason", "UI_MANUAL_COMMAND")),
                )
            elif action == "inject_sensor_fault":
                self.scenarios.inject_sensor_fault(
                    str(data["sensor_id"]),
                    str(data["mode"]),
                    data.get("value"),
                )
            elif action == "clear_sensor_fault":
                self.scenarios.clear_sensor_fault(str(data["sensor_id"]))
            elif action == "inject_actuator_fault":
                self.scenarios.inject_actuator_fault(
                    str(data["asset_id"]),
                    str(data["mode"]),
                    data.get("value"),
                )
            elif action == "clear_actuator_fault":
                self.scenarios.clear_actuator_fault(str(data["asset_id"]))
            elif action == "safe_runtime_reset":
                self.scenarios.safe_runtime_reset()
            elif action == "schedule_scenario_trigger":
                trigger = ScenarioTrigger(
                    action=str(data["scenario_action"]),
                    payload=dict(data.get("scenario_payload", {})),
                    trigger_id=str(data.get("trigger_id") or uuid4()),
                    after_seconds=(
                        float(data["after_seconds"])
                        if data.get("after_seconds") is not None
                        else None
                    ),
                    sensor_id=(
                        str(data["sensor_id"]) if data.get("sensor_id") is not None else None
                    ),
                    comparison=(
                        str(data["comparison"])
                        if data.get("comparison") is not None
                        else None
                    ),
                    threshold=(
                        float(data["threshold"])
                        if data.get("threshold") is not None
                        else None
                    ),
                    system_state=data.get("system_state"),
                    one_shot=bool(data.get("one_shot", True)),
                )
                self.scenarios.schedule(trigger)
            elif action == "cancel_scenario_trigger":
                self.scenarios.cancel(str(data["trigger_id"]))
            elif action == "configure_module":
                self.runtime.configure_module(
                    str(data["module_id"]),
                    installation_state=data.get("installation_state"),
                    enabled=data.get("enabled"),
                    actor=str(data.get("actor", role)),
                )
            elif action == "configure_design_profile":
                self.runtime.configure_design_profile(
                    PondDesignProfile.from_dict(data["profile"]),
                    actor=str(data.get("actor", role)),
                )
            elif action == "set_hydraulic_restriction":
                self.runtime.set_hydraulic_restriction(
                    str(data["route_id"]),
                    float(data["throughput_factor"]),
                    actor=str(data.get("actor", role)),
                )

            self.runtime.events.append(
                self.runtime.clock.current,
                EventType.SCENARIO,
                "UI_COMMAND_ACCEPTED",
                {"action": action, "role": role},
            )
            self._last_snapshot = self._tick_and_evaluate(0.0)
            return self._last_snapshot

    def start_background(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._background_loop,
                name="smart-koi-pond-runtime",
                daemon=True,
            )
            self._thread.start()

    def stop_background(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=max(2.0, self.step_seconds * 2.0))

    def _background_loop(self) -> None:
        while not self._stop.wait(self.step_seconds):
            self.step(self.step_seconds)
