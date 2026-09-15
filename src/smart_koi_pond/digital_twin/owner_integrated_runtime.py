from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from smart_koi_pond.digital_twin.water_quality_runtime import (
    WaterQualityRegulatingProductionRuntime,
)
from smart_koi_pond.domain.enums import EventType, OperatingMode


@dataclass(slots=True, frozen=True)
class BackwashRestorePolicy:
    """Explicit governed policy for one integrated backwash + water-restore workflow."""

    policy_id: str
    revision: str
    source_reference: str
    backwash_duration_seconds: float
    minimum_safe_water_level_pct: float
    restore_tolerance_pct: float = 0.5

    def __post_init__(self) -> None:
        if not self.policy_id or not self.revision or not self.source_reference:
            raise ValueError("policy_id, revision and source_reference are required")
        if self.backwash_duration_seconds <= 0:
            raise ValueError("backwash_duration_seconds must be positive")
        if not 0.0 <= self.minimum_safe_water_level_pct < 100.0:
            raise ValueError("minimum_safe_water_level_pct must be in [0, 100)")
        if not 0.0 < self.restore_tolerance_pct <= 5.0:
            raise ValueError("restore_tolerance_pct must be >0 and <=5")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackwashRestorePolicy:
        return cls(
            policy_id=str(data["policy_id"]),
            revision=str(data["revision"]),
            source_reference=str(data["source_reference"]),
            backwash_duration_seconds=float(data["backwash_duration_seconds"]),
            minimum_safe_water_level_pct=float(data["minimum_safe_water_level_pct"]),
            restore_tolerance_pct=float(data.get("restore_tolerance_pct", 0.5)),
        )


class OwnerIntegratedProductionRuntime(WaterQualityRegulatingProductionRuntime):
    """Canonical runtime extension for owner operation and filter-clean restoration.

    This remains inside the production runtime. The browser never sequences actuators.
    It only requests this governed workflow and projects the canonical state.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.backwash_restore_policy: BackwashRestorePolicy | None = None
        self._owner_backwash_active: dict[str, Any] | None = None
        self._owner_backwash_last: dict[str, Any] | None = None

    def configure_backwash_restore_policy(
        self,
        policy: BackwashRestorePolicy,
        *,
        actor: str = "engineering",
    ) -> None:
        before = (
            self.backwash_restore_policy.to_dict()
            if self.backwash_restore_policy is not None
            else {"configured": False}
        )

        def apply() -> None:
            self.backwash_restore_policy = policy

        self._apply_governed_configuration(
            scope="BACKWASH_RESTORE_POLICY",
            actor=actor,
            reason="BACKWASH_RESTORE_POLICY_CHANGE",
            before=before,
            after=policy.to_dict(),
            preflight=lambda: (),
            apply=apply,
        )
        self.events.append(
            self.clock.current,
            EventType.CONFIGURATION,
            "BACKWASH_RESTORE_POLICY_CONFIGURED",
            {"actor": actor, **policy.to_dict(), "hidden_default_values": False},
        )

    def _test_guidance(self) -> dict[str, Any]:
        p = self.policy
        return {
            "basis": "ACTIVE_CANONICAL_SIMULATION_POLICY",
            "production_setpoint_claimed": False,
            "presets": {
                "nitrite_high": {
                    "label": "Nitrit Tinggi",
                    "parameter": "nitrite",
                    "unit": "mg/L",
                    "test_value": p.nitrite_watch_above,
                    "watch_boundary": p.nitrite_watch_above,
                    "emergency_boundary": p.nitrite_emergency_above,
                },
                "nitrite_emergency": {
                    "label": "Nitrit Darurat",
                    "parameter": "nitrite",
                    "unit": "mg/L",
                    "test_value": p.nitrite_emergency_above,
                    "watch_boundary": p.nitrite_watch_above,
                    "emergency_boundary": p.nitrite_emergency_above,
                },
                "nitrate_high": {
                    "label": "Nitrat Tinggi",
                    "parameter": "nitrate",
                    "unit": "mg/L",
                    "test_value": p.nitrate_watch_above,
                    "watch_boundary": p.nitrate_watch_above,
                    "emergency_boundary": None,
                },
                "do_low": {
                    "label": "DO Rendah",
                    "parameter": "do",
                    "unit": "mg/L",
                    "test_value": p.do_watch_below,
                    "watch_boundary": p.do_watch_below,
                    "emergency_boundary": p.do_emergency_below,
                },
                "do_emergency": {
                    "label": "DO Darurat",
                    "parameter": "do",
                    "unit": "mg/L",
                    "test_value": p.do_emergency_below,
                    "watch_boundary": p.do_watch_below,
                    "emergency_boundary": p.do_emergency_below,
                },
                "ph_high": {
                    "label": "pH Tinggi",
                    "parameter": "ph",
                    "unit": "",
                    "test_value": p.ph_watch_above,
                    "watch_boundary": p.ph_watch_above,
                    "emergency_boundary": p.ph_emergency_above,
                },
                "ph_low": {
                    "label": "pH Rendah",
                    "parameter": "ph",
                    "unit": "",
                    "test_value": p.ph_watch_below,
                    "watch_boundary": p.ph_watch_below,
                    "emergency_boundary": p.ph_emergency_below,
                },
                "tan_high": {
                    "label": "TAN Tinggi",
                    "parameter": "tan",
                    "unit": "mg/L",
                    "test_value": p.tan_watch_above,
                    "watch_boundary": p.tan_watch_above,
                    "emergency_boundary": p.tan_emergency_above,
                },
            },
        }

    def _owner_advisory(self, snapshot: Any) -> list[str]:
        advice: list[str] = []
        hydraulic = snapshot.hydraulics or {}
        if hydraulic.get("configured"):
            if hydraulic.get("active_flow_status") == "FLOW_BELOW_CALCULATED_REQUIREMENT":
                advice.append("Sirkulasi aktual belum memenuhi kebutuhan kolam. Periksa hambatan filter/pipa dan kapasitas pompa.")
            if hydraulic.get("primary_capacity_status") == "DECLARED_CAPACITY_BELOW_CALCULATED_REQUIREMENT":
                advice.append("Kapasitas pompa utama yang dideklarasikan berada di bawah kebutuhan sirkulasi terhitung.")
        reasons = set(snapshot.classification.reasons)
        if "DO_LOW" in reasons or "DO_EMERGENCY" in reasons:
            advice.append("Kapasitas aerasi belum dapat dinilai hanya dari DO. Gunakan data kapasitas aerator/datasheet dan respons DO sebelum menyimpulkan perlu memperbesar aerator.")
        filtration = hydraulic.get("mechanical_filtration") or {}
        if filtration.get("configured") and float(filtration.get("loading_fraction") or 0.0) >= 1.0:
            advice.append("Filter mekanis mencapai atau melewati kapasitas yang dikonfigurasi; lakukan backwash sesuai policy yang disahkan.")
        source = (hydraulic.get("water_exchange") or {}).get("source_water") or {}
        if not source.get("pond_use_qualified", False):
            advice.append("Air sumber belum memenuhi syarat untuk pengisian otomatis.")
        if not advice and snapshot.classification.state == "NORMAL":
            advice.append("Tidak ada tindakan tambahan yang dibutuhkan dari bukti canonical saat ini.")
        return advice

    def owner_operation_snapshot(self, snapshot: Any | None = None) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "language": "id-ID",
            "automatic_operation_primary": True,
            "manual_controls_secondary": True,
            "test_guidance": self._test_guidance(),
            "backwash_restore_policy": (
                {"configured": True, **self.backwash_restore_policy.to_dict()}
                if self.backwash_restore_policy is not None
                else {"configured": False, "status": "INPUT_REQUIRED"}
            ),
            "backwash_restore_active": deepcopy(self._owner_backwash_active),
            "backwash_restore_last": deepcopy(self._owner_backwash_last),
            "owner_advisory": self._owner_advisory(snapshot) if snapshot is not None else [],
        }

    def start_integrated_backwash_restore(self, reason: str) -> None:
        if self.backwash_restore_policy is None:
            raise RuntimeError("BACKWASH_RESTORE_POLICY_INPUT_REQUIRED")
        if self.operating_mode != OperatingMode.NORMAL_AUTO:
            raise RuntimeError(f"operating mode already active: {self.operating_mode}")
        self._require_structural_capability("automation.filter_clean")
        self._require_structural_capability("automation.water_change")
        self._require_source_water_qualified("BACKWASH_RESTORE")
        if self.model.hydraulics is None:
            raise RuntimeError("POND_HYDRAULIC_PROFILE_INPUT_REQUIRED")
        filtration = getattr(self.model, "filtration", None)
        if filtration is None:
            raise RuntimeError("MECHANICAL_FILTER_PROFILE_INPUT_REQUIRED")
        discharge_flow = filtration.profile.backwash_discharge_flow_l_min
        top_up_flow = self.model.hydraulics.profile.top_up_flow_l_min
        if discharge_flow is None or discharge_flow <= 0:
            raise RuntimeError("BACKWASH_DISCHARGE_FLOW_INPUT_REQUIRED")
        if top_up_flow is None or top_up_flow <= 0:
            raise RuntimeError("TOP_UP_FLOW_INPUT_REQUIRED")

        policy = self.backwash_restore_policy
        starting_level = float(self.model.state.water_level_pct)
        design_volume = float(self.model.hydraulics.profile.effective_volume_l)
        starting_volume = design_volume * starting_level / 100.0
        projected_discharge = min(
            starting_volume,
            float(discharge_flow) * policy.backwash_duration_seconds / 60.0,
        )
        projected_level = max(0.0, (starting_volume - projected_discharge) / design_volume * 100.0)
        if projected_level < policy.minimum_safe_water_level_pct:
            raise RuntimeError(
                "BACKWASH_PROJECTED_LEVEL_BELOW_CONFIGURED_SAFE_MINIMUM:"
                f"{projected_level:.2f}%<{policy.minimum_safe_water_level_pct:.2f}%"
            )

        chemistry_fields = (
            "ph",
            "temperature_c",
            "dissolved_oxygen_mg_l",
            "total_ammonia_nitrogen_mg_l",
            "nitrite_mg_l",
            "nitrate_mg_l",
            "alkalinity_mg_l_as_caco3",
        )
        self._owner_backwash_active = {
            "stage": "PREFLIGHT_OK",
            "reason": reason,
            "requested_at": self.clock.current.isoformat(),
            "effective_backwash_started_at": None,
            "starting_level_pct": starting_level,
            "projected_post_backwash_level_pct": projected_level,
            "starting_captured_solids_g": float(filtration.captured_solids_g),
            "starting_chemistry": {name: getattr(self.model.state, name) for name in chemistry_fields},
            "policy_id": policy.policy_id,
            "policy_revision": policy.revision,
        }
        self.events.append(
            self.clock.current,
            EventType.RECOVERY,
            "INTEGRATED_BACKWASH_RESTORE_PREFLIGHT_PASS",
            {
                "starting_level_pct": starting_level,
                "projected_post_backwash_level_pct": projected_level,
                "backwash_duration_seconds": policy.backwash_duration_seconds,
                "source_water_qualified": True,
                "automatic_chemical_dosing_authorized": False,
            },
        )
        super().start_filter_clean([], reason)
        self._owner_backwash_active["stage"] = "BACKWASHING"

    def _finish_owner_backwash(self, snapshot: Any, outcome: str, detail: str) -> None:
        session = deepcopy(self._owner_backwash_active or {})
        filtration = (snapshot.hydraulics or {}).get("mechanical_filtration") or {}
        exchange = (snapshot.hydraulics or {}).get("water_exchange") or {}
        session.update(
            {
                "stage": "SELESAI" if outcome == "VERIFIED_SUCCESS" else "DITAHAN",
                "outcome": outcome,
                "detail": detail,
                "finished_at": snapshot.timestamp.isoformat(),
                "final_level_pct": snapshot.pond_truth.water_level_pct,
                "final_captured_solids_g": filtration.get("captured_solids_g"),
                "last_exchange": deepcopy(exchange.get("last_exchange")),
                "final_chemistry": {
                    "ph": snapshot.pond_truth.ph,
                    "temperature_c": snapshot.pond_truth.temperature_c,
                    "dissolved_oxygen_mg_l": snapshot.pond_truth.dissolved_oxygen_mg_l,
                    "total_ammonia_nitrogen_mg_l": snapshot.pond_truth.total_ammonia_nitrogen_mg_l,
                    "nitrite_mg_l": snapshot.pond_truth.nitrite_mg_l,
                    "nitrate_mg_l": snapshot.pond_truth.nitrate_mg_l,
                    "alkalinity_mg_l_as_caco3": snapshot.pond_truth.alkalinity_mg_l_as_caco3,
                },
            }
        )
        self._owner_backwash_last = session
        self._owner_backwash_active = None
        self.events.append(
            snapshot.timestamp,
            EventType.RECOVERY,
            "INTEGRATED_BACKWASH_RESTORE_FINISHED",
            {"outcome": outcome, "detail": detail, "final_level_pct": snapshot.pond_truth.water_level_pct},
        )

    def _advance_owner_backwash(self, snapshot: Any) -> Any:
        session = self._owner_backwash_active
        policy = self.backwash_restore_policy
        if session is None or policy is None:
            return snapshot

        if session["stage"] == "BACKWASHING":
            command = snapshot.commands.get("backwash_valve") if snapshot.commands else None
            if command is not None and command.requested_on and not command.accepted:
                self.request_return_to_auto()
                snapshot = super().tick(0.0)
                self._finish_owner_backwash(
                    snapshot,
                    "HOLD",
                    f"Backwash tidak dieksekusi: {command.reason}",
                )
                return snapshot
            valve = snapshot.assets.get("backwash_valve")
            if valve is not None and valve.feedback_on:
                if session["effective_backwash_started_at"] is None:
                    session["effective_backwash_started_at"] = snapshot.timestamp.isoformat()
                    self.events.append(snapshot.timestamp, EventType.RECOVERY, "INTEGRATED_BACKWASH_EFFECT_CONFIRMED", {})
                else:
                    started = datetime.fromisoformat(session["effective_backwash_started_at"])
                    if (snapshot.timestamp - started).total_seconds() >= policy.backwash_duration_seconds:
                        self.request_return_to_auto()
                        snapshot = super().tick(0.0)
                        session["stage"] = "STOPPING_BACKWASH"

        if session["stage"] == "STOPPING_BACKWASH" and snapshot.operating_mode == OperatingMode.NORMAL_AUTO:
            current_level = float(snapshot.pond_truth.water_level_pct)
            session["post_backwash_level_pct"] = current_level
            if current_level < session["starting_level_pct"] - policy.restore_tolerance_pct:
                super().start_water_change(
                    "POST_BACKWASH_WATER_RESTORE",
                    target_drain_level_pct=current_level,
                    target_refill_level_pct=float(session["starting_level_pct"]),
                )
                snapshot = super().tick(0.0)
                session["stage"] = "REFILLING"
                self.events.append(
                    snapshot.timestamp,
                    EventType.RECOVERY,
                    "INTEGRATED_BACKWASH_REFILL_STARTED",
                    {"from_level_pct": current_level, "target_level_pct": session["starting_level_pct"]},
                )
            else:
                self._finish_owner_backwash(snapshot, "VERIFIED_SUCCESS", "Backwash selesai; kehilangan air berada dalam toleransi restore.")

        if session.get("stage") == "REFILLING":
            top_up = snapshot.commands.get("top_up_valve") if snapshot.commands else None
            if top_up is not None and top_up.requested_on and not top_up.accepted:
                self.request_return_to_auto()
                snapshot = super().tick(0.0)
                self._finish_owner_backwash(snapshot, "HOLD", f"Pengisian dihentikan: {top_up.reason}")
            elif snapshot.operating_mode == OperatingMode.NORMAL_AUTO:
                final_level = float(snapshot.pond_truth.water_level_pct)
                if abs(final_level - float(session["starting_level_pct"])) <= policy.restore_tolerance_pct:
                    self._finish_owner_backwash(snapshot, "VERIFIED_SUCCESS", "Backwash, pengisian ulang, dan pemulihan level terverifikasi.")
                else:
                    self._finish_owner_backwash(snapshot, "HOLD", "Level air belum kembali ke target dalam toleransi yang dikonfigurasi.")
        return snapshot

    def _attach_owner_operation(self, snapshot: Any) -> Any:
        snapshot.water_recovery = dict(snapshot.water_recovery)
        snapshot.water_recovery["owner_operation"] = self.owner_operation_snapshot(snapshot)
        return snapshot

    def tick(self, seconds: float):
        snapshot = super().tick(seconds)
        snapshot = self._advance_owner_backwash(snapshot)
        return self._attach_owner_operation(snapshot)

    def publish(self, snapshot, *, after_sequence: int = 0):
        self._attach_owner_operation(snapshot)
        publication = super().publish(snapshot, after_sequence=after_sequence)
        publication["owner_integrated_operation_schema_version"] = 1
        return publication

    def capture_checkpoint(self):
        checkpoint = super().capture_checkpoint()
        checkpoint["backwash_restore_policy"] = (
            self.backwash_restore_policy.to_dict() if self.backwash_restore_policy else None
        )
        checkpoint["owner_backwash_active"] = deepcopy(self._owner_backwash_active)
        checkpoint["owner_backwash_last"] = deepcopy(self._owner_backwash_last)
        return checkpoint

    def restore_checkpoint(self, checkpoint) -> None:
        super().restore_checkpoint(checkpoint)
        policy = checkpoint.get("backwash_restore_policy")
        self.backwash_restore_policy = BackwashRestorePolicy.from_dict(policy) if policy else None
        self._owner_backwash_active = deepcopy(checkpoint.get("owner_backwash_active"))
        self._owner_backwash_last = deepcopy(checkpoint.get("owner_backwash_last"))
