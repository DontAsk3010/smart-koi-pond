from pathlib import Path


def test_windows_portable_entry_uses_canonical_runtime_and_loopback_defaults() -> None:
    source = Path("scripts/windows_virtual_pond_entry.py").read_text(encoding="utf-8")
    assert "from smart_koi_pond.dashboard.app import main as run_virtual_pond" in source
    assert 'os.getenv("SMART_KOI_HOST", "127.0.0.1")' in source
    assert 'os.getenv("SMART_KOI_PORT", "8080")' in source
    assert "SIMULATION / NO REAL DEVICE CONTROL" in source
    assert "runtime-data" in source
    assert "webbrowser.open" in source
    assert "0.0.0.0" not in source


def test_windows_workflow_builds_and_smokes_owner_executable() -> None:
    workflow = Path(".github/workflows/windows-virtual-pond.yml").read_text(
        encoding="utf-8"
    )
    assert "runs-on: windows-latest" in workflow
    assert "SMART_KOI_POND_VIRTUAL_POND.exe" in workflow
    assert "pyinstaller" in workflow.lower()
    assert 'SMART_KOI_HOST = "127.0.0.1"' in workflow
    assert 'SMART_KOI_PORT = "18082"' in workflow
    assert 'execution_mode -ne "SIMULATION"' in workflow
    assert "NO REAL DEVICE CONTROL" in workflow
    assert "INPUT REQUIRED" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "SMART_KOI_POND_VIRTUAL_POND_WINDOWS" in workflow
