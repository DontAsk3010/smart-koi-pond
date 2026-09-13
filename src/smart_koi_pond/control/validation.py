from dataclasses import dataclass, field

from smart_koi_pond.domain.enums import AvailabilityState, DataQuality
from smart_koi_pond.domain.models import SensorSample, ValidatedMeasurement

PLAUSIBILITY_BOUNDS: dict[str, tuple[float, float]] = {
    "temperature_c": (-5.0, 60.0),
    "dissolved_oxygen_mg_l": (0.0, 25.0),
    "ph": (0.0, 14.0),
    "water_level_pct": (0.0, 120.0),
    "circulation_flow_l_min": (0.0, 100_000.0),
}


@dataclass(slots=True, frozen=True)
class SensorValidationPolicy:
    """Validation/test configuration, not biological production setpoints."""

    disagreement_tolerance: dict[str, float] = field(
        default_factory=lambda: {"dissolved_oxygen_mg_l": 0.35}
    )
    persistence_samples: int = 2
    unchanged_epsilon: dict[str, float] = field(
        default_factory=lambda: {"dissolved_oxygen_mg_l": 0.01}
    )

    def __post_init__(self) -> None:
        if self.persistence_samples < 2:
            raise ValueError("persistence_samples must be at least 2")


def _validated_from_sample(
    sample: SensorSample,
    *,
    value: float | None,
    quality: DataQuality,
    reasons: tuple[str, ...] = (),
) -> ValidatedMeasurement:
    return ValidatedMeasurement(
        sensor_id=sample.sensor_id,
        parameter=sample.parameter,
        value=value,
        timestamp=sample.timestamp,
        availability=sample.availability,
        quality=quality,
        reasons=reasons,
        source_state=sample.source_state,
        adapter_id=sample.adapter_id,
        device_id=sample.device_id,
        unit=sample.unit,
        schema_version=sample.schema_version,
    )


def validate_sample(sample: SensorSample) -> ValidatedMeasurement:
    if sample.availability != AvailabilityState.AVAILABLE or sample.value is None:
        return _validated_from_sample(
            sample,
            value=None,
            quality=DataQuality.INVALID,
            reasons=("REQUIRED_INPUT_MISSING",),
        )

    lower, upper = PLAUSIBILITY_BOUNDS[sample.parameter]
    if not lower <= sample.value <= upper:
        return _validated_from_sample(
            sample,
            value=None,
            quality=DataQuality.INVALID,
            reasons=("OUT_OF_PLAUSIBLE_RANGE",),
        )

    return _validated_from_sample(
        sample,
        value=sample.value,
        quality=DataQuality.GOOD,
    )


def validate_all(samples: dict[str, SensorSample]) -> dict[str, ValidatedMeasurement]:
    return {sensor_id: validate_sample(sample) for sensor_id, sample in samples.items()}


class SensorValidationEngine:
    """Stateful production-style validation using only observable samples."""

    PRIMARY_SENSORS = ("temperature", "do", "ph", "water_level", "flow")
    REFERENCE_SOURCES = {"do": "do_reference"}

    def __init__(self, policy: SensorValidationPolicy | None = None) -> None:
        self.policy = policy or SensorValidationPolicy()
        self._last_values: dict[str, float] = {}
        self._unchanged_counts: dict[str, int] = {}
        self._disagreement_counts: dict[tuple[str, str], int] = {}

    def _track_temporal_state(self, samples: dict[str, SensorSample]) -> None:
        for sensor_id, sample in samples.items():
            if sample.availability != AvailabilityState.AVAILABLE or sample.value is None:
                self._unchanged_counts[sensor_id] = 0
                continue
            previous = self._last_values.get(sensor_id)
            epsilon = self.policy.unchanged_epsilon.get(sample.parameter, 0.0)
            if previous is not None and abs(sample.value - previous) <= epsilon:
                self._unchanged_counts[sensor_id] = self._unchanged_counts.get(sensor_id, 0) + 1
            else:
                self._unchanged_counts[sensor_id] = 0
            self._last_values[sensor_id] = sample.value

    @staticmethod
    def _with_quality(
        measurement: ValidatedMeasurement,
        *,
        quality: DataQuality,
        value: float | None,
        reasons: tuple[str, ...],
    ) -> ValidatedMeasurement:
        return ValidatedMeasurement(
            sensor_id=measurement.sensor_id,
            parameter=measurement.parameter,
            value=value,
            timestamp=measurement.timestamp,
            availability=measurement.availability,
            quality=quality,
            reasons=reasons,
            source_state=measurement.source_state,
            adapter_id=measurement.adapter_id,
            device_id=measurement.device_id,
            unit=measurement.unit,
            schema_version=measurement.schema_version,
        )

    @staticmethod
    def _fallback(
        reference: ValidatedMeasurement,
        primary_reason: str,
    ) -> ValidatedMeasurement:
        return ValidatedMeasurement(
            sensor_id=reference.sensor_id,
            parameter=reference.parameter,
            value=reference.value,
            timestamp=reference.timestamp,
            availability=reference.availability,
            quality=reference.quality,
            reasons=("FALLBACK_REFERENCE", f"PRIMARY_REJECTED:{primary_reason}"),
            source_state=reference.source_state,
            adapter_id=reference.adapter_id,
            device_id=reference.device_id,
            unit=reference.unit,
            schema_version=reference.schema_version,
        )

    def validate(
        self,
        samples: dict[str, SensorSample],
    ) -> dict[str, ValidatedMeasurement]:
        base = validate_all(samples)
        self._track_temporal_state(samples)
        canonical = {
            sensor_id: base[sensor_id]
            for sensor_id in self.PRIMARY_SENSORS
            if sensor_id in base
        }

        for primary_id, reference_id in self.REFERENCE_SOURCES.items():
            if primary_id not in canonical or reference_id not in base:
                continue
            primary = canonical[primary_id]
            reference = base[reference_id]

            if reference.quality != DataQuality.GOOD or reference.value is None:
                self._disagreement_counts[(primary_id, reference_id)] = 0
                continue
            if primary.quality != DataQuality.GOOD or primary.value is None:
                canonical[primary_id] = self._fallback(reference, "PRIMARY_INVALID")
                continue

            tolerance = self.policy.disagreement_tolerance.get(primary.parameter)
            if tolerance is None:
                continue
            pair = (primary_id, reference_id)
            difference = abs(primary.value - reference.value)
            if difference <= tolerance:
                self._disagreement_counts[pair] = 0
                continue

            count = self._disagreement_counts.get(pair, 0) + 1
            self._disagreement_counts[pair] = count
            if count < self.policy.persistence_samples:
                canonical[primary_id] = self._with_quality(
                    primary,
                    quality=DataQuality.SUSPECT,
                    value=primary.value,
                    reasons=("REFERENCE_DISAGREEMENT_PENDING",),
                )
                continue

            if self._unchanged_counts.get(primary_id, 0) >= self.policy.persistence_samples:
                reason = "STUCK_SUSPECTED"
            else:
                reason = "DRIFT_OR_DISAGREEMENT_SUSPECTED"
            canonical[primary_id] = self._fallback(reference, reason)

        return canonical
