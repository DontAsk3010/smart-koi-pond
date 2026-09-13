from datetime import UTC, datetime

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.models import PondState
from smart_koi_pond.scenarios.runner import ScenarioAction, ScenarioRunner


POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
)


def make_runtime() -> DigitalTwinRuntime:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, 6.0, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def test_scenario_action_is_reproducible() -> None:
    def force_low_do(runtime):
        runtime.model.set_truth("dissolved_oxygen_mg_l", 4.5)

    runtime_a = make_runtime()
    runner_a = ScenarioRunner(
        runtime_a,
        step_seconds=60,
        actions=(ScenarioAction(60, force_low_do),),
    )
    result_a = runner_a.run(180)

    runtime_b = make_runtime()
    runner_b = ScenarioRunner(
        runtime_b,
        step_seconds=60,
        actions=(ScenarioAction(60, force_low_do),),
    )
    result_b = runner_b.run(180)

    assert [item.classification.state for item in result_a] == [
        item.classification.state for item in result_b
    ]
    assert [round(item.pond_truth.dissolved_oxygen_mg_l, 6) for item in result_a] == [
        round(item.pond_truth.dissolved_oxygen_mg_l, 6) for item in result_b
    ]
