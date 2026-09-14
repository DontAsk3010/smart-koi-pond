from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ConfigurationTransactionState(StrEnum):
    PRECHECK = "PRECHECK"
    REJECTED = "REJECTED"
    STAGED = "STAGED"
    ACTIVATING = "ACTIVATING"
    VERIFYING = "VERIFYING"
    ACTIVE = "ACTIVE"
    LAST_GOOD = "LAST_GOOD"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    HOLD = "HOLD"


class RecoveryState(StrEnum):
    DETECTED = "DETECTED"
    CLASSIFIED = "CLASSIFIED"
    CONTAINED = "CONTAINED"
    SAFE_OR_DEGRADED = "SAFE_OR_DEGRADED"
    ATTEMPTING = "ATTEMPTING"
    RECONCILING = "RECONCILING"
    VERIFYING = "VERIFYING"
    RECOVERED = "RECOVERED"
    LOCKED_OUT = "LOCKED_OUT"
    ESCALATED = "ESCALATED"


@dataclass(slots=True)
class ConfigurationTransaction:
    transaction_id: str
    scope: str
    parent_version: str
    candidate_version: str
    actor: str
    reason: str
    created_at: datetime
    before: dict[str, Any]
    after: dict[str, Any]
    state: ConfigurationTransactionState = ConfigurationTransactionState.PRECHECK
    schema_version: int = 1
    errors: tuple[str, ...] = ()
    verification_result: str | None = None
    rollback_result: str | None = None
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def transition(
        self,
        state: ConfigurationTransactionState,
        now: datetime,
        *,
        reason: str | None = None,
    ) -> None:
        self.state = state
        self.transitions.append(
            {
                "state": state.value,
                "timestamp": now.isoformat(),
                "reason": reason,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        payload["state"] = self.state.value
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConfigurationTransaction:
        transaction = cls(
            transaction_id=str(data["transaction_id"]),
            scope=str(data["scope"]),
            parent_version=str(data["parent_version"]),
            candidate_version=str(data["candidate_version"]),
            actor=str(data["actor"]),
            reason=str(data["reason"]),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            before=dict(data.get("before", {})),
            after=dict(data.get("after", {})),
            state=ConfigurationTransactionState(data["state"]),
            schema_version=int(data.get("schema_version", 1)),
            errors=tuple(str(item) for item in data.get("errors", ())),
            verification_result=data.get("verification_result"),
            rollback_result=data.get("rollback_result"),
        )
        transaction.transitions = [dict(item) for item in data.get("transitions", [])]
        return transaction


@dataclass(slots=True)
class SoftwareUpdateRecord:
    update_id: str
    current_software_version: str
    candidate_software_version: str
    configuration_version: str
    actor: str
    reason: str
    created_at: datetime
    state: ConfigurationTransactionState
    compatibility_errors: tuple[str, ...] = ()
    verification_result: str | None = None
    rollback_result: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        payload["state"] = self.state.value
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SoftwareUpdateRecord:
        return cls(
            update_id=str(data["update_id"]),
            current_software_version=str(data["current_software_version"]),
            candidate_software_version=str(data["candidate_software_version"]),
            configuration_version=str(data["configuration_version"]),
            actor=str(data["actor"]),
            reason=str(data["reason"]),
            created_at=datetime.fromisoformat(str(data["created_at"])),
            state=ConfigurationTransactionState(data["state"]),
            compatibility_errors=tuple(
                str(item) for item in data.get("compatibility_errors", ())
            ),
            verification_result=data.get("verification_result"),
            rollback_result=data.get("rollback_result"),
        )


class GovernedChangeController:
    """Versioned atomic configuration and staged software-update coordinator.

    This class does not deploy binaries itself. Software activation requires an injected
    deployment executor and rollback executor so the runtime cannot pretend that a staged
    artifact was installed merely because its metadata exists.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        *,
        initial_configuration_version: str,
        initial_software_version: str,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.active_configuration_version = str(initial_configuration_version)
        self.last_good_configuration_version = str(initial_configuration_version)
        self.active_software_version = str(initial_software_version)
        self.last_good_software_version = str(initial_software_version)
        self.last_transaction: ConfigurationTransaction | None = None
        self.software_update: SoftwareUpdateRecord | None = None
        self._counter = 0
        self._event_sink = event_sink

    def _emit(self, code: str, payload: dict[str, Any]) -> None:
        if self._event_sink is not None:
            self._event_sink(code, payload)

    def _next_version(self) -> str:
        self._counter += 1
        return f"cfg-{self._counter:04d}"

    def apply_configuration(
        self,
        *,
        scope: str,
        actor: str,
        reason: str,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        now: datetime,
        preflight: Callable[[], tuple[str, ...] | list[str] | None],
        apply: Callable[[], None],
        rollback: Callable[[], None],
        verify: Callable[[], bool] | None = None,
    ) -> ConfigurationTransaction:
        tx = ConfigurationTransaction(
            transaction_id=str(uuid4()),
            scope=str(scope),
            parent_version=self.active_configuration_version,
            candidate_version=self._next_version(),
            actor=str(actor),
            reason=str(reason),
            created_at=now,
            before=dict(before),
            after=dict(after),
        )
        self.last_transaction = tx
        tx.transition(ConfigurationTransactionState.PRECHECK, now)
        self._emit("CONFIG_TRANSACTION_PRECHECK", tx.to_dict())
        try:
            errors = tuple(str(item) for item in (preflight() or ()))
        except Exception as exc:
            errors = (f"PREFLIGHT_EXCEPTION:{type(exc).__name__}:{exc}",)
        if errors:
            tx.errors = errors
            tx.transition(ConfigurationTransactionState.REJECTED, now, reason="PREFLIGHT_FAILED")
            self._emit("CONFIG_TRANSACTION_REJECTED", tx.to_dict())
            raise ValueError("configuration preflight failed: " + "; ".join(errors))

        tx.transition(ConfigurationTransactionState.STAGED, now)
        self._emit("CONFIG_TRANSACTION_STAGED", tx.to_dict())
        tx.transition(ConfigurationTransactionState.ACTIVATING, now)
        self._emit("CONFIG_TRANSACTION_ACTIVATING", tx.to_dict())
        try:
            apply()
            tx.transition(ConfigurationTransactionState.VERIFYING, now)
            self._emit("CONFIG_TRANSACTION_VERIFYING", tx.to_dict())
            verified = True if verify is None else bool(verify())
            tx.verification_result = "PASS" if verified else "FAIL"
            if not verified:
                raise RuntimeError("post-activation verification failed")
        except Exception as activation_error:
            tx.errors = (*tx.errors, f"ACTIVATION_OR_VERIFY_FAILED:{activation_error}")
            tx.transition(ConfigurationTransactionState.ROLLING_BACK, now)
            self._emit("CONFIG_TRANSACTION_ROLLING_BACK", tx.to_dict())
            try:
                rollback()
                tx.rollback_result = "PASS"
                tx.transition(
                    ConfigurationTransactionState.ROLLED_BACK,
                    now,
                    reason="LAST_GOOD_RESTORED",
                )
                self._emit("CONFIG_TRANSACTION_ROLLED_BACK", tx.to_dict())
            except Exception as rollback_error:
                tx.rollback_result = f"FAIL:{type(rollback_error).__name__}:{rollback_error}"
                tx.errors = (*tx.errors, f"ROLLBACK_FAILED:{rollback_error}")
                tx.transition(
                    ConfigurationTransactionState.HOLD,
                    now,
                    reason="ROLLBACK_NOT_PROVEN_SAFE",
                )
                self._emit("CONFIG_TRANSACTION_HOLD", tx.to_dict())
            raise

        self.active_configuration_version = tx.candidate_version
        tx.transition(ConfigurationTransactionState.ACTIVE, now)
        self._emit("CONFIG_TRANSACTION_ACTIVE", tx.to_dict())
        self.last_good_configuration_version = tx.candidate_version
        tx.transition(ConfigurationTransactionState.LAST_GOOD, now)
        self._emit("CONFIG_TRANSACTION_LAST_GOOD", tx.to_dict())
        return tx

    def stage_software_update(
        self,
        candidate_software_version: str,
        *,
        actor: str,
        reason: str,
        now: datetime,
        compatibility_errors: tuple[str, ...] | list[str] = (),
    ) -> SoftwareUpdateRecord:
        errors = tuple(str(item) for item in compatibility_errors)
        record = SoftwareUpdateRecord(
            update_id=str(uuid4()),
            current_software_version=self.active_software_version,
            candidate_software_version=str(candidate_software_version),
            configuration_version=self.active_configuration_version,
            actor=str(actor),
            reason=str(reason),
            created_at=now,
            state=(
                ConfigurationTransactionState.REJECTED
                if errors
                else ConfigurationTransactionState.STAGED
            ),
            compatibility_errors=errors,
        )
        self.software_update = record
        self._emit(
            "SOFTWARE_UPDATE_REJECTED" if errors else "SOFTWARE_UPDATE_STAGED",
            record.to_dict(),
        )
        return record

    def activate_staged_software_update(
        self,
        *,
        executor: Callable[[str], None],
        rollback_executor: Callable[[str], None],
        verify: Callable[[], bool],
        now: datetime,
    ) -> SoftwareUpdateRecord:
        record = self.software_update
        if record is None or record.state != ConfigurationTransactionState.STAGED:
            raise RuntimeError("no compatible STAGED software update is available")
        last_good = self.last_good_software_version
        record.state = ConfigurationTransactionState.ACTIVATING
        self._emit("SOFTWARE_UPDATE_ACTIVATING", record.to_dict())
        try:
            executor(record.candidate_software_version)
            record.state = ConfigurationTransactionState.VERIFYING
            self._emit("SOFTWARE_UPDATE_VERIFYING", record.to_dict())
            verified = bool(verify())
            record.verification_result = "PASS" if verified else "FAIL"
            if not verified:
                raise RuntimeError("software post-activation verification failed")
        except Exception:
            record.state = ConfigurationTransactionState.ROLLING_BACK
            self._emit("SOFTWARE_UPDATE_ROLLING_BACK", record.to_dict())
            try:
                rollback_executor(last_good)
                record.rollback_result = "PASS"
                record.state = ConfigurationTransactionState.ROLLED_BACK
                self.active_software_version = last_good
                self._emit("SOFTWARE_UPDATE_ROLLED_BACK", record.to_dict())
            except Exception as rollback_error:
                record.rollback_result = (
                    f"FAIL:{type(rollback_error).__name__}:{rollback_error}"
                )
                record.state = ConfigurationTransactionState.HOLD
                self._emit("SOFTWARE_UPDATE_HOLD", record.to_dict())
            raise

        self.active_software_version = record.candidate_software_version
        record.state = ConfigurationTransactionState.ACTIVE
        self._emit("SOFTWARE_UPDATE_ACTIVE", record.to_dict())
        self.last_good_software_version = record.candidate_software_version
        record.state = ConfigurationTransactionState.LAST_GOOD
        self._emit("SOFTWARE_UPDATE_LAST_GOOD", record.to_dict())
        return record

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "active_configuration_version": self.active_configuration_version,
            "last_good_configuration_version": self.last_good_configuration_version,
            "active_software_version": self.active_software_version,
            "last_good_software_version": self.last_good_software_version,
            "last_transaction": (
                self.last_transaction.to_dict() if self.last_transaction else None
            ),
            "software_update": self.software_update.to_dict() if self.software_update else None,
            "partial_configuration_active": False,
        }

    def checkpoint_state(self) -> dict[str, Any]:
        return {
            **self.snapshot(),
            "counter": self._counter,
        }

    def restore_state(self, state: Mapping[str, Any] | None) -> None:
        if not state:
            return
        self.active_configuration_version = str(
            state.get("active_configuration_version", self.active_configuration_version)
        )
        self.last_good_configuration_version = str(
            state.get("last_good_configuration_version", self.last_good_configuration_version)
        )
        self.active_software_version = str(
            state.get("active_software_version", self.active_software_version)
        )
        self.last_good_software_version = str(
            state.get("last_good_software_version", self.last_good_software_version)
        )
        self._counter = int(state.get("counter", self._counter))
        transaction = state.get("last_transaction")
        self.last_transaction = (
            ConfigurationTransaction.from_dict(transaction) if transaction else None
        )
        update = state.get("software_update")
        self.software_update = SoftwareUpdateRecord.from_dict(update) if update else None
        interrupted = {
            ConfigurationTransactionState.ACTIVATING,
            ConfigurationTransactionState.VERIFYING,
            ConfigurationTransactionState.ROLLING_BACK,
        }
        if self.last_transaction and self.last_transaction.state in interrupted:
            self.last_transaction.state = ConfigurationTransactionState.HOLD
            self.last_transaction.errors = (
                *self.last_transaction.errors,
                "RESTART_RECONCILIATION_REQUIRED",
            )
        if self.software_update and self.software_update.state in interrupted:
            self.software_update.state = ConfigurationTransactionState.HOLD
            self.software_update.verification_result = "RESTART_RECONCILIATION_REQUIRED"


@dataclass(slots=True, frozen=True)
class RecoveryPlan:
    plan_id: str
    revision: str
    trigger_code: str
    affected_assets: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    retry_limit: int
    cooldown_seconds: float
    verification_asset_id: str | None = None
    terminal_behavior: str = "LOCKED_OUT_ESCALATED"

    def __post_init__(self) -> None:
        if not self.plan_id or not self.revision or not self.trigger_code:
            raise ValueError("recovery plan identity, revision and trigger are required")
        if self.retry_limit <= 0:
            raise ValueError("retry_limit must be positive")
        if self.cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")


@dataclass(slots=True)
class RecoveryRecord:
    recovery_id: str
    plan_id: str
    plan_revision: str
    trigger_code: str
    reason: str
    detected_at: datetime
    state: RecoveryState = RecoveryState.DETECTED
    attempt_count: int = 0
    next_eligible_at: datetime | None = None
    current_action: str | None = None
    verification_id: str | None = None
    verification_result: str | None = None
    affected_assets: tuple[str, ...] = ()
    fallback_active: bool = False
    escalated: bool = False
    resolved_at: datetime | None = None
    transitions: list[dict[str, Any]] = field(default_factory=list)

    def transition(self, state: RecoveryState, now: datetime, *, reason: str | None = None) -> None:
        self.state = state
        self.transitions.append(
            {
                "state": state.value,
                "timestamp": now.isoformat(),
                "reason": reason,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["detected_at"] = self.detected_at.isoformat()
        payload["state"] = self.state.value
        payload["next_eligible_at"] = (
            self.next_eligible_at.isoformat() if self.next_eligible_at else None
        )
        payload["resolved_at"] = self.resolved_at.isoformat() if self.resolved_at else None
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RecoveryRecord:
        record = cls(
            recovery_id=str(data["recovery_id"]),
            plan_id=str(data["plan_id"]),
            plan_revision=str(data["plan_revision"]),
            trigger_code=str(data["trigger_code"]),
            reason=str(data["reason"]),
            detected_at=datetime.fromisoformat(str(data["detected_at"])),
            state=RecoveryState(data["state"]),
            attempt_count=int(data.get("attempt_count", 0)),
            next_eligible_at=(
                datetime.fromisoformat(str(data["next_eligible_at"]))
                if data.get("next_eligible_at")
                else None
            ),
            current_action=data.get("current_action"),
            verification_id=data.get("verification_id"),
            verification_result=data.get("verification_result"),
            affected_assets=tuple(str(item) for item in data.get("affected_assets", ())),
            fallback_active=bool(data.get("fallback_active", False)),
            escalated=bool(data.get("escalated", False)),
            resolved_at=(
                datetime.fromisoformat(str(data["resolved_at"]))
                if data.get("resolved_at")
                else None
            ),
        )
        record.transitions = [dict(item) for item in data.get("transitions", [])]
        return record


class RecoverySupervisor:
    SCHEMA_VERSION = 1
    _TERMINAL = {
        RecoveryState.RECOVERED,
        RecoveryState.LOCKED_OUT,
        RecoveryState.ESCALATED,
    }

    def __init__(
        self,
        *,
        event_sink: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.plans: dict[str, RecoveryPlan] = {}
        self.active: RecoveryRecord | None = None
        self.last_completed: RecoveryRecord | None = None
        self._event_sink = event_sink

    def _emit(self, code: str, payload: dict[str, Any]) -> None:
        if self._event_sink is not None:
            self._event_sink(code, payload)

    def register(self, plan: RecoveryPlan) -> None:
        self.plans[plan.plan_id] = plan

    def detect(self, plan_id: str, *, now: datetime, reason: str) -> RecoveryRecord:
        plan = self.plans[plan_id]
        if self.active is not None:
            return self.active
        record = RecoveryRecord(
            recovery_id=str(uuid4()),
            plan_id=plan.plan_id,
            plan_revision=plan.revision,
            trigger_code=plan.trigger_code,
            reason=str(reason),
            detected_at=now,
            affected_assets=plan.affected_assets,
        )
        record.transition(RecoveryState.DETECTED, now, reason=reason)
        record.transition(RecoveryState.CLASSIFIED, now, reason=plan.trigger_code)
        record.transition(RecoveryState.CONTAINED, now, reason="GOVERNED_CONTROL_PATH_ONLY")
        record.transition(RecoveryState.SAFE_OR_DEGRADED, now, reason="AWAITING_ELIGIBLE_ATTEMPT")
        self.active = record
        self._emit("RECOVERY_DETECTED", record.to_dict())
        return record

    def eligible(self, now: datetime) -> bool:
        record = self.active
        if record is None or record.state in self._TERMINAL:
            return False
        return record.next_eligible_at is None or now >= record.next_eligible_at

    def begin_attempt(self, *, now: datetime, action: str) -> RecoveryRecord:
        record = self.active
        if record is None:
            raise RuntimeError("no active recovery")
        plan = self.plans[record.plan_id]
        if action not in plan.allowed_actions:
            raise RuntimeError(f"recovery action is not allowed by plan: {action}")
        if not self.eligible(now):
            raise RuntimeError("recovery cooldown has not expired")
        if record.attempt_count >= plan.retry_limit:
            return self._terminal_lockout(now, "RETRY_LIMIT_EXHAUSTED")
        record.attempt_count += 1
        record.current_action = action
        record.verification_id = None
        record.verification_result = None
        record.next_eligible_at = None
        record.transition(RecoveryState.ATTEMPTING, now, reason=action)
        self._emit("RECOVERY_ATTEMPTING", record.to_dict())
        return record

    def mark_verifying(
        self,
        *,
        now: datetime,
        verification_id: str,
        fallback_active: bool,
    ) -> RecoveryRecord:
        record = self.active
        if record is None:
            raise RuntimeError("no active recovery")
        record.verification_id = str(verification_id)
        record.fallback_active = bool(fallback_active)
        record.transition(RecoveryState.RECONCILING, now, reason="COMMAND_PATH_ACCEPTED")
        record.transition(RecoveryState.VERIFYING, now, reason=verification_id)
        self._emit("RECOVERY_VERIFYING", record.to_dict())
        return record

    def fail_attempt(self, *, now: datetime, reason: str) -> RecoveryRecord:
        record = self.active
        if record is None:
            raise RuntimeError("no active recovery")
        plan = self.plans[record.plan_id]
        record.verification_result = str(reason)
        if record.attempt_count >= plan.retry_limit:
            return self._terminal_lockout(now, reason)
        record.next_eligible_at = now + timedelta(seconds=plan.cooldown_seconds)
        record.transition(RecoveryState.SAFE_OR_DEGRADED, now, reason=reason)
        self._emit("RECOVERY_ATTEMPT_FAILED", record.to_dict())
        return record

    def verification_result(
        self,
        *,
        now: datetime,
        verification_id: str,
        status: str,
    ) -> RecoveryRecord:
        record = self.active
        if record is None:
            raise RuntimeError("no active recovery")
        if record.verification_id != verification_id:
            return record
        record.verification_result = str(status)
        if status == "VERIFIED_SUCCESS":
            record.transition(RecoveryState.RECOVERED, now, reason=status)
            record.resolved_at = now
            self.last_completed = record
            self._emit("RECOVERY_VERIFIED", record.to_dict())
            return record
        return self.fail_attempt(now=now, reason=f"VERIFICATION_{status}")

    def _terminal_lockout(self, now: datetime, reason: str) -> RecoveryRecord:
        record = self.active
        if record is None:
            raise RuntimeError("no active recovery")
        record.escalated = True
        record.next_eligible_at = None
        record.transition(RecoveryState.LOCKED_OUT, now, reason=reason)
        self._emit("RECOVERY_LOCKED_OUT", record.to_dict())
        return record

    def clear_terminal(self, *, now: datetime, reason: str) -> None:
        record = self.active
        if record is None:
            return
        if record.state not in self._TERMINAL:
            raise RuntimeError("active recovery is not terminal")
        self.last_completed = record
        self._emit(
            "RECOVERY_TERMINAL_CLEARED",
            {**record.to_dict(), "clear_reason": str(reason)},
        )
        self.active = None

    def snapshot(self) -> dict[str, Any]:
        record = self.active
        plan = self.plans.get(record.plan_id) if record else None
        return {
            "schema_version": self.SCHEMA_VERSION,
            "active": record.to_dict() if record else None,
            "last_completed": self.last_completed.to_dict() if self.last_completed else None,
            "retry_limit": plan.retry_limit if plan else None,
            "cooldown_seconds": plan.cooldown_seconds if plan else None,
            "infinite_retry_allowed": False,
            "authority_escalation_allowed": False,
            "high_risk_chemical_dosing_allowed": False,
        }

    def checkpoint_state(self) -> dict[str, Any]:
        return self.snapshot()

    def restore_state(self, state: Mapping[str, Any] | None, *, now: datetime) -> None:
        if not state:
            return
        active = state.get("active")
        completed = state.get("last_completed")
        self.active = RecoveryRecord.from_dict(active) if active else None
        self.last_completed = RecoveryRecord.from_dict(completed) if completed else None
        if self.active and self.active.state not in self._TERMINAL:
            self.active.verification_id = None
            self.active.current_action = "RESTART_RECONCILIATION"
            self.active.next_eligible_at = None
            self.active.transition(
                RecoveryState.RECONCILING,
                now,
                reason="RESTART_RECONCILIATION_REQUIRED",
            )
            self._emit("RECOVERY_RESTART_RECONCILIATION_REQUIRED", self.active.to_dict())
