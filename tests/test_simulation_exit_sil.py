from datetime import UTC, datetime

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    AlarmLifecycle,
    AvailabilityState,
    BaselineStatus,
    CommandOwner,
    DataQuality,
    ModuleInstallationState,
    OperatingMode,
    SystemState,
    VerificationStatus,
)
from smart_koi_pond.domain.models import PondState
from smart_koi_pond.scenarios.sil_stress_matrix import (
    SIMULATION_EXIT_SIL_MATRIX,
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
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
    temperature_watch_above=30.0,
    temperature_emergency_above=32.0,
)


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


def make_runtime(
    *,
    dissolved_oxygen: float = 6.0,
    ambient_temperature: float = 28.0,
    oxygen_demand: float = 0.2,
    policy: SimulationControlPolicy = POLICY,
) -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, dissolved_oxygen, 7.2, 85.0),
            EnvironmentInputs(
                ambient_temperature,
                oxygen_demand,
            ),
        ),
        policy,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="simulation-exit-sil-v015",
        config_version="simulation-exit-sil-v015",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def restored(runtime: DigitalTwinRuntime) -> DigitalTwinRuntime:
    replacement = make_runtime(policy=runtime.policy)
    replacement.restore_checkpoint(runtime.capture_checkpoint())
    return replacement


def matrix_case(case_id: str):
    return next(item for item in SIMULATION_EXIT_SIL_MATRIX if item.case_id == case_id)


def test_sil_01_low_do_boundary_hysteresis() -> None:
    runtime = make_runtime(dissolved_oxygen=5.01)
    normal = runtime.tick(0)
    assert normal.classification.state == SystemState.NORMAL

    runtime.model.set_truth("dissolved_oxygen_mg_l", 5.0)
    watch_boundary = runtime.tick(0)
    assert "DO_LOW" in watch_boundary.classification.reasons
    assert watch_boundary.commands["backup_aerator"].final_on is True
    assert runtime.actuators.assets["backup_aerator"].feedback_on is True

    runtime.model.set_truth("dissolved_oxygen_mg_l", 4.0)
    emergency_boundary = runtime.tick(0)
    assert "DO_EMERGENCY" in emergency_boundary.classification.reasons
    assert emergency_boundary.commands["feeder"].final_on is False

    runtime.model.set_truth("dissolved_oxygen_mg_l", 5.2)
    recovery_band = runtime.tick(0)
    assert "backup_aerator" not in recovery_band.commands
    assert runtime.actuators.assets["backup_aerator"].feedback_on is True

    runtime.model.set_truth("dissolved_oxygen_mg_l", 5.5)
    recovered = runtime.tick(0)
    assert recovered.commands["backup_aerator"].final_on is False
    assert runtime.actuators.assets["backup_aerator"].feedback_on is False
    assert matrix_case("sil_01_low_do_boundary_hysteresis").status == GateStatus.PASS


def test_sil_02_heat_wave_boundary_feeding_inhibit() -> None:
    runtime = make_runtime()
    runtime.model.set_truth("temperature_c", 29.99)
    below_watch = runtime.tick(0)
    assert below_watch.classification.state == SystemState.NORMAL

    runtime.model.set_truth("temperature_c", 30.0)
    watch = runtime.tick(0)
    assert watch.classification.state == SystemState.WATCH
    assert "TEMPERATURE_HIGH" in watch.classification.reasons

    runtime.model.set_truth("temperature_c", 32.0)
    emergency = runtime.tick(0)
    assert emergency.classification.state == SystemState.EMERGENCY
    assert "TEMPERATURE_EMERGENCY" in emergency.classification.reasons
    assert emergency.commands["feeder"].final_on is False
    assert all("cool" not in asset_id for asset_id in emergency.commands)

    runtime.model.set_truth("temperature_c", 29.99)
    recovered = runtime.tick(0)
    assert recovered.classification.state == SystemState.NORMAL
    assert (
        matrix_case("sil_02_heat_wave_boundary_feeding_inhibit").status
        == GateStatus.PASS
    )


def test_sil_03_low_water_boundary_cutoff_lockout() -> None:
    policy = low_water_policy()
    runtime = make_runtime(policy=policy)
    runtime.model.set_truth("water_level_pct", 70.0)
    at_trigger_boundary = runtime.tick(0)
    assert "top_up_valve" not in at_trigger_boundary.commands

    runtime.model.set_truth("water_level_pct", 69.9)
    started = runtime.tick(0)
    assert started.commands["top_up_valve"].final_on is True

    runtime.model.set_truth("water_level_pct", 72.0)
    target = runtime.tick(2)
    assert target.commands["top_up_valve"].owner == CommandOwner.SAFETY
    assert target.commands["top_up_valve"].final_on is False
    assert target.water_recovery["lockout_reason"] is None

    cutoff = make_runtime(policy=policy)
    cutoff.model.set_truth("water_level_pct", 60.0)
    cutoff.tick(0)
    cutoff.model.set_truth("water_level_pct", 80.0)
    aborted = cutoff.tick(0)
    assert aborted.commands["top_up_valve"].owner == CommandOwner.SAFETY
    assert aborted.commands["top_up_valve"].final_on is False
    assert aborted.water_recovery["lockout_reason"] == "HARD_HIGH_LEVEL_CUTOFF"
    assert (
        matrix_case("sil_03_low_water_boundary_cutoff_lockout").status
        == GateStatus.PASS
    )


def test_sil_04_stale_fresh_stale_no_false_normal() -> None:
    runtime = make_runtime()
    runtime.sensors.set_availability("do", AvailabilityState.STALE)
    stale = runtime.tick(0)
    assert stale.validated["do"].availability == AvailabilityState.STALE
    assert stale.validated["do"].quality == DataQuality.INVALID
    assert stale.validated["do"].value is None
    assert stale.classification.state == SystemState.DEGRADED

    runtime.sensors.set_availability("do", None)
    fresh = runtime.tick(0)
    assert fresh.validated["do"].availability == AvailabilityState.AVAILABLE
    assert fresh.validated["do"].quality == DataQuality.GOOD
    assert fresh.classification.state == SystemState.NORMAL

    runtime.sensors.set_availability("do", AvailabilityState.STALE)
    stale_again = runtime.tick(0)
    assert stale_again.validated["do"].quality == DataQuality.INVALID
    assert stale_again.validated["do"].value is None
    assert stale_again.classification.state == SystemState.DEGRADED
    assert (
        matrix_case("sil_04_stale_fresh_stale_no_false_normal").status
        == GateStatus.PASS
    )


def test_sil_05_sensor_disagreement_persistence_recovery() -> None:
    runtime = make_runtime()
    runtime.sensors.set_availability("do_reference", None)
    runtime.tick(0)
    runtime.sensors.set_fault("do", SensorFault("drift", 1.0))

    pending = runtime.tick(0)
    assert pending.validated["do"].quality == DataQuality.SUSPECT
    assert "REFERENCE_DISAGREEMENT_PENDING" in pending.validated["do"].reasons

    fallback = runtime.tick(0)
    assert fallback.validated["do"].sensor_id == "do_reference"
    assert fallback.validated["do"].quality == DataQuality.GOOD
    assert "FALLBACK_REFERENCE" in fallback.validated["do"].reasons

    checkpoint = runtime.capture_checkpoint()
    resumed = make_runtime(policy=runtime.policy)
    resumed.restore_checkpoint(checkpoint)
    after_restart = resumed.tick(0)
    assert after_restart.validated["do"].quality == DataQuality.SUSPECT
    assert "REFERENCE_DISAGREEMENT_PENDING" in after_restart.validated["do"].reasons

    resumed.sensors.set_fault("do", None)
    recovered = resumed.tick(0)
    assert recovered.validated["do"].sensor_id == "do"
    assert recovered.validated["do"].quality == DataQuality.GOOD
    assert (
        matrix_case("sil_05_sensor_disagreement_persistence_recovery").status
        == GateStatus.PASS
    )


def test_sil_06_feedback_on_process_no_response() -> None:
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
    started = runtime.tick(0)
    incident_id = started.incidents[0].incident_id
    assert started.feedback["backup_aerator"].feedback_on is True

    failed = runtime.tick(2)
    assert any(
        task.status == VerificationStatus.FAILED_RESPONSE
        for task in failed.verification
    )
    assert any(
        alarm.condition_key.startswith("VERIFICATION:")
        for alarm in failed.alarms
    )
    assert failed.incidents[0].incident_id == incident_id
    assert (
        matrix_case("sil_06_feedback_on_process_no_response").status
        == GateStatus.PASS
    )


def test_sil_07_partial_actuator_degradation_extended() -> None:
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
    started = runtime.tick(0)
    assert started.feedback["backup_aerator"].feedback_on is True
    assert started.feedback["backup_aerator"].effectiveness == 0.1

    failed = runtime.tick(2)
    assert any(
        task.asset_id == "backup_aerator"
        and task.status == VerificationStatus.FAILED_RESPONSE
        for task in failed.verification
    )

    later = runtime.tick(300)
    assert later.assets["backup_aerator"].effectiveness == 0.1
    assert any(
        task.asset_id == "backup_aerator"
        and task.status == VerificationStatus.FAILED_RESPONSE
        for task in later.verification
    )
    assert (
        matrix_case("sil_07_partial_actuator_degradation_extended").status
        == GateStatus.PASS
    )


def test_sil_08_main_loss_degraded_backup_capability() -> None:
    runtime = make_runtime()
    runtime.actuators.set_availability("main_pump", AvailabilityState.FAILED)
    runtime.actuators.set_effectiveness("backup_pump", 0.25)

    first = runtime.tick(0)
    assert first.commands["backup_pump"].final_on is True
    assert first.capability.circulation_paths_available == 1

    second = runtime.tick(60)
    assert second.pond_truth.circulation_flow_l_min == 2.5
    assert "FLOW_LOW" in second.classification.reasons
    assert second.classification.state != SystemState.NORMAL
    assert second.capability.critical_capability_lost is False
    assert (
        matrix_case("sil_08_main_loss_degraded_backup_capability").status
        == GateStatus.PASS
    )


def test_sil_09_combined_low_do_circulation_fault() -> None:
    runtime = make_runtime(dissolved_oxygen=3.8)
    runtime.actuators.set_availability("main_pump", AvailabilityState.FAILED)
    snapshot = runtime.tick(0)

    assert snapshot.commands["backup_pump"].final_on is True
    assert snapshot.commands["backup_aerator"].final_on is True
    assert snapshot.incidents
    evidence = runtime.incident_evidence(snapshot.incidents[0].incident_id)
    sequences = [event.sequence for event in evidence]
    assert sequences == list(range(sequences[0], sequences[-1] + 1))
    assert (
        matrix_case("sil_09_combined_low_do_circulation_fault").status
        == GateStatus.PASS
    )


def test_sil_10_restart_active_fault_pending_verification() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    before = runtime.tick(0)
    assert any(
        task.status == VerificationStatus.PENDING for task in before.verification
    )
    incident_id = before.incidents[0].incident_id

    resumed = restored(runtime)
    assert resumed.operating_mode == OperatingMode.RECOVERY_SYNC
    assert resumed.actuators.assets["backup_aerator"].feedback_on is False
    assert any(
        task.status == VerificationStatus.ABORTED_BY_MODE_CHANGE
        for task in resumed.verification.tasks
    )
    assert any(
        event.code == "VERIFICATION_ABORTED_ON_RESTART"
        for event in resumed.events.events
    )
    assert resumed.alarm_incidents.active_incident is not None
    assert resumed.alarm_incidents.active_incident.incident_id == incident_id
    assert (
        matrix_case("sil_10_restart_active_fault_pending_verification").status
        == GateStatus.PASS
    )


def test_sil_11_restart_low_water_recovery_abort() -> None:
    policy = low_water_policy()
    runtime = make_runtime(policy=policy)
    runtime.model.set_truth("water_level_pct", 60.0)
    active = runtime.tick(0)
    assert active.water_recovery["active_attempt_id"] == "low-water-1"
    assert runtime.actuators.assets["top_up_valve"].feedback_on is True

    resumed = restored(runtime)
    assert resumed.actuators.assets["top_up_valve"].feedback_on is False
    assert resumed.low_water_recovery.active is None
    assert resumed.low_water_recovery.lockout_reason == "RUNTIME_RESTART_ABORT"
    assert any(
        event.code == "LOW_WATER_RECOVERY_ABORTED_ON_RESTART"
        for event in resumed.events.events
    )

    after = resumed.tick(0)
    assert "top_up_valve" not in after.commands
    assert after.water_recovery["lockout_reason"] == "RUNTIME_RESTART_ABORT"
    assert (
        matrix_case("sil_11_restart_low_water_recovery_abort").status
        == GateStatus.PASS
    )


def test_sil_12_mode_takeover_active_correction() -> None:
    runtime = make_runtime(policy=low_water_policy())
    runtime.model.set_truth("water_level_pct", 60.0)
    runtime.tick(0)
    assert runtime.actuators.assets["top_up_valve"].feedback_on is True

    runtime.start_manual_maintenance(
        ["top_up_valve"],
        "SIL takeover",
    )
    aborted = runtime.tick(0)
    assert aborted.operating_mode == OperatingMode.MANUAL_MAINTENANCE
    assert aborted.commands["top_up_valve"].owner == CommandOwner.SAFETY
    assert aborted.commands["top_up_valve"].final_on is False
    assert aborted.water_recovery["lockout_reason"].startswith(
        "UNSAFE_OPERATING_MODE:"
    )
    assert (
        matrix_case("sil_12_mode_takeover_active_correction").status
        == GateStatus.PASS
    )


def test_sil_13_filter_clean_life_support_interaction() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    runtime.start_filter_clean(["main_pump"], "SIL filter interaction")
    snapshot = runtime.tick(0)

    assert snapshot.operating_mode == OperatingMode.FILTER_CLEAN
    assert snapshot.commands["backup_pump"].final_on is True
    assert snapshot.commands["backwash_valve"].final_on is True
    assert snapshot.commands["backup_aerator"].final_on is True
    assert snapshot.assets["main_pump"].availability == (
        AvailabilityState.MAINTENANCE_UNAVAILABLE
    )
    assert (
        matrix_case("sil_13_filter_clean_life_support_interaction").status
        == GateStatus.PASS
    )


def test_sil_14_repeated_fault_recovery_lifecycle() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    first = runtime.tick(0)
    first_alarm = first.alarms[0]
    acknowledged = runtime.acknowledge_alarm(first_alarm.alarm_id, "sil-operator")
    assert acknowledged.lifecycle != AlarmLifecycle.RESOLVED

    still_faulted = runtime.tick(0)
    current_first = next(
        alarm for alarm in still_faulted.alarms if alarm.alarm_id == first_alarm.alarm_id
    )
    assert current_first.lifecycle != AlarmLifecycle.RESOLVED
    assert current_first.acknowledged_at is not None

    runtime.model.set_truth("dissolved_oxygen_mg_l", 6.0)
    runtime.tick(0)
    recovered = runtime.tick(0)
    resolved_first = next(
        alarm for alarm in recovered.alarms if alarm.alarm_id == first_alarm.alarm_id
    )
    assert resolved_first.lifecycle == AlarmLifecycle.RESOLVED

    runtime.model.set_truth("dissolved_oxygen_mg_l", 4.6)
    repeated = runtime.tick(0)
    active = [
        alarm for alarm in repeated.alarms if alarm.lifecycle != AlarmLifecycle.RESOLVED
    ]
    assert active
    assert all(alarm.alarm_id != first_alarm.alarm_id for alarm in active)
    assert (
        matrix_case("sil_14_repeated_fault_recovery_lifecycle").status
        == GateStatus.PASS
    )


def test_sil_15_accelerated_long_run_playback() -> None:
    runtime = make_runtime()
    runtime.clock.acceleration = 3600.0

    first = runtime.tick(1)
    first_sequence = runtime.historian.latest_sequence
    first_do = first.pond_truth.dissolved_oxygen_mg_l
    for _ in range(23):
        runtime.tick(1)

    history = runtime.recent_history(limit=24)
    assert len(history) == 24
    timestamps = [frame["timestamp"] for frame in history]
    assert timestamps == sorted(timestamps)
    assert history[-1]["frame_sequence"] - history[0]["frame_sequence"] == 23

    playback = runtime.playback_frame(first_sequence)
    assert playback["snapshot"]["pond_truth"]["dissolved_oxygen_mg_l"] == first_do
    assert playback["timestamp"] == history[0]["timestamp"]
    assert (
        matrix_case("sil_15_accelerated_long_run_playback").status
        == GateStatus.PASS
    )


def test_sil_17_capability_loss_restoration() -> None:
    runtime = make_runtime()
    healthy = runtime.tick(0)
    assert healthy.capability.registry is not None
    assert healthy.capability.registry.baseline.status == BaselineStatus.SATISFIED

    runtime.configure_module(
        "ph_monitoring",
        installation_state=ModuleInstallationState.NOT_INSTALLED,
    )
    lost = runtime.tick(0)
    assert lost.capability.registry is not None
    assert lost.capability.registry.baseline.status == BaselineStatus.NOT_MET
    assert lost.classification.state == SystemState.DEGRADED
    assert lost.validated["ph"].availability == AvailabilityState.UNSUPPORTED

    runtime.configure_module(
        "ph_monitoring",
        installation_state=ModuleInstallationState.INSTALLED,
    )
    restored_snapshot = runtime.tick(0)
    assert restored_snapshot.capability.registry is not None
    assert (
        restored_snapshot.capability.registry.baseline.status
        == BaselineStatus.SATISFIED
    )
    assert restored_snapshot.validated["ph"].quality == DataQuality.GOOD
    assert restored_snapshot.classification.state == SystemState.NORMAL
    assert (
        matrix_case("sil_17_capability_loss_restoration").status
        == GateStatus.PASS
    )


def test_sil_18_repeated_combined_fault_playback() -> None:
    runtime = make_runtime()
    runtime.tick(0)

    runtime.model.set_truth("dissolved_oxygen_mg_l", 3.8)
    runtime.actuators.set_availability("main_pump", AvailabilityState.FAILED)
    combined = runtime.tick(0)
    combined_sequence = runtime.historian.latest_sequence
    assert combined.incidents

    runtime.actuators.set_availability("main_pump", AvailabilityState.AVAILABLE)
    runtime.model.set_truth("dissolved_oxygen_mg_l", 6.0)
    runtime.tick(0)
    runtime.tick(0)

    runtime.model.set_truth("dissolved_oxygen_mg_l", 4.6)
    runtime.tick(0)

    playback = runtime.playback_frame(combined_sequence)
    assert playback["snapshot"]["pond_truth"]["dissolved_oxygen_mg_l"] == 3.8
    assert playback["snapshot"]["assets"]["main_pump"]["availability"] == "FAILED"
    assert playback["frame_sequence"] == combined_sequence
    assert (
        matrix_case("sil_18_repeated_combined_fault_playback").status
        == GateStatus.PASS
    )


def test_sil_19_invalid_level_during_top_up() -> None:
    runtime = make_runtime(policy=low_water_policy())
    runtime.model.set_truth("water_level_pct", 60.0)
    runtime.tick(0)
    assert runtime.actuators.assets["top_up_valve"].feedback_on is True

    runtime.sensors.set_availability("water_level", AvailabilityState.STALE)
    aborted = runtime.tick(0)
    assert aborted.validated["water_level"].quality == DataQuality.INVALID
    assert aborted.commands["top_up_valve"].owner == CommandOwner.SAFETY
    assert aborted.commands["top_up_valve"].final_on is False
    assert aborted.water_recovery["lockout_reason"] == (
        "INVALID_WATER_LEVEL_EVIDENCE"
    )
    assert runtime.actuators.assets["top_up_valve"].feedback_on is False
    assert (
        matrix_case("sil_19_invalid_level_during_top_up").status
        == GateStatus.PASS
    )


def test_sil_20_ack_unresolved_repeated_fault() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    first = runtime.tick(0)
    alarm = first.alarms[0]
    acknowledged = runtime.acknowledge_alarm(alarm.alarm_id, "sil-operator")
    assert acknowledged.acknowledged_at is not None
    assert acknowledged.lifecycle != AlarmLifecycle.RESOLVED

    still_active = runtime.tick(0)
    same_alarm = next(
        item for item in still_active.alarms if item.alarm_id == alarm.alarm_id
    )
    assert same_alarm.lifecycle != AlarmLifecycle.RESOLVED
    assert same_alarm.acknowledged_at == acknowledged.acknowledged_at

    runtime.model.set_truth("dissolved_oxygen_mg_l", 6.0)
    runtime.tick(0)
    resolved = runtime.tick(0)
    resolved_alarm = next(
        item for item in resolved.alarms if item.alarm_id == alarm.alarm_id
    )
    assert resolved_alarm.lifecycle == AlarmLifecycle.RESOLVED

    runtime.model.set_truth("dissolved_oxygen_mg_l", 4.6)
    repeated = runtime.tick(0)
    active = [
        item for item in repeated.alarms if item.lifecycle != AlarmLifecycle.RESOLVED
    ]
    assert active
    assert all(item.alarm_id != alarm.alarm_id for item in active)
    assert (
        matrix_case("sil_20_ack_unresolved_repeated_fault").status
        == GateStatus.PASS
    )


def test_sil_matrix_preserves_hold_for_unmodeled_network_fault_injection() -> None:
    payload = matrix_payload()
    assert len(SIMULATION_EXIT_SIL_MATRIX) == 20
    assert payload["gate"] == GateStatus.HOLD
    assert payload["pass_count"] == 19
    assert payload["hold_count"] == 1

    hold = next(
        item
        for item in SIMULATION_EXIT_SIL_MATRIX
        if item.case_id == "sil_16_supervisory_network_loss_active_fault"
    )
    assert hold.status == GateStatus.HOLD
    assert hold.test_reference == "HOLD:NETWORK_FAULT_INJECTION_NOT_MODELED"
