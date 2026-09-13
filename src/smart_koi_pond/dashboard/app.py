import os
from datetime import UTC, datetime

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.dashboard.webapp import serve
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.models import PondState


def build_simulation_runtime() -> DigitalTwinRuntime:
    """Build the V1 simulator demo runtime.

    These values are explicit software-simulation inputs, not production biological
    engineering setpoints or commissioning authority.
    """
    policy = SimulationControlPolicy(
        do_watch_below=5.0,
        do_emergency_below=4.0,
        do_recover_above=5.5,
        flow_watch_below=8.0,
        water_level_low_below=70.0,
        verification_delay_seconds=120.0,
        do_verification_min_delta=0.01,
    )
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(
                temperature_c=27.0,
                dissolved_oxygen_mg_l=6.0,
                ph=7.2,
                water_level_pct=85.0,
            ),
            EnvironmentInputs(
                ambient_temperature_c=28.0,
                oxygen_demand_mg_l_per_hour=0.2,
            ),
        ),
        policy,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        config_version="digital-twin-v1-demo-only",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def main() -> None:
    host = os.getenv("SMART_KOI_HOST", "127.0.0.1")
    port = int(os.getenv("SMART_KOI_PORT", "8080"))
    runtime = build_simulation_runtime()
    service = RuntimeApplicationService(runtime)
    print(f"Smart Koi Pond Digital Twin V1: http://{host}:{port}")
    print("SIMULATION / NO REAL DEVICE CONTROL")
    serve(service, host=host, port=port)


if __name__ == "__main__":
    main()
