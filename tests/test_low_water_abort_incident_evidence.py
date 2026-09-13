from datetime import UTC, datetime

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import AlarmLifecycle, AvailabilityState
from smart_koi_pond.domain.models import PondState
from smart_koi_pond.sensors.virtual import SensorFault


def policy(**overrides) -> SimulationControlPolicy:
    values = {
        "do_watch_below": 5.0,
        "do_emergency_below": 4.0,
        "do_recover_above": 5.5,
        "flow_watch_below": 8.0,
        "water_level_low_below": 70.0,
        "verification_delay_seconds": 1.0,
        "do_verification_min_delta": 0.01,
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


def runtime_for(test_policy: SimulationControlPolicy) -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, 6.0, 7.2, 60.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        test_policy,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="low-water-abort-evidence",
        config_version="low-water-abort-evidence-policy",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def assert_lockout_evidence(runtime, snapshot, reason: str) -> None:
    alarms = [
        alarm
        for alarm in snapshot.alarms
        if alarm.code == "LOW_WATER_RECOVERY_LOCKOUT"
        and alarm.lifecycle == AlarmLifecycle.ESCALATED
    ]
    assert len(alarms) == 1
    alarm = alarms[0]
    assert alarm.condition_key == "LOW_WATER_RECOVERY_LOCKOUT:low-water-1"
    assert f"REASON:{reason}" in alarm.reasons
    assert "AUTO_RETRY_LOCKED" in alarm.reasons

    incidents = [
        incident for incident in snapshot.incidents if alarm.alarm_id in incident.alarm_ids
    ]
    assert len(incidents) == 1
    evidence = runtime.incident_evidence(incidents[0].incident_id)
    codes = [event.code for event in evidence]
    assert "ALARM_OPENED" in codes
    assert any(
        code in {"LOW_WATER_RECOVERY_ABORTED", "LOW_WATER_RECOVERY_ABORTED_ON_RESTART"}
        for code in codes
    )
    sequences = [event.sequence for event in evidence]
    assert sequences == sorted(sequences)


def test_hard_high_cutoff_opens_persistent_lockout_alarm_and_incident() -> None:
    runtime = runtime_for(policy())
    runtime.tick(0)
    runtime.model.set_truth("water_level_pct", 85.0)

    aborted = runtime.tick(0)
    assert aborted.water_recovery["lockout_reason"] == "HARD_HIGH_LEVEL_CUTOFF"
    assert_lockout_evidence(runtime, aborted, "HARD_HIGH_LEVEL_CUTOFF")

    still_locked = runtime.tick(0)
    assert still_locked.water_recovery["lockout_reason"] == "HARD_HIGH_LEVEL_CUTOFF"
    assert_lockout_evidence(runtime, still_locked, "HARD_HIGH_LEVEL_CUTOFF")


def test_invalid_level_opens_lockout_alarm_and_incident() -> None:
    runtime = runtime_for(policy())
    runtime.tick(0)
    runtime.sensors.set_fault("water_level", SensorFault("dropout"))

    aborted = runtime.tick(0)
    assert aborted.water_recovery["lockout_reason"] == "INVALID_WATER_LEVEL_EVIDENCE"
    assert_lockout_evidence(runtime, aborted, "INVALID_WATER_LEVEL_EVIDENCE")


def test_unsafe_mode_opens_lockout_alarm_and_incident() -> None:
    runtime = runtime_for(policy())
    runtime.tick(0)
    runtime.start_manual_maintenance(["top_up_valve"], "service intervention")

    aborted = runtime.tick(0)
    reason = aborted.water_recovery["lockout_reason"]
    assert reason == "UNSAFE_OPERATING_MODE:MANUAL_MAINTENANCE"
    assert_lockout_evidence(runtime, aborted, reason)


def test_unavailable_valve_opens_lockout_alarm_and_incident() -> None:
    runtime = runtime_for(policy())
    runtime.tick(0)
    runtime.actuators.set_availability("top_up_valve", AvailabilityState.FAILED)

    aborted = runtime.tick(0)
    reason = "TOP_UP_VALVE_NOT_AVAILABLE:FAILED"
    assert aborted.water_recovery["lockout_reason"] == reason
    assert_lockout_evidence(runtime, aborted, reason)


def test_max_runtime_opens_lockout_alarm_and_incident() -> None:
    runtime = runtime_for(
        policy(
            low_water_max_runtime_seconds=1.0,
            low_water_verification_delay_seconds=3600.0,
        )
    )
    runtime.tick(0)

    aborted = runtime.tick(2)
    assert aborted.water_recovery["lockout_reason"] == "MAX_RUNTIME_EXCEEDED"
    assert_lockout_evidence(runtime, aborted, "MAX_RUNTIME_EXCEEDED")


def test_max_level_gain_opens_lockout_alarm_and_incident() -> None:
    runtime = runtime_for(
        policy(
            low_water_max_level_gain_pct=0.1,
            low_water_verification_delay_seconds=3600.0,
        )
    )
    runtime.tick(0)

    aborted = runtime.tick(60)
    assert aborted.water_recovery["lockout_reason"] == "MAX_LEVEL_GAIN_EXCEEDED"
    assert_lockout_evidence(runtime, aborted, "MAX_LEVEL_GAIN_EXCEEDED")


def test_failed_response_opens_recovery_lockout_alarm_and_incident() -> None:
    runtime = runtime_for(
        policy(
            water_level_verification_min_delta=0.2,
            low_water_verification_delay_seconds=1.0,
        )
    )
    runtime.actuators.set_effectiveness("top_up_valve", 0.0)
    runtime.tick(0)

    aborted = runtime.tick(2)
    reason = "VERIFICATION_FAILED_RESPONSE"
    assert aborted.water_recovery["lockout_reason"] == reason
    assert_lockout_evidence(runtime, aborted, reason)


def test_restart_abort_opens_lockout_alarm_and_incident_after_reconciliation() -> None:
    test_policy = policy()
    runtime = runtime_for(test_policy)
    runtime.tick(0)
    checkpoint = runtime.capture_checkpoint()

    resumed = runtime_for(test_policy)
    resumed.restore_checkpoint(checkpoint)
    after_restart = resumed.tick(0)

    assert after_restart.water_recovery["lockout_reason"] == "RUNTIME_RESTART_ABORT"
    assert resumed.actuators.assets["top_up_valve"].feedback_on is False
    assert_lockout_evidence(resumed, after_restart, "RUNTIME_RESTART_ABORT")
