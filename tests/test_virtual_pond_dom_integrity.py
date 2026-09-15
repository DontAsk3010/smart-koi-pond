from smart_koi_pond.dashboard.animated_pond_ui import ANIMATED_POND_SCRIPT
from smart_koi_pond.dashboard.equipment_detail_ui import EQUIPMENT_DETAIL_SCRIPT
from smart_koi_pond.dashboard.governance_status_ui import GOVERNANCE_STATUS_SCRIPT


def test_asset_status_renderer_only_rewrites_miniscada_nodes() -> None:
    """Drill-down identity must not let asset status rendering destroy pond chips."""

    assert "document.querySelectorAll('#processGrid [data-asset]')" in GOVERNANCE_STATUS_SCRIPT
    assert "document.querySelectorAll('[data-asset]')" not in GOVERNANCE_STATUS_SCRIPT

    # Animated pond device chips intentionally own nested renderer markup.
    assert "main.querySelector('small').innerHTML" in ANIMATED_POND_SCRIPT
    assert "chipMain:'main_pump'" in EQUIPMENT_DETAIL_SCRIPT


def test_governance_renderer_null_guards_optional_status_nodes() -> None:
    assert "if(govSource)govSource.textContent" in GOVERNANCE_STATUS_SCRIPT
    assert "if(story){story.className" in GOVERNANCE_STATUS_SCRIPT
