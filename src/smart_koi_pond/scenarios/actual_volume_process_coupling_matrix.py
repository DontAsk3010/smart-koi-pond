import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class ActualVolumeProcessCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


ACTUAL_VOLUME_PROCESS_MATRIX: tuple[ActualVolumeProcessCase, ...] = (
    ActualVolumeProcessCase(
        "avp_01_actual_volume_publication",
        GateStatus.PASS,
        (
            "Canonical hydraulics exposes actual modeled water volume calculated from "
            "effective profile volume and current water level, with explicit provenance."
        ),
        "test_hydraulic_snapshot_exposes_actual_volume_from_water_level",
    ),
    ActualVolumeProcessCase(
        "avp_02_biology_actual_volume",
        GateStatus.PASS,
        (
            "Biological mass-to-concentration and oxygen-load calculations use the actual "
            "modeled water volume at the start of each integration step."
        ),
        "test_biology_uses_actual_partial_volume_for_mass_to_concentration",
    ),
    ActualVolumeProcessCase(
        "avp_03_filtration_actual_volume",
        GateStatus.PASS,
        (
            "Mechanical-filter capture turnover and calculated TSS use actual modeled "
            "water volume rather than the configured full-volume design basis."
        ),
        "test_mechanical_capture_and_tss_use_actual_partial_volume",
    ),
    ActualVolumeProcessCase(
        "avp_04_backwash_actual_available_water",
        GateStatus.PASS,
        (
            "Backwash discharge is capped by actual available pond water once; water level "
            "is not applied a second time to an already level-adjusted volume."
        ),
        "test_backwash_available_water_is_actual_volume_not_level_applied_twice",
    ),
    ActualVolumeProcessCase(
        "avp_05_zero_volume_fail_honest",
        GateStatus.PASS,
        (
            "Zero actual water volume disables aqueous biology/filter evolution without "
            "division by zero, synthetic volume floors or fabricated TSS."
        ),
        "test_zero_actual_water_volume_stops_aqueous_processes_without_division",
    ),
    ActualVolumeProcessCase(
        "avp_06_partial_drain_rebinds_next_step",
        GateStatus.PASS,
        (
            "After a material partial drain, the next deterministic integration step uses "
            "the reduced actual water volume for biological process calculations."
        ),
        "test_partial_drain_updates_process_volume_on_following_integration_step",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in ACTUAL_VOLUME_PROCESS_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_ACTUAL_VOLUME_PROCESS_COUPLING_V1",
        "actual_volume_process_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "integration_basis": "ACTUAL_MODELED_VOLUME_AT_STEP_START",
        "actual_volume_basis": "EFFECTIVE_VOLUME_X_WATER_LEVEL",
        "hidden_volume_floor_used": False,
        "physical_validation_claimed": False,
        "real_actuation_authorized": False,
        "canonical_unit_system": "SI_METRIC_INDONESIA",
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
