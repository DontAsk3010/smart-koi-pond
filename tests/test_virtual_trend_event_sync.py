from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.trend_event_ui import TREND_EVENT_SCRIPT, TREND_EVENT_STYLE
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def test_virtual_browser_contains_historian_backed_trend_event_surface() -> None:
    assert "trend-event-style" in TREND_EVENT_STYLE
    assert "Historian-backed timeline" in TREND_EVENT_SCRIPT
    assert "visible markers" in TREND_EVENT_SCRIPT
    assert "HISTORIAN + LIVE" in TREND_EVENT_SCRIPT
    assert "LIVE BUFFER ONLY" in TREND_EVENT_SCRIPT
    assert TREND_EVENT_STYLE in COMPOSED_INDEX_HTML
    assert TREND_EVENT_SCRIPT in COMPOSED_INDEX_HTML


def test_trend_projection_preserves_unavailable_as_a_visible_gap() -> None:
    assert "if(t===null||!finite(value)){drawing=false;return}" in TREND_EVENT_SCRIPT
    assert "UNAVAILABLE — no canonical trend evidence" in TREND_EVENT_SCRIPT
    assert "Number(v)||0" not in TREND_EVENT_SCRIPT
    assert "??0" not in TREND_EVENT_SCRIPT
    assert "||0" not in TREND_EVENT_SCRIPT


def test_trend_markers_and_playback_cursor_use_canonical_time_evidence() -> None:
    for binding in (
        "eventBuffer.filter",
        "ev.timestamp",
        "displayed?.timestamp",
        "playbackMode",
        "Date.parse",
        "f.snapshot",
        "/api/history?limit=300",
    ):
        assert binding in TREND_EVENT_SCRIPT
    assert "markerKind" in TREND_EVENT_SCRIPT
    assert "playbackTimestamp" in TREND_EVENT_SCRIPT


def test_trend_extension_is_read_only() -> None:
    forbidden = (
        "fetch('/api/command'",
        'fetch("/api/command"',
        "sendCommand(",
        "manual_command",
        "start_water_change",
        "configure_",
    )
    for token in forbidden:
        assert token not in TREND_EVENT_SCRIPT


def test_historian_and_playback_preserve_trend_measurements() -> None:
    runtime = build_integrated_virtual_runtime()
    service = RuntimeApplicationService(runtime)
    service.step(1.0)
    service.step(1.0)

    history = service.history(limit=20)
    assert history
    frame = history[-1]
    saved = frame["snapshot"]
    playback = service.playback(frame["frame_sequence"])["snapshot"]

    assert playback["timestamp"] == saved["timestamp"]
    for key in (
        "temperature_c",
        "dissolved_oxygen_mg_l",
        "ph",
        "water_level_pct",
        "circulation_flow_l_min",
    ):
        assert playback["pond_truth"][key] == saved["pond_truth"][key]
