from __future__ import annotations

from typing import Any

from smart_koi_pond.dashboard.koi_stock_service import KoiStockRuntimeApplicationService
from smart_koi_pond.digital_twin.owner_integrated_runtime import BackwashRestorePolicy
from smart_koi_pond.domain.enums import EventType


class OwnerIntegratedRuntimeApplicationService(KoiStockRuntimeApplicationService):
    """Thin command boundary for owner-integrated runtime operations."""

    def _require_operator(self, action: str, role: str) -> None:
        if role in {"operator", "engineering"}:
            return
        self.runtime.events.append(
            self.runtime.clock.current,
            EventType.SCENARIO,
            "OWNER_OPERATION_COMMAND_REJECTED",
            {"action": action, "role": role, "reason": "OPERATOR_ROLE_REQUIRED"},
        )
        raise PermissionError(f"role {role} is not authorized for {action}")

    def _require_engineering_owner_action(self, action: str, role: str) -> None:
        if role == "engineering":
            return
        self.runtime.events.append(
            self.runtime.clock.current,
            EventType.CONFIGURATION,
            "OWNER_OPERATION_CONFIGURATION_REJECTED",
            {"action": action, "role": role, "reason": "ENGINEERING_ROLE_REQUIRED"},
        )
        raise PermissionError(f"role {role} is not authorized for {action}")

    def command(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        *,
        role: str = "viewer",
    ):
        if action not in {
            "configure_backwash_restore_policy",
            "start_integrated_backwash_restore",
        }:
            return super().command(action, payload, role=role)

        data = payload or {}
        with self._lock:
            if action == "configure_backwash_restore_policy":
                self._require_engineering_owner_action(action, role)
                configure = getattr(self.runtime, "configure_backwash_restore_policy", None)
                if configure is None:
                    raise RuntimeError("runtime does not support backwash restore policy")
                configure(
                    BackwashRestorePolicy.from_dict(data["policy"]),
                    actor=str(data.get("actor", role)),
                )
            else:
                self._require_operator(action, role)
                start = getattr(self.runtime, "start_integrated_backwash_restore", None)
                if start is None:
                    raise RuntimeError("runtime does not support integrated backwash restore")
                start(str(data.get("reason", "OWNER_BACKWASH_RESTORE")))

            self._last_snapshot = self._tick_and_evaluate(0.0)
            return self._last_snapshot

    def publication(self, *, after_sequence: int = 0):
        publication = super().publication(after_sequence=after_sequence)
        publication["owner_integrated_operation_schema_version"] = 1
        return publication
