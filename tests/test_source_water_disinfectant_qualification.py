from datetime import UTC, datetime

import pytest

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.source_water_service import (
    SourceWaterQualifiedRuntimeApplicationService,
)
from smart_koi_pond.dashboard.source_water_ui import SOURCE_WATER_UI_SCRIPT
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs
from smart_koi_pond.digital_twin.source_water_runtime import (
    SourceWaterQualifiedProductionRuntime,
)
from smart_koi_pond.digital_twin.water_exchange import (
    SOURCE_WATER_QUALIFICATION_NOT_QUALIFIED,
    SOURCE_WATER_QUALIFICATION_QUALIFIED,
    SourceWaterProfile,
    WaterExchangePondModel,
)
from smart_koi_pond.domain.models import PondState


def qualified_source(*, revision: str = "r1") -> SourceWaterProfile:
    return SourceWaterProfile(
        profile_id="qualified-source",
        revision=revision,
        source_reference="manual-source-sample-record",
        source_type="MUNICIPAL_TAP",
        free_chlorine_residual_mg_l=0.0,
        chloramine_residual_mg_l=0.0,
        pond_use_qualification=SOURCE_WATER_QUALIFICATION_QUALIFIED,
        qualification_basis="MANUAL_REFERENCE_POST_CONDITIONING_RESIDUAL",
        qualification_reference=f"qualification-{revision}",
        conditioning_method="EXTERNAL_MANUAL_DECHLORINATION",
        conditioning_reference=f"conditioning-{revision}",
    )


def low_water_runtime() -> SourceWaterQualifiedProductionRuntime:
    policy = SimulationControlPolicy(
        do_watch_below=5.0,
        do_emergency_below=4.0,
        do_recover_above=5.5,
        flow_watch_below=8.0,
        water_level_low_below=70.0,
        low_water_auto_recovery_enabled=True,
        water_level_recover_target=72.0,
        water_level_hard_high_cutoff=80.0,
        low_water_max_runtime_seconds=300.0,
        low_water_max_level_gain_pct=15.0,
        low_water_verification_delay_seconds=1.0,
        water_level_verification_min_delta=0.1,
    )
    runtime = SourceWaterQualifiedProductionRuntime(
        WaterExchangePondModel(
            PondState(27.0, 6.0, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        policy,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="source-water-qualification-low-water",
        config_version="source-water-qualification-v1",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_source_type_never_implies_disinfectant_absence_or_qualification() -> None:
    profile = SourceWaterProfile(
        profile_id="municipal",
        revision="r1",
        source_reference="municipal-line",
        source_type="MUNICIPAL_TAP",
    )
    model = WaterExchangePondModel(
        PondState(27.0, 6.0, 7.2, 85.0),
        EnvironmentInputs(28.0, 0.2),
        source_water=profile,
    )

    source = model.source_water_snapshot()
    assert source["free_chlorine_residual_mg_l"] is None
    assert source["chloramine_residual_mg_l"] is None
    assert source["pond_use_qualified"] is False
    assert source["qualification"]["state"] == "INPUT_REQUIRED"
    assert source["qualification"]["source_type_implies_safe_chemistry"] is False
    assert source["qualification"]["automatic_chemical_dosing_authorized"] is False


def test_qualified_source_requires_explicit_basis_and_reference() -> None:
    with pytest.raises(ValueError, match="qualification_basis"):
        SourceWaterProfile(
            profile_id="bad",
            revision="r1",
            source_reference="source",
            source_type="WELL",
            pond_use_qualification="QUALIFIED",
            qualification_reference="record",
        )
    with pytest.raises(ValueError, match="qualification_reference"):
        SourceWaterProfile(
            profile_id="bad",
            revision="r1",
            source_reference="source",
            source_type="WELL",
            pond_use_qualification="QUALIFIED",
            qualification_basis="MEASURED",
        )


def test_water_change_rejects_unqualified_source_before_drain_phase() -> None:
    runtime = build_integrated_virtual_runtime()
    before_mode = runtime.operating_mode
    before_phase = runtime.modes.status.phase

    with pytest.raises(RuntimeError, match="SOURCE_WATER_NOT_QUALIFIED"):
        runtime.start_water_change(
            "UNQUALIFIED_SOURCE_MUST_NOT_DRAIN",
            target_drain_level_pct=75.0,
            target_refill_level_pct=85.0,
        )

    assert runtime.operating_mode == before_mode
    assert runtime.modes.status.phase == before_phase
    assert runtime.actuators.assets["drain_valve"].feedback_on is False
    event = runtime.events.events[-1]
    assert event.code == "SOURCE_WATER_OPERATION_INHIBITED"
    assert event.payload["operation"] == "WATER_CHANGE"
    assert event.payload["drain_started"] is False


def test_qualified_source_allows_existing_governed_water_change_path() -> None:
    runtime = build_integrated_virtual_runtime()
    runtime.model.configure_source_water_profile(qualified_source())

    runtime.start_water_change(
        "QUALIFIED_SOURCE_WATER_CHANGE",
        target_drain_level_pct=75.0,
        target_refill_level_pct=85.0,
    )

    assert runtime.model.source_water_is_qualified() is True
    assert runtime.modes.status.phase.value == "DRAINING"


def test_low_water_auto_top_up_never_energizes_with_unqualified_source() -> None:
    runtime = low_water_runtime()
    runtime.model.set_truth("water_level_pct", 60.0)

    snapshot = runtime.tick(0.0)

    command = snapshot.commands["top_up_valve"]
    assert command.requested_on is True
    assert command.accepted is False
    assert command.final_on is False
    assert command.reason.startswith("SOURCE_WATER_NOT_QUALIFIED")
    assert snapshot.feedback["top_up_valve"].feedback_on is False
    assert snapshot.water_recovery["lockout_reason"] == "SOURCE_WATER_NOT_QUALIFIED"
    assert snapshot.water_recovery["source_water_qualified"] is False
    assert snapshot.water_recovery["auto_top_up_source_water_dependency_satisfied"] is False
    assert any(
        event.code == "SOURCE_WATER_TOP_UP_INHIBITED"
        for event in runtime.events.events
    )


def test_unqualified_transition_forces_already_open_top_up_to_safe_off() -> None:
    runtime = build_integrated_virtual_runtime()
    runtime.model.configure_source_water_profile(qualified_source())
    runtime.start_manual_maintenance(
        ["top_up_valve"],
        "SOURCE_WATER_SAFETY_OFF_REGRESSION",
    )

    opened, open_feedback = runtime.manual_command(
        "top_up_valve",
        True,
        "QUALIFIED_MANUAL_TOP_UP",
    )
    assert opened.accepted is True
    assert open_feedback.feedback_on is True

    runtime.model.configure_source_water_profile(
        SourceWaterProfile(
            profile_id="qualified-source",
            revision="r2",
            source_reference="new-unqualified-source-evidence",
            source_type="MUNICIPAL_TAP",
            pond_use_qualification=SOURCE_WATER_QUALIFICATION_NOT_QUALIFIED,
        )
    )
    inhibited, feedback = runtime.manual_command(
        "top_up_valve",
        True,
        "MUST_NOT_CONTINUE_AFTER_QUALIFICATION_LOSS",
    )

    assert inhibited.requested_on is True
    assert inhibited.accepted is False
    assert inhibited.final_on is False
    assert inhibited.reason.startswith("SOURCE_WATER_NOT_QUALIFIED")
    assert feedback.feedback_on is False
    assert runtime.actuators.assets["top_up_valve"].feedback_on is False
    event = next(
        event
        for event in reversed(runtime.events.events)
        if event.code == "SOURCE_WATER_TOP_UP_INHIBITED"
    )
    assert event.payload["was_on_before_safety_off"] is True
    assert event.payload["feedback_on_after_safety_off"] is False


def test_source_water_qualification_survives_checkpoint_history_and_playback() -> None:
    runtime = build_integrated_virtual_runtime()
    runtime.model.configure_source_water_profile(qualified_source())
    snapshot = runtime.tick(0.0)
    checkpoint = runtime.capture_checkpoint()

    runtime.model.configure_source_water_profile(
        SourceWaterProfile(
            profile_id="qualified-source",
            revision="r2",
            source_reference="changed-source",
            source_type="MUNICIPAL_TAP",
            pond_use_qualification=SOURCE_WATER_QUALIFICATION_NOT_QUALIFIED,
        )
    )
    assert runtime.model.source_water_is_qualified() is False

    runtime.restore_checkpoint(checkpoint)
    restored = runtime.model.source_water_snapshot()
    assert restored["revision"] == "r1"
    assert restored["pond_use_qualified"] is True
    assert restored["qualification"]["reference"] == "qualification-r1"

    service = SourceWaterQualifiedRuntimeApplicationService(runtime)
    live = service.publication(after_sequence=0)
    assert live["source_water_exchange_schema_version"] == 2
    assert live["snapshot"]["hydraulics"]["water_exchange"]["source_water"][
        "pond_use_qualified"
    ] is True

    history = service.history(limit=20)
    assert history
    frame = history[-1]
    playback = service.playback(frame["frame_sequence"])
    assert playback["snapshot"]["hydraulics"]["water_exchange"]["source_water"][
        "qualification"
    ] == frame["snapshot"]["hydraulics"]["water_exchange"]["source_water"][
        "qualification"
    ]
    assert snapshot.hydraulics["water_exchange"]["source_water"][
        "pond_use_qualified"
    ] is True


def test_source_water_ui_is_fail_honest_and_does_not_offer_auto_dosing() -> None:
    assert "Free chlorine residual (mg/L)" in SOURCE_WATER_UI_SCRIPT
    assert "Chloramine residual (mg/L)" in SOURCE_WATER_UI_SCRIPT
    assert "Pond-use qualification" in SOURCE_WATER_UI_SCRIPT
    assert "INHIBITED — SOURCE WATER NOT QUALIFIED" in SOURCE_WATER_UI_SCRIPT
    assert "source type implies safe chemistry: NO" in SOURCE_WATER_UI_SCRIPT
    assert "automatic chemical dosing: DISABLED" in SOURCE_WATER_UI_SCRIPT
    assert "QUALIFIED requires qualification basis and reference" in SOURCE_WATER_UI_SCRIPT
