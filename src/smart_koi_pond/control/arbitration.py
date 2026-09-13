from smart_koi_pond.domain.enums import (
    AvailabilityState,
    CommandOwner,
    OperatingMode,
)
from smart_koi_pond.domain.models import ArbitratedCommand, CommandIntent

BLOCKING_AVAILABILITY = {
    AvailabilityState.PLANNED_OFF,
    AvailabilityState.MAINTENANCE_UNAVAILABLE,
    AvailabilityState.CALIBRATION,
    AvailabilityState.UNAVAILABLE,
    AvailabilityState.FAILED,
    AvailabilityState.UNKNOWN,
}


def arbitrate(
    intent: CommandIntent,
    availability: AvailabilityState,
    current_owner: CommandOwner,
    operating_mode: OperatingMode,
) -> ArbitratedCommand:
    if intent.owner == CommandOwner.SAFETY:
        if intent.requested_on:
            return ArbitratedCommand(
                intent.asset_id,
                intent.requested_on,
                False,
                CommandOwner.SAFETY,
                False,
                "SAFETY_OWNER_CANNOT_ENERGIZE",
            )
        return ArbitratedCommand(
            intent.asset_id,
            intent.requested_on,
            False,
            CommandOwner.SAFETY,
            True,
            intent.reason,
        )

    if intent.owner == CommandOwner.AUTO and current_owner != CommandOwner.AUTO:
        return ArbitratedCommand(
            intent.asset_id,
            intent.requested_on,
            False,
            current_owner,
            False,
            "AUTO_BLOCKED_BY_COMMAND_OWNERSHIP",
        )

    if intent.owner != CommandOwner.AUTO and current_owner != intent.owner:
        return ArbitratedCommand(
            intent.asset_id,
            intent.requested_on,
            False,
            current_owner,
            False,
            "COMMAND_OWNER_MISMATCH",
        )

    if availability in BLOCKING_AVAILABILITY and intent.requested_on:
        return ArbitratedCommand(
            intent.asset_id,
            intent.requested_on,
            False,
            intent.owner,
            False,
            f"ASSET_NOT_AVAILABLE:{availability}",
        )

    if operating_mode == OperatingMode.SAFE_TOTAL_SHUTDOWN and intent.asset_id == "feeder":
        return ArbitratedCommand(
            intent.asset_id,
            intent.requested_on,
            False,
            CommandOwner.SHUTDOWN,
            True,
            "SHUTDOWN_INHIBIT",
        )

    return ArbitratedCommand(
        intent.asset_id,
        intent.requested_on,
        intent.requested_on,
        intent.owner,
        True,
        intent.reason,
    )
