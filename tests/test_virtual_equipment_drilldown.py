from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.equipment_detail_ui import EQUIPMENT_DETAIL_SCRIPT
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def test_virtual_browser_contains_interactive_equipment_drilldown() -> None:
    assert "Equipment / Process Drill-Down" in COMPOSED_INDEX_HTML
    assert "Requested / Final Command" in COMPOSED_INDEX_HTML
    assert "Device Feedback / Effect" in COMPOSED_INDEX_HTML
    assert "Module / Dependencies" in COMPOSED_INDEX_HTML
    assert "Recent matching events from loaded canonical event stream" in COMPOSED_INDEX_HTML
    assert "window.openEquipmentDetail" in EQUIPMENT_DETAIL_SCRIPT
    assert "#process [data-asset]" in EQUIPMENT_DETAIL_SCRIPT
    assert "#overviewAssets .asset" in EQUIPMENT_DETAIL_SCRIPT


def test_drilldown_reads_only_canonical_snapshot_and_loaded_event_evidence() -> None:
    for binding in (
        "s.assets?.[id]",
        "s.commands?.[id]",
        "s.feedback?.[id]",
        "s?.verification",
        "s?.capability?.registry?.modules",
        "eventBuffer",
        "playbackMode",
        "Date.parse(s.timestamp)",
    ):
        assert binding in EQUIPMENT_DETAIL_SCRIPT
    assert "NO CURRENT COMMAND PUBLISHED FOR THIS SNAPSHOT" in EQUIPMENT_DETAIL_SCRIPT
    assert "NO VERIFICATION TASK PUBLISHED FOR THIS ASSET/SNAPSHOT" in EQUIPMENT_DETAIL_SCRIPT
    assert "NO MATCHING EVENT IN THE LOADED EVENT STREAM FOR THIS POINT IN TIME" in (
        EQUIPMENT_DETAIL_SCRIPT
    )


def test_historian_playback_preserves_equipment_diagnostic_snapshot_fields() -> None:
    runtime = build_integrated_virtual_runtime()
    service = RuntimeApplicationService(runtime)
    service.step(1.0)

    history = service.history(limit=20)
    assert history
    frame = history[-1]
    playback = service.playback(frame["frame_sequence"])["snapshot"]
    saved = frame["snapshot"]

    assert playback["assets"] == saved["assets"]
    assert playback["commands"] == saved["commands"]
    assert playback["feedback"] == saved["feedback"]
    assert playback["verification"] == saved["verification"]
    assert playback["capability"] == saved["capability"]
    assert playback["operating_status"] == saved["operating_status"]


def test_drilldown_does_not_create_command_or_control_path() -> None:
    forbidden = (
        "fetch('/api/command'",
        'fetch("/api/command"',
        "sendCommand(",
        "manual_command",
        "start_water_change",
        "configure_",
    )
    for token in forbidden:
        assert token not in EQUIPMENT_DETAIL_SCRIPT
