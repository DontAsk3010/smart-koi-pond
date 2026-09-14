from __future__ import annotations

from collections.abc import Callable
from typing import Any

from smart_koi_pond.control.validation import SensorValidationEngine
from smart_koi_pond.digital_twin.biology import BiologicalProcessProfile
from smart_koi_pond.digital_twin.filtration import MechanicalFiltrationProfile
from smart_koi_pond.digital_twin.hydraulics import PondDesignProfile
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.digital_twin.water_exchange import SourceWaterProfile
from smart_koi_pond.domain.enums import (
    ActuatorSourceState,
    AvailabilityState,
    EventType,
    ExecutionMode,
    ModuleInstallationState,
    SensorSourceState,
    VerificationStatus,
)
from smart_koi_pond.events.historian import RuntimeHistorian
from smart_koi_pond.governance.reconfiguration import (
    ConfigurationTransaction,
    GovernedChangeController,
    RecoveryPlan,
    RecoveryState,
    RecoverySupervisor,
)


class _GovernedRuntimeHistorian(RuntimeHistorian):
    """Historian that snapshots governance state before serializing a runtime frame."""

    def __init__(self, runtime: ProductionDigitalTwinRuntime, path: str | None) -> None:
        self.runtime = runtime
        super().__init__(path)

    def append(self, *, run_id: str, event_sequence: int, snapshot: Any) -> dict[str, Any]:
        snapshot.configuration_control = self.runtime.change_control.snapshot()
        snapshot.recovery_control = self.runtime.recovery_supervisor.snapshot()
        return super().append(
            run_id=run_id,
            event_sequence=event_sequence,
            snapshot=snapshot,
        )


class ProductionDigitalTwinRuntime(DigitalTwinRuntime):
    """Production-lineage runtime with Handbook V0.16 governed change/recovery.

    The class deliberately reuses DigitalTwinRuntime control, arbitration, verification,
    alarm, persistence and adapter contracts. It does not create a second control engine.
    """

    CIRCULATION_RECOVERY_PLAN_ID = "circulation-fallback-v1"

    def __init__(
        self,
        *args: Any,
        software_version: str = "smart-koi-pond-runtime-v0.16",
        **kwargs: Any,
    ) -> None:
        historian_path = kwargs.get("historian_path")
        super().__init__(*args, **kwargs)
        self.change_control = GovernedChangeController(
            initial_configuration_version=self.config_version,
            initial_software_version=software_version,
            event_sink=self._configuration_event,
        )
        self.recovery_supervisor = RecoverySupervisor(event_sink=self._recovery_event)
        self.recovery_supervisor.register(
            RecoveryPlan(
                plan_id=self.CIRCULATION_RECOVERY_PLAN_ID,
                revision="1",
                trigger_code="PRIMARY_CIRCULATION_LOSS",
                affected_assets=("main_pump", "backup_pump"),
                allowed_actions=("START_BACKUP_PUMP",),
                retry_limit=2,
                cooldown_seconds=60.0,
                verification_asset_id="backup_pump",
            )
        )
        self._install_model_configuration_hooks()
        self.historian = _GovernedRuntimeHistorian(self, historian_path)

    def _install_model_configuration_hooks(self) -> None:
        """Govern direct model mutations without replacing the accepted model object.

        Existing source-water/mass-balance contracts rely on the concrete model type.
        Instance-level hooks preserve that type while routing material mutation through
        the V0.16 transaction boundary.
        """
        self._original_configure_biological_profile = (
            self.model.configure_biological_profile
        )
        self._original_configure_mechanical_filtration_profile = (
            self.model.configure_mechanical_filtration_profile
        )
        self._original_configure_source_water_profile = getattr(
            self.model,
            "configure_source_water_profile",
            None,
        )
        setattr(
            self.model,
            "configure_biological_profile",
            self._governed_configure_biological_profile,
        )
        setattr(
            self.model,
            "configure_mechanical_filtration_profile",
            self._governed_configure_mechanical_filtration_profile,
        )
        if self._original_configure_source_water_profile is not None:
            setattr(
                self.model,
                "configure_source_water_profile",
                self._governed_configure_source_water_profile,
            )

    def _governed_configure_biological_profile(
        self,
        profile: BiologicalProcessProfile,
    ) -> None:
        before = self.model.biological_snapshot()
        self._apply_governed_configuration(
            scope="BIOLOGICAL_PROCESS_PROFILE",
            actor="engineering",
            reason="BIOLOGICAL_PROCESS_PROFILE_CHANGE",
            before=before,
            after=profile.to_dict(),
            preflight=lambda: (
                ()
                if self.model.hydraulics is not None
                else ("HYDRAULIC_PROFILE_REQUIRED",)
            ),
            apply=lambda: self._original_configure_biological_profile(profile),
        )

    def _governed_configure_mechanical_filtration_profile(
        self,
        profile: MechanicalFiltrationProfile,
    ) -> None:
        before = self.model.mechanical_filtration_snapshot()

        def preflight() -> tuple[str, ...]:
            if self.model.hydraulics is None:
                return ("HYDRAULIC_PROFILE_REQUIRED",)
            if not self.model.hydraulics.has_route(profile.filtered_route_id):
                return (f"FILTER_ROUTE_NOT_CONFIGURED:{profile.filtered_route_id}",)
            return ()

        self._apply_governed_configuration(
            scope="MECHANICAL_FILTRATION_PROFILE",
            actor="engineering",
            reason="MECHANICAL_FILTRATION_PROFILE_CHANGE",
            before=before,
            after=profile.to_dict(),
            preflight=preflight,
            apply=lambda: self._original_configure_mechanical_filtration_profile(profile),
        )

    def _governed_configure_source_water_profile(
        self,
        profile: SourceWaterProfile,
    ) -> None:
        configure = self._original_configure_source_water_profile
        if configure is None:
            raise RuntimeError("runtime model does not support source-water mixing")
        snapshot = getattr(self.model, "source_water_snapshot", None)
        before = snapshot() if snapshot is not None else {"configured": False}
        self._apply_governed_configuration(
            scope="SOURCE_WATER_PROFILE",
            actor="engineering",
            reason="SOURCE_WATER_PROFILE_CHANGE",
            before=before,
            after=profile.to_dict(),
            preflight=lambda: (),
            apply=lambda: configure(profile),
        )

    def _configuration_event(self, code: str, payload: dict[str, Any]) -> None:
        self.events.append(
            self.clock.current,
            EventType.CONFIGURATION,
            code,
            payload,
        )

    def _recovery_event(self, code: str, payload: dict[str, Any]) -> None:
        self.events.append(
            self.clock.current,
            EventType.RECOVERY,
            code,
            payload,
        )

    def _capture_mutable_configuration_state(self) -> dict[str, Any]:
        return {
            "execution_mode": self.execution_mode.value,
            "sensor_adapter_state": self.sensors.checkpoint_state(),
            "actuator_adapter_state": self.actuators.checkpoint_state(),
            "model_engineering_state": self.model.checkpoint_state(),
            "capability_registry_state": self.capability_registry.checkpoint_state(),
        }

    def _restore_mutable_configuration_state(self, state: dict[str, Any]) -> None:
        self.execution_mode = ExecutionMode(state["execution_mode"])
        self.sensors.restore_state(state.get("sensor_adapter_state"))
        self.actuators.restore_state(state.get("actuator_adapter_state"))
        self.model.restore_engineering_state(state.get("model_engineering_state"))
        self.capability_registry.restore_state(state.get("capability_registry_state"))
        self._sync_structural_module_state()
        self._validate_io_contract(self.execution_mode)
        self.validation = SensorValidationEngine(self.validation.policy)
        self._last_feedback = self.actuators.feedback_map()

    def _apply_governed_configuration(
        self,
        *,
        scope: str,
        actor: str,
        reason: str,
        before: dict[str, Any],
        after: dict[str, Any],
        preflight: Callable[[], tuple[str, ...] | list[str] | None],
        apply: Callable[[], None],
        verify: Callable[[], bool] | None = None,
    ) -> ConfigurationTransaction:
        rollback_state = self._capture_mutable_configuration_state()
        return self.change_control.apply_configuration(
            scope=scope,
            actor=actor,
            reason=reason,
            before=before,
            after=after,
            now=self.clock.current,
            preflight=preflight,
            apply=apply,
            rollback=lambda: self._restore_mutable_configuration_state(rollback_state),
            verify=verify,
        )

    def set_execution_mode(
        self,
        mode: ExecutionMode | str,
        *,
        actor: str = "engineering",
    ) -> None:
        target = ExecutionMode(mode)
        if target == self.execution_mode:
            return
        before = {"execution_mode": self.execution_mode.value}
        self._apply_governed_configuration(
            scope="EXECUTION_MODE",
            actor=actor,
            reason="EXECUTION_MODE_CHANGE",
            before=before,
            after={"execution_mode": target.value},
            preflight=lambda: self._execution_mode_preflight(target),
            apply=lambda: super(ProductionDigitalTwinRuntime, self).set_execution_mode(
                target, actor=actor
            ),
        )

    def _execution_mode_preflight(self, target: ExecutionMode) -> tuple[str, ...]:
        try:
            self._validate_io_contract(target)
        except Exception as exc:
            return (str(exc),)
        return ()

    def configure_sensor_source(
        self,
        sensor_id: str,
        source: SensorSourceState | str,
        *,
        actor: str = "engineering",
    ) -> None:
        target = SensorSourceState(source)
        before_value = SensorSourceState(self.sensors.source_for(sensor_id))
        if target == before_value:
            return

        def preflight() -> tuple[str, ...]:
            if (
                self.execution_mode == ExecutionMode.SIMULATION
                and target == SensorSourceState.REAL_SOURCE
            ):
                return ("REAL_SOURCE_CANNOT_BE_ENABLED_IN_SIMULATION",)
            return ()

        self._apply_governed_configuration(
            scope=f"SENSOR_SOURCE:{sensor_id}",
            actor=actor,
            reason="SENSOR_SOURCE_CHANGE",
            before={"sensor_id": sensor_id, "source": before_value.value},
            after={"sensor_id": sensor_id, "source": target.value},
            preflight=preflight,
            apply=lambda: super(ProductionDigitalTwinRuntime, self).configure_sensor_source(
                sensor_id, target, actor=actor
            ),
        )

    def configure_actuator_source(
        self,
        asset_id: str,
        source: ActuatorSourceState | str,
        *,
        actor: str = "engineering",
    ) -> None:
        target = ActuatorSourceState(source)
        before_value = ActuatorSourceState(self.actuators.source_for(asset_id))
        if target == before_value:
            return

        def preflight() -> tuple[str, ...]:
            if (
                self.execution_mode == ExecutionMode.SIMULATION
                and target == ActuatorSourceState.REAL_ACTUATOR
            ):
                return ("REAL_ACTUATOR_CANNOT_BE_ENABLED_IN_SIMULATION",)
            return ()

        self._apply_governed_configuration(
            scope=f"ACTUATOR_SOURCE:{asset_id}",
            actor=actor,
            reason="ACTUATOR_SOURCE_CHANGE",
            before={"asset_id": asset_id, "source": before_value.value},
            after={"asset_id": asset_id, "source": target.value},
            preflight=preflight,
            apply=lambda: super(ProductionDigitalTwinRuntime, self).configure_actuator_source(
                asset_id, target, actor=actor
            ),
        )

    def configure_design_profile(
        self,
        profile: PondDesignProfile,
        *,
        actor: str = "engineering",
    ) -> None:
        before = self.model.design_profile_snapshot()

        def preflight() -> tuple[str, ...]:
            filtration = self.model.filtration
            if filtration is None:
                return ()
            route_ids = {route.route_id for route in profile.routes}
            required = filtration.profile.filtered_route_id
            if required not in route_ids:
                return (f"ACTIVE_FILTER_ROUTE_WOULD_BE_REMOVED:{required}",)
            return ()

        self._apply_governed_configuration(
            scope="POND_DESIGN_PROFILE",
            actor=actor,
            reason="POND_DESIGN_PROFILE_CHANGE",
            before=before,
            after=profile.to_dict(),
            preflight=preflight,
            apply=lambda: super(ProductionDigitalTwinRuntime, self).configure_design_profile(
                profile, actor=actor
            ),
        )

    def set_hydraulic_restriction(
        self,
        route_id: str,
        throughput_factor: float,
        *,
        actor: str = "engineering",
    ) -> None:
        if self.model.hydraulics is None:
            before_value = None
        else:
            before_value = self.model.hydraulics.route_restriction(route_id)

        def preflight() -> tuple[str, ...]:
            if self.model.hydraulics is None:
                return ("HYDRAULIC_PROFILE_REQUIRED",)
            if not self.model.hydraulics.has_route(route_id):
                return (f"UNKNOWN_HYDRAULIC_ROUTE:{route_id}",)
            if not 0.0 <= float(throughput_factor) <= 1.0:
                return ("THROUGHPUT_FACTOR_OUT_OF_RANGE",)
            return ()

        self._apply_governed_configuration(
            scope=f"HYDRAULIC_RESTRICTION:{route_id}",
            actor=actor,
            reason="HYDRAULIC_ROUTE_RESTRICTION_CHANGE",
            before={"route_id": route_id, "throughput_factor": before_value},
            after={"route_id": route_id, "throughput_factor": float(throughput_factor)},
            preflight=preflight,
            apply=lambda: super(ProductionDigitalTwinRuntime, self).set_hydraulic_restriction(
                route_id, throughput_factor, actor=actor
            ),
        )

    def configure_module(
        self,
        module_id: str,
        *,
        installation_state: ModuleInstallationState | str | None = None,
        enabled: bool | None = None,
        actor: str = "engineering",
    ) -> None:
        before = self.capability_registry.configuration_for(module_id)

        def preflight() -> tuple[str, ...]:
            manifest = self.capability_registry.manifests.get(module_id)
            if manifest is None:
                return (f"UNKNOWN_MODULE:{module_id}",)
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
                    return ("MODULE_ASSETS_NOT_SAFE_OFF:" + ",".join(running),)
            return ()

        after = dict(before)
        if installation_state is not None:
            after["installation_state"] = ModuleInstallationState(installation_state).value
        if enabled is not None:
            after["enabled"] = bool(enabled)
        self._apply_governed_configuration(
            scope=f"MODULE:{module_id}",
            actor=actor,
            reason="MODULE_CONFIGURATION_CHANGE",
            before=before,
            after=after,
            preflight=preflight,
            apply=lambda: super(ProductionDigitalTwinRuntime, self).configure_module(
                module_id,
                installation_state=installation_state,
                enabled=enabled,
                actor=actor,
            ),
        )

    def stage_software_update(
        self,
        candidate_software_version: str,
        *,
        actor: str = "engineering",
        reason: str = "SOFTWARE_UPDATE",
        compatibility_errors: tuple[str, ...] | list[str] = (),
    ):
        return self.change_control.stage_software_update(
            candidate_software_version,
            actor=actor,
            reason=reason,
            now=self.clock.current,
            compatibility_errors=compatibility_errors,
        )

    def activate_staged_software_update(
        self,
        *,
        executor: Callable[[str], None],
        rollback_executor: Callable[[str], None],
        verify: Callable[[], bool],
    ):
        return self.change_control.activate_staged_software_update(
            executor=executor,
            rollback_executor=rollback_executor,
            verify=verify,
            now=self.clock.current,
        )

    def _process_circulation_recovery(self, snapshot: Any) -> bool:
        before = self.recovery_supervisor.snapshot()
        now = snapshot.timestamp
        backup_command = snapshot.commands.get("backup_pump")
        main_asset = snapshot.assets.get("main_pump")
        main_failed = (
            main_asset is not None and main_asset.availability == AvailabilityState.FAILED
        )
        if self.recovery_supervisor.active is None and (
            main_failed or backup_command is not None
        ):
            self.recovery_supervisor.detect(
                self.CIRCULATION_RECOVERY_PLAN_ID,
                now=now,
                reason=("MAIN_PUMP_FAILED" if main_failed else "LOW_CIRCULATION_FLOW"),
            )

        record = self.recovery_supervisor.active
        if record is None:
            return before != self.recovery_supervisor.snapshot()

        if record.state == RecoveryState.VERIFYING and record.verification_id:
            for task in reversed(snapshot.verification):
                if task.verification_id != record.verification_id:
                    continue
                if task.status != VerificationStatus.PENDING:
                    self.recovery_supervisor.verification_result(
                        now=now,
                        verification_id=task.verification_id,
                        status=task.status.value,
                    )
                break

        record = self.recovery_supervisor.active
        if (
            record is not None
            and record.state
            not in {
                RecoveryState.VERIFYING,
                RecoveryState.RECOVERED,
                RecoveryState.LOCKED_OUT,
                RecoveryState.ESCALATED,
            }
            and self.recovery_supervisor.eligible(now)
        ):
            self.recovery_supervisor.begin_attempt(now=now, action="START_BACKUP_PUMP")
            if backup_command is None:
                self.recovery_supervisor.fail_attempt(
                    now=now,
                    reason="FALLBACK_COMMAND_NOT_AVAILABLE",
                )
            elif not backup_command.accepted or not backup_command.final_on:
                self.recovery_supervisor.fail_attempt(
                    now=now,
                    reason=f"FALLBACK_COMMAND_REJECTED:{backup_command.reason}",
                )
            else:
                pending = next(
                    (
                        task
                        for task in reversed(snapshot.verification)
                        if task.asset_id == "backup_pump"
                        and task.status == VerificationStatus.PENDING
                    ),
                    None,
                )
                if pending is None:
                    self.recovery_supervisor.fail_attempt(
                        now=now,
                        reason="PROCESS_VERIFICATION_NOT_CREATED",
                    )
                else:
                    self.recovery_supervisor.mark_verifying(
                        now=now,
                        verification_id=pending.verification_id,
                        fallback_active=True,
                    )

        return before != self.recovery_supervisor.snapshot()

    def tick(self, seconds: float):
        snapshot = super().tick(seconds)
        recovery_changed = self._process_circulation_recovery(snapshot)
        snapshot.configuration_control = self.change_control.snapshot()
        snapshot.recovery_control = self.recovery_supervisor.snapshot()
        if recovery_changed:
            latest_event = self.events.events[-1].sequence if self.events.events else 0
            self.historian.append(
                run_id=self.run_id,
                event_sequence=latest_event,
                snapshot=snapshot,
            )
        return snapshot

    def capture_checkpoint(self):
        checkpoint = super().capture_checkpoint()
        checkpoint["governed_change_control_state"] = self.change_control.checkpoint_state()
        checkpoint["governed_recovery_state"] = self.recovery_supervisor.checkpoint_state()
        return checkpoint

    def restore_checkpoint(self, checkpoint) -> None:
        super().restore_checkpoint(checkpoint)
        self.change_control.restore_state(checkpoint.get("governed_change_control_state"))
        self.recovery_supervisor.restore_state(
            checkpoint.get("governed_recovery_state"),
            now=self.clock.current,
        )

    def publish(self, snapshot, *, after_sequence: int = 0):
        snapshot.configuration_control = self.change_control.snapshot()
        snapshot.recovery_control = self.recovery_supervisor.snapshot()
        publication = super().publish(snapshot, after_sequence=after_sequence)
        publication["governed_configuration_schema_version"] = 1
        publication["self_recovery_schema_version"] = 1
        publication["authority_escalation_by_recovery"] = False
        publication["high_risk_chemical_dosing_by_recovery"] = False
        return publication
