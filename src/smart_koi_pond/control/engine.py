from dataclasses import dataclass

from smart_koi_pond.domain.enums import CommandOwner, DataQuality, SystemState
from smart_koi_pond.domain.models import (
    Classification,
    CommandIntent,
    StateEstimate,
    ValidatedMeasurement,
)


@dataclass(slots=True, frozen=True)
class SimulationControlPolicy:
    """Explicit test policy. Values are not production biological setpoints."""

    do_watch_below: float
    do_emergency_below: float
    do_recover_above: float
    flow_watch_below: float
    water_level_low_below: float
    verification_delay_seconds: float = 120.0
    do_verification_min_delta: float = 0.01
    flow_verification_min_delta: float = 0.5


def estimate_state(validated: dict[str, ValidatedMeasurement]) -> StateEstimate:
    values = {item.parameter: item.value for item in validated.values()}
    quality = {item.parameter: item.quality for item in validated.values()}
    timestamp = max(item.timestamp for item in validated.values())
    return StateEstimate(timestamp=timestamp, values=values, quality=quality)


def classify(estimate: StateEstimate, policy: SimulationControlPolicy) -> Classification:
    do_value = estimate.values.get("dissolved_oxygen_mg_l")
    flow = estimate.values.get("circulation_flow_l_min")
    level = estimate.values.get("water_level_pct")
    reasons: list[str] = []

    if estimate.quality.get("dissolved_oxygen_mg_l") != DataQuality.GOOD:
        return Classification(SystemState.DEGRADED, ("REQUIRED_INPUT_MISSING:DO",))

    state = SystemState.NORMAL
    if do_value is not None and do_value <= policy.do_emergency_below:
        state = SystemState.EMERGENCY
        reasons.append("DO_EMERGENCY")
    elif do_value is not None and do_value <= policy.do_watch_below:
        state = SystemState.WATCH
        reasons.append("DO_LOW")

    if estimate.quality.get("circulation_flow_l_min") != DataQuality.GOOD:
        state = SystemState.DEGRADED if state == SystemState.NORMAL else state
        reasons.append("REQUIRED_INPUT_MISSING:FLOW")
    elif flow is not None and flow < policy.flow_watch_below:
        if state == SystemState.NORMAL:
            state = SystemState.DEGRADED
        reasons.append("FLOW_LOW")

    if level is not None and level < policy.water_level_low_below:
        if state in {SystemState.NORMAL, SystemState.WATCH}:
            state = SystemState.DEGRADED
        reasons.append("WATER_LEVEL_LOW")

    return Classification(state, tuple(reasons) or ("STATE_HEALTHY",))


def decide(
    estimate: StateEstimate,
    classification: Classification,
    policy: SimulationControlPolicy,
) -> list[CommandIntent]:
    intents: list[CommandIntent] = []
    do_value = estimate.values.get("dissolved_oxygen_mg_l")
    flow = estimate.values.get("circulation_flow_l_min")

    if do_value is not None and classification.state in {SystemState.WATCH, SystemState.EMERGENCY}:
        intents.append(
            CommandIntent("backup_aerator", True, CommandOwner.AUTO, "LOW_DO_CORRECTION")
        )
    elif do_value is not None and do_value >= policy.do_recover_above:
        intents.append(
            CommandIntent("backup_aerator", False, CommandOwner.AUTO, "DO_RECOVERED")
        )

    if flow is not None and flow < policy.flow_watch_below:
        intents.append(CommandIntent("backup_pump", True, CommandOwner.AUTO, "LOW_FLOW_BACKUP"))

    if classification.state in {SystemState.EMERGENCY, SystemState.FAILSAFE}:
        intents.append(CommandIntent("feeder", False, CommandOwner.AUTO, "FEEDING_SAFETY_INHIBIT"))
    return intents
