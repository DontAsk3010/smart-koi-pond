from datetime import datetime
from typing import Any, Mapping, Protocol, runtime_checkable

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


@runtime_checkable
class SensorAdapter(Protocol):
    PARAMETER_MAP: Mapping[str, str]

    @property
    def adapter_id(self) -> str: ...

    def source_for(self, sensor_id: str) -> SensorSourceState: ...

    def device_id_for(self, sensor_id: str) -> str | None: ...

    def sample(self, state: PondState, timestamp: datetime) -> dict[str, SensorSample]: ...

    def set_availability(
        self,
        sensor_id: str,
        availability: AvailabilityState | None,
    ) -> None: ...

    def availability_override(self, sensor_id: str) -> AvailabilityState | None: ...

    def checkpoint_state(self) -> dict[str, Any]: ...

    def restore_state(self, state: dict[str, Any] | None) -> None: ...


@runtime_checkable
class ActuatorAdapter(Protocol):
    assets: Mapping[str, Any]

    @property
    def adapter_id(self) -> str: ...

    def source_for(self, asset_id: str) -> ActuatorSourceState: ...

    def authority_for(self, asset_id: str) -> ControlAuthorityState: ...

    def device_id_for(self, asset_id: str) -> str | None: ...

    def set_availability(self, asset_id: str, availability: AvailabilityState) -> None: ...

    def set_owner(self, asset_id: str, owner: CommandOwner) -> None: ...

    def set_effectiveness(self, asset_id: str, effectiveness: float) -> None: ...

    def feedback_map(self) -> dict[str, bool]: ...

    def process_effect_map(self) -> dict[str, float]: ...

    def execute(self, command: ArbitratedCommand, timestamp: datetime) -> DeviceFeedback: ...

    def checkpoint_state(self) -> dict[str, Any]: ...

    def restore_state(self, state: dict[str, Any] | None) -> None: ...
