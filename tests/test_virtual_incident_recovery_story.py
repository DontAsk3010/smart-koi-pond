from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.incident_recovery_story_ui import (
    INCIDENT_RECOVERY_STORY_SCRIPT,
    INCIDENT_RECOVERY_STORY_STYLE,
)
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.models import PondState


def test_virtual_browser_contains_incident_recovery_story_surface() -> None:
    assert "incident-recovery-story-style" in INCIDENT_RECOVERY_STORY_STYLE
    assert "Trigger / Detect" in INCIDENT_RECOVERY_STORY_SCRIPT
    assert "Command / Fallback" in INCIDENT_RECOVERY_STORY_SCRIPT
    assert "Process Verification" in INCIDENT_RECOVERY_STORY_SCRIPT
    assert "Escalate / Lockout" in INCIDENT_RECOVERY_STORY_SCRIPT
    assert INCIDENT_RECOVERY_STORY_STYLE in COMPOSED_INDEX_HTML
    assert INCIDENT_RECOVERY_STORY_SCRIPT in COMPOSED_INDEX_HTML


def test_incident_story_is_point_in_time_and_hides_future_playback_evidence() -> None:
    for token in (
        "playbackMode",
        "displayed?.timestamp",
        "time>cutoff",
        "future evidence after the selected playback timestamp is hidden",
        "start_event_sequence",
        "end_event_sequence",
    ):
        assert token in INCIDENT_RECOVERY_STORY_SCRIPT


def test_incident_story_never_infers_missing_recovery_or_verification() -> None:
    assert "NO EVIDENCE AT THIS POINT" in INCIDENT_RECOVERY_STORY_SCRIPT
    assert "No stage outcome is inferred." in INCIDENT_RECOVERY_STORY_SCRIPT
    assert "Command/feedback alone never proves recovery." in INCIDENT_RECOVERY_STORY_SCRIPT
    assert "NO VERIFICATION TASK EVIDENCE" in INCIDENT_RECOVERY_STORY_SCRIPT
    assert "No resolution claim" in INCIDENT_RECOVERY_STORY_SCRIPT


def test_incident_story_is_read_only() -> None:
    for forbidden in (
        "fetch('/api/command'",
        'fetch("/api/command"',
        "sendCommand(",
        "ackAlarm(",
        "manual_command",
        "return_to_auto",
    ):
        assert forbidden not in INCIDENT_RECOVERY_STORY_SCRIPT


def test_runtime_incident_evidence_is_ordered_for_story_projection() -> None:
    policy = SimulationControlPolicy(
        do_watch_below=5.0,
        do_emergency_below=4.0,
        do_recover_above=5.5,
        flow_watch_below=8.0,
        water_level_low_below=70.0,
        verification_delay_seconds=1.0,
        do_verification_min_delta=10.0,
    )
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, 4.6, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        policy,
        clock=SimulationClock.start(),
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()

    first = runtime.tick(0.0)
    incident = first.incidents[0]
    runtime.tick(2.0)
    evidence = runtime.incident_evidence(incident.incident_id)

    sequences = [event.sequence for event in evidence]
    assert sequences == sorted(sequences)
    assert sequences[0] >= incident.start_event_sequence
    assert any(event.event_type.value == "COMMAND" for event in evidence)
    assert any(event.event_type.value == "VERIFICATION" for event in evidence)
