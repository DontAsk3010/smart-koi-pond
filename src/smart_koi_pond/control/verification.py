from collections.abc import Iterable
from datetime import datetime, timedelta

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.domain.enums import VerificationStatus
from smart_koi_pond.domain.models import VerificationTask


class VerificationManager:
    def __init__(self) -> None:
        self.tasks: list[VerificationTask] = []
        self._counter = 0

    def start_for_asset(
        self,
        asset_id: str,
        now: datetime,
        values: dict[str, float | None],
        policy: SimulationControlPolicy,
    ) -> VerificationTask | None:
        delay_seconds = policy.verification_delay_seconds
        if asset_id == "backup_aerator":
            parameter = "dissolved_oxygen_mg_l"
            minimum_delta = policy.do_verification_min_delta
        elif asset_id == "backup_pump":
            parameter = "circulation_flow_l_min"
            minimum_delta = policy.flow_verification_min_delta
        elif asset_id == "top_up_valve" and policy.low_water_auto_recovery_enabled:
            parameter = "water_level_pct"
            minimum_delta = policy.water_level_verification_min_delta
            delay_seconds = policy.low_water_verification_delay_seconds
        else:
            return None

        baseline = values.get(parameter)
        if baseline is None:
            return None
        self._counter += 1
        task = VerificationTask(
            verification_id=f"verify-{self._counter}",
            asset_id=asset_id,
            parameter=parameter,
            baseline=baseline,
            minimum_delta=minimum_delta,
            due_at=now + timedelta(seconds=delay_seconds),
        )
        self.tasks.append(task)
        return task

    def evaluate(self, now: datetime, values: dict[str, float | None]) -> list[VerificationTask]:
        completed: list[VerificationTask] = []
        for task in self.tasks:
            if task.status != VerificationStatus.PENDING or now < task.due_at:
                continue
            value = values.get(task.parameter)
            task.observed_value = value
            if value is None:
                task.status = VerificationStatus.INSUFFICIENT_EVIDENCE
            elif value >= task.baseline + task.minimum_delta:
                task.status = VerificationStatus.VERIFIED_SUCCESS
            else:
                task.status = VerificationStatus.FAILED_RESPONSE
            completed.append(task)
        return completed

    def restore(self, tasks: Iterable[VerificationTask]) -> None:
        self.tasks = list(tasks)
        counters: list[int] = []
        for task in self.tasks:
            prefix, separator, suffix = task.verification_id.rpartition("-")
            if separator and prefix == "verify" and suffix.isdigit():
                counters.append(int(suffix))
        self._counter = max(counters, default=0)
