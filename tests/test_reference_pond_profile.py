import pytest

from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML
from smart_koi_pond.digital_twin.hydraulics import (
    REFERENCE_STANDARD_METRIC_PROFILE_ID,
    EngineeringProvenance,
    PondDesignProfile,
    reference_standard_metric_v1,
)


def test_reference_standard_metric_v1_is_exact_and_explicit() -> None:
    profile = reference_standard_metric_v1()

    assert profile.profile_id == REFERENCE_STANDARD_METRIC_PROFILE_ID
    assert profile.reference_profile_id == REFERENCE_STANDARD_METRIC_PROFILE_ID
    assert profile.revision == "1"
    assert profile.provenance == EngineeringProvenance.EXPERT_REFERENCE_PROFILE
    assert profile.length_m == pytest.approx(4.0)
    assert profile.width_m == pytest.approx(2.0)
    assert profile.water_depth_m == pytest.approx(1.5)
    assert profile.effective_volume_l == pytest.approx(12_000.0)
    assert profile.circulation_turnovers_per_hour_guide == pytest.approx(1.0)
    assert profile.overridden_fields == ()
    assert len(profile.routes) == 1
    assert profile.routes[0].rated_flow_l_min == pytest.approx(200.0)
    assert profile.routes[0].provenance == EngineeringProvenance.EXPERT_REFERENCE_PROFILE


def test_reference_profile_calculates_requirement_without_hardware_fault_claim() -> None:
    runtime = build_integrated_virtual_runtime()
    runtime.configure_design_profile(reference_standard_metric_v1(), actor="test-reference")
    snapshot = runtime.tick(0.0)
    hydraulic = snapshot.hydraulics

    assert hydraulic["required_circulation_flow_l_min"] == pytest.approx(200.0)
    assert hydraulic["profile_provenance"] == "EXPERT_REFERENCE_PROFILE"
    assert hydraulic["reference_profile_id"] == REFERENCE_STANDARD_METRIC_PROFILE_ID
    assert hydraulic["hardware_fault_conclusion"] == "NOT_ESTABLISHED"
    assert hydraulic["hardware_upgrade_required"] is False
    assert hydraulic["sizing_advisory_is_mandatory_hardware_lock"] is False


def test_user_override_retains_reference_lineage_and_recalculates() -> None:
    profile = reference_standard_metric_v1().to_dict()
    profile.update(
        {
            "profile_id": "owner-pond-20m3",
            "revision": "user-r1",
            "length_m": 5.0,
            "width_m": 2.5,
            "water_depth_m": 1.6,
            "effective_volume_l": 20_000.0,
            "overridden_fields": [
                "profile_id",
                "length_m",
                "width_m",
                "water_depth_m",
                "effective_volume_l",
            ],
            "provenance": "USER_CONFIGURED",
        }
    )
    configured = PondDesignProfile.from_dict(profile)
    runtime = build_integrated_virtual_runtime()
    runtime.configure_design_profile(configured, actor="test-owner")
    snapshot = runtime.tick(0.0)

    assert snapshot.design_profile["reference_profile_id"] == REFERENCE_STANDARD_METRIC_PROFILE_ID
    assert snapshot.design_profile["provenance"] == "USER_CONFIGURED"
    assert "effective_volume_l" in snapshot.design_profile["overridden_fields"]
    assert snapshot.hydraulics["required_circulation_flow_l_min"] == pytest.approx(
        333.333333333
    )
    assert snapshot.hydraulics["hardware_fault_conclusion"] == "NOT_ESTABLISHED"


def test_reference_lineage_survives_checkpoint_restart() -> None:
    runtime = build_integrated_virtual_runtime()
    profile = reference_standard_metric_v1().to_dict()
    profile["effective_volume_l"] = 15_000.0
    profile["revision"] = "user-r2"
    profile["provenance"] = "USER_CONFIGURED"
    profile["overridden_fields"] = ["effective_volume_l"]
    runtime.configure_design_profile(PondDesignProfile.from_dict(profile), actor="test-owner")
    checkpoint = runtime.capture_checkpoint()

    restored = build_integrated_virtual_runtime()
    restored.restore_checkpoint(checkpoint)
    snapshot = restored.tick(0.0)

    assert snapshot.design_profile["reference_profile_id"] == REFERENCE_STANDARD_METRIC_PROFILE_ID
    assert snapshot.design_profile["overridden_fields"] == ["effective_volume_l"]
    assert snapshot.design_profile["provenance"] == "USER_CONFIGURED"
    assert snapshot.design_profile["effective_volume_l"] == pytest.approx(15_000.0)


def test_reference_profile_is_visible_in_historian_and_playback() -> None:
    app = RuntimeApplicationService(build_integrated_virtual_runtime())
    app.command(
        "configure_design_profile",
        {"profile": reference_standard_metric_v1().to_dict(), "actor": "test-owner"},
        role="engineering",
    )
    app.step(1.0)
    frame = app.history(limit=10)[-1]
    playback = app.playback(frame["frame_sequence"])

    assert frame["snapshot"]["design_profile"]["reference_profile_id"] == (
        REFERENCE_STANDARD_METRIC_PROFILE_ID
    )
    assert playback["snapshot"]["design_profile"] == frame["snapshot"]["design_profile"]
    assert playback["snapshot"]["hydraulics"] == frame["snapshot"]["hydraulics"]


def test_reference_profile_browser_surface_is_explicit_not_site_measurement() -> None:
    assert "Reference Standard Metric V1" in COMPOSED_INDEX_HTML
    assert "4.0 m × 2.0 m × 1.5 m" in COMPOSED_INDEX_HTML
    assert "12,000 L" in COMPOSED_INDEX_HTML
    assert "not a measurement of your pond" in COMPOSED_INDEX_HTML
    assert "Use Reference Standard Metric V1" in COMPOSED_INDEX_HTML
    assert "Calculate Nominal Volume from Geometry" in COMPOSED_INDEX_HTML
    assert "EXPERT_REFERENCE_PROFILE" in COMPOSED_INDEX_HTML
    assert "USER_CONFIGURED" in COMPOSED_INDEX_HTML
    assert "reference_profile_id" in COMPOSED_INDEX_HTML
    assert "overridden_fields" in COMPOSED_INDEX_HTML


def test_legacy_integrated_startup_still_does_not_claim_reference_as_site_fact() -> None:
    runtime = build_integrated_virtual_runtime()
    snapshot = RuntimeApplicationService(runtime).publication()["snapshot"]

    assert snapshot["design_profile"]["configured"] is False
    assert runtime.config_version == "integrated-virtual-pond-v1-input-required"
    assert any(
        event.code == "INTEGRATED_VIRTUAL_POND_STARTED"
        and event.details["hidden_engineering_defaults"] is False
        for event in runtime.events.events
    )
