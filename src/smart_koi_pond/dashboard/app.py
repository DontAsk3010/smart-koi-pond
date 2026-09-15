import os
from datetime import UTC, datetime

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.source_water_service import (
    SourceWaterQualifiedRuntimeApplicationService,
)
from smart_koi_pond.dashboard.webapp import serve
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.digital_twin.source_water_runtime import (
    SourceWaterQualifiedProductionRuntime,
)
from smart_koi_pond.digital_twin.water_exchange import WaterExchangePondModel
from smart_koi_pond.domain.enums import EventType
from smart_koi_pond.domain.models import PondState


def build_integrated_virtual_runtime(
    *,
    historian_path: str | None = None,
) -> DigitalTwinRuntime:
    """Build the production-lineage Integrated Virtual Pond runtime.

    The base water values below are simulation initial-state values only. They are not
    pond measurements, hardware sizing facts, biological engineering references, or
    production setpoints. Pond/hydraulic, biological, mechanical-filtration and
    source-water profiles remain explicitly unconfigured until supplied through
    governed configuration paths.
    """
    policy = SimulationControlPolicy(
        do_watch_below=5.0,
        do_emergency_below=4.0,
        do_recover_above=5.5,
        flow_watch_below=8.0,
        water_level_low_below=70.0,
        verification_delay_seconds=120.0,
        do_verification_min_delta=0.01,
        temperature_watch_above=30.0,
        temperature_emergency_above=32.0,
        tan_watch_above=0.4,
        tan_emergency_above=1.5,
        nitrite_watch_above=0.4,
        nitrite_emergency_above=1.5,
        nitrate_watch_above=20.0,
        ph_watch_below=6.8,
        ph_watch_above=8.2,
        ph_emergency_below=6.0,
        ph_emergency_above=9.0,
    )
    runtime = SourceWaterQualifiedProductionRuntime(
        WaterExchangePondModel(
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
        config_version="integrated-virtual-pond-v1-input-required",
        historian_path=historian_path,
        module_enabled={
            "flow_monitoring": False,
            "backup_circulation": False,
        },
    )
    runtime.events.append(
        runtime.clock.current,
        EventType.CONFIGURATION,
        "INTEGRATED_VIRTUAL_POND_STARTED",
        {
            "execution_mode": "SIMULATION",
            "real_device_control": False,
            "pond_profile": "INPUT_REQUIRED",
            "biological_profile": "INPUT_REQUIRED",
            "mechanical_filtration_profile": "INPUT_REQUIRED",
            "source_water_profile": "INPUT_REQUIRED",
            "source_water_qualification": "INPUT_REQUIRED",
            "automatic_chemical_dosing_authorized": False,
            "flow_monitoring": "DISABLED_UNTIL_POND_PROFILE_CONFIGURED",
            "backup_circulation": "DISABLED_UNTIL_EXPLICIT_CONFIGURATION",
            "simulation_initial_state_is_physical_measurement": False,
            "hidden_engineering_defaults": False,
            "governed_reconfiguration": True,
            "bounded_self_recovery": True,
        },
    )
    return runtime


def build_simulation_runtime(
    *,
    historian_path: str | None = None,
) -> DigitalTwinRuntime:
    """Build the retained V1 regression runtime.

    This compatibility entry point intentionally preserves the accepted V1 initial
    conditions used by the established regression and fault/recovery evidence lanes.
    It is not the browser entry point for the Integrated Virtual Pond.
    """
    policy = SimulationControlPolicy(
        do_watch_below=5.0,
        do_emergency_below=4.0,
        do_recover_above=5.5,
        flow_watch_below=8.0,
        water_level_low_below=70.0,
        verification_delay_seconds=120.0,
        do_verification_min_delta=0.01,
        temperature_watch_above=30.0,
        temperature_emergency_above=32.0,
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
        historian_path=historian_path,
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return runtime


def main() -> None:
    host = os.getenv("SMART_KOI_HOST", "127.0.0.1")
    port = int(os.getenv("SMART_KOI_PORT", "8080"))
    historian_path = os.getenv(
        "SMART_KOI_HISTORIAN_PATH",
        "runtime-data/historian.jsonl",
    )
    runtime = build_integrated_virtual_runtime(historian_path=historian_path)
    service = SourceWaterQualifiedRuntimeApplicationService(runtime)
    print(f"Smart Koi Pond — Integrated Virtual Pond: http://{host}:{port}")
    print("SIMULATION / NO REAL DEVICE CONTROL")
    print(
        "Pond/hydraulic, biology, filter and source-water facts: "
        "INPUT REQUIRED until configured"
    )
    print("Source-water pond-use qualification: FAIL-CLOSED / EVIDENCE REQUIRED")
    print("Automatic chemical dosing authority: DISABLED")
    print("Governed reconfiguration / rollback / bounded self-recovery: ENABLED")
    print(f"Historian: {historian_path}")
    serve(service, host=host, port=port)


if __name__ == "__main__":
    main()
