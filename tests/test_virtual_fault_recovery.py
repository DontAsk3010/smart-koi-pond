from smart_koi_pond.dashboard.app import build_simulation_runtime
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.digital_twin.scenario_control import (
    ScenarioTrigger,
    VirtualScenarioController,
)
from smart_koi_pond.domain.enums import AvailabilityState, OperatingMode


def make_runtime():
    return build_simulation_runtime()


def test_failed_off_actuator_removes_process_effect_and_backup_takes_over() -> None:
    runtime = make_runtime()
    controller = VirtualScenarioController(runtime)

    controller.inject_actuator_fault("main_pump", "failed_off")

    main = runtime.actuators.assets["main_pump"]
    assert main.availability == AvailabilityState.FAILED
    assert main.feedback_on is False
    assert runtime.actuators.process_effect_map()["main_pump"] == 0.0

    snapshot = runtime.tick(30.0)
    assert snapshot.pond_truth.circulation_flow_l_min == 0.0
    assert snapshot.commands["backup_pump"].accepted is True
    assert snapshot.commands["backup_pump"].final_on is True


def test_degraded_actuator_changes_effect_and_repair_stays_deenergized() -> None:
    runtime = make_runtime()
    controller = VirtualScenarioController(runtime)

    controller.inject_actuator_fault("primary_aerator", "degraded", 0.25)
    assert runtime.actuators.assets["primary_aerator"].feedback_on is True
    assert runtime.actuators.process_effect_map()["primary_aerator"] == 0.25

    controller.clear_actuator_fault("primary_aerator")
    asset = runtime.actuators.assets["primary_aerator"]
    assert asset.effectiveness == 1.0
    assert asset.feedback_on is False
    assert runtime.actuators.process_effect_map()["primary_aerator"] == 0.0


def test_safe_runtime_reset_preserves_fault_and_deenergizes_outputs() -> None:
    runtime = make_runtime()
    controller = VirtualScenarioController(runtime)
    controller.inject_actuator_fault("main_pump", "failed_off")
    runtime.actuators.assets["backup_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()

    controller.safe_runtime_reset()

    assert runtime.operating_mode == OperatingMode.RECOVERY_SYNC
    assert runtime.actuators.fault_for("main_pump") is not None
    assert runtime.actuators.assets["main_pump"].availability == AvailabilityState.FAILED
    assert all(not asset.feedback_on for asset in runtime.actuators.assets.values())
    codes = [event.code for event in runtime.events.events]
    assert "SAFE_RUNTIME_RESET_REQUESTED" in codes
    assert "RUNTIME_RESTART_RECONCILIATION_REQUIRED" in codes
    assert "SAFE_RUNTIME_RESET_COMPLETE" in codes


def test_timed_automatic_fault_fires_once() -> None:
    runtime = make_runtime()
    service = RuntimeApplicationService(runtime)
    trigger = ScenarioTrigger(
        action="inject_actuator_fault",
        payload={"asset_id": "main_pump", "mode": "failed_off"},
        trigger_id="timed-main-pump-fault",
        after_seconds=10.0,
    )
    service.scenarios.schedule(trigger)

    service.step(9.0)
    assert runtime.actuators.fault_for("main_pump") is None

    service.step(1.0)
    assert runtime.actuators.fault_for("main_pump") is not None
    assert trigger.fired_count == 1

    service.step(30.0)
    assert trigger.fired_count == 1


def test_sensor_condition_can_trigger_automatic_fault() -> None:
    runtime = make_runtime()
    service = RuntimeApplicationService(runtime)
    trigger = ScenarioTrigger(
        action="inject_sensor_fault",
        payload={"sensor_id": "ph", "mode": "dropout"},
        trigger_id="low-do-ph-fault",
        sensor_id="do",
        comparison="below",
        threshold=6.1,
    )
    service.scenarios.schedule(trigger)

    snapshot = service.step(1.0)

    assert trigger.fired_count == 1
    assert snapshot.validated["ph"].value is None
    assert snapshot.validated["ph"].availability == AvailabilityState.UNAVAILABLE


def test_engineering_role_is_required_for_hardware_fault_and_reset() -> None:
    service = RuntimeApplicationService(make_runtime())

    try:
        service.command(
            "inject_actuator_fault",
            {"asset_id": "main_pump", "mode": "failed_off"},
            role="operator",
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("operator must not inject virtual hardware faults")

    service.command(
        "inject_actuator_fault",
        {"asset_id": "main_pump", "mode": "failed_off"},
        role="engineering",
    )
    assert service.runtime.actuators.fault_for("main_pump") is not None

    try:
        service.command("safe_runtime_reset", {}, role="operator")
    except PermissionError:
        pass
    else:
        raise AssertionError("operator must not invoke engineering safe reset")


def test_publication_exposes_armed_scenario_triggers() -> None:
    service = RuntimeApplicationService(make_runtime())
    service.command(
        "schedule_scenario_trigger",
        {
            "trigger_id": "scheduled-fault-1",
            "scenario_action": "inject_actuator_fault",
            "scenario_payload": {"asset_id": "main_pump", "mode": "failed_off"},
            "after_seconds": 60,
        },
        role="engineering",
    )

    publication = service.publication()
    assert publication["scenario_triggers"][0]["trigger_id"] == "scheduled-fault-1"
    assert publication["scenario_triggers"][0]["fired_count"] == 0
