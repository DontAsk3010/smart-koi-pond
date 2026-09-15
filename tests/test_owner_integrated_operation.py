from __future__ import annotations

import pytest

from smart_koi_pond.actuators.virtual import ActuatorFault
from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.owner_integrated_operation_ui import (
    OWNER_INTEGRATED_OPERATION_SCRIPT,
    OWNER_INTEGRATED_OPERATION_STYLE,
)
from smart_koi_pond.dashboard.owner_integrated_service import (
    OwnerIntegratedRuntimeApplicationService,
)
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML
from smart_koi_pond.digital_twin.filtration import MechanicalFiltrationProfile
from smart_koi_pond.digital_twin.hydraulics import HydraulicRouteSpec, PondDesignProfile
from smart_koi_pond.digital_twin.owner_integrated_runtime import (
    BackwashRestorePolicy,
    OwnerIntegratedProductionRuntime,
)
from smart_koi_pond.digital_twin.water_exchange import SourceWaterProfile
from smart_koi_pond.domain.enums import OperatingMode


def _configured_runtime(*, qualified_source: bool = True) -> OwnerIntegratedProductionRuntime:
    runtime = build_integrated_virtual_runtime()
    assert isinstance(runtime, OwnerIntegratedProductionRuntime)
    runtime.configure_design_profile(
        PondDesignProfile(
            profile_id="owner-integrated-test-pond",
            revision="1",
            effective_volume_l=1000.0,
            circulation_turnovers_per_hour_guide=1.0,
            routes=(
                HydraulicRouteSpec(
                    route_id="main-circulation",
                    asset_id="main_pump",
                    rated_flow_l_min=100.0,
                ),
            ),
            top_up_flow_l_min=100.0,
            drain_flow_l_min=100.0,
        )
    )
    runtime.model.configure_mechanical_filtration_profile(
        MechanicalFiltrationProfile(
            profile_id="owner-test-filter",
            revision="1",
            source_reference="TEST_EXPLICIT_FILTER_DATA",
            filtered_route_id="main-circulation",
            capture_efficiency_per_pass=0.5,
            max_captured_solids_g=1000.0,
            minimum_route_throughput_factor_at_capacity=0.5,
            backwash_solids_removal_g_per_min=50.0,
            backwash_discharge_flow_l_min=100.0,
        )
    )
    runtime.model.filtration.captured_solids_g = 200.0
    runtime.model.configure_source_water_profile(
        SourceWaterProfile(
            profile_id="owner-test-source",
            revision="1",
            source_reference="TEST_EXPLICIT_SOURCE_WATER",
            source_type="WELL",
            temperature_c=24.0,
            dissolved_oxygen_mg_l=8.0,
            ph=7.8,
            total_ammonia_nitrogen_mg_l=0.0,
            nitrite_mg_l=0.0,
            nitrate_mg_l=0.0,
            alkalinity_mg_l_as_caco3=80.0,
            free_chlorine_residual_mg_l=0.0,
            chloramine_residual_mg_l=0.0,
            pond_use_qualification=("QUALIFIED" if qualified_source else "NOT_QUALIFIED"),
            qualification_basis=("TEST_EVIDENCE" if qualified_source else None),
            qualification_reference=("TEST_REFERENCE" if qualified_source else None),
        )
    )
    runtime.configure_backwash_restore_policy(
        BackwashRestorePolicy(
            policy_id="owner-backwash-test",
            revision="1",
            source_reference="TEST_EXPLICIT_POLICY",
            backwash_duration_seconds=60.0,
            minimum_safe_water_level_pct=70.0,
            restore_tolerance_pct=0.5,
        )
    )
    runtime.model.state.nitrate_mg_l = 40.0
    runtime.model.state.alkalinity_mg_l_as_caco3 = 100.0
    runtime.model.state.ph = 7.0
    return runtime


def test_owner_test_guidance_uses_active_policy_not_hidden_frontend_numbers() -> None:
    runtime = build_integrated_virtual_runtime()
    snapshot = runtime.tick(0.0)
    guide = snapshot.water_recovery["owner_operation"]["test_guidance"]
    presets = guide["presets"]

    assert guide["production_setpoint_claimed"] is False
    assert presets["nitrite_high"]["test_value"] == runtime.policy.nitrite_watch_above == 0.4
    assert presets["nitrite_emergency"]["test_value"] == runtime.policy.nitrite_emergency_above == 1.5
    assert presets["nitrate_high"]["test_value"] == runtime.policy.nitrate_watch_above == 20.0
    assert presets["do_low"]["test_value"] == runtime.policy.do_watch_below == 5.0
    assert presets["ph_high"]["test_value"] == runtime.policy.ph_watch_above == 8.2
    assert presets["ph_low"]["test_value"] == runtime.policy.ph_watch_below == 6.8


def test_integrated_backwash_reduces_water_then_qualified_refill_restores_and_changes_chemistry() -> None:
    runtime = _configured_runtime(qualified_source=True)
    start_level = runtime.model.state.water_level_pct
    start_nitrate = runtime.model.state.nitrate_mg_l
    start_ph = runtime.model.state.ph

    runtime.start_integrated_backwash_restore("OWNER_ACCEPTANCE")
    first = runtime.tick(0.0)
    assert first.operating_mode == OperatingMode.FILTER_CLEAN
    assert first.assets["backwash_valve"].feedback_on is True

    after_backwash = runtime.tick(60.0)
    active = after_backwash.water_recovery["owner_operation"]["backwash_restore_active"]
    assert active is not None
    assert active["stage"] == "REFILLING"
    assert active["post_backwash_level_pct"] < start_level
    assert runtime.model.filtration.captured_solids_g < 200.0

    final = runtime.tick(60.0)
    owner = final.water_recovery["owner_operation"]
    assert final.operating_mode == OperatingMode.NORMAL_AUTO
    assert owner["backwash_restore_active"] is None
    assert owner["backwash_restore_last"]["outcome"] == "VERIFIED_SUCCESS"
    assert final.pond_truth.water_level_pct == pytest.approx(start_level)
    assert final.pond_truth.nitrate_mg_l < start_nitrate
    assert final.pond_truth.ph != pytest.approx(start_ph)

    journey = owner["backwash_restore_last"]["integrated_water_journey"]
    assert journey["backwash_discharge_l"] > 0.0
    assert journey["refill_l"] > 0.0
    assert journey["source_water_mixing_applied"] is True
    assert journey["chemistry_before_after"]["nitrate_mg_l"]["after"] < start_nitrate

    exchange = final.hydraulics["water_exchange"]["last_exchange"]
    assert exchange["parameter_results"]["nitrate_mg_l"]["status"] == "CALCULATED_CONSERVED_MASS_MIXING"
    assert exchange["parameter_results"]["ph"]["status"] == "MODELED_SIMPLIFIED_BUFFER_WEIGHTED_H_ACTIVITY"


def test_rejected_backwash_valve_finishes_integrated_workflow_as_hold() -> None:
    runtime = _configured_runtime(qualified_source=True)
    runtime.actuators.set_fault("backwash_valve", ActuatorFault("failed_off", None))

    runtime.start_integrated_backwash_restore("REJECTED_BACKWASH_TEST")
    final = runtime.tick(0.0)
    owner = final.water_recovery["owner_operation"]

    assert final.operating_mode == OperatingMode.NORMAL_AUTO
    assert owner["backwash_restore_active"] is None
    last = owner["backwash_restore_last"]
    assert last["stage"] == "DITAHAN"
    assert last["outcome"] == "HOLD"
    assert "ASSET_NOT_AVAILABLE:FAILED" in last["detail"]
    assert any(
        event.code == "INTEGRATED_BACKWASH_RESTORE_FINISHED"
        and event.payload["outcome"] == "HOLD"
        for event in runtime.events.events
    )


def test_owner_projection_and_checkpoint_do_not_alias_mutable_backwash_state() -> None:
    runtime = _configured_runtime(qualified_source=True)
    runtime.start_integrated_backwash_restore("COPY_ISOLATION_TEST")
    snapshot = runtime.tick(0.0)

    projected = snapshot.water_recovery["owner_operation"]["backwash_restore_active"]
    assert projected is not None
    projected["starting_chemistry"]["ph"] = 99.0
    assert runtime._owner_backwash_active is not None
    assert runtime._owner_backwash_active["starting_chemistry"]["ph"] != 99.0

    checkpoint = runtime.capture_checkpoint()
    captured_stage = checkpoint["owner_backwash_active"]["stage"]
    captured_ph = checkpoint["owner_backwash_active"]["starting_chemistry"]["ph"]

    runtime.tick(60.0)
    assert checkpoint["owner_backwash_active"]["stage"] == captured_stage
    assert checkpoint["owner_backwash_active"]["starting_chemistry"]["ph"] == captured_ph

    restored = _configured_runtime(qualified_source=True)
    restored.restore_checkpoint(checkpoint)
    checkpoint["owner_backwash_active"]["starting_chemistry"]["ph"] = 88.0
    assert restored._owner_backwash_active is not None
    assert restored._owner_backwash_active["starting_chemistry"]["ph"] == captured_ph


def test_unqualified_source_fails_closed_before_integrated_backwash_starts() -> None:
    runtime = _configured_runtime(qualified_source=False)
    level_before = runtime.model.state.water_level_pct

    with pytest.raises(RuntimeError, match="SOURCE_WATER_NOT_QUALIFIED"):
        runtime.start_integrated_backwash_restore("OWNER_ACCEPTANCE")

    assert runtime.operating_mode == OperatingMode.NORMAL_AUTO
    assert runtime.model.state.water_level_pct == level_before
    assert runtime.actuators.assets["backwash_valve"].feedback_on is False


def test_owner_service_exposes_one_operator_backwash_command_and_engineering_policy() -> None:
    runtime = _configured_runtime(qualified_source=True)
    service = OwnerIntegratedRuntimeApplicationService(runtime)

    with pytest.raises(PermissionError):
        service.command("start_integrated_backwash_restore", {}, role="viewer")

    service.command(
        "start_integrated_backwash_restore",
        {"reason": "OWNER_ONE_BUTTON_TEST"},
        role="operator",
    )
    assert service.last_snapshot.operating_mode == OperatingMode.FILTER_CLEAN


def test_indonesian_owner_surface_is_composed_and_manual_controls_are_secondary() -> None:
    assert OWNER_INTEGRATED_OPERATION_STYLE in COMPOSED_INDEX_HTML
    assert OWNER_INTEGRATED_OPERATION_SCRIPT in COMPOSED_INDEX_HTML
    for label in (
        "Operasi & Penilaian Kolam",
        "Jalankan Uji",
        "KONDISI KOLAM",
        "TINDAKAN SISTEM",
        "HASIL PEMULIHAN",
        "SARAN PEMILIK",
        "Backwash & Pulihkan Air",
        "Kontrol Manual / Perawatan",
        "Input sensor virtual",
    ):
        assert label in OWNER_INTEGRATED_OPERATION_SCRIPT
    assert "#functionalAcceptanceHarness{display:none!important}" in OWNER_INTEGRATED_OPERATION_STYLE
    assert "configure_backwash_restore_policy" in OWNER_INTEGRATED_OPERATION_SCRIPT
    assert "start_integrated_backwash_restore" in OWNER_INTEGRATED_OPERATION_SCRIPT
