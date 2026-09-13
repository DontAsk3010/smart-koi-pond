import json
from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    CommandOwner,
    OperatingMode,
    VerificationStatus,
    WorkflowPhase,
)
from smart_koi_pond.domain.models import PondState
from smart_koi_pond.persistence import JsonCheckpointStore

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
)


def make_runtime(*, dissolved_oxygen: float = 6.0, config_version: str = "test-config-v1"):
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, dissolved_oxygen, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="run-test-001",
        config_version=config_version,
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_normal_restart_reconciles_without_stale_command_replay() -> None:
    runtime = make_runtime()
    runtime.tick(30)
    checkpoint = runtime.capture_checkpoint()

    restored = make_runtime()
    restored.restore_checkpoint(checkpoint)

    assert restored.run_id == runtime.run_id
    assert restored.operating_mode == OperatingMode.RECOVERY_SYNC
    assert all(not asset.feedback_on for asset in restored.actuators.assets.values())

    restart_event = restored.events.events[-1]
    assert restart_event.code == "RUNTIME_RESTART_RECONCILIATION_REQUIRED"
    assert restart_event.payload["stale_command_replay"] is False

    first = restored.tick(1)
    assert restored.actuators.assets["main_pump"].feedback_on is True
    assert restored.actuators.assets["primary_aerator"].feedback_on is True
    assert first.operating_mode == OperatingMode.NORMAL_AUTO


def test_maintenance_lock_survives_restart_and_requires_explicit_release() -> None:
    runtime = make_runtime()
    runtime.start_manual_maintenance(
        ["main_pump"],
        "clean pump basket",
        service_locked=["main_pump"],
    )
    checkpoint = runtime.capture_checkpoint()

    restored = make_runtime()
    restored.restore_checkpoint(checkpoint)

    main = restored.actuators.assets["main_pump"]
    assert restored.operating_mode == OperatingMode.HOLD
    assert restored.modes.phase == WorkflowPhase.HOLD
    assert main.owner == CommandOwner.MAINTENANCE
    assert main.availability == AvailabilityState.MAINTENANCE_UNAVAILABLE

    restored.tick(1)
    assert restored.operating_mode == OperatingMode.HOLD

    restored.request_return_to_auto()
    restored.tick(1)
    assert restored.operating_mode == OperatingMode.NORMAL_AUTO
    assert restored.actuators.assets["main_pump"].owner == CommandOwner.AUTO
    assert restored.actuators.assets["main_pump"].availability == AvailabilityState.AVAILABLE


def test_checkpoint_rejects_configuration_lineage_mismatch() -> None:
    checkpoint = make_runtime(config_version="config-A").capture_checkpoint()
    restored = make_runtime(config_version="config-B")

    with pytest.raises(ValueError, match="config_version"):
        restored.restore_checkpoint(checkpoint)


def test_pending_verification_is_aborted_on_restart() -> None:
    runtime = make_runtime(dissolved_oxygen=4.6)
    runtime.actuators.assets["backup_aerator"].feedback_on = False
    runtime._last_feedback = runtime.actuators.feedback_map()
    runtime.tick(30)
    assert runtime.verification.tasks[0].status == VerificationStatus.PENDING

    restored = make_runtime(dissolved_oxygen=4.6)
    restored.restore_checkpoint(runtime.capture_checkpoint())

    assert restored.verification.tasks[0].status == VerificationStatus.ABORTED_BY_MODE_CHANGE
    assert any(
        event.code == "VERIFICATION_ABORTED_ON_RESTART"
        for event in restored.events.events
    )


def test_event_sequence_continues_after_restart() -> None:
    runtime = make_runtime()
    runtime.tick(30)
    last_before = runtime.events.events[-1].sequence

    restored = make_runtime()
    restored.restore_checkpoint(runtime.capture_checkpoint())
    assert restored.events.events[last_before - 1].sequence == last_before
    assert restored.events.events[-1].sequence > last_before

    restored.tick(1)
    sequences = [event.sequence for event in restored.events.events]
    assert sequences == list(range(1, len(sequences) + 1))


def test_canonical_publication_is_json_safe_and_cursor_ordered() -> None:
    runtime = make_runtime()
    first = runtime.tick(30)
    publication = runtime.publish(first)
    json.dumps(publication)

    assert publication["schema_version"] == 1
    assert publication["run_id"] == runtime.run_id
    assert publication["events"]
    assert [event["sequence"] for event in publication["events"]] == sorted(
        event["sequence"] for event in publication["events"]
    )

    cursor = publication["next_event_sequence"]
    second = runtime.tick(30)
    delta = runtime.publish(second, after_sequence=cursor)
    assert all(event["sequence"] > cursor for event in delta["events"])
    assert delta["next_event_sequence"] >= cursor


def test_snapshot_is_point_in_time_not_mutated_by_later_ticks() -> None:
    runtime = make_runtime()
    first = runtime.tick(60)
    first_do = first.pond_truth.dissolved_oxygen_mg_l

    runtime.tick(600)
    assert first.pond_truth.dissolved_oxygen_mg_l == first_do


def test_json_checkpoint_store_round_trip(tmp_path) -> None:
    runtime = make_runtime()
    runtime.tick(30)
    checkpoint = runtime.capture_checkpoint()
    store = JsonCheckpointStore(tmp_path / "runtime-checkpoint.json")

    store.write(checkpoint)
    loaded = store.read()

    assert loaded["schema_version"] == checkpoint["schema_version"]
    assert loaded["run_id"] == checkpoint["run_id"]
    assert loaded["config_version"] == checkpoint["config_version"]
