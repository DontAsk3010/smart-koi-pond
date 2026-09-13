import json
from datetime import UTC, datetime

from smart_koi_pond.control.engine import SimulationControlPolicy
from smart_koi_pond.dashboard.service import RuntimeApplicationService
from smart_koi_pond.digital_twin.clock import SimulationClock
from smart_koi_pond.digital_twin.model import EnvironmentInputs, PondModel
from smart_koi_pond.digital_twin.runtime import DigitalTwinRuntime
from smart_koi_pond.domain.models import PondState


POLICY = SimulationControlPolicy(
    do_watch_below=5.0,
    do_emergency_below=4.0,
    do_recover_above=5.5,
    flow_watch_below=8.0,
    water_level_low_below=70.0,
    verification_delay_seconds=120.0,
    do_verification_min_delta=0.01,
)


def make_service() -> RuntimeApplicationService:
    runtime = DigitalTwinRuntime(
        PondModel(
            PondState(27.0, 6.0, 7.2, 85.0),
            EnvironmentInputs(28.0, 0.2),
        ),
        POLICY,
        clock=SimulationClock.start(datetime(2026, 1, 1, tzinfo=UTC)),
        run_id="animated-pond-matrix",
        config_version="animated-pond-v1",
    )
    runtime.actuators.assets["main_pump"].feedback_on = True
    runtime.actuators.assets["primary_aerator"].feedback_on = True
    runtime._last_feedback = runtime.actuators.feedback_map()
    return RuntimeApplicationService(runtime)


def result(name: str, passed: bool, evidence: dict) -> dict:
    return {"case": name, "status": "PASS" if passed else "HOLD", "evidence": evidence}


def main() -> None:
    cases = []

    service = make_service()
    pv = service.publication()["snapshot"]["process_visual"]
    cases.append(
        result(
            "main_circulation_motion",
            pv["circulation"]["primary"]["motion_active"]
            and pv["circulation"]["measured_total_flow_l_min"] > 0,
            pv["circulation"],
        )
    )

    service.runtime.actuators.assets["main_pump"].feedback_on = False
    service.runtime.actuators.assets["backup_pump"].feedback_on = True
    service.runtime._last_feedback = service.runtime.actuators.feedback_map()
    service.step(0)
    pv = service.publication()["snapshot"]["process_visual"]
    cases.append(
        result(
            "backup_takeover",
            pv["circulation"]["active_route_ids"] == ["backup_pump"],
            pv["circulation"],
        )
    )

    service = make_service()
    service.runtime.actuators.set_effectiveness("main_pump", 0.0)
    service.step(0)
    pv = service.publication()["snapshot"]["process_visual"]
    cases.append(
        result(
            "no_false_flow_on_zero_effectiveness",
            not pv["circulation"]["flow_motion_active"],
            pv["circulation"],
        )
    )

    service = make_service()
    service.command(
        "start_water_change",
        {"target_drain_level_pct": 80.0, "target_refill_level_pct": 85.0},
        role="engineering",
    )
    pv = service.publication()["snapshot"]["process_visual"]
    cases.append(
        result(
            "water_change_drain_projection",
            pv["water_management"]["discharge_kind"] == "DRAIN",
            pv["water_management"],
        )
    )

    service = make_service()
    service.command("start_filter_clean", {"service_scope": []}, role="engineering")
    pv = service.publication()["snapshot"]["process_visual"]
    cases.append(
        result(
            "backwash_without_fake_waste_rate",
            pv["water_management"]["discharge_kind"] == "BACKWASH"
            and pv["water_management"]["quantitative_discharge_rate_l_min"] is None,
            pv["water_management"],
        )
    )

    service = make_service()
    service.command("pause", role="operator")
    before = service.last_snapshot.timestamp
    stepped = service.command("step", {"seconds": 1.0}, role="operator")
    cases.append(
        result(
            "paused_single_step",
            stepped.simulation_paused
            and (stepped.timestamp - before).total_seconds() == 1.0,
            {
                "before": before.isoformat(),
                "after": stepped.timestamp.isoformat(),
                "paused": stepped.simulation_paused,
            },
        )
    )

    service = make_service()
    service.step(10)
    frame = service.history(limit=1)[0]
    playback = service.playback(frame["frame_sequence"])
    cases.append(
        result(
            "historian_playback_same_projection",
            playback["snapshot"]["process_visual"]
            == frame["snapshot"]["process_visual"],
            {"frame_sequence": frame["frame_sequence"]},
        )
    )

    passed = sum(case["status"] == "PASS" for case in cases)
    held = len(cases) - passed
    output = {
        "schema_version": 1,
        "gate": "PASS" if held == 0 else "HOLD",
        "pass": passed,
        "hold": held,
        "cases": cases,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    if held:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
