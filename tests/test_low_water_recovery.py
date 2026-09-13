from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.arbitration import arbitrate
from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    CommandOwner,
    DataQuality,
    OperatingMode,
    SystemState,
    VerificationStatus,
)
from smart_koi_pond.domain.models import CommandIntent, PondState
from smart_koi_pond.scenarios.regression_matrix import (
    V1_REGRESSION_MATRIX,
    GateStatus,
)
from smart_koi_pond.sensors.virtual import SensorFault


def low_water_policy(**overrides) -> SimulationControlPolicy:
    values = {
        "do_watch_below": 5.0,
        "do_emergency_below": 4.0,
        "do_recover_above": 5.5,
        "flow_watch_below": 8.0,
        "water_level_low_below": 70.0,
        "verification_delay_seconds": 1.0,
        "do_verification_min_delta": 0.01,
        "temperature_watch_above": 30.0,
        "temperature_emergency_above": 32.0,
        "low_water_auto_recovery_enabled": True,
        "water_level_recover_target": 72.0,
        "water_level_hard_high_cutoff": 80.0,
        "low_water_max_runtime_seconds": 7200.0,
        "low_water_max_level_gain_pct": 15.0,
        "low_water_verification_delay_seconds": 1.0,
        "water_level_verification_min_delta": 0.1,
    }
    values.update(overrides)
    return SimulationControlPolicy(**values)


def make_runtime(policy: SimulationControlPolicy) -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, 6.0, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        policy,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="low-water-acceptance-run",
        config_version="low-water-acceptance-policy",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def case_status() -> GateStatus:
    return next(
        case.status
        for case in V1_REGRESSION_MATRIX
        if case.case_id == "low_water_autonomous_recovery"
    )


def recovery_event_codes(runtime: DigitalTwinRuntime) -> list[str]:
    return [event.code for event in runtime.events.events if event.event_type == "RECOVERY"]


def test_low_water_policy_rejects_incomplete_or_unsafe_bounds() -> None:
    with pytest.raises(ValueError):
        SimulationControlPolicy(
            do_watch_below=5.0,
            do_emergency_below=4.0,
            do_recover_above=5.5,
            flow_watch_below=8.0,
            water_level_low_below=70.0,
            low_water_auto_recovery_enabled=True,
        )

    with pytest.raises(ValueError):
        low_water_policy(
            water_level_recover_target=82.0,
            water_level_hard_high_cutoff=80.0,
        )


def test_safety_owner_can_only_deenergize() -> None:
    unsafe_on = arbitrate(
        CommandIntent("top_up_valve", True, CommandOwner.SAFETY, "test"),
        AvailabilityState.AVAILABLE,
        CommandOwner.AUTO,
        OperatingMode.NORMAL_AUTO,
    )
    assert unsafe_on.accepted is False
    assert unsafe_on.final_on is False
    assert unsafe_on.reason == "SAFETY_OWNER_CANNOT_ENERGIZE"

    safe_off = arbitrate(
        CommandIntent("top_up_valve", False, CommandOwner.SAFETY, "hard-stop"),
        AvailabilityState.FAILED,
        CommandOwner.MAINTENANCE,
        OperatingMode.MANUAL_MAINTENANCE,
    )
    assert safe_off.accepted is True
    assert safe_off.final_on is False
    assert safe_off.owner == CommandOwner.SAFETY


def test_low_water_autonomous_recovery_is_interlocked_verified_and_fail_safe() -> None:
    runtime = make_runtime(low_water_policy())
    runtime.model.set_truth("water_level_pct", 60.0)

    started = runtime.tick(0)
    assert started.classification.state == SystemState.CORRECTING
    assert started.validated["water_level"].quality == DataQuality.GOOD
    assert started.commands["top_up_valve"].accepted is True
    assert started.commands["top_up_valve"].final_on is True
    assert started.feedback["top_up_valve"].feedback_on is True
    assert "drain_valve" not in started.commands
    assert started.water_recovery["active_attempt_id"] == "low-water-1"
    assert started.water_recovery["response_verified"] is False
    assert any(
        task.asset_id == "top_up_valve"
        and task.status == VerificationStatus.PENDING
        for task in started.verification
    )
    assert started.incidents

    verified = runtime.tick(60)
    assert verified.pond_truth.water_level_pct > 60.0
    assert verified.water_recovery["response_verified"] is True
    assert verified.commands["top_up_valve"].final_on is True
    assert verified.feedback["top_up_valve"].feedback_on is True
    assert any(
        task.asset_id == "top_up_valve"
        and task.status == VerificationStatus.VERIFIED_SUCCESS
        for task in verified.verification
    )

    recovered = runtime.tick(3600)
    assert recovered.pond_truth.water_level_pct >= 72.0
    assert recovered.pond_truth.water_level_pct < 80.0
    assert recovered.commands["top_up_valve"].owner == CommandOwner.SAFETY
    assert recovered.commands["top_up_valve"].final_on is False
    assert recovered.feedback["top_up_valve"].feedback_on is False
    assert recovered.water_recovery["active_attempt_id"] is None
    assert recovered.water_recovery["lockout_reason"] is None
    assert "drain_valve" not in recovered.commands

    codes = recovery_event_codes(runtime)
    assert "LOW_WATER_RECOVERY_STARTED" in codes
    assert "LOW_WATER_RESPONSE_VERIFIED" in codes
    assert "LOW_WATER_RECOVERY_TARGET_REACHED" in codes
    assert "LOW_WATER_RECOVERY_SAFE_OFF_CONFIRMED" in codes
    assert "LOW_WATER_RECOVERY_COMPLETED" in codes
    assert case_status() == GateStatus.PASS


def test_failed_top_up_response_forces_off_opens_evidence_and_locks_out() -> None:
    runtime = make_runtime(
        low_water_policy(
            water_level_verification_min_delta=0.2,
            low_water_verification_delay_seconds=1.0,
        )
    )
    runtime.model.set_truth("water_level_pct", 60.0)
    runtime.actuators.set_effectiveness("top_up_valve", 0.0)

    started = runtime.tick(0)
    assert started.feedback["top_up_valve"].feedback_on is True
    assert started.feedback["top_up_valve"].effectiveness == 0.0

    failed = runtime.tick(2)
    assert any(
        task.asset_id == "top_up_valve"
        and task.status == VerificationStatus.FAILED_RESPONSE
        for task in failed.verification
    )
    assert failed.commands["top_up_valve"].owner == CommandOwner.SAFETY
    assert failed.commands["top_up_valve"].final_on is False
    assert runtime.actuators.assets["top_up_valve"].feedback_on is False
    assert failed.water_recovery["lockout_reason"] == "VERIFICATION_FAILED_RESPONSE"
    assert any(
        alarm.condition_key.startswith("VERIFICATION:") for alarm in failed.alarms
    )
    assert failed.incidents

    no_retry = runtime.tick(0)
    assert "top_up_valve" not in no_retry.commands
    assert runtime.actuators.assets["top_up_valve"].feedback_on is False
    assert no_retry.water_recovery["lockout_reason"] == "VERIFICATION_FAILED_RESPONSE"
    assert "LOW_WATER_RECOVERY_ABORTED" in recovery_event_codes(runtime)
    assert "LOW_WATER_RECOVERY_SAFE_OFF_CONFIRMED" in recovery_event_codes(runtime)


def test_hard_high_cutoff_forces_off_and_does_not_self_clear_lockout() -> None:
    runtime = make_runtime(low_water_policy())
    runtime.model.set_truth("water_level_pct", 60.0)
    runtime.tick(0)

    runtime.model.set_truth("water_level_pct", 85.0)
    aborted = runtime.tick(0)
    assert aborted.commands["top_up_valve"].owner == CommandOwner.SAFETY
    assert aborted.commands["top_up_valve"].final_on is False
    assert runtime.actuators.assets["top_up_valve"].feedback_on is False
    assert aborted.water_recovery["lockout_reason"] == "HARD_HIGH_LEVEL_CUTOFF"
    assert "LOW_WATER_RECOVERY_ABORTED" in recovery_event_codes(runtime)

    still_locked = runtime.tick(0)
    assert "top_up_valve" not in still_locked.commands
    assert still_locked.water_recovery["lockout_reason"] == "HARD_HIGH_LEVEL_CUTOFF"


def test_invalid_level_evidence_aborts_and_forces_valve_off() -> None:
    runtime = make_runtime(low_water_policy())
    runtime.model.set_truth("water_level_pct", 60.0)
    runtime.tick(0)

    runtime.sensors.set_fault("water_level", SensorFault("dropout"))
    aborted = runtime.tick(0)
    assert aborted.validated["water_level"].quality == DataQuality.INVALID
    assert aborted.commands["top_up_valve"].owner == CommandOwner.SAFETY
    assert aborted.commands["top_up_valve"].final_on is False
    assert aborted.water_recovery["lockout_reason"] == "INVALID_WATER_LEVEL_EVIDENCE"
    assert runtime.actuators.assets["top_up_valve"].feedback_on is False


def test_unsafe_mode_transition_aborts_even_after_ownership_changes() -> None:
    runtime = make_runtime(low_water_policy())
    runtime.model.set_truth("water_level_pct", 60.0)
    runtime.tick(0)
    assert runtime.actuators.assets["top_up_valve"].feedback_on is True

    runtime.start_manual_maintenance(["top_up_valve"], "service intervention")
    aborted = runtime.tick(0)
    assert aborted.operating_mode == OperatingMode.MANUAL_MAINTENANCE
    assert aborted.commands["top_up_valve"].owner == CommandOwner.SAFETY
    assert aborted.commands["top_up_valve"].final_on is False
    assert runtime.actuators.assets["top_up_valve"].feedback_on is False
    assert aborted.water_recovery["lockout_reason"].startswith(
        "UNSAFE_OPERATING_MODE:"
    )


def test_restart_aborts_active_refill_without_stale_command_replay() -> None:
    policy = low_water_policy()
    runtime = make_runtime(policy)
    runtime.model.set_truth("water_level_pct", 60.0)
    active = runtime.tick(0)
    assert active.water_recovery["active_attempt_id"] == "low-water-1"
    assert runtime.actuators.assets["top_up_valve"].feedback_on is True

    checkpoint = runtime.capture_checkpoint()
    resumed = make_runtime(policy)
    resumed.restore_checkpoint(checkpoint)

    assert resumed.actuators.assets["top_up_valve"].feedback_on is False
    assert resumed.low_water_recovery.lockout_reason == "RUNTIME_RESTART_ABORT"
    assert resumed.low_water_recovery.active is None
    assert any(
        event.code == "LOW_WATER_RECOVERY_ABORTED_ON_RESTART"
        for event in resumed.events.events
    )

    after_restart = resumed.tick(0)
    assert runtime.policy.low_water_auto_recovery_enabled is True
    assert after_restart.water_recovery["lockout_reason"] == "RUNTIME_RESTART_ABORT"
    assert "top_up_valve" not in after_restart.commands
    assert resumed.actuators.assets["top_up_valve"].feedback_on is False
