from smart_koi_pond.actuators.virtual import VirtualActuatorBank
from smart_koi_pond.control.arbitration import arbitrate
from smart_koi_pond.control.engine import (
    SimulationControlPolicy,
    classify,
    decide,
    estimate_state,
)
from smart_koi_pond.control.validation import validate_all
from smart_koi_pond.control.verification import VerificationManager
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import PondModel
from smart_koi_pond.domain.enums import EventType, ExecutionMode, OperatingMode, SystemState
from smart_koi_pond.domain.models import RuntimeSnapshot
from smart_koi_pond.events.log import EventLog
from smart_koi_pond.sensors.virtual import VirtualSensorSuite


class DigitalTwinRuntime:
    def __init__(
        self,
        model: PondModel,
        policy: SimulationControlPolicy,
        *,
        clock: SimulationClock | None = None,
    ) -> None:
        self.model = model
        self.policy = policy
        self.clock = clock or SimulationClock.start()
        self.execution_mode = ExecutionMode.SIMULATION
        self.operating_mode = OperatingMode.NORMAL_AUTO
        self.sensors = VirtualSensorSuite()
        self.actuators = VirtualActuatorBank()
        self.events = EventLog()
        self.verification = VerificationManager()
        self._last_feedback = self.actuators.feedback_map()

    def tick(self, seconds: float) -> RuntimeSnapshot:
        self.clock.advance(seconds)
        now = self.clock.current
        self.model.step(seconds, self.actuators.feedback_map())

        raw = self.sensors.sample(self.model.state, now)
        validated = validate_all(raw)
        estimate = estimate_state(validated)
        classification = classify(estimate, self.policy)

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
        for intent in decide(estimate, classification, self.policy):
            asset = self.actuators.assets[intent.asset_id]
            command = arbitrate(
                intent,
                asset.availability,
                asset.owner,
                self.operating_mode,
            )
            commands[intent.asset_id] = command
            device_feedback = self.actuators.execute(command, now)
            feedback[intent.asset_id] = device_feedback
            self.events.append(
                now,
                EventType.COMMAND,
                "COMMAND_ARBITRATED",
                {
                    "asset_id": command.asset_id,
                    "accepted": command.accepted,
                    "final_on": command.final_on,
                    "reason": command.reason,
                },
            )

            prior = self._last_feedback.get(intent.asset_id, False)
            if command.accepted and command.final_on and not prior and device_feedback.feedback_on:
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

        if classification.state in {SystemState.WATCH, SystemState.EMERGENCY} and any(
            command.accepted and command.final_on for command in commands.values()
        ):
            classification = type(classification)(SystemState.CORRECTING, classification.reasons)

        self.events.append(
            now,
            EventType.STATE,
            classification.state,
            {"reasons": classification.reasons},
        )

        return RuntimeSnapshot(
            timestamp=now,
            execution_mode=self.execution_mode,
            operating_mode=self.operating_mode,
            pond_truth=self.model.state,
            raw_samples=raw,
            validated=validated,
            estimate=estimate,
            classification=classification,
            commands=commands,
            feedback=feedback,
            verification=list(self.verification.tasks),
        )
