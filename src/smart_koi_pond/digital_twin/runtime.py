from dataclasses import replace
from uuid import uuid4

from smart_koi_pond.actuators.virtual import VirtualActuatorBank
from smart_koi_pond.capabilities.registry import CapabilityRegistry
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
from smart_koi_pond.control.water_management import LowWaterRecoveryManager
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import PondModel
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    BaselineStatus,
    CommandOwner,
    EventType,
    ExecutionMode,
    ModuleInstallationState,
    OperatingMode,
    SystemState,
)
from smart_koi_pond.domain.models import (
    AssetStatus,
    CapabilityProfile,
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
        capability_profile: CapabilityProfile | None = None,
        module_installation: dict[str, ModuleInstallationState | str] | None = None,
        module_enabled: dict[str, bool] | None = None,
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
        self.low_water_recovery = LowWaterRecoveryManager()
        self.modes = OperatingModeManager(self.actuators, self.sensors, self.events)
        self.alarm_incidents = AlarmIncidentManager(self.events)
        self.historian = RuntimeHistorian(historian_path)
        self.publisher = CanonicalRuntimePublisher()
        self.capability_registry = CapabilityRegistry(
            profile=capability_profile,
            module_installation=module_installation,
            module_enabled=module_enabled,
        )
        self._sync_structural_module_state()
        self._last_feedback = self.actuators.feedback_map()

    @property
    def operating_mode(self) -> OperatingMode:
        return self.modes.mode

    def _sync_structural_module_state(self) -> None:
        for module_id, manifest in self.capability_registry.manifests.items():
            config = self.capability_registry.configuration_for(module_id)
            installed = config["installation_state"] == ModuleInstallationState.INSTALLED
            for sensor_id in manifest.sensor_ids:
                override = self.sensors.availability_override(sensor_id)
                if installed:
                    if override == AvailabilityState.UNSUPPORTED:
                        self.sensors.set_availability(sensor_id, None)
                else:
                    self.sensors.set_availability(sensor_id, AvailabilityState.UNSUPPORTED)
            for asset_id in manifest.asset_ids:
                asset = self.actuators.assets.get(asset_id)
                if asset is None:
                    continue
                if installed:
                    if asset.availability == AvailabilityState.UNSUPPORTED:
                        self.actuators.set_availability(asset_id, AvailabilityState.AVAILABLE)
                else:
                    self.actuators.set_availability(asset_id, AvailabilityState.UNSUPPORTED)

    def _registry_snapshot(self, validated):
        return self.capability_registry.evaluate(
            validated=validated,
            actuators=self.actuators,
            feature_flags={
                "auto_top_up": self.policy.low_water_auto_recovery_enabled,
            },
        )

    def _apply_capability(
        self,
        classification: Classification,
        validated,
    ) -> tuple[Classification, CapabilitySummary]:
        capability = assess_capability(self.actuators)
        registry = self._registry_snapshot(validated)
        reasons = list(classification.reasons)
        reasons.extend(
            reason for reason in capability.degraded_reasons if reason not in reasons
        )
        reasons.extend(
            reason for reason in registry.baseline.reasons if reason not in reasons
        )
        state = classification.state
        if capability.critical_capability_lost:
            state = SystemState.FAILSAFE
        elif (
            capability.degraded_reasons
            or registry.baseline.status != BaselineStatus.SATISFIED
        ) and state == SystemState.NORMAL:
            state = SystemState.DEGRADED
        summary = replace(
            capability,
            degraded_reasons=tuple(
                dict.fromkeys((*capability.degraded_reasons, *registry.baseline.reasons))
            ),
            registry=registry,
        )
        return Classification(state, tuple(reasons)), summary

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

    def _intent_is_configured(self, intent: CommandIntent, now) -> bool:
        if self.capability_registry.asset_is_configured(intent.asset_id):
            return True
        self.events.append(
            now,
            EventType.COMMAND,
            "COMMAND_INHIBITED_MODULE_NOT_CONFIGURED",
            {
                "asset_id": intent.asset_id,
                "owner": intent.owner,
                "reason": intent.reason,
            },
        )
        return False

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
        classification, capability = self._apply_capability(classification, validated)

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
        registry = capability.registry
        auto_top_up_available = (
            registry is not None
            and "automation.auto_top_up" in registry.available_capabilities
        )
        water_intents = (
            self.low_water_recovery.plan(
                now=now,
                estimate=estimate,
                operating_mode=self.operating_mode,
                actuators=self.actuators,
                completed_verifications=completed,
                policy=self.policy,
                events=self.events,
            )
            if auto_top_up_available
            else []
        )
        workflow_intents = self.modes.command_intents()
        ordinary_water_intents = [
            intent for intent in water_intents if intent.owner != CommandOwner.SAFETY
        ]
        safety_water_intents = [
            intent for intent in water_intents if intent.owner == CommandOwner.SAFETY
        ]

        all_intents = [
            *auto_intents,
            *ordinary_water_intents,
            *workflow_intents,
            *safety_water_intents,
        ]
        for intent in all_intents:
            if not self._intent_is_configured(intent, now):
                continue
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

            if intent.asset_id == LowWaterRecoveryManager.ASSET_ID:
                self.low_water_recovery.observe_command(
                    command,
                    device_feedback,
                    now,
                    self.events,
                )

        self._last_feedback = self.actuators.feedback_map()

        if self.modes.complete_recovery_if_ready(now, validated):
            classification, capability = self._apply_capability(classification, validated)

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

        top_up_command = commands.get(LowWaterRecoveryManager.ASSET_ID)
        if (
            top_up_command is not None
            and top_up_command.owner == CommandOwner.AUTO
            and top_up_command.accepted
            and top_up_command.final_on
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
                "baseline_status": (
                    capability.registry.baseline.status
                    if capability.registry is not None
                    else None
                ),
            },
        )

        self.alarm_incidents.update(now, classification, completed)

        assets = {}
        for asset_id, asset in self.actuators.assets.items():
            configured = self.capability_registry.asset_is_configured(asset_id)
            assets[asset_id] = AssetStatus(
                asset_id=asset_id,
                owner=asset.owner,
                availability=(asset.availability if configured else AvailabilityState.UNSUPPORTED),
                feedback_on=asset.feedback_on if configured else False,
                effectiveness=asset.effectiveness,
            )

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
            water_recovery=self.low_water_recovery.status(self.policy),
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
        checkpoint["low_water_recovery_state"] = self.low_water_recovery.checkpoint_state()
        checkpoint["capability_registry_state"] = self.capability_registry.checkpoint_state()
        return checkpoint

    def restore_checkpoint(self, checkpoint) -> None:
        restore_runtime_checkpoint(self, checkpoint)
        self.capability_registry.restore_state(checkpoint.get("capability_registry_state"))
        self._sync_structural_module_state()
        self.validation = SensorValidationEngine(self.validation.policy)
        self.alarm_incidents.restore_checkpoint_state(
            checkpoint.get("alarm_incident_state")
        )
        self.low_water_recovery.restore_after_restart(
            checkpoint.get("low_water_recovery_state"),
            now=self.clock.current,
            events=self.events,
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

    def configure_module(
        self,
        module_id: str,
        *,
        installation_state: ModuleInstallationState | str | None = None,
        enabled: bool | None = None,
        actor: str = "engineering",
    ) -> None:
        manifest = self.capability_registry.manifests.get(module_id)
        if manifest is None:
            raise KeyError(f"unknown module: {module_id}")
        if (
            installation_state is not None
            and ModuleInstallationState(installation_state)
            != ModuleInstallationState.INSTALLED
        ):
            running = [
                asset_id
                for asset_id in manifest.asset_ids
                if self.actuators.assets.get(asset_id) is not None
                and self.actuators.assets[asset_id].feedback_on
            ]
            if running:
                raise RuntimeError(
                    "module assets must be safely OFF before removal: " + ", ".join(running)
                )

        before = self.capability_registry.configuration_for(module_id)
        self.capability_registry.configure(
            module_id,
            installation_state=installation_state,
            enabled=enabled,
        )
        self._sync_structural_module_state()
        after = self.capability_registry.configuration_for(module_id)
        self.events.append(
            self.clock.current,
            EventType.CONFIGURATION,
            "MODULE_CONFIGURATION_CHANGED",
            {
                "module_id": module_id,
                "actor": actor,
                "before": before,
                "after": after,
            },
        )

    def _require_structural_capability(self, capability: str) -> None:
        if not self.capability_registry.capability_structurally_enabled(capability):
            raise RuntimeError(f"required capability is not configured: {capability}")

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
        self._require_structural_capability("automation.water_change")
        self.modes.start_water_change(
            reason,
            self.clock.current,
            target_drain_level_pct=target_drain_level_pct,
            target_refill_level_pct=target_refill_level_pct,
        )

    def start_filter_clean(self, service_scope, reason: str) -> None:
        self._require_structural_capability("automation.filter_clean")
        self.modes.start_filter_clean(service_scope, reason, self.clock.current)

    def start_blackout(self, reason: str) -> None:
        self.modes.start_blackout(reason, self.clock.current)

    def restore_power(self) -> None:
        self.modes.restore_power(self.clock.current)

    def request_return_to_auto(self) -> None:
        self.modes.request_return_to_auto(self.clock.current)

    def manual_command(self, asset_id: str, on: bool, reason: str):
        if not self.capability_registry.asset_is_configured(asset_id):
            raise RuntimeError(f"asset module is not configured: {asset_id}")
        asset = self.actuators.assets[asset_id]
        if asset.owner not in {CommandOwner.MANUAL, CommandOwner.MAINTENANCE}:
            raise RuntimeError(f"asset is not under manual ownership: {asset_id}")
        intent = CommandIntent(asset_id, on, asset.owner, reason)
        command, feedback = self._execute_intent(intent, self.clock.current)
        self._last_feedback = self.actuators.feedback_map()
        return command, feedback
