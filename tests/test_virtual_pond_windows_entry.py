from pathlib import Path

from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def test_virtual_pond_is_primary_browser_surface() -> None:
    assert "Smart Koi Pond — Virtual Pond" in COMPOSED_INDEX_HTML
    assert "SMART KOI POND · CANONICAL RUNTIME" in COMPOSED_INDEX_HTML
    assert "Virtual Pond" in COMPOSED_INDEX_HTML
    assert "Open Integrated Setup" in COMPOSED_INDEX_HTML
    assert "System Overview" in COMPOSED_INDEX_HTML
    assert "Historian / Events" in COMPOSED_INDEX_HTML
    assert "REAL DEVICE CONTROL: CLOSED" in COMPOSED_INDEX_HTML
    assert "No false zero for unavailable flow" in COMPOSED_INDEX_HTML
    assert "processButton.click()" in COMPOSED_INDEX_HTML


def test_virtual_pond_home_reads_canonical_snapshot_without_own_state_engine() -> None:
    assert "s.pond_truth||{}" in COMPOSED_INDEX_HTML
    assert "s.process_visual||{}" in COMPOSED_INDEX_HTML
    assert "CANONICAL_RUNTIME_SNAPSHOT" in COMPOSED_INDEX_HTML
    assert "INPUT REQUIRED" in COMPOSED_INDEX_HTML
    assert "UNAVAILABLE" in COMPOSED_INDEX_HTML
    assert "new WebSocket" not in COMPOSED_INDEX_HTML
    assert "localStorage.setItem" not in COMPOSED_INDEX_HTML


def test_windows_launcher_stays_loopback_and_simulation_only() -> None:
    launcher = Path("START_VIRTUAL_POND_WINDOWS.bat").read_text(encoding="utf-8")
    assert "SIMULATION / NO REAL DEVICE CONTROL" in launcher
    assert 'SMART_KOI_HOST=127.0.0.1' in launcher
    assert 'SMART_KOI_PORT=8080' in launcher
    assert "http://127.0.0.1:8080" in launcher
    assert "PYTHONPATH=%CD%\\src" in launcher
    assert "smart_koi_pond.dashboard.app" in launcher
    assert "0.0.0.0" not in launcher
