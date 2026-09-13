import json
import threading
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.web_ui import INDEX_HTML
from smart_koi_pond.dashboard.webapp import create_server
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import CommandOwner
from smart_koi_pond.domain.models import PondState

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
)


def make_runtime() -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, 6.0, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="ui-test-run",
        config_version="ui-test-config",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_snapshot_exposes_runtime_identity_clock_and_all_assets() -> None:
    runtime = make_runtime()
    snapshot = runtime.tick(0)

    assert snapshot.run_id == "ui-test-run"
    assert snapshot.config_version == "ui-test-config"
    assert snapshot.simulation_paused is False
    assert snapshot.simulation_acceleration == 1.0
    assert set(snapshot.assets) == set(runtime.actuators.assets)
    assert snapshot.assets["main_pump"].owner == CommandOwner.AUTO
    assert snapshot.assets["main_pump"].feedback_on is True


def test_pause_freezes_both_authoritative_clock_and_pond_truth() -> None:
    runtime = make_runtime()
    service = RuntimeApplicationService(runtime)
    before = service.last_snapshot
    before_truth = before.pond_truth.dissolved_oxygen_mg_l
    before_time = before.timestamp

    service.command("pause", role="operator")
    paused = service.step(120)

    assert paused.timestamp == before_time
    assert paused.pond_truth.dissolved_oxygen_mg_l == before_truth
    assert paused.simulation_paused is True


def test_acceleration_scales_clock_and_process_model_together() -> None:
    normal = RuntimeApplicationService(make_runtime())
    accelerated = RuntimeApplicationService(make_runtime())

    accelerated.command("set_acceleration", {"value": 10}, role="engineering")
    fast = accelerated.step(60)
    slow = normal.step(600)

    assert (fast.timestamp - datetime(2026, 1, 1, tzinfo=UTC)).total_seconds() == 600
    assert fast.pond_truth.dissolved_oxygen_mg_l == pytest.approx(
        slow.pond_truth.dissolved_oxygen_mg_l
    )


def test_viewer_cannot_send_operational_command_and_rejection_is_audited() -> None:
    service = RuntimeApplicationService(make_runtime())

    with pytest.raises(PermissionError):
        service.command("pause", role="viewer")

    assert any(event.code == "UI_COMMAND_REJECTED" for event in service.runtime.events.events)


def test_publication_cursor_reconnect_returns_only_newer_events() -> None:
    service = RuntimeApplicationService(make_runtime())
    initial = service.publication(after_sequence=0)
    cursor = initial["next_event_sequence"]

    service.command("pause", role="operator")
    delta = service.publication(after_sequence=cursor)

    assert delta["events"]
    assert all(event["sequence"] > cursor for event in delta["events"])
    assert delta["snapshot"]["simulation_paused"] is True


def test_ui_shell_is_live_contract_bound_with_alarm_and_playback() -> None:
    assert "SIMULATION / NO REAL DEVICE CONTROL" in INDEX_HTML
    assert "PLAYBACK / READ ONLY" in INDEX_HTML
    assert "/api/runtime?after=" in INDEX_HTML
    assert "/api/command" in INDEX_HTML
    assert "/api/history?limit=" in INDEX_HTML
    assert "/api/playback?frame=" in INDEX_HTML
    assert "/api/incident?id=" in INDEX_HTML
    assert "acknowledge_alarm" in INDEX_HTML
    assert "Overview" in INDEX_HTML
    assert "Pond Schematic" in INDEX_HTML
    assert "Trends & Graphs" in INDEX_HTML
    assert "Scenario Simulator" in INDEX_HTML
    assert "Control Logic" in INDEX_HTML
    assert "Event Log" in INDEX_HTML
    assert "not yet implemented" not in INDEX_HTML


def test_http_adapter_serves_canonical_publication_and_role_gated_commands() -> None:
    service = RuntimeApplicationService(make_runtime())
    server = create_server(service, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        with urlopen(f"http://{host}:{port}/api/runtime?after=0", timeout=2) as response:
            publication = json.loads(response.read())
        assert publication["run_id"] == "ui-test-run"

        body = json.dumps({"action": "pause", "payload": {}}).encode()
        viewer = Request(
            f"http://{host}:{port}/api/command",
            data=body,
            headers={"Content-Type": "application/json", "X-Koi-Role": "viewer"},
            method="POST",
        )
        with pytest.raises(HTTPError) as denied:
            urlopen(viewer, timeout=2)
        assert denied.value.code == 403

        operator = Request(
            f"http://{host}:{port}/api/command",
            data=body,
            headers={"Content-Type": "application/json", "X-Koi-Role": "operator"},
            method="POST",
        )
        with urlopen(operator, timeout=2) as response:
            accepted = json.loads(response.read())
        assert accepted["accepted"] is True
        assert accepted["publication"]["snapshot"]["simulation_paused"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_historian_playback_incident_and_alarm_acknowledgement() -> None:
    service = RuntimeApplicationService(make_runtime())
    service.runtime.model.set_truth("dissolved_oxygen_mg_l", 4.6)
    service.step(0)
    current = service.last_snapshot
    alarm_id = current.alarms[0].alarm_id
    incident_id = current.incidents[0].incident_id

    server = create_server(service, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        with urlopen(f"http://{host}:{port}/api/history?limit=20", timeout=2) as response:
            history = json.loads(response.read())
        assert history["frames"]
        frame = history["frames"][-1]["frame_sequence"]

        with urlopen(
            f"http://{host}:{port}/api/playback?frame={frame}",
            timeout=2,
        ) as response:
            playback = json.loads(response.read())
        assert playback["frame_sequence"] == frame
        assert playback["snapshot"]["run_id"] == "ui-test-run"

        with urlopen(
            f"http://{host}:{port}/api/incident?id={incident_id}",
            timeout=2,
        ) as response:
            incident = json.loads(response.read())
        assert incident["incident_id"] == incident_id
        assert incident["events"]

        body = json.dumps(
            {
                "action": "acknowledge_alarm",
                "payload": {"alarm_id": alarm_id, "actor": "test-operator"},
            }
        ).encode()
        request = Request(
            f"http://{host}:{port}/api/command",
            data=body,
            headers={"Content-Type": "application/json", "X-Koi-Role": "operator"},
            method="POST",
        )
        with urlopen(request, timeout=2) as response:
            acknowledged = json.loads(response.read())

        alarm = next(
            item
            for item in acknowledged["publication"]["snapshot"]["alarms"]
            if item["alarm_id"] == alarm_id
        )
        assert alarm["acknowledged_by"] == "test-operator"
        assert alarm["lifecycle"] != "RESOLVED"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
