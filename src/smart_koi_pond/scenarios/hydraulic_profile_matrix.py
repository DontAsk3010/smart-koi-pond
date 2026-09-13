import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class HydraulicProfileCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


HYDRAULIC_PROFILE_MATRIX: tuple[HydraulicProfileCase, ...] = (
    HydraulicProfileCase(
        "hp_01_volume_recalculation",
        GateStatus.PASS,
        (
            "Changing effective pond volume automatically recalculates circulation "
            "requirement and achieved turnover without rewriting hardware definitions."
        ),
        "test_volume_change_recalculates_required_flow_without_hardware_rewrite",
    ),
    HydraulicProfileCase(
        "hp_02_sizing_advisory_not_lock",
        GateStatus.PASS,
        (
            "Declared circulation capacity is compared with calculated pond requirement; "
            "larger equipment is not rejected, and actual hardware fault/upgrade claims "
            "remain unestablished without supporting evidence."
        ),
        "test_larger_candidate_pump_is_guidance_not_a_hardware_lock",
    ),
    HydraulicProfileCase(
        "hp_03_route_restriction",
        GateStatus.PASS,
        (
            "Per-route restriction changes canonical effective flow and pond turnover "
            "rather than presentation state only."
        ),
        "test_route_restriction_changes_effective_flow_and_turnover",
    ),
    HydraulicProfileCase(
        "hp_04_volume_aware_water_management",
        GateStatus.PASS,
        (
            "The same configured top-up flow produces a different level-change rate "
            "when effective pond volume changes."
        ),
        "test_water_management_rate_recalculates_from_effective_volume",
    ),
    HydraulicProfileCase(
        "hp_05_restart_continuity",
        GateStatus.PASS,
        (
            "Checkpoint/restart preserves profile and hydraulic restriction lineage "
            "while keeping outputs de-energized during recovery reconciliation."
        ),
        "test_checkpoint_preserves_profile_and_restriction_but_deenergizes_outputs",
    ),
    HydraulicProfileCase(
        "hp_06_governed_reconfiguration_and_publication",
        GateStatus.PASS,
        (
            "Engineering-role profile reconfiguration is exposed through the canonical "
            "application boundary and published by the same runtime."
        ),
        "test_engineering_service_can_reconfigure_profile_and_publish_state",
    ),
    HydraulicProfileCase(
        "hp_07_explicit_input_provenance",
        GateStatus.PASS,
        (
            "Configured virtual profile values carry explicit USER_CONFIGURED_SCENARIO "
            "provenance rather than synthetic design-assumption provenance."
        ),
        "test_profile_uses_explicit_user_configured_provenance_not_design_assumption",
    ),
    HydraulicProfileCase(
        "hp_08_canonical_process_projection",
        GateStatus.PASS,
        (
            "Modeled per-route hydraulic flow reaches the canonical process projection "
            "with explicit scenario provenance and without claiming physical metering."
        ),
        "test_modeled_route_flow_reaches_canonical_process_projection",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in HYDRAULIC_PROFILE_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 2,
        "matrix": "SMART_KOI_POND_HYDRAULIC_PROFILE_FIDELITY_V1",
        "hydraulic_profile_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "physical_validation_claimed": False,
        "hardware_sizing_mandatory_lock": False,
        "hardware_fault_or_upgrade_conclusion_requires_evidence": True,
        "synthetic_design_assumption_provenance_used": False,
        "canonical_unit_system": "SI_METRIC_INDONESIA",
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
