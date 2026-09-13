from dataclasses import dataclass
from datetime import datetime

from smart_koi_pond.domain.enums import AvailabilityState
from smart_koi_pond.domain.models import PondState, SensorSample


@dataclass(slots=True, frozen=True)
class SensorFault:
    mode: str
    value: float | None = None


class VirtualSensorSuite:
    PARAMETER_MAP = {
        "temperature": "temperature_c",
        "do": "dissolved_oxygen_mg_l",
        "ph": "ph",
        "water_level": "water_level_pct",
        "flow": "circulation_flow_l_min",
    }

    def __init__(self) -> None:
        self._faults: dict[str, SensorFault] = {}
        self._stuck_values: dict[str, float] = {}
        self._availability_overrides: dict[str, AvailabilityState] = {}

    def set_fault(self, sensor_id: str, fault: SensorFault | None) -> None:
        if fault is None:
            self._faults.pop(sensor_id, None)
            self._stuck_values.pop(sensor_id, None)
        else:
            self._faults[sensor_id] = fault

    def set_availability(
        self,
        sensor_id: str,
        availability: AvailabilityState | None,
    ) -> None:
        if sensor_id not in self.PARAMETER_MAP:
            raise KeyError(sensor_id)
        if availability is None or availability == AvailabilityState.AVAILABLE:
            self._availability_overrides.pop(sensor_id, None)
        else:
            self._availability_overrides[sensor_id] = availability

    def availability_override(self, sensor_id: str) -> AvailabilityState | None:
        if sensor_id not in self.PARAMETER_MAP:
            raise KeyError(sensor_id)
        return self._availability_overrides.get(sensor_id)

    def sample(self, state: PondState, timestamp: datetime) -> dict[str, SensorSample]:
        samples: dict[str, SensorSample] = {}
        for sensor_id, attribute in self.PARAMETER_MAP.items():
            truth = float(getattr(state, attribute))
            fault = self._faults.get(sensor_id)
            availability_override = self._availability_overrides.get(sensor_id)
            value: float | None = truth
            availability = AvailabilityState.AVAILABLE

            if availability_override is not None:
                availability = availability_override
                if availability_override != AvailabilityState.AVAILABLE:
                    value = None
            elif fault is not None:
                if fault.mode == "dropout":
                    value = None
                    availability = AvailabilityState.UNAVAILABLE
                elif fault.mode == "stuck":
                    value = self._stuck_values.setdefault(sensor_id, truth)
                elif fault.mode == "drift":
                    value = truth + float(fault.value or 0.0)
                else:
                    raise ValueError(f"unsupported sensor fault mode: {fault.mode}")

            samples[sensor_id] = SensorSample(
                sensor_id=sensor_id,
                parameter=attribute,
                value=value,
                timestamp=timestamp,
                availability=availability,
            )
        return samples
