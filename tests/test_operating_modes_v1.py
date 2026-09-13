from datetime import UTC, datetime

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    CommandOwner,
    OperatingMode,
    SystemState,
    WorkflowPhase,
)
from smart_koi_pond.domain.models import PondState
from smart_koi_pond.sensors.virtual import SensorFault

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
)


def make_runtime() -> DigitalTwinRuntime:
    model = PondModel(
        PondState(
            temperature_c=27.0,
            dissolved_oxygen_mg_l=6.0,
            ph=7.2,
            water_level_pct=85.0,
        ),
        EnvironmentInputs(
            ambient_temperature_c=28.0,
            oxygen_demand_mg_l_per_hour=0.2,
        ),
    )
    runtime = DigitalTwinRuntime(
        model,
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_manual_maintenance_is_scoped_and_unaffected_backup_remains_automatic() -> None:
    runtime = make_runtime()
    runtime.start_manual_maintenance(
        ["main_pump"],
        "clean main circulation pump",
        service_locked=["main_pump"],
    )

    snapshot = runtime.tick(30)

    assert snapshot.operating_mode == OperatingMode.MANUAL_MAINTENANCE
    assert snapshot.operating_status.phase == WorkflowPhase.ACTIVE
    assert (
        runtime.actuators.assets["main_pump"].availability
        == AvailabilityState.MAINTENANCE_UNAVAILABLE
    )
    assert snapshot.commands["backup_pump"].accepted is True
    assert snapshot.commands["backup_pump"].final_on is True
    assert snapshot.classification.state == SystemState.DEGRADED

    runtime.request_return_to_auto()
    recovered = runtime.tick(30)
    assert recovered.operating_mode == OperatingMode.NORMAL_AUTO
    assert runtime.actuators.assets["main_pump"].owner == CommandOwner.AUTO
    assert runtime.actuators.assets["main_pump"].availability == AvailabilityState.AVAILABLE


def test_sensor_calibration_is_planned_unavailability_not_false_zero() -> None:
    runtime = make_runtime()
    runtime.start_sensor_calibration(["do"], "scheduled DO calibration")

    snapshot = runtime.tick(10)

    assert snapshot.operating_mode == OperatingMode.SENSOR_CALIBRATION
    assert snapshot.validated["do"].value is None
    assert snapshot.validated["do"].availability == AvailabilityState.CALIBRATION
    assert snapshot.classification.state == SystemState.DEGRADED
    assert "backup_aerator" not in snapshot.commands

    runtime.request_return_to_auto()
    recovered = runtime.tick(10)
    assert recovered.operating_mode == OperatingMode.NORMAL_AUTO
    assert recovered.validated["do"].availability == AvailabilityState.AVAILABLE
    assert recovered.validated["do"].value is not None


def test_water_change_runs_drain_refill_and_closes_paths_before_return_to_auto() -> None:
    runtime = make_runtime()
    runtime.start_water_change(
        "scheduled simulated water exchange",
        target_drain_level_pct=80.0,
        target_refill_level_pct=84.0,
    )

    started = runtime.tick(1)
    assert started.operating_status.phase == WorkflowPhase.DRAINING
    assert started.commands["drain_valve"].final_on is True
    assert started.commands["top_up_valve"].final_on is False
    assert started.commands["feeder"].final_on is False

    refilling = runtime.tick(1200)
    assert refilling.operating_status.phase == WorkflowPhase.REFILLING
    assert refilling.pond_truth.water_level_pct <= 80.0
    assert refilling.commands["drain_valve"].final_on is False
    assert refilling.commands["top_up_valve"].final_on is True

    completed = runtime.tick(1800)
    assert completed.operating_mode == OperatingMode.NORMAL_AUTO
    assert runtime.actuators.assets["drain_valve"].feedback_on is False
    assert runtime.actuators.assets["top_up_valve"].feedback_on is False
    assert completed.pond_truth.water_level_pct >= 84.0


def test_filter_clean_is_planned_and_backup_flow_continues() -> None:
    runtime = make_runtime()
    runtime.start_filter_clean(["main_pump"], "filter service and backwash")

    cleaning = runtime.tick(30)

    assert cleaning.operating_mode == OperatingMode.FILTER_CLEAN
    assert cleaning.operating_status.phase == WorkflowPhase.BACKWASHING
    assert (
        runtime.actuators.assets["main_pump"].availability
        == AvailabilityState.MAINTENANCE_UNAVAILABLE
    )
    assert cleaning.commands["backup_pump"].final_on is True
    assert cleaning.commands["backwash_valve"].final_on is True

    runtime.request_return_to_auto()
    recovered = runtime.tick(30)
    assert recovered.operating_mode == OperatingMode.NORMAL_AUTO
    assert runtime.actuators.assets["backwash_valve"].feedback_on is False
    assert runtime.actuators.assets["main_pump"].availability == AvailabilityState.AVAILABLE


def test_partial_shutdown_does_not_become_false_total_failure() -> None:
    runtime = make_runtime()
    runtime.start_partial_shutdown(["main_pump"], "planned partial isolation")

    snapshot = runtime.tick(30)

    assert snapshot.operating_mode == OperatingMode.PARTIAL_SHUTDOWN
    assert (
        runtime.actuators.assets["main_pump"].availability
        == AvailabilityState.PLANNED_OFF
    )
    assert snapshot.capability.circulation_paths_available == 1
    assert snapshot.capability.critical_capability_lost is False
    assert snapshot.commands["backup_pump"].final_on is True
    assert snapshot.classification.state == SystemState.DEGRADED


def test_safe_total_shutdown_preserves_minimum_life_support_when_fish_present() -> None:
    runtime = make_runtime()
    runtime.start_safe_total_shutdown("electrical service", fish_present=True)

    snapshot = runtime.tick(10)

    assert snapshot.operating_mode == OperatingMode.SAFE_TOTAL_SHUTDOWN
    assert snapshot.commands["main_pump"].final_on is True
    assert snapshot.commands["primary_aerator"].final_on is True
    assert snapshot.commands["feeder"].final_on is False
    assert snapshot.capability.critical_capability_lost is False
    assert snapshot.classification.state != SystemState.NORMAL

    empty_pond = make_runtime()
    empty_pond.start_safe_total_shutdown("empty pond service", fish_present=False)
    stopped = empty_pond.tick(10)
    assert stopped.capability.critical_capability_lost is True
    assert stopped.classification.state == SystemState.FAILSAFE


def test_blackout_recovery_holds_until_fresh_required_measurements_exist() -> None:
    runtime = make_runtime()
    runtime.start_blackout("simulated mains failure")

    blackout = runtime.tick(10)
    assert blackout.operating_mode == OperatingMode.BLACKOUT_RECOVERY
    assert blackout.operating_status.phase == WorkflowPhase.BLACKOUT
    assert blackout.classification.state == SystemState.FAILSAFE

    runtime.sensors.set_fault("do", SensorFault("dropout"))
    runtime.restore_power()
    held = runtime.tick(10)
    assert held.operating_mode == OperatingMode.RECOVERY_SYNC
    assert runtime.actuators.assets["main_pump"].feedback_on is True
    assert runtime.actuators.assets["primary_aerator"].feedback_on is True

    runtime.sensors.set_fault("do", None)
    recovered = runtime.tick(10)
    assert recovered.operating_mode == OperatingMode.NORMAL_AUTO
    assert runtime.actuators.assets["main_pump"].owner == CommandOwner.AUTO
    assert runtime.actuators.assets["primary_aerator"].owner == CommandOwner.AUTO
