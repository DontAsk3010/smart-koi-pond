from smart_koi_pond.actuators.virtual import ActuatorFault
from smart_koi_pond.domain.enums import OperatingMode

from test_owner_integrated_operation import _configured_runtime


def test_mid_backwash_rejection_reports_partial_discharge_honestly() -> None:
    runtime = _configured_runtime(qualified_source=True)
    starting_level = runtime.model.state.water_level_pct

    runtime.start_integrated_backwash_restore("MID_BACKWASH_FAULT")
    runtime.tick(0.0)
    runtime.tick(30.0)
    runtime.actuators.set_fault("backwash_valve", ActuatorFault("failed_off", None))

    final = runtime.tick(1.0)
    owner = final.water_recovery["owner_operation"]
    result = owner["backwash_restore_last"]

    assert final.operating_mode == OperatingMode.NORMAL_AUTO
    assert owner["backwash_restore_active"] is None
    assert result["outcome"] == "HOLD"
    assert "Backwash berhenti setelah air mulai terbuang" in result["detail"]
    assert "ASSET_NOT_AVAILABLE:FAILED" in result["detail"]
    assert final.pond_truth.water_level_pct < starting_level
    assert result["integrated_water_journey"]["backwash_discharge_l"] > 0.0
