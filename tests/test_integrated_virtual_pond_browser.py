import pytest

from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def pond_profile() -> dict:
    return {
        "profile_id": "test-owner-pond",
        "revision": "r1",
        "effective_volume_l": 20_000.0,
        "circulation_turnovers_per_hour_guide": 1.0,
        "biomass_kg": 50.0,
        "feed_kg_per_day": 1.0,
        "provenance": "USER_CONFIGURED_SCENARIO",
        "routes": [
            {
                "route_id": "main-circulation",
                "asset_id": "main_pump",
                "rated_flow_l_min": 400.0,
                "role": "PRIMARY",
                "base_throughput_factor": 1.0,
                "provenance": "USER_CONFIGURED_SCENARIO",
            },
            {
                "route_id": "backup-circulation",
                "asset_id": "backup_pump",
                "rated_flow_l_min": 350.0,
                "role": "BACKUP",
                "base_throughput_factor": 1.0,
                "provenance": "USER_CONFIGURED_SCENARIO",
            },
        ],
    }


def biology_profile() -> dict:
    return {
        "profile_id": "test-owner-biology",
        "revision": "r1",
        "source_reference": "TEST_FIXTURE_EXPLICIT_INPUT_NOT_PRODUCTION_SETPOINT",
        "biofilter_ammonia_capacity_g_n_per_day": 20.0,
        "biofilter_nitrite_capacity_g_n_per_day": 10.0,
        "fish_oxygen_demand_g_o2_per_kg_hour": 0.01,
        "feed_oxygen_demand_g_o2_per_kg_feed": 2.0,
        "ammonia_n_generation_g_per_kg_feed": 30.0,
        "solid_waste_g_per_kg_feed": 200.0,
        "nitrification_oxygen_g_o2_per_g_n": 1.0,
        "alkalinity_consumption_g_caco3_per_g_n": 2.0,
        "nitrification_do_reference_mg_l": 5.0,
        "ph_drop_per_100_mg_l_alkalinity_loss": 0.1,
        "provenance": "USER_CONFIGURED_SCENARIO",
    }


def filter_profile(*, turbidity: float | None = None) -> dict:
    return {
        "profile_id": "test-owner-filter",
        "revision": "r1",
        "source_reference": "TEST_FIXTURE_EXPLICIT_INPUT_NOT_PRODUCTION_RATING",
        "filtered_route_id": "main-circulation",
        "capture_efficiency_per_pass": 0.5,
        "max_captured_solids_g": 500.0,
        "minimum_route_throughput_factor_at_capacity": 0.5,
        "backwash_solids_removal_g_per_min": 50.0,
        "backwash_discharge_flow_l_min": 100.0,
        "turbidity_ntu_per_mg_l_tss": turbidity,
        "provenance": "USER_CONFIGURED_SCENARIO",
    }


def service() -> RuntimeApplicationService:
    return RuntimeApplicationService(build_integrated_virtual_runtime())


def configure_stack(app: RuntimeApplicationService, *, turbidity: float | None = None) -> None:
    app.command(
        "configure_design_profile",
        {"profile": pond_profile(), "actor": "test-owner"},
        role="engineering",
    )
    app.command(
        "configure_biological_profile",
        {"profile": biology_profile(), "actor": "test-owner"},
        role="engineering",
    )
    app.command(
        "configure_mechanical_filtration_profile",
        {"profile": filter_profile(turbidity=turbidity), "actor": "test-owner"},
        role="engineering",
    )
    for parameter, value in {
        "tan": 0.2,
        "nitrite": 0.1,
        "nitrate": 5.0,
        "alkalinity": 150.0,
        "waste_solids": 100.0,
    }.items():
        app.command(
            "set_environment_state",
            {"parameter": parameter, "value": value},
            role="engineering",
        )


def test_integrated_entrypoint_starts_honestly_input_required() -> None:
    runtime = build_integrated_virtual_runtime()
    app = RuntimeApplicationService(runtime)
    publication = app.publication()
    snapshot = publication["snapshot"]

    assert runtime.config_version == "integrated-virtual-pond-v1-input-required"
    assert snapshot["design_profile"]["configured"] is False
    assert snapshot["biology"]["configured"] is False
    assert snapshot["hydraulics"]["mechanical_filtration"]["configured"] is False
    assert all(not asset.feedback_on for asset in runtime.actuators.assets.values())
    assert any(
        event.code == "INTEGRATED_VIRTUAL_POND_STARTED"
        for event in runtime.events.events
    )
    assert "digital-twin-v1-demo-only" not in COMPOSED_INDEX_HTML


def test_full_stack_configuration_becomes_visible_from_canonical_publication() -> None:
    app = service()
    configure_stack(app)
    app.command(
        "manual_command",
        {"asset_id": "main_pump", "on": True, "reason": "TEST_OWNER_COMMAND"},
        role="engineering",
    )
    snapshot = app.step(3600.0)
    publication = app.publication()["snapshot"]
    mechanical = publication["hydraulics"]["mechanical_filtration"]

    assert snapshot.design_profile["configured"] is True
    assert publication["hydraulics"]["configured"] is True
    assert publication["biology"]["configured"] is True
    assert mechanical["configured"] is True
    assert publication["pond_truth"]["circulation_flow_l_min"] > 0.0
    assert mechanical["captured_solids_g"] > 0.0
    assert mechanical["loading_fraction"] > 0.0
    assert mechanical["process_throughput_factor"] < 1.0
    assert mechanical["tss_mg_l"] is not None
    assert publication["process_visual"]["source"] == "CANONICAL_RUNTIME_SNAPSHOT"


def test_unknown_turbidity_remains_unavailable_in_visible_state() -> None:
    app = service()
    configure_stack(app, turbidity=None)
    publication = app.publication()["snapshot"]
    mechanical = publication["hydraulics"]["mechanical_filtration"]

    assert mechanical["tss_mg_l"] is not None
    assert mechanical["turbidity_ntu"] is None
    assert mechanical["water_clarity_conclusion"] == "NOT_ESTABLISHED"


def test_owner_volume_revision_recalculates_requirement_in_same_runtime() -> None:
    app = service()
    app.command(
        "configure_design_profile",
        {"profile": pond_profile(), "actor": "test-owner"},
        role="engineering",
    )
    first = app.publication()["snapshot"]["hydraulics"]

    revised = pond_profile()
    revised["revision"] = "r2"
    revised["effective_volume_l"] = 40_000.0
    app.command(
        "configure_design_profile",
        {"profile": revised, "actor": "test-owner"},
        role="engineering",
    )
    second = app.publication()["snapshot"]["hydraulics"]

    assert first["required_circulation_flow_l_min"] == pytest.approx(333.333333)
    assert second["required_circulation_flow_l_min"] == pytest.approx(666.666667)
    assert second["profile_revision"] == "r2"


def test_environment_disturbance_is_visible_through_canonical_state() -> None:
    app = service()
    configure_stack(app)
    snapshot = app.command(
        "set_environment_state",
        {"parameter": "tan", "value": 0.9},
        role="engineering",
    )
    publication = app.publication()["snapshot"]

    assert snapshot.pond_truth.total_ammonia_nitrogen_mg_l == pytest.approx(0.9)
    assert publication["pond_truth"]["total_ammonia_nitrogen_mg_l"] == pytest.approx(0.9)
    assert "TAN_HIGH" in publication["classification"]["reasons"]


def test_actuator_fault_removes_false_flow_from_visible_process_state() -> None:
    app = service()
    app.command(
        "configure_design_profile",
        {"profile": pond_profile(), "actor": "test-owner"},
        role="engineering",
    )
    app.command(
        "manual_command",
        {"asset_id": "main_pump", "on": True, "reason": "TEST_OWNER_COMMAND"},
        role="engineering",
    )
    assert app.step(1.0).pond_truth.circulation_flow_l_min > 0.0

    snapshot = app.command(
        "inject_actuator_fault",
        {"asset_id": "main_pump", "mode": "failed_off"},
        role="engineering",
    )
    publication = app.publication()["snapshot"]

    assert snapshot.assets["main_pump"].feedback_on is False
    assert publication["pond_truth"]["circulation_flow_l_min"] == pytest.approx(0.0)
    assert publication["process_visual"]["circulation"]["flow_motion_active"] is False


def test_historian_playback_preserves_integrated_process_state() -> None:
    app = service()
    configure_stack(app, turbidity=0.4)
    app.command(
        "manual_command",
        {"asset_id": "main_pump", "on": True, "reason": "TEST_OWNER_COMMAND"},
        role="engineering",
    )
    app.step(60.0)
    frame = app.history(limit=20)[-1]
    playback = app.playback(frame["frame_sequence"])

    assert playback["snapshot"]["design_profile"] == frame["snapshot"]["design_profile"]
    assert playback["snapshot"]["hydraulics"] == frame["snapshot"]["hydraulics"]
    assert playback["snapshot"]["process_visual"] == frame["snapshot"]["process_visual"]


def test_browser_surface_exposes_integrated_setup_without_hidden_process_values() -> None:
    assert "Integrated Pond" in COMPOSED_INDEX_HTML
    assert "No hidden engineering defaults" in COMPOSED_INDEX_HTML
    assert "INPUT REQUIRED" in COMPOSED_INDEX_HTML
    assert "Apply Pond / Hydraulic Profile" in COMPOSED_INDEX_HTML
    assert "Apply Biology Profile" in COMPOSED_INDEX_HTML
    assert "Apply Mechanical Filter" in COMPOSED_INDEX_HTML
    assert "Live Process Evidence" in COMPOSED_INDEX_HTML
    assert "/api/command" in COMPOSED_INDEX_HTML
