import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class RegressionCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


V1_REGRESSION_MATRIX: tuple[RegressionCase, ...] = (
    RegressionCase(
        "restart_manual_maintenance",
        GateStatus.PASS,
        "Service ownership/locks survive restart and require explicit recovery sync.",
        "test_restart_during_governed_operating_modes_enters_hold",
    ),
    RegressionCase(
        "restart_sensor_calibration",
        GateStatus.PASS,
        "Calibration availability survives restart and is not converted to a healthy value.",
        "test_restart_during_governed_operating_modes_enters_hold",
    ),
    RegressionCase(
        "restart_water_change",
        GateStatus.PASS,
        "Unfinished drain/refill workflow enters HOLD; stale valve commands are not replayed.",
        "test_restart_during_governed_operating_modes_enters_hold",
    ),
    RegressionCase(
        "restart_filter_clean",
        GateStatus.PASS,
        "Backwash/service workflow enters HOLD and preserves governed ownership.",
        "test_restart_during_governed_operating_modes_enters_hold",
    ),
    RegressionCase(
        "restart_partial_shutdown",
        GateStatus.PASS,
        "Planned isolation survives restart without becoming an unexpected failure cascade.",
        "test_restart_during_governed_operating_modes_enters_hold",
    ),
    RegressionCase(
        "restart_safe_total_shutdown",
        GateStatus.PASS,
        "Shutdown ownership survives restart; return to AUTO is explicit and reconciled.",
        "test_restart_during_governed_operating_modes_enters_hold",
    ),
    RegressionCase(
        "blackout_restart_recovery_sync",
        GateStatus.PASS,
        "Blackout restart enters RECOVERY_SYNC and restarts minimum life support before AUTO.",
        "test_blackout_restart_restarts_life_support_before_auto",
    ),
    RegressionCase(
        "main_pump_failure_backup_flow",
        GateStatus.PASS,
        "Main-pump failure reduces capability and the independent backup path restores flow.",
        "test_main_pump_failure_uses_backup_without_false_total_failure",
    ),
    RegressionCase(
        "failed_correction_escalation",
        GateStatus.PASS,
        "Failed response is verification evidence and escalates alarm/incident lifecycle.",
        "test_failed_correction_has_verification_and_incident_evidence",
    ),
    RegressionCase(
        "sensor_dropout_vs_real_low_do",
        GateStatus.PASS,
        "Missing DO is DEGRADED/unknown while genuine measured low DO requests correction.",
        "test_sensor_dropout_is_distinct_from_genuine_low_do",
    ),
    RegressionCase(
        "water_level_fault_detection",
        GateStatus.PASS,
        "Low level is detected deterministically without fabricating a normal reading.",
        "test_low_water_is_detected_without_fabricating_recovery",
    ),
    RegressionCase(
        "supervisory_network_loss_local_control",
        GateStatus.PASS,
        "The local runtime performs critical correction without dashboard/cloud construction.",
        "test_local_critical_control_has_no_supervisory_network_dependency",
    ),
    RegressionCase(
        "combined_fault_incident_chronology",
        GateStatus.PASS,
        "Combined life-support faults remain reconstructable as ordered incident evidence.",
        "test_combined_fault_has_ordered_incident_evidence",
    ),
    RegressionCase(
        "historian_playback_consistency",
        GateStatus.PASS,
        "Historian playback returns the point-in-time canonical snapshot, not current state.",
        "test_historian_playback_preserves_point_in_time_runtime_truth",
    ),
    RegressionCase(
        "heat_wave_safety_classification",
        GateStatus.PASS,
        "Simulation-policy temperature limits classify heat-wave risk and inhibit feeding at the "
        "emergency tier without claiming a physical cooling actuator.",
        "test_heat_wave_is_classified_and_feeding_is_inhibited",
    ),
    RegressionCase(
        "sensor_stuck_drift_discrimination",
        GateStatus.PASS,
        "Stateful validation uses temporal history plus an independently observable reference "
        "source to reject persistent stuck/drift disagreement without hidden simulator truth.",
        "test_sensor_reference_discriminates_real_fault_stuck_and_drift",
    ),
    RegressionCase(
        "partial_actuator_degradation",
        GateStatus.PASS,
        "Feedback ON is separated from process effectiveness; degraded output scales the pond "
        "response and verification can fail despite positive device feedback.",
        "test_partial_actuator_degradation_is_detected_by_process_verification",
    ),
    RegressionCase(
        "low_water_autonomous_recovery",
        GateStatus.HOLD,
        "Low level is detected, but autonomous top-up requires governed hard-limit/interlock and "
        "site evidence not yet implemented.",
        "test_low_water_is_detected_without_fabricating_recovery",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in V1_REGRESSION_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_DIGITAL_TWIN_V1",
        "end_to_end_gate": GateStatus.HOLD if holds else GateStatus.PASS,
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
