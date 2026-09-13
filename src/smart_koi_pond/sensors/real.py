from datetime import datetime
from typing import Any

from smart_koi_pond.domain.enums import AvailabilityState, SensorSourceState
from smart_koi_pond.domain.models import PondState, SensorSample


class BufferedRealSensorSuite:
    """Production-lineage real-source boundary with no direct hardware dependency.

    Transport drivers may ingest observations here later. The adapter never reads
    Digital Twin truth and never invents a value for a missing physical sample.
    """

    ADAPTER_ID = "buffered-real-sensor-suite"
    PARAMETER_MAP = {
        "temperature": "temperature_c",
        "do": "dissolved_oxygen_mg_l",
        "do_reference": "dissolved_oxygen_mg_l",
        "ph": "ph",
        "water_level": "water_level_pct",
        "flow": "circulation_flow_l_min",
    }
    UNIT_MAP = {
        "temperature": "degC",
        "do": "mg/L",
        "do_reference": "mg/L",
        "ph": "pH",
        "water_level": "%",
        "flow": "L/min",
    }

    def __init__(self, *, device_bindings: dict[str, str] | None = None) -> None:
        self._samples: dict[str, SensorSample] = {}
        self._availability_overrides: dict[str, AvailabilityState] = {}
        self._device_ids: dict[str, str] = {}
        for sensor_id, device_id in (device_bindings or {}).items():
            self.bind_device(sensor_id, device_id)

    @property
    def adapter_id(self) -> str:
        return self.ADAPTER_ID

    def source_for(self, sensor_id: str) -> SensorSourceState:
        if sensor_id not in self.PARAMETER_MAP:
            raise KeyError(sensor_id)
        return SensorSourceState.REAL_SOURCE

    def device_id_for(self, sensor_id: str) -> str | None:
        if sensor_id not in self.PARAMETER_MAP:
            raise KeyError(sensor_id)
        return self._device_ids.get(sensor_id)

    def has_sample(self, sensor_id: str) -> bool:
        if sensor_id not in self.PARAMETER_MAP:
            raise KeyError(sensor_id)
        return sensor_id in self._samples

    def bind_device(self, sensor_id: str, device_id: str) -> None:
        if sensor_id not in self.PARAMETER_MAP:
            raise KeyError(sensor_id)
        device_id = device_id.strip()
        if not device_id:
            raise ValueError("device_id must be non-empty")
        existing = self._device_ids.get(sensor_id)
        if existing is not None and existing != device_id:
            raise RuntimeError(
                f"sensor identity already bound: {sensor_id} -> {existing}; start a new reconciled binding"
            )
        self._device_ids[sensor_id] = device_id

    def ingest(
        self,
        sensor_id: str,
        *,
        device_id: str,
        value: float | None,
        timestamp: datetime,
        availability: AvailabilityState = AvailabilityState.AVAILABLE,
    ) -> None:
        if sensor_id not in self.PARAMETER_MAP:
            raise KeyError(sensor_id)
        expected_device = self._device_ids.get(sensor_id)
        if expected_device is None:
            raise RuntimeError(f"sensor has no governed device binding: {sensor_id}")
        if device_id != expected_device:
            raise RuntimeError(
                f"sensor identity mismatch for {sensor_id}: expected {expected_device}, got {device_id}"
            )

        previous = self._samples.get(sensor_id)
        normalized_value = value if availability == AvailabilityState.AVAILABLE else None
        if previous is not None:
            if timestamp < previous.timestamp:
                raise ValueError(f"out-of-order telemetry rejected for {sensor_id}")
            if timestamp == previous.timestamp:
                same = (
                    previous.value == normalized_value
                    and previous.availability == availability
                    and previous.device_id == device_id
                )
                if same:
                    return
                raise ValueError(f"conflicting duplicate telemetry rejected for {sensor_id}")

        self._samples[sensor_id] = SensorSample(
            sensor_id=sensor_id,
            parameter=self.PARAMETER_MAP[sensor_id],
            value=normalized_value,
            timestamp=timestamp,
            availability=availability,
            source_state=SensorSourceState.REAL_SOURCE,
            adapter_id=self.ADAPTER_ID,
            device_id=device_id,
            unit=self.UNIT_MAP[sensor_id],
        )

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
        del state
        samples: dict[str, SensorSample] = {}
        for sensor_id, parameter in self.PARAMETER_MAP.items():
            device_id = self._device_ids.get(sensor_id)
            override = self._availability_overrides.get(sensor_id)
            latest = self._samples.get(sensor_id)
            if override is not None:
                samples[sensor_id] = SensorSample(
                    sensor_id=sensor_id,
                    parameter=parameter,
                    value=None,
                    timestamp=timestamp,
                    availability=override,
                    source_state=SensorSourceState.REAL_SOURCE,
                    adapter_id=self.ADAPTER_ID,
                    device_id=device_id,
                    unit=self.UNIT_MAP[sensor_id],
                )
            elif latest is not None:
                samples[sensor_id] = latest
            else:
                samples[sensor_id] = SensorSample(
                    sensor_id=sensor_id,
                    parameter=parameter,
                    value=None,
                    timestamp=timestamp,
                    availability=AvailabilityState.UNKNOWN,
                    source_state=SensorSourceState.REAL_SOURCE,
                    adapter_id=self.ADAPTER_ID,
                    device_id=device_id,
                    unit=self.UNIT_MAP[sensor_id],
                )
        return samples

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "device_bindings": dict(self._device_ids),
            "availability_overrides": {
                sensor_id: availability.value
                for sensor_id, availability in self._availability_overrides.items()
            },
            "cached_samples_persisted": False,
        }

    def restore_state(self, state: dict[str, Any] | None) -> None:
        self._samples.clear()
        self._availability_overrides.clear()
        self._device_ids.clear()
        if not state:
            return
        for sensor_id, device_id in state.get("device_bindings", {}).items():
            self.bind_device(sensor_id, str(device_id))
        for sensor_id, availability in state.get("availability_overrides", {}).items():
            self.set_availability(sensor_id, AvailabilityState(availability))
