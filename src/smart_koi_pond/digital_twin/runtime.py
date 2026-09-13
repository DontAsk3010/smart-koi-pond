from dataclasses import replace
from uuid import uuid4

from smart_koi_pond.actuators.virtual import VirtualActuatorBank
from smart_koi_pond.control.arbitration import arbitrate
from smart_koi_pond.control.engine import (
    SimulationControlPolicy,
    classify,
    decide,
    estimate_state,
)
from smart_koi_pond.control.operating_modes import OperatingModeManager, assess_capability
from smart_koi_pond.control.validation import SensorValidationEngine
from smart_koi_pond.control.verification import VerificationManager
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import PondModel
from smart_koi_pond.domain.enums import (
    CommandOwner,
    EventType,
    ExecutionMode,
    OperatingMode,
    SystemState,
)
from smart_koi_pond.domain.models import (
    AssetStatus,
    CapabilitySummary,
    Classification,
    CommandIntent,
    RuntimeSnapshot,
)
from smart_koi_pond.events.historian import RuntimeHistorian
from smart_koi_pond.events.lifecycle import AlarmIncidentManager
from smart_koi_pond.events.log import EventLog
from smart_koi_pond.events.publication import CanonicalRuntimePublisher
from smart_koi_pond.persistence.checkpoint import (
    capture_checkpoint as capture_runtime_checkpoint,
)
from smart_koi_pond.persistence.checkpoint import (
    restore_checkpoint as restore_runtime_checkpoint,
)
from smart_koi_pond.sensors.virtual import VirtualSensorSuite


class DigitalTwinRuntime:
    def __init__(
        self,
        model: PondModel,
        policy: SimulationControlPolicy,
        *,
        clock: SimulationClock | None = None,
        run_id: str | None = None,
        config_version: str = "simulation-policy-v1",
        historian_path: str | None = None,
    ) -> None:
        self.model = model
        self.policy = policy
        self.clock = clock or SimulationClock.start()
        self.run_id = run_id or str(uuid4())
        self.config_version = config_version
        self.execution_mode = ExecutionMode.SIMULATION
        self.sensors = VirtualSensorSuite()
        self.validation = SensorValidationEngine()
        self.actuators = VirtualActuatorBank()
        self.events = EventLog()
        self.verification = VerificationManager()
        self.modes = OperatingModeManager(self.actuators, self.sensors, self.events)
        self.alarm_incidents = AlarmIncidentManager(self.events)
        self.historian = RuntimeHistorian(historian_path)
        self.publisher = CanonicalRuntimePublisher()
        self._last_feedback = self.actuators.feedback_map()

    @property
    def operating_mode(self) -> OperatingMode:
        return self.modes.mode

    def _apply_capability(
        self,
        classification: Classification,
    ) -> tuple[Classification, CapabilitySummary]:
        capability = assess_capability(self.actuators)
        reasons = list(classification.reasons)
        reasons.extend(
            reason for reason in capability.degraded_reasons if reason not in reasons
        )
        state = classification.state
        if capability.critical_capability_lost:
            state = SystemState.FAILSAFE
        elif capability.degraded_reasons and state == SystemState.NORMAL:
            state = SystemState.DEGRADED
        return Classification(state, tuple(reasons)), capability

    def _execute_intent(self, intent: CommandIntent, now):
        asset = self.actuators.assets[intent.asset_id]
        command = arbitrate(
            intent,
            asset.availability,
            asset.owner,
            self.operating_mode,
        )
        device_feedback = self.actuators.execute(command, now)
        self.events.append(
            now,
            EventType.COMMAND,
            "COMMAND_ARBITRATED",
            {
                "asset_id": command.asset_id,
                "owner": command.owner,
                "accepted": command.accepted,
                "final_on": command.final_on,
                "reason": command.reason,
            },
        )
        return command, device_feedback

    def tick(self, seconds: float) -> RuntimeSnapshot:
        before = self.clock.current
        self.clock.advance(seconds)
        now = self.clock.current
        simulated_seconds = (now - before).total_seconds()
        self.model.step(simulated_seconds, self.actuators.process_effect_map())

        raw = self.sensors.sample(self.model.state, now)
        validated = self.validation.validate(raw)
        for logical_id, measurement in validated.items():
            if measurement.reasons:
                self.events.append(
                    now,
                    EventType.SENSOR_QUALITY,
                    "SENSOR_VALIDATION_EVIDENCE",
                    {
                        "logical_id": logical_id,
                        "source_sensor_id": measurement.sensor_id,
                        "quality": measurement.quality,
                        "reasons": measurement.reasons,
                    },
                )
        estimate = estimate_state(validated)
        classification = classify(estimate, self.policy)

        self.modes.advance_phase(now, validated)
        classification, capability = self._apply_capability(classification)

        completed = self.verification.evaluate(now, estimate.values)
        for task in completed:
            self.events.append(
                now,
                EventType.VERIFICATION,
                task.status,
                {
                    "verification_id": task.verification_id,
                    "asset_id": task.asset_id,
                    "parameter": task.parameter,
                    "baseline": task.baseline,
                    "observed": task.observed_value,
                },
            )

        commands = {}
        feedback = {}
        auto_intents = decide(estimate, classification, self.policy)
        workflow_intents = self.modes.command_intents()

        for intent in [*auto_intents, *workflow_intents]:
            command, device_feedback = self._execute_intent(intent, now)
            commands[intent.asset_id] = command
            feedback[intent.asset_id] = device_feedback

            prior = self._last_feedback.get(intent.asset_id, False)
            if (
                command.owner == CommandOwner.AUTO
                and command.accepted
                and command.final_on
                and not prior
                and device_feedback.feedback_on
            ):
                task = self.verification.start_for_asset(
                    intent.asset_id,
                    now,
                    estimate.values,
                    self.policy,
                )
                if task is not None:
                    self.events.append(
                        now,
                        EventType.VERIFICATION,
                        "VERIFICATION_STARTED",
                        {
                            "verification_id": task.verification_id,
                            "asset_id": task.asset_id,
                            "parameter": task.parameter,
                        },
                    )

        self._last_feedback = self.actuators.feedback_map()

        if self.modes.complete_recovery_if_ready(now, validated):
            classification, capability = self._apply_capability(classification)

        if classification.state in {SystemState.WATCH, SystemState.EMERGENCY} and any(
            command.owner == CommandOwner.AUTO
            and command.accepted
            and command.final_on
            for command in commands.values()
        ):
            classification = Classification(
                SystemState.CORRECTING,
                classification.reasons,
            )

        self.events.append(
            now,
            EventType.STATE,
            classification.state,
            {
                "reasons": classification.reasons,
                "operating_mode": self.operating_mode,
                "operating_phase": self.modes.phase,
            },
        )

        self.alarm_incidents.update(now, classification, completed)

        assets = {
            asset_id: AssetStatus(
                asset_id=asset_id,
                owner=asset.owner,
                availability=asset.availability,
                feedback_on=asset.feedback_on,
                effectiveness=asset.effectiveness,
            )
            for asset_id, asset in self.actuators.assets.items()
        }

        snapshot = RuntimeSnapshot(
            timestamp=now,
            run_id=self.run_id,
            config_version=self.config_version,
            simulation_paused=self.clock.paused,
            simulation_acceleration=self.clock.acceleration,
            execution_mode=self.execution_mode,
            operating_mode=self.operating_mode,
            operating_status=self.modes.status,
            pond_truth=replace(self.model.state),
            raw_samples=raw,
            validated=validated,
            estimate=estimate,
            classification=classification,
            capability=capability,
            assets=assets,
            commands=commands,
            feedback=feedback,
            verification=list(self.verification.tasks),
            alarms=self.alarm_incidents.snapshot_alarms(),
            incidents=self.alarm_incidents.snapshot_incidents(),
        )
        latest_event = self.events.events[-1].sequence if self.events.events else 0
        self.historian.append(
            run_id=self.run_id,
            event_sequence=latest_event,
            snapshot=snapshot,
        )
        return snapshot

    def capture_checkpoint(self):
        checkpoint = capture_runtime_checkpoint(self)
        checkpoint["alarm_incident_state"] = self.alarm_incidents.checkpoint_state()
        return checkpoint

    def restore_checkpoint(self, checkpoint) -> None:
        restore_runtime_checkpoint(self, checkpoint)
        self.validation = SensorValidationEngine(self.validation.policy)
        self.alarm_incidents.restore_checkpoint_state(
            checkpoint.get("alarm_incident_state")
        )

    def publish(self, snapshot: RuntimeSnapshot, *, after_sequence: int = 0):
        publication = self.publisher.publish(
            run_id=self.run_id,
            snapshot=snapshot,
            event_log=self.events,
            after_sequence=after_sequence,
        )
        publication["historian_latest_frame_sequence"] = self.historian.latest_sequence
        return publication

    def recent_history(self, limit: int = 100):
        return self.historian.recent(limit=limit, run_id=self.run_id)

    def playback_frame(self, frame_sequence: int):
        return self.historian.by_sequence(frame_sequence, run_id=self.run_id)

    def acknowledge_alarm(self, alarm_id: str, actor: str):
        return self.alarm_incidents.acknowledge(
            alarm_id,
            actor,
            self.clock.current,
        )

    def incident_evidence(self, incident_id: str):
        return self.alarm_incidents.evidence_for_incident(incident_id)

    def start_manual_maintenance(
        self,
        scope,
        reason: str,
        *,
        service_locked=(),
    ) -> None:
        self.modes.start_manual_maintenance(
            scope,
            reason,
            self.clock.current,
            service_locked=service_locked,
        )

    def start_sensor_calibration(self, sensor_ids, reason: str) -> None:
        self.modes.start_sensor_calibration(sensor_ids, reason, self.clock.current)

    def start_partial_shutdown(self, asset_ids, reason: str) -> None:
        self.modes.start_partial_shutdown(asset_ids, reason, self.clock.current)

    def start_safe_total_shutdown(
        self,
        reason: str,
        *,
        fish_present: bool = True,
    ) -> None:
        self.modes.start_safe_total_shutdown(
            reason,
            self.clock.current,
            fish_present=fish_present,
        )

    def start_water_change(
        self,
        reason: str,
        *,
        target_drain_level_pct: float,
        target_refill_level_pct: float,
    ) -> None:
        self.modes.start_water_change(
            reason,
            self.clock.current,
            target_drain_level_pct=target_drain_level_pct,
            target_refill_level_pct=target_refill_level_pct,
        )

    def start_filter_clean(self, service_scope, reason: str) -> None:
        self.modes.start_filter_clean(service_scope, reason, self.clock.current)

    def start_blackout(self, reason: str) -> None:
        self.modes.start_blackout(reason, self.clock.current)

    def restore_power(self) -> None:
        self.modes.restore_power(self.clock.current)

    def request_return_to_auto(self) -> None:
        self.modes.request_return_to_auto(self.clock.current)

    def manual_command(self, asset_id: str, on: bool, reason: str):
        asset = self.actuators.assets[asset_id]
        if asset.owner not in {CommandOwner.MANUAL, CommandOwner.MAINTENANCE}:
            raise RuntimeError(f"asset is not under manual ownership: {asset_id}")
        intent = CommandIntent(asset_id, on, asset.owner, reason)
        command, feedback = self._execute_intent(intent, self.clock.current)
        self._last_feedback = self.actuators.feedback_map()
        return command, feedback
