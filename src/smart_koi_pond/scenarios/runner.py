from dataclasses import dataclass
from typing import Callable

from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.models import RuntimeSnapshot


@dataclass(slots=True, frozen=True)
class ScenarioAction:
    at_seconds: float
    action: Callable[[DigitalTwinRuntime], None]


class ScenarioRunner:
    def __init__(
        self,
        runtime: DigitalTwinRuntime,
        *,
        step_seconds: float,
        actions: tuple[ScenarioAction, ...] = (),
    ) -> None:
        self.runtime = runtime
        self.step_seconds = step_seconds
        self.actions = tuple(sorted(actions, key=lambda item: item.at_seconds))

    def run(self, duration_seconds: float) -> list[RuntimeSnapshot]:
        elapsed = 0.0
        action_index = 0
        snapshots: list[RuntimeSnapshot] = []
        while elapsed < duration_seconds:
            while (
                action_index < len(self.actions)
                and self.actions[action_index].at_seconds <= elapsed
            ):
                self.actions[action_index].action(self.runtime)
                action_index += 1
            snapshots.append(self.runtime.tick(self.step_seconds))
            elapsed += self.step_seconds
        return snapshots
