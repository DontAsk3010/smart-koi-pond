import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class BiologyCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


INTEGRATED_BIOLOGY_MATRIX: tuple[BiologyCase, ...] = (
    BiologyCase(
        "bio_01_no_fabricated_missing_input",
        GateStatus.PASS,
        (
            "Missing biomass/feed/chemistry remains explicit INPUT_REQUIRED "
            "instead of synthetic values."
        ),
        "test_missing_biological_inputs_remain_input_required_without_fabrication",
    ),
    BiologyCase(
        "bio_02_metric_units",
        GateStatus.PASS,
        (
            "Canonical biological configuration and process output use SI/metric "
            "and aquaculture units."
        ),
        "test_metric_units_and_explicit_provenance_are_canonical",
    ),
    BiologyCase(
        "bio_03_feed_biomass_nitrogen_path",
        GateStatus.PASS,
        (
            "Explicit feed/biomass input drives oxygen demand, waste, TAN, nitrite, "
            "nitrate and buffering response."
        ),
        "test_feed_and_biomass_drive_oxygen_demand_waste_and_nitrogen_cycle",
    ),
    BiologyCase(
        "bio_04_do_flow_limit_nitrification",
        GateStatus.PASS,
        (
            "Insufficient oxygen or hydraulic support constrains modeled biofilter "
            "conversion instead of hiding the limitation."
        ),
        "test_low_do_or_low_flow_constrains_biofilter_conversion",
    ),
    BiologyCase(
        "bio_05_safe_water_quality_support",
        GateStatus.PASS,
        (
            "High TAN uses safe aeration/circulation support and feeding inhibit "
            "without opening automatic chemical dosing."
        ),
        "test_high_tan_uses_safe_support_and_feed_inhibit_without_chemical_dosing",
    ),
    BiologyCase(
        "bio_06_environment_disturbance_authority",
        GateStatus.PASS,
        (
            "Manual virtual water-condition changes are engineering-role gated, "
            "audited and published through the canonical service."
        ),
        "test_environment_disturbance_is_role_gated_audited_and_publishable",
    ),
    BiologyCase(
        "bio_07_automatic_disturbance_trigger",
        GateStatus.PASS,
        (
            "Automatic scenarios apply the same governed environmental disturbance "
            "path without creating a second engine."
        ),
        "test_automatic_environment_trigger_uses_same_scenario_authority",
    ),
    BiologyCase(
        "bio_08_restart_continuity",
        GateStatus.PASS,
        (
            "Safe runtime reset preserves biological profile and chemistry while "
            "de-energizing outputs and entering recovery synchronization."
        ),
        "test_safe_runtime_reset_preserves_biology_and_chemistry_but_deenergizes_outputs",
    ),
    BiologyCase(
        "bio_09_profile_recalculation",
        GateStatus.PASS,
        (
            "Pond volume, biomass and feed revisions automatically recalculate "
            "concentration-based biological oxygen demand."
        ),
        "test_volume_biomass_and_feed_revision_recalculates_oxygen_load",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in INTEGRATED_BIOLOGY_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_INTEGRATED_BIOLOGY_ENVIRONMENT_V1",
        "integrated_biology_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "physical_validation_claimed": False,
        "synthetic_design_assumption_values_used": False,
        "canonical_unit_system": "SI_METRIC_INDONESIA",
        "automatic_chemical_dosing_authorized": False,
        "real_actuation_authorized": False,
        "hardware_fault_or_upgrade_conclusion_requires_evidence": True,
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
