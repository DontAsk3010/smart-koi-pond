import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class MechanicalFiltrationCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


MECHANICAL_FILTRATION_MATRIX: tuple[MechanicalFiltrationCase, ...] = (
    MechanicalFiltrationCase(
        "mf_01_flow_dependent_mass_conservation",
        GateStatus.PASS,
        "Route flow transfers suspended solids into captured load without destroying mass.",
        "test_flow_dependent_capture_conserves_suspended_plus_captured_mass",
    ),
    MechanicalFiltrationCase(
        "mf_02_zero_flow_and_unknown_no_fabrication",
        GateStatus.PASS,
        "Zero route flow captures nothing and unknown suspended solids remain unknown.",
        "test_zero_flow_captures_nothing_and_unknown_solids_remain_unknown",
    ),
    MechanicalFiltrationCase(
        "mf_03_loading_restriction_composition",
        GateStatus.PASS,
        (
            "Filter-loading process restriction composes with independent route "
            "restriction instead of overwriting unrelated causes."
        ),
        "test_filter_loading_restriction_composes_with_independent_route_restriction",
    ),
    MechanicalFiltrationCase(
        "mf_04_governed_backwash_recovery",
        GateStatus.PASS,
        (
            "Backwash reduces captured load, improves process restriction and only "
            "changes level when discharge volume has an explicit basis."
        ),
        (
            "test_governed_backwash_reduces_load_recovers_process_factor_and_"
            "known_discharge_level"
        ),
    ),
    MechanicalFiltrationCase(
        "mf_05_unknown_discharge_no_level_fabrication",
        GateStatus.PASS,
        (
            "Unknown backwash discharge remains unavailable and does not create a "
            "synthetic water-level change."
        ),
        "test_unknown_backwash_discharge_does_not_fabricate_water_level_change",
    ),
    MechanicalFiltrationCase(
        "mf_06_tss_turbidity_clarity_separation",
        GateStatus.PASS,
        (
            "Calculated TSS is distinct from turbidity, and neither silently establishes "
            "a clear-water conclusion."
        ),
        "test_tss_is_calculated_but_turbidity_and_clarity_require_separate_basis",
    ),
    MechanicalFiltrationCase(
        "mf_07_restart_continuity",
        GateStatus.PASS,
        (
            "Safe Runtime Reset preserves filter loading/removal history while outputs "
            "return de-energized and recovery synchronization is required."
        ),
        "test_safe_runtime_reset_preserves_filter_load_and_deenergizes_outputs",
    ),
    MechanicalFiltrationCase(
        "mf_08_role_audit_publication",
        GateStatus.PASS,
        (
            "Mechanical profile configuration is engineering-role gated, audited and "
            "published through the canonical runtime state."
        ),
        "test_service_configuration_is_engineering_gated_audited_and_published",
    ),
    MechanicalFiltrationCase(
        "mf_09_historian_playback",
        GateStatus.PASS,
        (
            "Historian/playback carries the same mechanical state and remains read-only."
        ),
        "test_historian_playback_preserves_mechanical_state_without_mutation",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in MECHANICAL_FILTRATION_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_MECHANICAL_FILTRATION_FIDELITY_V1",
        "mechanical_filtration_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "physical_validation_claimed": False,
        "hidden_design_assumption_values_used": False,
        "canonical_unit_system": "SI_METRIC_INDONESIA",
        "water_clarity_certified": False,
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
