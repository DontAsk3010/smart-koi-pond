from smart_koi_pond.domain.enums import (
    AvailabilityState,
    DataQuality,
)
from smart_koi_pond.domain.models import SensorSample, ValidatedMeasurement

PLAUSIBILITY_BOUNDS: dict[str, tuple[float, float]] = {
    "temperature_c": (-5.0, 60.0),
    "dissolved_oxygen_mg_l": (0.0, 25.0),
    "ph": (0.0, 14.0),
    "water_level_pct": (0.0, 120.0),
    "circulation_flow_l_min": (0.0, 100_000.0),
}


def validate_sample(sample: SensorSample) -> ValidatedMeasurement:
    if sample.availability != AvailabilityState.AVAILABLE or sample.value is None:
        return ValidatedMeasurement(
            sensor_id=sample.sensor_id,
            parameter=sample.parameter,
            value=None,
            timestamp=sample.timestamp,
            availability=sample.availability,
            quality=DataQuality.INVALID,
            reasons=("REQUIRED_INPUT_MISSING",),
        )

    lower, upper = PLAUSIBILITY_BOUNDS[sample.parameter]
    if not lower <= sample.value <= upper:
        return ValidatedMeasurement(
            sensor_id=sample.sensor_id,
            parameter=sample.parameter,
            value=None,
            timestamp=sample.timestamp,
            availability=sample.availability,
            quality=DataQuality.INVALID,
            reasons=("OUT_OF_PLAUSIBLE_RANGE",),
        )

    return ValidatedMeasurement(
        sensor_id=sample.sensor_id,
        parameter=sample.parameter,
        value=sample.value,
        timestamp=sample.timestamp,
        availability=sample.availability,
        quality=DataQuality.GOOD,
    )


def validate_all(samples: dict[str, SensorSample]) -> dict[str, ValidatedMeasurement]:
    return {sensor_id: validate_sample(sample) for sensor_id, sample in samples.items()}
