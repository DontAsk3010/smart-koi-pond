from datetime import datetime, UTC

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    AvailabilityState,
    CommandOwner,
    DataQuality,
    SystemState,
    VerificationStatus,
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


def make_runtime(*, do: float = 6.0) -> DigitalTwinRuntime:
    model = PondModel(
        PondState(
            temperature_c=27.0,
            dissolved_oxygen_mg_l=do,
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


def test_low_do_triggers_correction_and_verifies_effect() -> None:
    runtime = make_runtime(do=4.6)

    first = runtime.tick(60)
    assert first.classification.state == SystemState.CORRECTING
    assert first.commands["backup_aerator"].final_on is True
    assert runtime.actuators.assets["backup_aerator"].feedback_on is True

    runtime.tick(60)
    third = runtime.tick(60)
    assert third.verification[0].status == VerificationStatus.VERIFIED_SUCCESS
    assert (
        third.estimate.values["dissolved_oxygen_mg_l"]
        > first.estimate.values["dissolved_oxygen_mg_l"]
    )


def test_sensor_dropout_is_not_converted_to_zero_or_emergency() -> None:
    runtime = make_runtime(do=6.0)
    runtime.sensors.set_fault("do", SensorFault("dropout"))

    snapshot = runtime.tick(30)
    measured = snapshot.validated["do"]
    assert measured.value is None
    assert measured.quality == DataQuality.INVALID
    assert measured.availability == AvailabilityState.UNAVAILABLE
    assert snapshot.classification.state == SystemState.DEGRADED
    assert "backup_aerator" not in snapshot.commands


def test_planned_off_and_manual_ownership_block_auto_without_false_failure() -> None:
    runtime = make_runtime(do=4.5)
    runtime.actuators.set_availability("backup_aerator", AvailabilityState.PLANNED_OFF)

    planned = runtime.tick(30)
    assert planned.commands["backup_aerator"].accepted is False
    assert "PLANNED_OFF" in planned.commands["backup_aerator"].reason
    assert runtime.actuators.assets["backup_aerator"].availability == AvailabilityState.PLANNED_OFF

    runtime.actuators.set_availability("backup_aerator", AvailabilityState.AVAILABLE)
    runtime.actuators.set_owner("backup_aerator", CommandOwner.MAINTENANCE)
    manual = runtime.tick(30)
    assert manual.commands["backup_aerator"].accepted is False
    assert manual.commands["backup_aerator"].reason == "AUTO_BLOCKED_BY_COMMAND_OWNERSHIP"


def test_simulation_clock_pause_resume_preserves_time_order() -> None:
    runtime = make_runtime()
    start = runtime.clock.current
    runtime.clock.pause()
    runtime.tick(60)
    assert runtime.clock.current == start
    runtime.clock.resume()
    runtime.tick(60)
    assert runtime.clock.current > start


def test_low_flow_starts_backup_pump() -> None:
    runtime = make_runtime()
    runtime.actuators.assets["main_pump"].feedback_on = False
    runtime._last_feedback = runtime.actuators.feedback_map()

    snapshot = runtime.tick(30)
    assert snapshot.estimate.values["circulation_flow_l_min"] == 0.0
    assert snapshot.commands["backup_pump"].accepted is True
    assert snapshot.commands["backup_pump"].final_on is True
