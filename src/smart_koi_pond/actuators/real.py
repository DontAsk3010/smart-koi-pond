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


@dataclass(slots=True)
class RealAsset:
    asset_id: str
    feedback_on: bool = False
    availability: AvailabilityState = AvailabilityState.UNKNOWN
    owner: CommandOwner = CommandOwner.AUTO
    effectiveness: float = 1.0


class InhibitedRealActuatorBank:
    """Real-actuator observation boundary with hard command inhibition.

    This adapter is suitable for SHADOW/read-only integration. It can ingest
    physical feedback but intentionally has no path that energizes hardware.
    A later separately governed live adapter must satisfy its own acceptance gate.
    """

    ADAPTER_ID = "inhibited-real-actuator-bank"
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

    def __init__(self, *, device_bindings: dict[str, str] | None = None) -> None:
        self.assets = {asset_id: RealAsset(asset_id) for asset_id in self.DEFAULT_ASSETS}
        self._device_ids: dict[str, str] = {}
        self._feedback_timestamps: dict[str, datetime] = {}
        for asset_id, device_id in (device_bindings or {}).items():
            self.bind_device(asset_id, device_id)

    @property
    def adapter_id(self) -> str:
        return self.ADAPTER_ID

    def source_for(self, asset_id: str) -> ActuatorSourceState:
        if asset_id not in self.assets:
            raise KeyError(asset_id)
        return ActuatorSourceState.REAL_ACTUATOR

    def authority_for(self, asset_id: str) -> ControlAuthorityState:
        if asset_id not in self.assets:
            raise KeyError(asset_id)
        return ControlAuthorityState.COMMAND_INHIBITED

    def device_id_for(self, asset_id: str) -> str | None:
        if asset_id not in self.assets:
            raise KeyError(asset_id)
        return self._device_ids.get(asset_id)

    def bind_device(self, asset_id: str, device_id: str) -> None:
        if asset_id not in self.assets:
            raise KeyError(asset_id)
        device_id = device_id.strip()
        if not device_id:
            raise ValueError("device_id must be non-empty")
        existing = self._device_ids.get(asset_id)
        if existing is not None and existing != device_id:
            raise RuntimeError(
                "actuator identity already bound: "
                f"{asset_id} -> {existing}; start a new reconciled binding"
            )
        self._device_ids[asset_id] = device_id

    def ingest_feedback(
        self,
        asset_id: str,
        *,
        device_id: str,
        feedback_on: bool,
        timestamp: datetime,
        availability: AvailabilityState = AvailabilityState.AVAILABLE,
    ) -> None:
        if asset_id not in self.assets:
            raise KeyError(asset_id)
        expected_device = self._device_ids.get(asset_id)
        if expected_device is None:
            raise RuntimeError(f"actuator has no governed device binding: {asset_id}")
        if device_id != expected_device:
            raise RuntimeError(
                f"actuator identity mismatch for {asset_id}: "
                f"expected {expected_device}, got {device_id}"
            )
        previous_timestamp = self._feedback_timestamps.get(asset_id)
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise ValueError(f"non-monotonic actuator feedback rejected for {asset_id}")
        asset = self.assets[asset_id]
        asset.availability = availability
        asset.feedback_on = (
            bool(feedback_on)
            if availability == AvailabilityState.AVAILABLE
            else False
        )
        self._feedback_timestamps[asset_id] = timestamp

    def set_availability(self, asset_id: str, availability: AvailabilityState) -> None:
        asset = self.assets[asset_id]
        if (
            asset_id not in self._device_ids
            and availability in {AvailabilityState.AVAILABLE, AvailabilityState.STANDBY}
        ):
            raise RuntimeError(f"cannot mark unbound real actuator available: {asset_id}")
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
        return {asset_id: 0.0 for asset_id in self.assets}

    def execute(self, command: ArbitratedCommand, timestamp: datetime) -> DeviceFeedback:
        if command.accepted or command.final_on:
            raise RuntimeError(
                "command reached command-inhibited real actuator adapter; "
                "runtime authority gate failed"
            )
        asset = self.assets[command.asset_id]
        return DeviceFeedback(
            asset_id=asset.asset_id,
            commanded_on=False,
            feedback_on=asset.feedback_on,
            availability=asset.availability,
            timestamp=timestamp,
            effectiveness=asset.effectiveness,
            source_state=ActuatorSourceState.REAL_ACTUATOR,
            authority_state=ControlAuthorityState.COMMAND_INHIBITED,
            adapter_id=self.ADAPTER_ID,
            device_id=self._device_ids.get(command.asset_id),
        )

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            "device_bindings": dict(self._device_ids),
            "assets": {
                asset_id: {
                    "owner": asset.owner.value,
                    "effectiveness": asset.effectiveness,
                }
                for asset_id, asset in self.assets.items()
            },
            "physical_feedback_persisted": False,
        }

    def restore_state(self, state: dict[str, Any] | None) -> None:
        self._device_ids.clear()
        self._feedback_timestamps.clear()
        for asset in self.assets.values():
            asset.feedback_on = False
            asset.availability = AvailabilityState.UNKNOWN
            asset.owner = CommandOwner.AUTO
            asset.effectiveness = 1.0
        if not state:
            return
        for asset_id, device_id in state.get("device_bindings", {}).items():
            self.bind_device(asset_id, str(device_id))
        for asset_id, saved in state.get("assets", {}).items():
            if asset_id not in self.assets:
                continue
            self.set_owner(asset_id, CommandOwner(saved["owner"]))
            self.set_effectiveness(asset_id, float(saved.get("effectiveness", 1.0)))
