import pytest

from smart_koi_pond.control.ammonia import UNIONIZED_AMMONIA_PARAMETER
from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.fault_controls_ui import FAULT_CONTROLS_UI_SCRIPT
from smart_koi_pond.dashboard.koi_stock_service import KoiStockRuntimeApplicationService
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def _service():
    runtime = build_integrated_virtual_runtime()
    return runtime, KoiStockRuntimeApplicationService(runtime)


def _set_environment(service, parameter: str, value: float):
    return service.command(
        "set_environment_state",
        {"parameter": parameter, "value": value},
        role="engineering",
    )


def test_visual_functional_acceptance_harness_is_composed_into_existing_simulator() -> None:
    html = COMPOSED_INDEX_HTML
    for marker in (
        "functionalAcceptanceHarness",
        "VISUAL FUNCTIONAL ACCEPTANCE — CANONICAL CLOSED LOOP",
        "faNitriteHigh",
        "faNitriteEmergency",
        "faNitrateHigh",
        "faLowDo",
        "faPhHigh",
        "faPhLow",
        "faPumpFail",
        "faSameTanLowerRisk",
        "faSameTanHigherRisk",
        "faUnsafeSource",
        "faSafeSource",
        "faAttemptWaterChange",
        "faInputs",
        "faThresholds",
        "faClassification",
        "faCommands",
        "faVerification",
        "faTimeline",
        "faTrendCanvas",
    ):
        assert marker in html


def test_acceptance_ui_uses_canonical_command_and_snapshot_evidence_only() -> None:
    script = FAULT_CONTROLS_UI_SCRIPT
    assert "sendCommand('set_environment_state'" in script
    assert "sendCommand('configure_source_water_profile'" in script
    assert "sendCommand('start_water_change'" in script
    assert "sendCommand('inject_actuator_fault'" in script
    assert "snapshot.estimate" in script
    assert "snapshot.commands" in script
    assert "snapshot.feedback" in script
    assert "snapshot.verification" in script
    assert "snapshot.incidents" in script
    assert "snapshot.water_recovery" in script
    assert "fetch('/api/command'" not in script
    assert "new WebSocket" not in script
    assert "automatic acid/base/salt/binder dosing remains CLOSED" in script


def test_same_tan_visual_scenario_uses_canonical_nh3_derivation() -> None:
    _, service = _service()
    _set_environment(service, "tan", 0.5)
    _set_environment(service, "ph", 7.5)
    low = _set_environment(service, "temperature", 20.0)
    low_nh3 = low.estimate.values[UNIONIZED_AMMONIA_PARAMETER]

    _set_environment(service, "ph", 8.5)
    high = _set_environment(service, "temperature", 28.0)
    high_nh3 = high.estimate.values[UNIONIZED_AMMONIA_PARAMETER]

    assert low.pond_truth.total_ammonia_nitrogen_mg_l == pytest.approx(0.5)
    assert high.pond_truth.total_ammonia_nitrogen_mg_l == pytest.approx(0.5)
    assert high_nh3 > low_nh3
    assert high.estimate.provenance[UNIONIZED_AMMONIA_PARAMETER] == "CALCULATED"
    assert (
        high.estimate.derivation[UNIONIZED_AMMONIA_PARAMETER]["formula_id"]
        == "EPA_EMERSON_FRESHWATER_NH3_FRACTION_V1"
    )
    assert high.estimate.derivation[UNIONIZED_AMMONIA_PARAMETER]["fabricated"] is False


def test_nitrite_high_scenario_inhibits_feeding_and_requests_governed_support() -> None:
    _, service = _service()
    _set_environment(service, "tan", 0.1)
    _set_environment(service, "nitrate", 10.0)
    snapshot = _set_environment(service, "nitrite", 0.6)

    assert "NITRITE_HIGH" in snapshot.classification.reasons
    assert snapshot.commands["feeder"].requested_on is False
    assert snapshot.commands["backup_aerator"].requested_on is True
    assert snapshot.commands["backup_aerator"].reason == "BIOLOGICAL_LOAD_SUPPORT"


def test_nitrate_high_does_not_create_chemical_dosing_commands() -> None:
    _, service = _service()
    _set_environment(service, "tan", 0.1)
    _set_environment(service, "nitrite", 0.05)
    snapshot = _set_environment(service, "nitrate", 25.0)

    assert "NITRATE_HIGH" in snapshot.classification.reasons
    assert snapshot.commands["feeder"].requested_on is False
    forbidden = {"acid", "base", "salt", "binder", "chemical_doser"}
    assert not forbidden.intersection(snapshot.commands)


def test_unsafe_source_water_fails_closed_before_water_change() -> None:
    runtime, service = _service()
    service.command(
        "configure_source_water_profile",
        {
            "profile": {
                "profile_id": "acceptance-unsafe-source",
                "revision": "scenario-1",
                "source_reference": "VIRTUAL_ACCEPTANCE_SCENARIO_UNSAFE_SOURCE",
                "source_type": "OTHER",
                "temperature_c": 27.0,
                "dissolved_oxygen_mg_l": 6.0,
                "ph": 7.2,
                "total_ammonia_nitrogen_mg_l": 0.1,
                "nitrite_mg_l": 0.05,
                "nitrate_mg_l": 10.0,
                "alkalinity_mg_l_as_caco3": 100.0,
                "free_chlorine_residual_mg_l": 0.5,
                "chloramine_residual_mg_l": 0.0,
                "pond_use_qualification": "NOT_QUALIFIED",
                "provenance": "USER_CONFIGURED_SCENARIO",
            },
            "actor": "functional-acceptance-test",
        },
        role="engineering",
    )

    with pytest.raises(RuntimeError, match="SOURCE_WATER_NOT_QUALIFIED"):
        service.command(
            "start_water_change",
            {
                "target_drain_level_pct": 80.0,
                "target_refill_level_pct": 85.0,
                "reason": "VISUAL_FUNCTIONAL_ACCEPTANCE_SOURCE_WATER",
            },
            role="engineering",
        )

    inhibited = [
        event
        for event in runtime.events.events
        if event.code == "SOURCE_WATER_OPERATION_INHIBITED"
    ]
    assert inhibited
    assert inhibited[-1].payload["drain_started"] is False
    assert inhibited[-1].payload["automatic_chemical_dosing_authorized"] is False
