from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML
from smart_koi_pond.domain.enums import CommandOwner, OperatingMode


def test_source_water_ui_backwash_uses_real_backwash_valve_workflow() -> None:
    runtime = build_integrated_virtual_runtime()
    service = RuntimeApplicationService(runtime)

    service.command(
        "start_filter_clean",
        {"service_scope": [], "reason": "BACKWASH_ACCEPTANCE"},
        role="engineering",
    )

    assert runtime.operating_mode == OperatingMode.FILTER_CLEAN
    assert runtime.actuators.assets["backwash_valve"].owner == CommandOwner.WORKFLOW
    assert "service_scope:[]" in COMPOSED_INDEX_HTML
