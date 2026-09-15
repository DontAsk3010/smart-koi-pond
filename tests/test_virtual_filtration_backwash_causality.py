from datetime import UTC, datetime

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.filtration_backwash_causality_ui import (
    FILTRATION_BACKWASH_CAUSALITY_SCRIPT,
    FILTRATION_BACKWASH_CAUSALITY_STYLE,
)
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.filtration import MechanicalFiltrationProfile
from smart_koi_pond.digital_twin.hydraulics import (
    EngineeringProvenance,
    HydraulicRouteRole,
    HydraulicRouteSpec,
    PondDesignProfile,
)
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.models import PondState


def _service() -> RuntimeApplicationService:
    model = PondModel(
        PondState(27.0, 6.0, 7.2, 100.0, waste_solids_g=400.0),
        EnvironmentInputs(27.0, 0.0),
    )
    model.configure_design_profile(
        PondDesignProfile(
            profile_id="virtual-filtration-pond",
            revision="r1",
            effective_volume_l=20_000.0,
            circulation_turnovers_per_hour_guide=1.0,
            provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
            routes=(
                HydraulicRouteSpec(
                    route_id="main-route",
                    asset_id="main_pump",
                    rated_flow_l_min=400.0,
                    role=HydraulicRouteRole.PRIMARY,
                ),
            ),
        )
    )
    model.configure_mechanical_filtration_profile(
        MechanicalFiltrationProfile(
            profile_id="virtual-filter",
            revision="r1",
            source_reference="TEST_EXPLICIT_INPUT",
            filtered_route_id="main-route",
            capture_efficiency_per_pass=0.5,
            max_captured_solids_g=500.0,
            minimum_route_throughput_factor_at_capacity=0.5,
            backwash_solids_removal_g_per_min=50.0,
            backwash_discharge_flow_l_min=100.0,
            provenance=EngineeringProvenance.USER_CONFIGURED_SCENARIO,
        )
    )
    runtime = DigitalTwinRuntime(
        model,
        SimulationControlPolicy(
            do_watch_below=5.0,
            do_emergency_below=4.0,
            do_recover_above=5.5,
            flow_watch_below=8.0,
            water_level_low_below=70.0,
        ),
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return RuntimeApplicationService(runtime)


def test_virtual_browser_contains_filtration_backwash_causal_chain() -> None:
    assert "filtration-backwash-causality-style" in FILTRATION_BACKWASH_CAUSALITY_STYLE
    for label in (
        "Filter Loading",
        "Hydraulic Consequence",
        "Backwash Command / Feedback",
        "Solids Removal / Water Loss",
        "Refill / Source-Water Dependency",
        "Post-Process Evidence",
    ):
        assert label in FILTRATION_BACKWASH_CAUSALITY_SCRIPT
    assert FILTRATION_BACKWASH_CAUSALITY_STYLE in COMPOSED_INDEX_HTML
    assert FILTRATION_BACKWASH_CAUSALITY_SCRIPT in COMPOSED_INDEX_HTML


def test_causal_view_uses_canonical_filtration_hydraulic_and_water_evidence() -> None:
    for field in (
        "captured_solids_g",
        "max_captured_solids_g",
        "loading_fraction",
        "process_throughput_factor",
        "runtime_throughput_factor",
        "effective_flow_l_min",
        "last_backwash_removed_g",
        "last_backwash_discharge_l",
        "cumulative_backwash_removed_g",
        "cumulative_backwash_discharge_l",
        "source_water",
        "source_water_qualified",
        "verification",
    ):
        assert field in FILTRATION_BACKWASH_CAUSALITY_SCRIPT


def test_causal_view_never_equates_valve_command_with_cleaning_success() -> None:
    assert (
        "Valve command or feedback ON does not prove filter cleaning."
        in FILTRATION_BACKWASH_CAUSALITY_SCRIPT
    )
    assert "NO COMPLETION / RECOVERY CLAIM" in FILTRATION_BACKWASH_CAUSALITY_SCRIPT
    assert (
        "BACKWASH IN PROGRESS — NO COMPLETION CLAIM"
        in FILTRATION_BACKWASH_CAUSALITY_SCRIPT
    )
    assert (
        "Current values are evidence, not proof of physical filter cleanliness."
        in FILTRATION_BACKWASH_CAUSALITY_SCRIPT
    )
    for forbidden in (
        "BACKWASH SUCCESS",
        "FILTER CLEAN SUCCESS",
        "fetch('/api/command'",
        'fetch("/api/command"',
        "sendCommand(",
    ):
        assert forbidden not in FILTRATION_BACKWASH_CAUSALITY_SCRIPT


def test_mechanical_process_evidence_survives_governed_backwash_and_playback() -> None:
    service = _service()
    service.step(3600.0)
    before = service.publication()["snapshot"]["hydraulics"]["mechanical_filtration"]
    assert before["captured_solids_g"] > 0.0
    assert before["process_throughput_factor"] < 1.0

    service.command(
        "start_filter_clean",
        {"service_scope": [], "reason": "CAUSAL_VIEW_ACCEPTANCE"},
        role="engineering",
    )
    service.step(60.0)
    publication = service.publication()["snapshot"]
    filtration = publication["hydraulics"]["mechanical_filtration"]

    assert filtration["last_backwash_removed_g"] > 0.0
    assert filtration["last_backwash_discharge_l"] > 0.0
    assert filtration["captured_solids_g"] < before["captured_solids_g"]
    assert filtration["process_throughput_factor"] > before["process_throughput_factor"]

    history = service.history(limit=20)
    frame = history[-1]
    playback = service.playback(frame["frame_sequence"])["snapshot"]
    assert (
        playback["hydraulics"]["mechanical_filtration"]
        == frame["snapshot"]["hydraulics"]["mechanical_filtration"]
    )
