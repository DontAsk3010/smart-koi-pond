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
    temperature_watch_above: float | None = None
    temperature_emergency_above: float | None = None
    low_water_auto_recovery_enabled: bool = False
    water_level_recover_target: float | None = None
    water_level_hard_high_cutoff: float | None = None
    low_water_max_runtime_seconds: float = 300.0
    low_water_max_level_gain_pct: float = 15.0
    low_water_verification_delay_seconds: float = 30.0
    water_level_verification_min_delta: float = 0.5
    tan_watch_above: float | None = None
    tan_emergency_above: float | None = None
    nitrite_watch_above: float | None = None
    nitrite_emergency_above: float | None = None
    nitrate_watch_above: float | None = None
    ph_watch_below: float | None = None
    ph_watch_above: float | None = None
    ph_emergency_below: float | None = None
    ph_emergency_above: float | None = None

    def __post_init__(self) -> None:
        if (
            self.temperature_watch_above is not None
            and self.temperature_emergency_above is not None
            and self.temperature_emergency_above <= self.temperature_watch_above
        ):
            raise ValueError(
                "temperature_emergency_above must be greater than temperature_watch_above"
            )
        if (
            self.tan_watch_above is not None
            and self.tan_emergency_above is not None
            and self.tan_emergency_above <= self.tan_watch_above
        ):
            raise ValueError("tan_emergency_above must be greater than tan_watch_above")
        if (
            self.nitrite_watch_above is not None
            and self.nitrite_emergency_above is not None
            and self.nitrite_emergency_above <= self.nitrite_watch_above
        ):
            raise ValueError(
                "nitrite_emergency_above must be greater than nitrite_watch_above"
            )
        if (
            self.ph_watch_below is not None
            and self.ph_emergency_below is not None
            and self.ph_emergency_below >= self.ph_watch_below
        ):
            raise ValueError("ph_emergency_below must be below ph_watch_below")
        if (
            self.ph_watch_above is not None
            and self.ph_emergency_above is not None
            and self.ph_emergency_above <= self.ph_watch_above
        ):
            raise ValueError("ph_emergency_above must be above ph_watch_above")

        if self.low_water_auto_recovery_enabled:
            if self.water_level_recover_target is None:
                raise ValueError(
                    "water_level_recover_target is required when low-water auto recovery is enabled"
                )
            if self.water_level_hard_high_cutoff is None:
                raise ValueError(
                    "water_level_hard_high_cutoff is required when "
                    "low-water auto recovery is enabled"
                )
            if not (
                self.water_level_low_below
                < self.water_level_recover_target
                < self.water_level_hard_high_cutoff
            ):
                raise ValueError(
                    "low-water trigger must be below recovery target and hard high-level cutoff"
                )
            if self.low_water_max_runtime_seconds <= 0:
                raise ValueError("low_water_max_runtime_seconds must be positive")
            if self.low_water_max_level_gain_pct <= 0:
                raise ValueError("low_water_max_level_gain_pct must be positive")
            if self.low_water_verification_delay_seconds < 0:
                raise ValueError("low_water_verification_delay_seconds cannot be negative")
            if self.water_level_verification_min_delta <= 0:
                raise ValueError("water_level_verification_min_delta must be positive")


def estimate_state(validated: dict[str, ValidatedMeasurement]) -> StateEstimate:
    values = {item.parameter: item.value for item in validated.values()}
    quality = {item.parameter: item.quality for item in validated.values()}
    timestamp = max(item.timestamp for item in validated.values())
    return StateEstimate(timestamp=timestamp, values=values, quality=quality)


def _mark_missing(
    state: SystemState,
    reasons: list[str],
    parameter: str,
) -> SystemState:
    if state == SystemState.NORMAL:
        state = SystemState.DEGRADED
    reasons.append(f"REQUIRED_INPUT_MISSING:{parameter}")
    return state


def _classify_upper_limit(
    *,
    state: SystemState,
    reasons: list[str],
    value: float | None,
    quality: DataQuality | None,
    watch_above: float | None,
    emergency_above: float | None,
    parameter: str,
    watch_reason: str,
    emergency_reason: str,
) -> SystemState:
    if watch_above is None and emergency_above is None:
        return state
    if quality != DataQuality.GOOD or value is None:
        return _mark_missing(state, reasons, parameter)
    if emergency_above is not None and value >= emergency_above:
        reasons.append(emergency_reason)
        return SystemState.EMERGENCY
    if watch_above is not None and value >= watch_above:
        if state == SystemState.NORMAL:
            state = SystemState.WATCH
        reasons.append(watch_reason)
    return state


def classify(estimate: StateEstimate, policy: SimulationControlPolicy) -> Classification:
    do_value = estimate.values.get("dissolved_oxygen_mg_l")
    flow = estimate.values.get("circulation_flow_l_min")
    level = estimate.values.get("water_level_pct")
    temperature = estimate.values.get("temperature_c")
    tan = estimate.values.get("total_ammonia_nitrogen_mg_l")
    nitrite = estimate.values.get("nitrite_mg_l")
    nitrate = estimate.values.get("nitrate_mg_l")
    ph = estimate.values.get("ph")
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

    temperature_policy_active = (
        policy.temperature_watch_above is not None
        or policy.temperature_emergency_above is not None
    )
    if temperature_policy_active:
        if estimate.quality.get("temperature_c") != DataQuality.GOOD:
            state = _mark_missing(state, reasons, "TEMPERATURE")
        elif (
            temperature is not None
            and policy.temperature_emergency_above is not None
            and temperature >= policy.temperature_emergency_above
        ):
            state = SystemState.EMERGENCY
            reasons.append("TEMPERATURE_EMERGENCY")
        elif (
            temperature is not None
            and policy.temperature_watch_above is not None
            and temperature >= policy.temperature_watch_above
        ):
            if state == SystemState.NORMAL:
                state = SystemState.WATCH
            reasons.append("TEMPERATURE_HIGH")

    if estimate.quality.get("circulation_flow_l_min") != DataQuality.GOOD:
        state = _mark_missing(state, reasons, "FLOW")
    elif flow is not None and flow < policy.flow_watch_below:
        if state == SystemState.NORMAL:
            state = SystemState.DEGRADED
        reasons.append("FLOW_LOW")

    if policy.low_water_auto_recovery_enabled and (
        estimate.quality.get("water_level_pct") != DataQuality.GOOD or level is None
    ):
        state = _mark_missing(state, reasons, "WATER_LEVEL")
    elif level is not None and level < policy.water_level_low_below:
        if state in {SystemState.NORMAL, SystemState.WATCH}:
            state = SystemState.DEGRADED
        reasons.append("WATER_LEVEL_LOW")

    state = _classify_upper_limit(
        state=state,
        reasons=reasons,
        value=tan,
        quality=estimate.quality.get("total_ammonia_nitrogen_mg_l"),
        watch_above=policy.tan_watch_above,
        emergency_above=policy.tan_emergency_above,
        parameter="TAN",
        watch_reason="TAN_HIGH",
        emergency_reason="TAN_EMERGENCY",
    )
    state = _classify_upper_limit(
        state=state,
        reasons=reasons,
        value=nitrite,
        quality=estimate.quality.get("nitrite_mg_l"),
        watch_above=policy.nitrite_watch_above,
        emergency_above=policy.nitrite_emergency_above,
        parameter="NITRITE",
        watch_reason="NITRITE_HIGH",
        emergency_reason="NITRITE_EMERGENCY",
    )
    state = _classify_upper_limit(
        state=state,
        reasons=reasons,
        value=nitrate,
        quality=estimate.quality.get("nitrate_mg_l"),
        watch_above=policy.nitrate_watch_above,
        emergency_above=None,
        parameter="NITRATE",
        watch_reason="NITRATE_HIGH",
        emergency_reason="NITRATE_EMERGENCY",
    )

    ph_policy_active = any(
        value is not None
        for value in (
            policy.ph_watch_below,
            policy.ph_watch_above,
            policy.ph_emergency_below,
            policy.ph_emergency_above,
        )
    )
    if ph_policy_active:
        if estimate.quality.get("ph") != DataQuality.GOOD or ph is None:
            state = _mark_missing(state, reasons, "PH")
        elif (
            policy.ph_emergency_below is not None
            and ph <= policy.ph_emergency_below
        ) or (
            policy.ph_emergency_above is not None
            and ph >= policy.ph_emergency_above
        ):
            state = SystemState.EMERGENCY
            reasons.append("PH_EMERGENCY")
        elif (
            policy.ph_watch_below is not None and ph <= policy.ph_watch_below
        ) or (
            policy.ph_watch_above is not None and ph >= policy.ph_watch_above
        ):
            if state == SystemState.NORMAL:
                state = SystemState.WATCH
            reasons.append("PH_OUT_OF_TARGET")

    return Classification(state, tuple(reasons) or ("STATE_HEALTHY",))


def decide(
    estimate: StateEstimate,
    classification: Classification,
    policy: SimulationControlPolicy,
) -> list[CommandIntent]:
    intents: dict[str, CommandIntent] = {}
    do_value = estimate.values.get("dissolved_oxygen_mg_l")
    flow = estimate.values.get("circulation_flow_l_min")
    tan = estimate.values.get("total_ammonia_nitrogen_mg_l")
    nitrite = estimate.values.get("nitrite_mg_l")
    nitrate = estimate.values.get("nitrate_mg_l")
    ph = estimate.values.get("ph")

    acute_nitrogen_support = (
        tan is not None
        and policy.tan_watch_above is not None
        and tan >= policy.tan_watch_above
    ) or (
        nitrite is not None
        and policy.nitrite_watch_above is not None
        and nitrite >= policy.nitrite_watch_above
    )
    nitrate_high = (
        nitrate is not None
        and policy.nitrate_watch_above is not None
        and nitrate >= policy.nitrate_watch_above
    )

    if (do_value is not None and do_value <= policy.do_watch_below) or acute_nitrogen_support:
        reason = "BIOLOGICAL_LOAD_SUPPORT" if acute_nitrogen_support else "LOW_DO_CORRECTION"
        intents["backup_aerator"] = CommandIntent(
            "backup_aerator",
            True,
            CommandOwner.AUTO,
            reason,
        )
    elif do_value is not None and do_value >= policy.do_recover_above:
        intents["backup_aerator"] = CommandIntent(
            "backup_aerator",
            False,
            CommandOwner.AUTO,
            "DO_RECOVERED",
        )

    if (flow is not None and flow < policy.flow_watch_below) or acute_nitrogen_support:
        reason = "BIOFILTER_FLOW_SUPPORT" if acute_nitrogen_support else "LOW_FLOW_BACKUP"
        intents["backup_pump"] = CommandIntent(
            "backup_pump",
            True,
            CommandOwner.AUTO,
            reason,
        )

    ph_outside = (
        ph is not None
        and (
            (policy.ph_watch_below is not None and ph <= policy.ph_watch_below)
            or (policy.ph_watch_above is not None and ph >= policy.ph_watch_above)
        )
    )
    if acute_nitrogen_support or nitrate_high or ph_outside:
        intents["feeder"] = CommandIntent(
            "feeder",
            False,
            CommandOwner.AUTO,
            "WATER_QUALITY_FEED_INHIBIT",
        )

    if classification.state in {SystemState.EMERGENCY, SystemState.FAILSAFE}:
        intents["feeder"] = CommandIntent(
            "feeder",
            False,
            CommandOwner.AUTO,
            "FEEDING_SAFETY_INHIBIT",
        )
    return list(intents.values())
