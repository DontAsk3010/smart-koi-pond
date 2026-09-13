from datetime import UTC, datetime

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    AlarmLifecycle,
    AvailabilityState,
    IncidentLifecycle,
    VerificationStatus,
)
from smart_koi_pond.domain.models import PondState
from smart_koi_pond.events.historian import RuntimeHistorian

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=1.0,
    do_verification_min_delta=10.0,
)


def make_runtime(
    *,
    dissolved_oxygen: float = 6.0,
    historian_path: str | None = None,
) -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, dissolved_oxygen, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="alarm-test-run",
        config_version="alarm-test-config",
        historian_path=historian_path,
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_alarm_acknowledgement_never_counts_as_resolution() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    snapshot = runtime.tick(0)
    alarm = snapshot.alarms[0]

    acknowledged = runtime.acknowledge_alarm(alarm.alarm_id, "operator")
    assert acknowledged.acknowledged_at is not None
    assert acknowledged.lifecycle != AlarmLifecycle.RESOLVED

    runtime.model.set_truth("dissolved_oxygen_mg_l", 6.0)
    recovering = runtime.tick(0)
    assert recovering.alarms[0].lifecycle == AlarmLifecycle.RECOVERING

    resolved = runtime.tick(0)
    assert resolved.alarms[0].lifecycle == AlarmLifecycle.RESOLVED
    assert resolved.alarms[0].acknowledged_at == acknowledged.acknowledged_at


def test_failed_verification_opens_escalated_alarm_inside_same_incident() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    first = runtime.tick(0)
    first_incident = first.incidents[0].incident_id

    second = runtime.tick(2)
    failed = [
        task
        for task in second.verification
        if task.status == VerificationStatus.FAILED_RESPONSE
    ]
    assert failed

    verification_alarms = [
        alarm
        for alarm in second.alarms
        if alarm.condition_key.startswith("VERIFICATION:")
    ]
    assert verification_alarms
    assert verification_alarms[0].lifecycle == AlarmLifecycle.ESCALATED
    assert second.incidents[0].incident_id == first_incident
    assert verification_alarms[0].alarm_id in second.incidents[0].alarm_ids


def test_active_alarm_and_incident_survive_runtime_restart() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    before = runtime.tick(0)
    checkpoint = runtime.capture_checkpoint()

    restored = make_runtime(dissolved_oxygen=4.6)
    restored.restore_checkpoint(checkpoint)

    assert restored.alarm_incidents.active_alarms
    assert restored.alarm_incidents.active_incident is not None
    assert (
        restored.alarm_incidents.active_incident.incident_id
        == before.incidents[0].incident_id
    )
    evidence = restored.incident_evidence(before.incidents[0].incident_id)
    assert any(
        event.code == "RUNTIME_RESTART_RECONCILIATION_REQUIRED"
        for event in evidence
    )


def test_historian_jsonl_survives_process_restart_and_is_point_in_time(
    tmp_path,
) -> None:
    path = tmp_path / "historian.jsonl"
    runtime = make_runtime(historian_path=str(path))
    first = runtime.tick(60)
    first_sequence = runtime.historian.latest_sequence
    first_do = first.pond_truth.dissolved_oxygen_mg_l

    runtime.model.set_truth("dissolved_oxygen_mg_l", 3.0)
    runtime.tick(60)

    reloaded = RuntimeHistorian(path)
    old = reloaded.by_sequence(first_sequence, run_id="alarm-test-run")
    assert old["snapshot"]["pond_truth"]["dissolved_oxygen_mg_l"] == first_do
    assert reloaded.latest_sequence >= 2


def test_incident_evidence_is_contiguous_and_preserves_lifecycle_events() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    active = runtime.tick(0)
    incident_id = active.incidents[0].incident_id

    runtime.model.set_truth("dissolved_oxygen_mg_l", 6.0)
    runtime.tick(0)
    resolved = runtime.tick(0)
    assert resolved.incidents[0].lifecycle == IncidentLifecycle.RESOLVED

    evidence = runtime.incident_evidence(incident_id)
    sequences = [event.sequence for event in evidence]
    assert sequences == list(range(sequences[0], sequences[-1] + 1))
    assert any(event.code == "INCIDENT_OPENED" for event in evidence)
    assert any(event.code == "INCIDENT_RESOLVED" for event in evidence)


def test_combined_capability_loss_and_low_do_stays_one_incident() -> None:
    runtime = make_runtime(dissolved_oxygen=3.8)
    runtime.actuators.set_availability("main_pump", AvailabilityState.PLANNED_OFF)
    runtime.actuators.set_availability("backup_pump", AvailabilityState.PLANNED_OFF)

    snapshot = runtime.tick(0)

    assert len(snapshot.incidents) == 1
    assert snapshot.incidents[0].lifecycle == IncidentLifecycle.OPEN
    assert snapshot.alarms
