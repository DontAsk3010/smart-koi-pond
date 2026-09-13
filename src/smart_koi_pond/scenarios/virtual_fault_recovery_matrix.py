import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class FaultRecoveryCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


VIRTUAL_FAULT_RECOVERY_MATRIX: tuple[FaultRecoveryCase, ...] = (
    FaultRecoveryCase(
        "vfr_01_failed_actuator_changes_process",
        GateStatus.PASS,
        (
            "A failed-off virtual circulation actuator loses feedback and process effect; "
            "canonical control observes loss of flow and requests the backup path."
        ),
        "test_failed_off_actuator_removes_process_effect_and_backup_takes_over",
    ),
    FaultRecoveryCase(
        "vfr_02_degraded_actuator_effect",
        GateStatus.PASS,
        (
            "Virtual actuator degradation changes modeled process effectiveness rather "
            "than changing presentation state only."
        ),
        "test_degraded_actuator_changes_effect_and_repair_stays_deenergized",
    ),
    FaultRecoveryCase(
        "vfr_03_repair_fail_safe",
        GateStatus.PASS,
        (
            "Clearing a simulated hardware fault restores nominal configuration but "
            "leaves the repaired actuator de-energized until a later governed command."
        ),
        "test_degraded_actuator_changes_effect_and_repair_stays_deenergized",
    ),
    FaultRecoveryCase(
        "vfr_04_safe_runtime_reset",
        GateStatus.PASS,
        (
            "Safe reset preserves simulated hardware faults and system lineage while "
            "de-energizing outputs and entering governed restart reconciliation."
        ),
        "test_safe_runtime_reset_preserves_fault_and_deenergizes_outputs",
    ),
    FaultRecoveryCase(
        "vfr_05_timed_automatic_fault",
        GateStatus.PASS,
        "A one-shot fault can be armed on simulation time and fires exactly once.",
        "test_timed_automatic_fault_fires_once",
    ),
    FaultRecoveryCase(
        "vfr_06_condition_automatic_fault",
        GateStatus.PASS,
        (
            "Validated sensor state can arm an automatic fault scenario and the resulting "
            "fault is reflected in the canonical runtime snapshot."
        ),
        "test_sensor_condition_can_trigger_automatic_fault",
    ),
    FaultRecoveryCase(
        "vfr_07_engineering_authority_and_visibility",
        GateStatus.PASS,
        (
            "Fault injection and safe reset require engineering authority, while armed "
            "scenario triggers remain visible in canonical publication."
        ),
        "test_engineering_role_is_required_for_hardware_fault_and_reset;"
        "test_publication_exposes_armed_scenario_triggers",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in VIRTUAL_FAULT_RECOVERY_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_VIRTUAL_FAULT_RECOVERY_V1",
        "virtual_fault_recovery_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "physical_validation_claimed": False,
        "real_actuation_authorized": False,
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
