from datetime import UTC, datetime

import pytest

from smart_koi_pond.actuators.virtual import ActuatorFault
from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.digital_twin.hydraulics import PondDesignProfile
from smart_koi_pond.digital_twin.governed_runtime import ProductionDigitalTwinRuntime
from smart_koi_pond.digital_twin.filtration import MechanicalFiltrationProfile
from smart_koi_pond.domain.enums import AvailabilityState, ExecutionMode
from smart_koi_pond.governance.reconfiguration import (
    ConfigurationTransactionState,
    GovernedChangeController,
    RecoveryPlan,
    RecoveryState,
    RecoverySupervisor,
)


def pond_profile(revision: str = "r1") -> PondDesignProfile:
    return PondDesignProfile.from_dict(
        {
            "profile_id": "recovery-test-pond",
            "revision": revision,
            "effective_volume_l": 12_000.0,
            "circulation_turnovers_per_hour_guide": 1.0,
            "biomass_kg": 20.0,
            "feed_kg_per_day": 0.4,
            "provenance": "USER_CONFIGURED_SCENARIO",
            "routes": [
                {
                    "route_id": "main-circulation",
                    "asset_id": "main_pump",
                    "rated_flow_l_min": 240.0,
                    "role": "PRIMARY",
                    "base_throughput_factor": 1.0,
                    "provenance": "USER_CONFIGURED_SCENARIO",
                },
                {
                    "route_id": "backup-circulation",
                    "asset_id": "backup_pump",
                    "rated_flow_l_min": 220.0,
                    "role": "BACKUP",
                    "base_throughput_factor": 1.0,
                    "provenance": "USER_CONFIGURED_SCENARIO",
                },
            ],
        }
    )


def configured_runtime() -> ProductionDigitalTwinRuntime:
    runtime = build_integrated_virtual_runtime()
    assert isinstance(runtime, ProductionDigitalTwinRuntime)
    runtime.configure_design_profile(pond_profile(), actor="test-engineer")
    runtime.configure_module("flow_monitoring", enabled=True, actor="test-engineer")
    runtime.configure_module("backup_circulation", enabled=True, actor="test-engineer")
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_failed_preflight_is_atomic_and_does_not_mutate_model() -> None:
    runtime = configured_runtime()
    before = runtime.model.checkpoint_state()
    invalid_filter = MechanicalFiltrationProfile.from_dict(
        {
            "profile_id": "invalid-filter",
            "revision": "r1",
            "source_reference": "TEST_ONLY",
            "filtered_route_id": "missing-route",
            "capture_efficiency_per_pass": 0.5,
            "max_captured_solids_g": 100.0,
            "minimum_route_throughput_factor_at_capacity": 0.5,
            "backwash_solids_removal_g_per_min": 10.0,
            "backwash_discharge_flow_l_min": None,
            "turbidity_ntu_per_mg_l_tss": None,
            "provenance": "USER_CONFIGURED_SCENARIO",
        }
    )

    with pytest.raises(ValueError, match="preflight"):
        runtime.model.configure_mechanical_filtration_profile(invalid_filter)

    assert runtime.model.checkpoint_state() == before
    tx = runtime.change_control.last_transaction
    assert tx is not None
    assert tx.state == ConfigurationTransactionState.REJECTED
    assert runtime.change_control.active_configuration_version == tx.parent_version


def test_successful_configuration_has_parent_and_last_good_lineage() -> None:
    runtime = build_integrated_virtual_runtime()
    parent = runtime.change_control.active_configuration_version

    runtime.configure_design_profile(pond_profile(), actor="test-engineer")

    tx = runtime.change_control.last_transaction
    assert tx is not None
    assert tx.parent_version == parent
    assert tx.state == ConfigurationTransactionState.LAST_GOOD
    assert runtime.change_control.active_configuration_version == tx.candidate_version
    assert runtime.change_control.last_good_configuration_version == tx.candidate_version
    assert tx.verification_result == "PASS"


def test_failed_post_activation_verification_rolls_back_to_last_good() -> None:
    state = {"value": "last-good"}
    controller = GovernedChangeController(
        initial_configuration_version="cfg-base",
        initial_software_version="software-base",
    )

    with pytest.raises(RuntimeError, match="verification"):
        controller.apply_configuration(
            scope="TEST",
            actor="test",
            reason="force rollback",
            before={"value": "last-good"},
            after={"value": "candidate"},
            now=datetime(2026, 1, 1, tzinfo=UTC),
            preflight=lambda: (),
            apply=lambda: state.update(value="candidate"),
            rollback=lambda: state.update(value="last-good"),
            verify=lambda: False,
        )

    assert state["value"] == "last-good"
    assert controller.active_configuration_version == "cfg-base"
    assert controller.last_good_configuration_version == "cfg-base"
    assert controller.last_transaction is not None
    assert controller.last_transaction.state == ConfigurationTransactionState.ROLLED_BACK
    assert controller.last_transaction.rollback_result == "PASS"


def test_software_update_is_staged_then_verified_before_last_good() -> None:
    installed = {"version": "software-base"}
    controller = GovernedChangeController(
        initial_configuration_version="cfg-base",
        initial_software_version="software-base",
    )
    staged = controller.stage_software_update(
        "software-next",
        actor="release-service",
        reason="accepted CI artifact",
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert staged.state == ConfigurationTransactionState.STAGED
    assert controller.last_good_software_version == "software-base"

    controller.activate_staged_software_update(
        executor=lambda version: installed.update(version=version),
        rollback_executor=lambda version: installed.update(version=version),
        verify=lambda: installed["version"] == "software-next",
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert installed["version"] == "software-next"
    assert controller.active_software_version == "software-next"
    assert controller.last_good_software_version == "software-next"
    assert controller.software_update is not None
    assert controller.software_update.state == ConfigurationTransactionState.LAST_GOOD


def test_failed_software_verification_rolls_back_and_does_not_promote_candidate() -> None:
    installed = {"version": "software-base"}
    controller = GovernedChangeController(
        initial_configuration_version="cfg-base",
        initial_software_version="software-base",
    )
    controller.stage_software_update(
        "software-bad",
        actor="release-service",
        reason="negative acceptance",
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )

    with pytest.raises(RuntimeError, match="verification"):
        controller.activate_staged_software_update(
            executor=lambda version: installed.update(version=version),
            rollback_executor=lambda version: installed.update(version=version),
            verify=lambda: False,
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )

    assert installed["version"] == "software-base"
    assert controller.last_good_software_version == "software-base"
    assert controller.software_update is not None
    assert controller.software_update.state == ConfigurationTransactionState.ROLLED_BACK


def test_primary_pump_failure_recovers_through_existing_backup_and_process_verification() -> None:
    runtime = configured_runtime()
    runtime.tick(1.0)
    runtime.actuators.set_fault("main_pump", ActuatorFault("failed_off"))

    first = runtime.tick(1.0)
    recovery = first.recovery_control["active"]
    assert recovery is not None
    assert recovery["state"] == RecoveryState.VERIFYING
    assert recovery["current_action"] == "START_BACKUP_PUMP"
    assert first.commands["backup_pump"].accepted is True
    assert first.commands["backup_pump"].final_on is True

    final = runtime.tick(120.0)
    recovery = final.recovery_control["active"]
    assert recovery["state"] == RecoveryState.RECOVERED
    assert recovery["verification_result"] == "VERIFIED_SUCCESS"
    assert recovery["fallback_active"] is True
    assert final.pond_truth.circulation_flow_l_min > 0.0


def test_unavailable_fallback_uses_bounded_retry_then_terminal_lockout() -> None:
    runtime = configured_runtime()
    runtime.actuators.set_fault("main_pump", ActuatorFault("failed_off"))
    runtime.actuators.set_availability("backup_pump", AvailabilityState.FAILED)

    runtime.tick(1.0)
    first = runtime.recovery_supervisor.snapshot()["active"]
    assert first["attempt_count"] == 1
    assert first["state"] == RecoveryState.SAFE_OR_DEGRADED

    runtime.tick(60.0)
    second = runtime.recovery_supervisor.snapshot()["active"]
    assert second["attempt_count"] == 2
    assert second["state"] == RecoveryState.LOCKED_OUT
    assert second["escalated"] is True

    runtime.tick(600.0)
    terminal = runtime.recovery_supervisor.snapshot()["active"]
    assert terminal["attempt_count"] == 2
    assert terminal["state"] == RecoveryState.LOCKED_OUT
    assert runtime.recovery_supervisor.snapshot()["infinite_retry_allowed"] is False


def test_recovery_supervisor_restart_requires_reconciliation_not_stale_success() -> None:
    runtime = configured_runtime()
    runtime.actuators.set_fault("main_pump", ActuatorFault("failed_off"))
    snapshot = runtime.tick(1.0)
    assert snapshot.recovery_control["active"]["state"] == RecoveryState.VERIFYING
    checkpoint = runtime.capture_checkpoint()

    restored = configured_runtime()
    restored.restore_checkpoint(checkpoint)
    state = restored.recovery_supervisor.snapshot()["active"]

    assert state["state"] == RecoveryState.RECONCILING
    assert state["verification_id"] is None
    assert state["current_action"] == "RESTART_RECONCILIATION"
    assert all(not asset.feedback_on for asset in restored.actuators.assets.values())
    restart_events = [
        event for event in restored.events.events if "RESTART_RECONCILIATION" in event.code
    ]
    assert restart_events


def test_publication_and_historian_expose_governed_change_and_recovery_state() -> None:
    runtime = configured_runtime()
    runtime.actuators.set_fault("main_pump", ActuatorFault("failed_off"))
    snapshot = runtime.tick(1.0)
    publication = runtime.publish(snapshot)
    history = runtime.recent_history(limit=20)

    assert publication["snapshot"]["configuration_control"][
        "active_configuration_version"
    ] == runtime.change_control.active_configuration_version
    assert publication["snapshot"]["recovery_control"]["active"] is not None
    assert publication["governed_configuration_schema_version"] == 1
    assert publication["self_recovery_schema_version"] == 1
    assert history[-1]["snapshot"]["configuration_control"]
    assert history[-1]["snapshot"]["recovery_control"]["active"] is not None


def test_recovery_cannot_escalate_real_authority_or_enable_high_risk_dosing() -> None:
    runtime = configured_runtime()
    runtime.actuators.set_fault("main_pump", ActuatorFault("failed_off"))
    snapshot = runtime.tick(1.0)
    publication = runtime.publish(snapshot)

    assert runtime.execution_mode == ExecutionMode.SIMULATION
    assert publication["authority_escalation_by_recovery"] is False
    assert publication["high_risk_chemical_dosing_by_recovery"] is False
    assert snapshot.recovery_control["authority_escalation_allowed"] is False
    assert snapshot.recovery_control["high_risk_chemical_dosing_allowed"] is False
    assert all(
        status.source_state.value == "VIRTUAL_ACTUATOR"
        for status in snapshot.assets.values()
    )


def test_recovery_supervisor_plan_rejects_infinite_retry_semantics() -> None:
    with pytest.raises(ValueError, match="retry_limit"):
        RecoveryPlan(
            plan_id="invalid",
            revision="1",
            trigger_code="FAULT",
            affected_assets=(),
            allowed_actions=("RETRY",),
            retry_limit=0,
            cooldown_seconds=0.0,
        )

    supervisor = RecoverySupervisor()
    supervisor.register(
        RecoveryPlan(
            plan_id="bounded",
            revision="1",
            trigger_code="FAULT",
            affected_assets=("asset",),
            allowed_actions=("RETRY",),
            retry_limit=1,
            cooldown_seconds=0.0,
        )
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    supervisor.detect("bounded", now=now, reason="FAULT")
    supervisor.begin_attempt(now=now, action="RETRY")
    supervisor.fail_attempt(now=now, reason="FAILED")
    assert supervisor.snapshot()["active"]["state"] == RecoveryState.LOCKED_OUT
