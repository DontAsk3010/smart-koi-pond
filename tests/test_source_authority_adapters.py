from datetime import UTC, datetime, timedelta

import pytest

from smart_koi_pond.actuators.real import InhibitedRealActuatorBank
from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.enums import (
    ActuatorSourceState,
    AvailabilityState,
    CommandOwner,
    ControlAuthorityState,
    DataQuality,
    ExecutionMode,
    SensorSourceState,
    SystemState,
    ValidationPhase,
    VerificationStatus,
)
from smart_koi_pond.domain.models import ArbitratedCommand, PondState
from smart_koi_pond.interfaces.hybrid import HybridActuatorBank, HybridSensorSuite
from smart_koi_pond.sensors.real import BufferedRealSensorSuite

POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
)
START = datetime(2026, 1, 1, tzinfo=UTC)


def make_runtime(
    *,
    do: float = 6.0,
    sensors=None,
    actuators=None,
    execution_mode: ExecutionMode = ExecutionMode.SIMULATION,
    validation_phase: ValidationPhase = ValidationPhase.SIMULATION,
) -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, do, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        POLICY,
        clock=SimulationClock.start(START),
        sensors=sensors,
        actuators=actuators,
        execution_mode=execution_mode,
        validation_phase=validation_phase,
    )
    if runtime.actuators.source_for("main_pump") == ActuatorSourceState.VIRTUAL_ACTUATOR:
        runtime.actuators.assets["main_pump"].feedback_on = True
    if runtime.actuators.source_for("primary_aerator") == ActuatorSourceState.VIRTUAL_ACTUATOR:
        runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_default_runtime_publishes_virtual_source_and_authority() -> None:
    runtime = make_runtime()
    snapshot = runtime.tick(1)
    publication = runtime.publish(snapshot)

    assert snapshot.raw_samples["do"].source_state == SensorSourceState.VIRTUAL_SOURCE
    assert snapshot.validated["do"].source_state == SensorSourceState.VIRTUAL_SOURCE
    assert snapshot.assets["main_pump"].source_state == ActuatorSourceState.VIRTUAL_ACTUATOR
    assert snapshot.assets["main_pump"].authority_state == ControlAuthorityState.AUTHORIZED
    assert publication["snapshot"]["validated"]["do"]["source_state"] == "VIRTUAL_SOURCE"
    assert publication["snapshot"]["assets"]["main_pump"]["authority_state"] == "AUTHORIZED"


def test_simulation_rejects_real_io_claims_and_live_modes_remain_closed() -> None:
    real_sensors = BufferedRealSensorSuite()
    with pytest.raises(RuntimeError, match="SIMULATION cannot claim real I/O"):
        make_runtime(sensors=real_sensors)

    with pytest.raises(RuntimeError, match="not authorized"):
        make_runtime(execution_mode=ExecutionMode.LIMITED_LIVE)
    with pytest.raises(RuntimeError, match="not authorized"):
        make_runtime(execution_mode=ExecutionMode.FULL_LIVE)


def test_real_sensor_identity_order_and_duplicate_rules_are_fail_closed() -> None:
    sensors = BufferedRealSensorSuite(device_bindings={"do": "site-a.pond-01.sensor.do.01"})
    sensors.ingest(
        "do",
        device_id="site-a.pond-01.sensor.do.01",
        value=5.2,
        timestamp=START,
    )
    sensors.ingest(
        "do",
        device_id="site-a.pond-01.sensor.do.01",
        value=5.2,
        timestamp=START,
    )

    with pytest.raises(RuntimeError, match="identity mismatch"):
        sensors.ingest(
            "do",
            device_id="wrong-device",
            value=5.2,
            timestamp=START + timedelta(seconds=1),
        )
    with pytest.raises(ValueError, match="out-of-order"):
        sensors.ingest(
            "do",
            device_id="site-a.pond-01.sensor.do.01",
            value=5.1,
            timestamp=START - timedelta(seconds=1),
        )
    with pytest.raises(ValueError, match="conflicting duplicate"):
        sensors.ingest(
            "do",
            device_id="site-a.pond-01.sensor.do.01",
            value=5.1,
            timestamp=START,
        )


def test_real_sensor_switch_requires_binding_and_reconciliation_fresh_sample() -> None:
    sensors = HybridSensorSuite()
    runtime = make_runtime(sensors=sensors)
    runtime.set_execution_mode(ExecutionMode.SHADOW)

    with pytest.raises(RuntimeError, match="no governed device binding"):
        runtime.configure_sensor_source("do", SensorSourceState.REAL_SOURCE)

    sensors.real.bind_device("do", "site-a.pond-01.sensor.do.01")
    sensors.real.ingest(
        "do",
        device_id="site-a.pond-01.sensor.do.01",
        value=5.4,
        timestamp=START - timedelta(seconds=1),
    )
    with pytest.raises(RuntimeError, match="predates reconciliation boundary"):
        runtime.configure_sensor_source("do", SensorSourceState.REAL_SOURCE)

    sensors.real.ingest(
        "do",
        device_id="site-a.pond-01.sensor.do.01",
        value=5.4,
        timestamp=runtime.clock.current,
    )
    runtime.configure_sensor_source("do", SensorSourceState.REAL_SOURCE)
    snapshot = runtime.tick(1)

    assert snapshot.validated["do"].quality == DataQuality.GOOD
    assert snapshot.validated["do"].source_state == SensorSourceState.REAL_SOURCE
    assert snapshot.validated["do"].device_id == "site-a.pond-01.sensor.do.01"
    assert any(event.code == "SENSOR_SOURCE_CHANGED" for event in runtime.events.events)


def test_shadow_real_actuator_is_inhibited_even_when_control_requests_on() -> None:
    actuators = HybridActuatorBank()
    actuators.real.bind_device("backup_aerator", "site-a.pond-01.aerator.backup.01")
    runtime = make_runtime(do=4.6, actuators=actuators)
    runtime.set_execution_mode(ExecutionMode.SHADOW)
    runtime.configure_actuator_source("backup_aerator", ActuatorSourceState.REAL_ACTUATOR)
    runtime.actuators.set_availability("backup_aerator", AvailabilityState.AVAILABLE)

    snapshot = runtime.tick(30)
    command = snapshot.commands["backup_aerator"]

    assert command.accepted is False
    assert command.final_on is False
    assert command.reason == "REAL_ACTUATOR_COMMAND_INHIBITED"
    assert runtime.actuators.assets["backup_aerator"].feedback_on is False
    assert snapshot.classification.state != SystemState.CORRECTING
    assert any(
        event.code == "REAL_ACTUATOR_COMMAND_INHIBITED" for event in runtime.events.events
    )


def test_real_actuator_adapter_itself_rejects_active_commands() -> None:
    actuators = InhibitedRealActuatorBank(
        device_bindings={"backup_aerator": "site-a.pond-01.aerator.backup.01"}
    )
    actuators.set_availability("backup_aerator", AvailabilityState.AVAILABLE)
    command = ArbitratedCommand(
        asset_id="backup_aerator",
        requested_on=True,
        final_on=True,
        owner=CommandOwner.AUTO,
        accepted=True,
        reason="test",
    )

    with pytest.raises(RuntimeError, match="authority gate failed"):
        actuators.execute(command, START)


def test_source_transition_aborts_pending_verification_and_is_audited() -> None:
    actuators = HybridActuatorBank()
    actuators.real.bind_device("backup_aerator", "site-a.pond-01.aerator.backup.01")
    runtime = make_runtime(do=4.6, actuators=actuators)
    runtime.set_execution_mode(ExecutionMode.SHADOW)
    runtime.tick(30)
    assert runtime.verification.tasks[0].status == VerificationStatus.PENDING

    actuators.virtual.assets["backup_aerator"].feedback_on = False
    runtime.configure_actuator_source("backup_aerator", ActuatorSourceState.REAL_ACTUATOR)

    assert runtime.verification.tasks[0].status == VerificationStatus.ABORTED_BY_MODE_CHANGE
    assert any(
        event.code == "VERIFICATION_ABORTED_BY_IO_TRANSITION"
        for event in runtime.events.events
    )
    assert any(event.code == "ACTUATOR_SOURCE_CHANGED" for event in runtime.events.events)


def test_real_source_checkpoint_restores_identity_but_not_cached_observation() -> None:
    sensors = HybridSensorSuite()
    sensors.real.bind_device("do", "site-a.pond-01.sensor.do.01")
    runtime = make_runtime(sensors=sensors)
    runtime.set_execution_mode(ExecutionMode.SHADOW)
    sensors.real.ingest(
        "do",
        device_id="site-a.pond-01.sensor.do.01",
        value=5.6,
        timestamp=runtime.clock.current,
    )
    runtime.configure_sensor_source("do", SensorSourceState.REAL_SOURCE)
    runtime.tick(1)
    checkpoint = runtime.capture_checkpoint()

    restored = make_runtime(sensors=HybridSensorSuite(), execution_mode=ExecutionMode.SHADOW)
    restored.restore_checkpoint(checkpoint)

    assert restored.sensors.source_for("do") == SensorSourceState.REAL_SOURCE
    assert restored.sensors.device_id_for("do") == "site-a.pond-01.sensor.do.01"
    assert restored.sensors.real.has_sample("do") is False
    snapshot = restored.tick(1)
    assert snapshot.validated["do"].value is None
    assert snapshot.validated["do"].quality == DataQuality.INVALID


def test_checkpoint_rejects_adapter_identity_mismatch() -> None:
    runtime = make_runtime(sensors=HybridSensorSuite())
    checkpoint = runtime.capture_checkpoint()
    restored = make_runtime()

    with pytest.raises(ValueError, match="sensor adapter identity"):
        restored.restore_checkpoint(checkpoint)
