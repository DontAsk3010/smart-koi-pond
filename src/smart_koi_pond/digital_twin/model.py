from dataclasses import dataclass

from smart_koi_pond.domain.models import PondState


@dataclass(slots=True, frozen=True)
class EnvironmentInputs:
    ambient_temperature_c: float
    oxygen_demand_mg_l_per_hour: float
    leak_pct_per_hour: float = 0.0


@dataclass(slots=True, frozen=True)
class ActuatorEffects:
    main_pump_flow_l_min: float = 12.0
    backup_pump_flow_l_min: float = 10.0
    primary_aerator_gain_mg_l_per_hour: float = 0.55
    backup_aerator_gain_mg_l_per_hour: float = 0.75
    top_up_gain_pct_per_hour: float = 12.0
    temperature_exchange_per_hour: float = 0.08


class PondModel:
    """Small deterministic control-test model, not a calibrated biological model."""

    def __init__(
        self,
        state: PondState,
        environment: EnvironmentInputs,
        effects: ActuatorEffects | None = None,
    ) -> None:
        self.state = state
        self.environment = environment
        self.effects = effects or ActuatorEffects()

    def set_truth(self, parameter: str, value: float) -> None:
        if parameter == "temperature_c":
            self.state.temperature_c = value
        elif parameter == "dissolved_oxygen_mg_l":
            self.state.dissolved_oxygen_mg_l = value
        elif parameter == "ph":
            self.state.ph = value
        elif parameter == "water_level_pct":
            self.state.water_level_pct = value
        else:
            raise KeyError(parameter)

    def step(self, seconds: float, feedback_on: dict[str, bool]) -> PondState:
        hours = seconds / 3600.0
        e = self.effects

        flow = 0.0
        if feedback_on.get("main_pump", False):
            flow += e.main_pump_flow_l_min
        if feedback_on.get("backup_pump", False):
            flow += e.backup_pump_flow_l_min
        self.state.circulation_flow_l_min = flow

        do_delta = -self.environment.oxygen_demand_mg_l_per_hour
        if feedback_on.get("primary_aerator", False):
            do_delta += e.primary_aerator_gain_mg_l_per_hour
        if feedback_on.get("backup_aerator", False):
            do_delta += e.backup_aerator_gain_mg_l_per_hour
        self.state.dissolved_oxygen_mg_l = max(
            0.0, self.state.dissolved_oxygen_mg_l + do_delta * hours
        )

        temp_delta = (
            self.environment.ambient_temperature_c - self.state.temperature_c
        ) * e.temperature_exchange_per_hour
        self.state.temperature_c += temp_delta * hours

        level_delta = -self.environment.leak_pct_per_hour
        if feedback_on.get("top_up_valve", False):
            level_delta += e.top_up_gain_pct_per_hour
        next_level = self.state.water_level_pct + level_delta * hours
        self.state.water_level_pct = min(100.0, max(0.0, next_level))
        return self.state
