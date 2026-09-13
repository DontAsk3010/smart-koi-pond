import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class SILCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


SIMULATION_EXIT_SIL_MATRIX: tuple[SILCase, ...] = (
    SILCase(
        "sil_01_low_do_boundary_hysteresis",
        GateStatus.PASS,
        (
            "DO watch/emergency/recovery boundaries preserve the recovery band "
            "without actuator chatter."
        ),
        "test_sil_01_low_do_boundary_hysteresis",
    ),
    SILCase(
        "sil_02_heat_wave_boundary_feeding_inhibit",
        GateStatus.PASS,
        (
            "Temperature watch/emergency boundaries inhibit feeding without "
            "inventing a cooling actuator."
        ),
        "test_sil_02_heat_wave_boundary_feeding_inhibit",
    ),
    SILCase(
        "sil_03_low_water_boundary_cutoff_lockout",
        GateStatus.PASS,
        (
            "Low-water trigger, recovery target and hard-high cutoff remain "
            "bounded and fail-safe."
        ),
        "test_sil_03_low_water_boundary_cutoff_lockout",
    ),
    SILCase(
        "sil_04_stale_fresh_stale_no_false_normal",
        GateStatus.PASS,
        (
            "Stale/fresh transitions preserve explicit invalidity and never "
            "synthesize a normal value."
        ),
        "test_sil_04_stale_fresh_stale_no_false_normal",
    ),
    SILCase(
        "sil_05_sensor_disagreement_persistence_recovery",
        GateStatus.PASS,
        (
            "Reference disagreement requires persistence, supports observable "
            "fallback, and resets validation history on restart."
        ),
        "test_sil_05_sensor_disagreement_persistence_recovery",
    ),
    SILCase(
        "sil_06_feedback_on_process_no_response",
        GateStatus.PASS,
        (
            "Positive device feedback without process recovery becomes "
            "FAILED_RESPONSE evidence and escalates the incident."
        ),
        "test_sil_06_feedback_on_process_no_response",
    ),
    SILCase(
        "sil_07_partial_actuator_degradation_extended",
        GateStatus.PASS,
        (
            "Partial effectiveness remains distinct from feedback and failed "
            "process response across accelerated time."
        ),
        "test_sil_07_partial_actuator_degradation_extended",
    ),
    SILCase(
        "sil_08_main_loss_degraded_backup_capability",
        GateStatus.PASS,
        (
            "Main circulation loss with a weak backup blocks false-normal "
            "classification while preserving partial capability truth."
        ),
        "test_sil_08_main_loss_degraded_backup_capability",
    ),
    SILCase(
        "sil_09_combined_low_do_circulation_fault",
        GateStatus.PASS,
        (
            "Combined oxygen and circulation faults invoke both governed "
            "corrective paths and preserve ordered incident evidence."
        ),
        "test_sil_09_combined_low_do_circulation_fault",
    ),
    SILCase(
        "sil_10_restart_active_fault_pending_verification",
        GateStatus.PASS,
        (
            "Restart aborts pending verification, clears stale feedback, "
            "preserves incident evidence, and enters reconciliation."
        ),
        "test_sil_10_restart_active_fault_pending_verification",
    ),
    SILCase(
        "sil_11_restart_low_water_recovery_abort",
        GateStatus.PASS,
        (
            "Restart during autonomous top-up forces safe OFF and persistent "
            "lockout without stale command replay."
        ),
        "test_sil_11_restart_low_water_recovery_abort",
    ),
    SILCase(
        "sil_12_mode_takeover_active_correction",
        GateStatus.PASS,
        (
            "Governed operating-mode takeover aborts unsafe autonomous water "
            "recovery and leaves explicit ownership evidence."
        ),
        "test_sil_12_mode_takeover_active_correction",
    ),
    SILCase(
        "sil_13_filter_clean_life_support_interaction",
        GateStatus.PASS,
        (
            "Filter-clean isolation preserves required backup circulation and "
            "independent oxygen correction."
        ),
        "test_sil_13_filter_clean_life_support_interaction",
    ),
    SILCase(
        "sil_14_repeated_fault_recovery_lifecycle",
        GateStatus.PASS,
        (
            "Repeated disturbance/recovery cycles preserve lifecycle ordering "
            "and do not treat acknowledgement as resolution."
        ),
        "test_sil_14_repeated_fault_recovery_lifecycle",
    ),
    SILCase(
        "sil_15_accelerated_long_run_playback",
        GateStatus.PASS,
        (
            "Accelerated long-run execution keeps monotonic chronology and "
            "point-in-time historian playback."
        ),
        "test_sil_15_accelerated_long_run_playback",
    ),
    SILCase(
        "sil_16_supervisory_network_loss_active_fault",
        GateStatus.PASS,
        (
            "A supervisory publication outage does not stop local correction; "
            "canonical events missed by the consumer are replayed from the last "
            "delivered sequence after reconnection."
        ),
        "test_sil_16_supervisory_network_loss_active_fault",
    ),
    SILCase(
        "sil_17_capability_loss_restoration",
        GateStatus.PASS,
        (
            "Mandatory capability loss blocks false NORMAL and explicit restoration "
            "returns the baseline only after fresh evidence."
        ),
        "test_sil_17_capability_loss_restoration",
    ),
    SILCase(
        "sil_18_repeated_combined_fault_playback",
        GateStatus.PASS,
        (
            "Historian playback preserves recorded point-in-time truth after "
            "repeated and combined faults."
        ),
        "test_sil_18_repeated_combined_fault_playback",
    ),
    SILCase(
        "sil_19_invalid_level_during_top_up",
        GateStatus.PASS,
        (
            "Invalid level evidence during active top-up forces immediate safety "
            "OFF and lockout."
        ),
        "test_sil_19_invalid_level_during_top_up",
    ),
    SILCase(
        "sil_20_ack_unresolved_repeated_fault",
        GateStatus.PASS,
        (
            "Alarm acknowledgement never resolves, suppresses, or rewrites an "
            "unresolved repeated fault."
        ),
        "test_sil_20_ack_unresolved_repeated_fault",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in SIMULATION_EXIT_SIL_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_SIMULATION_EXIT_SIL_V015",
        "gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "pass_count": sum(case["status"] == GateStatus.PASS for case in cases),
        "hold_count": len(holds),
        "cases": cases,
    }


def write_evidence(path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(matrix_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_evidence(args.output)


if __name__ == "__main__":
    main()
