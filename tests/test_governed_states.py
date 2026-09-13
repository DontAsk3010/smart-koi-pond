from smart_koi_pond.domain import AvailabilityState, OperatingMode, SystemState


def test_governed_state_vocabulary_is_importable() -> None:
    assert SystemState.NORMAL == "NORMAL"
    assert OperatingMode.SAFE_TOTAL_SHUTDOWN == "SAFE_TOTAL_SHUTDOWN"
    assert AvailabilityState.PLANNED_OFF == "PLANNED_OFF"


def test_planned_off_is_not_failed() -> None:
    assert AvailabilityState.PLANNED_OFF != AvailabilityState.FAILED
