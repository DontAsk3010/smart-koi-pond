from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    DataQuality,
    OperatingMode,
    SystemState,
    VerificationStatus,
    WorkflowPhase,
)
from smart_koi_pond.domain.models import PondState
from smart_koi_pond.scenarios.regression_matrix import (
    V1_REGRESSION_MATRIX,
    GateStatus,
    matrix_payload,
)
from smart_koi_pond.sensors.virtual import SensorFault

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=1.0,
    do_verification_min_delta=0.01,
    temperature_watch_above=30.0,
    temperature_emergency_above=32.0,
)


def make_runtime(
    *,
    dissolved_oxygen: float = 6.0,
    ambient_temperature: float = 28.0,
    policy: SimulationControlPolicy = POLICY,
) -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, dissolved_oxygen, 7.2, 85.0),
            EnvironmentInputs(ambient_temperature, 0.2),
        ),
        policy,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="v1-regression-run",
        config_version="v1-regression-test-policy",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def restored(runtime: DigitalTwinRuntime) -> DigitalTwinRuntime:
    replacement = make_runtime(policy=runtime.policy)
    replacement.restore_checkpoint(runtime.capture_checkpoint())
    return replacement


def case(case_id: str):
    return next(item for item in V1_REGRESSION_MATRIX if item.case_id == case_id)


@pytest.mark.parametrize(
    "case_id,starter",
    [
        (
            "restart_manual_maintenance",
            lambda runtime: runtime.start_manual_maintenance(
                ["main_pump"],
                "regression maintenance",
                service_locked=["main_pump"],
            ),
        ),
        (
            "restart_sensor_calibration",
            lambda runtime: runtime.start_sensor_calibration(
                ["do"],
                "regression calibration",
            ),
        ),
        (
            "restart_water_change",
            lambda runtime: runtime.start_water_change(
                "regression water change",
                target_drain_level_pct=80.0,
                target_refill_level_pct=84.0,
            ),
        ),
        (
            "restart_filter_clean",
            lambda runtime: runtime.start_filter_clean(
                ["main_pump"],
                "regression filter clean",
            ),
        ),
        (
            "restart_partial_shutdown",
            lambda runtime: runtime.start_partial_shutdown(
                ["main_pump"],
                "regression partial shutdown",
            ),
        ),
        (
            "restart_safe_total_shutdown",
            lambda runtime: runtime.start_safe_total_shutdown(
                "regression safe shutdown",
                fish_present=True,
            ),
        ),
    ],
)
def test_restart_during_governed_operating_modes_enters_hold(case_id, starter) -> None:
    runtime = make_runtime()
    starter(runtime)
    runtime.tick(1)

    resumed = restored(runtime)
    assert resumed.operating_mode == OperatingMode.HOLD
    assert resumed.modes.phase == WorkflowPhase.HOLD
    assert any(
        event.code == "RUNTIME_RESTART_RECONCILIATION_REQUIRED"
        for event in resumed.events.events
    )

    resumed.request_return_to_auto()
    snapshot = resumed.tick(1)
    assert snapshot.operating_mode == OperatingMode.NORMAL_AUTO
    assert case(case_id).status == GateStatus.PASS


def test_blackout_restart_restarts_life_support_before_auto() -> None:
    runtime = make_runtime()
    runtime.start_blackout("regression blackout")
    runtime.tick(1)

    resumed = restored(runtime)
    assert resumed.operating_mode == OperatingMode.RECOVERY_SYNC
    assert all(not asset.feedback_on for asset in resumed.actuators.assets.values())

    snapshot = resumed.tick(1)
    assert snapshot.operating_mode == OperatingMode.NORMAL_AUTO
    assert resumed.actuators.assets["main_pump"].feedback_on is True
    assert resumed.actuators.assets["primary_aerator"].feedback_on is True
    assert case("blackout_restart_recovery_sync").status == GateStatus.PASS


def test_main_pump_failure_uses_backup_without_false_total_failure() -> None:
    runtime = make_runtime()
    runtime.actuators.set_availability("main_pump", AvailabilityState.FAILED)

    first = runtime.tick(1)
    assert first.capability.circulation_paths_available == 1
    assert first.capability.critical_capability_lost is False
    assert first.commands["backup_pump"].accepted is True
    assert first.commands["backup_pump"].final_on is True

    second = runtime.tick(1)
    assert second.pond_truth.circulation_flow_l_min > 0
    assert case("main_pump_failure_backup_flow").status == GateStatus.PASS


def test_failed_correction_has_verification_and_incident_evidence() -> None:
    policy = SimulationControlPolicy(
        do_watch_below=5.0,
        do_emergency_below=4.0,
        do_recover_above=5.5,
        flow_watch_below=8.0,
        water_level_low_below=70.0,
        verification_delay_seconds=1.0,
        do_verification_min_delta=10.0,
        temperature_watch_above=30.0,
        temperature_emergency_above=32.0,
    )
    runtime = make_runtime(dissolved_oxygen=4.6, policy=policy)
    first = runtime.tick(0)
    assert first.incidents

    second = runtime.tick(2)
    assert any(
        task.status == VerificationStatus.FAILED_RESPONSE for task in second.verification
    )
    assert any(
        alarm.condition_key.startswith("VERIFICATION:") for alarm in second.alarms
    )
    evidence = runtime.incident_evidence(second.incidents[0].incident_id)
    sequences = [event.sequence for event in evidence]
    assert sequences == sorted(sequences)
    assert case("failed_correction_escalation").status == GateStatus.PASS


def test_sensor_dropout_is_distinct_from_genuine_low_do() -> None:
    missing = make_runtime(dissolved_oxygen=6.0)
    missing.sensors.set_fault("do", SensorFault("dropout"))
    unavailable = missing.tick(0)
    assert unavailable.validated["do"].quality == DataQuality.INVALID
    assert unavailable.classification.state == SystemState.DEGRADED
    assert "backup_aerator" not in unavailable.commands

    real_fault = make_runtime(dissolved_oxygen=4.6)
    low_do = real_fault.tick(0)
    assert low_do.validated["do"].quality == DataQuality.GOOD
    assert low_do.classification.state == SystemState.CORRECTING
    assert low_do.commands["backup_aerator"].final_on is True
    assert case("sensor_dropout_vs_real_low_do").status == GateStatus.PASS


def test_low_water_is_detected_without_fabricating_recovery() -> None:
    runtime = make_runtime()
    runtime.model.set_truth("water_level_pct", 60.0)
    snapshot = runtime.tick(0)

    assert snapshot.classification.state == SystemState.DEGRADED
    assert "WATER_LEVEL_LOW" in snapshot.classification.reasons
    assert "top_up_valve" not in snapshot.commands
    assert case("water_level_fault_detection").status == GateStatus.PASS
    assert case("low_water_autonomous_recovery").status == GateStatus.HOLD


def test_local_critical_control_has_no_supervisory_network_dependency() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    snapshot = runtime.tick(0)

    assert snapshot.commands["backup_aerator"].accepted is True
    assert runtime.actuators.assets["backup_aerator"].feedback_on is True
    assert case("supervisory_network_loss_local_control").status == GateStatus.PASS


def test_combined_fault_has_ordered_incident_evidence() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    runtime.actuators.set_availability("main_pump", AvailabilityState.FAILED)
    snapshot = runtime.tick(0)

    assert snapshot.commands["backup_pump"].final_on is True
    assert snapshot.commands["backup_aerator"].final_on is True
    assert snapshot.incidents
    evidence = runtime.incident_evidence(snapshot.incidents[0].incident_id)
    sequences = [event.sequence for event in evidence]
    assert sequences == list(range(sequences[0], sequences[-1] + 1))
    assert case("combined_fault_incident_chronology").status == GateStatus.PASS


def test_historian_playback_preserves_point_in_time_runtime_truth() -> None:
    runtime = make_runtime()
    first = runtime.tick(60)
    frame_sequence = runtime.historian.latest_sequence
    first_do = first.pond_truth.dissolved_oxygen_mg_l

    runtime.model.set_truth("dissolved_oxygen_mg_l", 3.0)
    runtime.tick(60)
    playback = runtime.playback_frame(frame_sequence)

    assert playback["snapshot"]["pond_truth"]["dissolved_oxygen_mg_l"] == first_do
    assert playback["snapshot"]["run_id"] == runtime.run_id
    assert case("historian_playback_consistency").status == GateStatus.PASS


def test_heat_wave_is_classified_and_feeding_is_inhibited() -> None:
    runtime = make_runtime(ambient_temperature=40.0)
    snapshot = runtime.tick(6 * 3600)

    assert snapshot.pond_truth.temperature_c >= POLICY.temperature_emergency_above
    assert snapshot.classification.state == SystemState.EMERGENCY
    assert "TEMPERATURE_EMERGENCY" in snapshot.classification.reasons
    assert snapshot.commands["feeder"].accepted is True
    assert snapshot.commands["feeder"].final_on is False
    assert snapshot.incidents
    assert case("heat_wave_safety_classification").status == GateStatus.PASS


def test_sensor_reference_discriminates_real_fault_stuck_and_drift() -> None:
    stuck = make_runtime(dissolved_oxygen=6.0)
    stuck.sensors.set_availability("do_reference", None)
    stuck.tick(0)
    stuck.sensors.set_fault("do", SensorFault("stuck"))
    stuck.model.set_truth("dissolved_oxygen_mg_l", 3.5)

    pending = stuck.tick(0)
    assert pending.validated["do"].quality == DataQuality.SUSPECT
    assert pending.classification.state == SystemState.DEGRADED

    detected_stuck = stuck.tick(0)
    assert detected_stuck.validated["do"].sensor_id == "do_reference"
    assert detected_stuck.validated["do"].value == 3.5
    assert "PRIMARY_REJECTED:STUCK_SUSPECTED" in detected_stuck.validated["do"].reasons
    assert detected_stuck.classification.state == SystemState.CORRECTING
    assert detected_stuck.commands["backup_aerator"].final_on is True

    drift = make_runtime(dissolved_oxygen=6.0)
    drift.sensors.set_availability("do_reference", None)
    drift.tick(0)
    drift.sensors.set_fault("do", SensorFault("drift", 1.0))
    first_drift = drift.tick(0)
    assert first_drift.validated["do"].quality == DataQuality.SUSPECT
    detected_drift = drift.tick(0)
    assert detected_drift.validated["do"].sensor_id == "do_reference"
    assert detected_drift.validated["do"].value == 6.0
    assert (
        "PRIMARY_REJECTED:DRIFT_OR_DISAGREEMENT_SUSPECTED"
        in detected_drift.validated["do"].reasons
    )
    assert detected_drift.classification.state == SystemState.NORMAL

    real_fault = make_runtime(dissolved_oxygen=6.0)
    real_fault.sensors.set_availability("do_reference", None)
    real_fault.tick(0)
    real_fault.model.set_truth("dissolved_oxygen_mg_l", 3.5)
    genuine = real_fault.tick(0)
    assert genuine.validated["do"].sensor_id == "do"
    assert genuine.validated["do"].quality == DataQuality.GOOD
    assert "FALLBACK_REFERENCE" not in genuine.validated["do"].reasons
    assert genuine.classification.state == SystemState.CORRECTING
    assert genuine.commands["backup_aerator"].final_on is True
    assert case("sensor_stuck_drift_discrimination").status == GateStatus.PASS


def test_partial_actuator_degradation_is_detected_by_process_verification() -> None:
    policy = SimulationControlPolicy(
        do_watch_below=5.0,
        do_emergency_below=4.0,
        do_recover_above=5.5,
        flow_watch_below=8.0,
        water_level_low_below=70.0,
        verification_delay_seconds=1.0,
        do_verification_min_delta=0.2,
        temperature_watch_above=30.0,
        temperature_emergency_above=32.0,
    )
    runtime = make_runtime(dissolved_oxygen=4.6, policy=policy)
    runtime.actuators.set_effectiveness("backup_aerator", 0.1)

    first = runtime.tick(0)
    assert first.feedback["backup_aerator"].feedback_on is True
    assert first.feedback["backup_aerator"].effectiveness == 0.1
    assert first.assets["backup_aerator"].effectiveness == 0.1

    second = runtime.tick(2)
    assert runtime.actuators.assets["backup_aerator"].feedback_on is True
    assert any(
        task.asset_id == "backup_aerator"
        and task.status == VerificationStatus.FAILED_RESPONSE
        for task in second.verification
    )
    assert any(
        alarm.condition_key.startswith("VERIFICATION:") for alarm in second.alarms
    )

    checkpoint = runtime.capture_checkpoint()
    resumed = make_runtime(policy=policy)
    resumed.restore_checkpoint(checkpoint)
    assert resumed.actuators.assets["backup_aerator"].effectiveness == 0.1
    assert resumed.actuators.assets["backup_aerator"].feedback_on is False
    assert case("partial_actuator_degradation").status == GateStatus.PASS


def test_matrix_is_complete_and_end_to_end_gate_is_hold_until_gaps_close() -> None:
    payload = matrix_payload()
    case_ids = {item.case_id for item in V1_REGRESSION_MATRIX}

    required = {
        "restart_manual_maintenance",
        "restart_sensor_calibration",
        "restart_water_change",
        "restart_filter_clean",
        "restart_partial_shutdown",
        "restart_safe_total_shutdown",
        "blackout_restart_recovery_sync",
        "main_pump_failure_backup_flow",
        "failed_correction_escalation",
        "sensor_dropout_vs_real_low_do",
        "water_level_fault_detection",
        "supervisory_network_loss_local_control",
        "combined_fault_incident_chronology",
        "historian_playback_consistency",
        "heat_wave_safety_classification",
        "sensor_stuck_drift_discrimination",
        "partial_actuator_degradation",
        "low_water_autonomous_recovery",
    }
    assert case_ids == required
    assert payload["end_to_end_gate"] == GateStatus.HOLD
    assert payload["pass_count"] == 17
    assert payload["hold_count"] == 1
