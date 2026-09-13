from datetime import datetime
from typing import Any

from smart_koi_pond.actuators.real import InhibitedRealActuatorBank
from smart_koi_pond.actuators.virtual import VirtualActuatorBank
from smart_koi_pond.domain.enums import (
    ActuatorSourceState,
    AvailabilityState,
    CommandOwner,
    ControlAuthorityState,
    SensorSourceState,
)
from smart_koi_pond.domain.models import (
    ArbitratedCommand,
    DeviceFeedback,
    PondState,
    SensorSample,
)
from smart_koi_pond.sensors.real import BufferedRealSensorSuite
from smart_koi_pond.sensors.virtual import VirtualSensorSuite


class HybridSensorSuite:
    """Per-sensor virtual/real composition for progressive source replacement."""

    ADAPTER_ID = "hybrid-sensor-suite"
    PARAMETER_MAP = VirtualSensorSuite.PARAMETER_MAP

    def __init__(
        self,
        *,
        virtual: VirtualSensorSuite | None = None,
        real: BufferedRealSensorSuite | None = None,
    ) -> None:
        self.virtual = virtual or VirtualSensorSuite()
        self.real = real or BufferedRealSensorSuite()
        self._sources = {
            sensor_id: SensorSourceState.VIRTUAL_SOURCE for sensor_id in self.PARAMETER_MAP
        }

    @property
    def adapter_id(self) -> str:
        return self.ADAPTER_ID

    def source_for(self, sensor_id: str) -> SensorSourceState:
        if sensor_id not in self.PARAMETER_MAP:
            raise KeyError(sensor_id)
        return self._sources[sensor_id]

    def device_id_for(self, sensor_id: str) -> str | None:
        if self.source_for(sensor_id) == SensorSourceState.REAL_SOURCE:
            return self.real.device_id_for(sensor_id)
        return None

    def set_source(
        self,
        sensor_id: str,
        source: SensorSourceState,
        *,
        require_fresh_real_sample: bool = True,
        not_before: datetime | None = None,
    ) -> None:
        if sensor_id not in self.PARAMETER_MAP:
            raise KeyError(sensor_id)
        source = SensorSourceState(source)
        if source == SensorSourceState.REAL_SOURCE:
            if self.real.device_id_for(sensor_id) is None:
                raise RuntimeError(f"real sensor has no governed device binding: {sensor_id}")
            if require_fresh_real_sample:
                if not self.real.has_sample(sensor_id):
                    raise RuntimeError(
                        f"fresh real sample required before source switch: {sensor_id}"
                    )
                if not_before is not None and not self.real.sample_is_fresh(sensor_id, not_before):
                    raise RuntimeError(
                        f"real sample predates reconciliation boundary: {sensor_id}"
                    )
        self._sources[sensor_id] = source

    def sample(self, state: PondState, timestamp: datetime) -> dict[str, SensorSample]:
        virtual_samples = self.virtual.sample(state, timestamp)
        real_samples = self.real.sample(state, timestamp)
        return {
            sensor_id: (
                real_samples[sensor_id]
                if self._sources[sensor_id] == SensorSourceState.REAL_SOURCE
                else virtual_samples[sensor_id]
            )
            for sensor_id in self.PARAMETER_MAP
        }

    def set_availability(
        self,
        sensor_id: str,
        availability: AvailabilityState | None,
    ) -> None:
        if self.source_for(sensor_id) == SensorSourceState.REAL_SOURCE:
            self.real.set_availability(sensor_id, availability)
        else:
            self.virtual.set_availability(sensor_id, availability)

    def availability_override(self, sensor_id: str) -> AvailabilityState | None:
        if self.source_for(sensor_id) == SensorSourceState.REAL_SOURCE:
            return self.real.availability_override(sensor_id)
        return self.virtual.availability_override(sensor_id)

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "sources": {sensor_id: source.value for sensor_id, source in self._sources.items()},
            "virtual": self.virtual.checkpoint_state(),
            "real": self.real.checkpoint_state(),
        }

    def restore_state(self, state: dict[str, Any] | None) -> None:
        self.virtual.restore_state(None)
        self.real.restore_state(None)
        self._sources = {
            sensor_id: SensorSourceState.VIRTUAL_SOURCE for sensor_id in self.PARAMETER_MAP
        }
        if not state:
            return
        self.virtual.restore_state(state.get("virtual"))
        self.real.restore_state(state.get("real"))
        for sensor_id, source in state.get("sources", {}).items():
            if sensor_id in self.PARAMETER_MAP:
                self.set_source(
                    sensor_id,
                    SensorSourceState(source),
                    require_fresh_real_sample=False,
                )


class HybridActuatorBank:
    """Per-asset virtual/real composition with real-side authority inherited from its adapter."""

    ADAPTER_ID = "hybrid-actuator-bank"

    def __init__(
        self,
        *,
        virtual: VirtualActuatorBank | None = None,
        real: InhibitedRealActuatorBank | None = None,
    ) -> None:
        self.virtual = virtual or VirtualActuatorBank()
        self.real = real or InhibitedRealActuatorBank()
        self._sources = {
            asset_id: ActuatorSourceState.VIRTUAL_ACTUATOR
            for asset_id in self.virtual.assets
        }

    @property
    def adapter_id(self) -> str:
        return self.ADAPTER_ID

    @property
    def assets(self):
        return {
            asset_id: (
                self.real.assets[asset_id]
                if self._sources[asset_id] == ActuatorSourceState.REAL_ACTUATOR
                else self.virtual.assets[asset_id]
            )
            for asset_id in self._sources
        }

    def source_for(self, asset_id: str) -> ActuatorSourceState:
        if asset_id not in self._sources:
            raise KeyError(asset_id)
        return self._sources[asset_id]

    def authority_for(self, asset_id: str) -> ControlAuthorityState:
        if self.source_for(asset_id) == ActuatorSourceState.REAL_ACTUATOR:
            return self.real.authority_for(asset_id)
        return self.virtual.authority_for(asset_id)

    def device_id_for(self, asset_id: str) -> str | None:
        if self.source_for(asset_id) == ActuatorSourceState.REAL_ACTUATOR:
            return self.real.device_id_for(asset_id)
        return None

    def set_source(self, asset_id: str, source: ActuatorSourceState) -> None:
        if asset_id not in self._sources:
            raise KeyError(asset_id)
        source = ActuatorSourceState(source)
        if source == ActuatorSourceState.REAL_ACTUATOR:
            if self.virtual.assets[asset_id].feedback_on:
                raise RuntimeError(
                    f"virtual actuator must be safely OFF before source switch: {asset_id}"
                )
            if self.real.device_id_for(asset_id) is None:
                raise RuntimeError(f"real actuator has no governed device binding: {asset_id}")
        self._sources[asset_id] = source

    def set_availability(self, asset_id: str, availability: AvailabilityState) -> None:
        if self.source_for(asset_id) == ActuatorSourceState.REAL_ACTUATOR:
            self.real.set_availability(asset_id, availability)
        else:
            self.virtual.set_availability(asset_id, availability)

    def set_owner(self, asset_id: str, owner: CommandOwner) -> None:
        if self.source_for(asset_id) == ActuatorSourceState.REAL_ACTUATOR:
            self.real.set_owner(asset_id, owner)
        else:
            self.virtual.set_owner(asset_id, owner)

    def set_effectiveness(self, asset_id: str, effectiveness: float) -> None:
        if self.source_for(asset_id) == ActuatorSourceState.REAL_ACTUATOR:
            self.real.set_effectiveness(asset_id, effectiveness)
        else:
            self.virtual.set_effectiveness(asset_id, effectiveness)

    def feedback_map(self) -> dict[str, bool]:
        return {asset_id: asset.feedback_on for asset_id, asset in self.assets.items()}

    def process_effect_map(self) -> dict[str, float]:
        virtual_effect = self.virtual.process_effect_map()
        return {
            asset_id: (
                0.0
                if self._sources[asset_id] == ActuatorSourceState.REAL_ACTUATOR
                else virtual_effect[asset_id]
            )
            for asset_id in self._sources
        }

    def execute(self, command: ArbitratedCommand, timestamp: datetime) -> DeviceFeedback:
        if self.source_for(command.asset_id) == ActuatorSourceState.REAL_ACTUATOR:
            return self.real.execute(command, timestamp)
        return self.virtual.execute(command, timestamp)

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "sources": {asset_id: source.value for asset_id, source in self._sources.items()},
            "virtual": self.virtual.checkpoint_state(),
            "real": self.real.checkpoint_state(),
        }

    def restore_state(self, state: dict[str, Any] | None) -> None:
        self.virtual.restore_state(None)
        self.real.restore_state(None)
        self._sources = {
            asset_id: ActuatorSourceState.VIRTUAL_ACTUATOR
            for asset_id in self.virtual.assets
        }
        if not state:
            return
        self.virtual.restore_state(state.get("virtual"))
        self.real.restore_state(state.get("real"))
        for asset_id, source in state.get("sources", {}).items():
            if asset_id not in self._sources:
                continue
            self.set_source(asset_id, ActuatorSourceState(source))
