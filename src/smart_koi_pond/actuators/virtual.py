from dataclasses import dataclass
from datetime import datetime

from smart_koi_pond.domain.enums import AvailabilityState, CommandOwner
from smart_koi_pond.domain.models import ArbitratedCommand, DeviceFeedback


@dataclass(slots=True)
class VirtualAsset:
    asset_id: str
    feedback_on: bool = False
    availability: AvailabilityState = AvailabilityState.AVAILABLE
    owner: CommandOwner = CommandOwner.AUTO
    effectiveness: float = 1.0


class VirtualActuatorBank:
    DEFAULT_ASSETS = (
        "main_pump",
        "backup_pump",
        "primary_aerator",
        "backup_aerator",
        "top_up_valve",
        "drain_valve",
        "backwash_valve",
        "feeder",
        "uv_lamp",
    )

    def __init__(self) -> None:
        self.assets = {asset_id: VirtualAsset(asset_id) for asset_id in self.DEFAULT_ASSETS}

    def set_availability(self, asset_id: str, availability: AvailabilityState) -> None:
        asset = self.assets[asset_id]
        asset.availability = availability
        if availability not in {AvailabilityState.AVAILABLE, AvailabilityState.STANDBY}:
            asset.feedback_on = False

    def set_owner(self, asset_id: str, owner: CommandOwner) -> None:
        self.assets[asset_id].owner = owner

    def set_effectiveness(self, asset_id: str, effectiveness: float) -> None:
        if not 0.0 <= effectiveness <= 1.0:
            raise ValueError("effectiveness must be between 0.0 and 1.0")
        self.assets[asset_id].effectiveness = float(effectiveness)

    def feedback_map(self) -> dict[str, bool]:
        return {asset_id: asset.feedback_on for asset_id, asset in self.assets.items()}

    def process_effect_map(self) -> dict[str, float]:
        return {
            asset_id: asset.effectiveness if asset.feedback_on else 0.0
            for asset_id, asset in self.assets.items()
        }

    def execute(self, command: ArbitratedCommand, timestamp: datetime) -> DeviceFeedback:
        asset = self.assets[command.asset_id]
        if command.accepted:
            asset.feedback_on = command.final_on
        return DeviceFeedback(
            asset_id=asset.asset_id,
            commanded_on=command.final_on,
            feedback_on=asset.feedback_on,
            availability=asset.availability,
            timestamp=timestamp,
            effectiveness=asset.effectiveness,
        )
