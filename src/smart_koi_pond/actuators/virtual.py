from dataclasses import dataclass
from datetime import datetime
from typing import Any

from smart_koi_pond.domain.enums import (
    ActuatorSourceState,
    AvailabilityState,
    CommandOwner,
    ControlAuthorityState,
)
from smart_koi_pond.domain.models import ArbitratedCommand, DeviceFeedback


@dataclass(slots=True, frozen=True)
class ActuatorFault:
    mode: str
    value: float | None = None


@dataclass(slots=True)
class VirtualAsset:
    asset_id: str
    feedback_on: bool = False
    availability: AvailabilityState = AvailabilityState.AVAILABLE
    owner: CommandOwner = CommandOwner.AUTO
    effectiveness: float = 1.0


class VirtualActuatorBank:
    ADAPTER_ID = "virtual-actuator-bank"
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
        self._faults: dict[str, ActuatorFault] = {}
        self._fault_restore: dict[str, tuple[AvailabilityState, float]] = {}

    @property
    def adapter_id(self) -> str:
        return self.ADAPTER_ID

    def source_for(self, asset_id: str) -> ActuatorSourceState:
        if asset_id not in self.assets:
            raise KeyError(asset_id)
        return ActuatorSourceState.VIRTUAL_ACTUATOR

    def authority_for(self, asset_id: str) -> ControlAuthorityState:
        if asset_id not in self.assets:
            raise KeyError(asset_id)
        return ControlAuthorityState.AUTHORIZED

    def device_id_for(self, asset_id: str) -> str | None:
        if asset_id not in self.assets:
            raise KeyError(asset_id)
        return None

    def fault_for(self, asset_id: str) -> ActuatorFault | None:
        if asset_id not in self.assets:
            raise KeyError(asset_id)
        return self._faults.get(asset_id)

    def set_fault(self, asset_id: str, fault: ActuatorFault | None) -> None:
        asset = self.assets[asset_id]
        if fault is None:
            restore = self._fault_restore.pop(asset_id, None)
            self._faults.pop(asset_id, None)
            if restore is not None:
                asset.availability, asset.effectiveness = restore
            asset.feedback_on = False
            return

        mode = str(fault.mode)
        if mode not in {"failed_off", "degraded"}:
            raise ValueError("actuator fault mode must be failed_off or degraded")
        if asset_id not in self._faults:
            self._fault_restore[asset_id] = (asset.availability, asset.effectiveness)

        if mode == "failed_off":
            asset.availability = AvailabilityState.FAILED
            asset.effectiveness = 0.0
            asset.feedback_on = False
        else:
            value = float(fault.value if fault.value is not None else 0.5)
            if not 0.0 <= value < 1.0:
                raise ValueError("degraded actuator effectiveness must satisfy 0.0 <= value < 1.0")
            asset.effectiveness = value

        self._faults[asset_id] = ActuatorFault(mode, fault.value)

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
        effects: dict[str, float] = {}
        for asset_id, asset in self.assets.items():
            fault = self._faults.get(asset_id)
            if fault is not None and fault.mode == "failed_off":
                effects[asset_id] = 0.0
            else:
                effects[asset_id] = asset.effectiveness if asset.feedback_on else 0.0
        return effects

    def execute(self, command: ArbitratedCommand, timestamp: datetime) -> DeviceFeedback:
        asset = self.assets[command.asset_id]
        fault = self._faults.get(command.asset_id)
        if fault is not None and fault.mode == "failed_off":
            asset.feedback_on = False
        elif command.accepted:
            asset.feedback_on = command.final_on
        return DeviceFeedback(
            asset_id=asset.asset_id,
            commanded_on=command.final_on,
            feedback_on=asset.feedback_on,
            availability=asset.availability,
            timestamp=timestamp,
            effectiveness=asset.effectiveness,
            source_state=ActuatorSourceState.VIRTUAL_ACTUATOR,
            authority_state=ControlAuthorityState.AUTHORIZED,
            adapter_id=self.ADAPTER_ID,
        )

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "assets": {
                asset_id: {
                    "owner": asset.owner.value,
                    "availability": asset.availability.value,
                    "feedback_on": asset.feedback_on,
                    "effectiveness": asset.effectiveness,
                }
                for asset_id, asset in self.assets.items()
            },
            "faults": {
                asset_id: {"mode": fault.mode, "value": fault.value}
                for asset_id, fault in self._faults.items()
            },
            "fault_restore": {
                asset_id: {
                    "availability": availability.value,
                    "effectiveness": effectiveness,
                }
                for asset_id, (availability, effectiveness) in self._fault_restore.items()
            },
        }

    def restore_state(self, state: dict[str, Any] | None) -> None:
        self._faults.clear()
        self._fault_restore.clear()
        if not state:
            return
        for asset_id, saved in state.get("assets", {}).items():
            if asset_id not in self.assets:
                continue
            self.set_availability(asset_id, AvailabilityState(saved["availability"]))
            self.set_owner(asset_id, CommandOwner(saved["owner"]))
            self.set_effectiveness(asset_id, float(saved.get("effectiveness", 1.0)))
            self.assets[asset_id].feedback_on = False
        for asset_id, saved in state.get("fault_restore", {}).items():
            if asset_id not in self.assets:
                continue
            self._fault_restore[asset_id] = (
                AvailabilityState(saved["availability"]),
                float(saved["effectiveness"]),
            )
        for asset_id, saved in state.get("faults", {}).items():
            if asset_id not in self.assets:
                continue
            mode = str(saved["mode"])
            value = saved.get("value")
            self._faults[asset_id] = ActuatorFault(mode, value)
            if mode == "failed_off":
                self.assets[asset_id].availability = AvailabilityState.FAILED
                self.assets[asset_id].effectiveness = 0.0
                self.assets[asset_id].feedback_on = False
