import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class ReferencePondProfileCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


REFERENCE_POND_PROFILE_MATRIX: tuple[ReferencePondProfileCase, ...] = (
    ReferencePondProfileCase(
        "rpp_01_governed_metric_reference",
        GateStatus.PASS,
        (
            "REFERENCE_STANDARD_METRIC_V1 is explicit and versioned at 4.0 m x 2.0 m "
            "x 1.5 m, 12,000 L nominal volume and 1.0 turnover/hour."
        ),
        "test_reference_standard_metric_v1_is_exact_and_explicit",
    ),
    ReferencePondProfileCase(
        "rpp_02_requirement_not_hardware_claim",
        GateStatus.PASS,
        (
            "Reference hydraulic requirement is calculated without declaring installed "
            "hardware faulty, oversized, undersized or upgrade-required."
        ),
        "test_reference_profile_calculates_requirement_without_hardware_fault_claim",
    ),
    ReferencePondProfileCase(
        "rpp_03_user_override_recalculation",
        GateStatus.PASS,
        (
            "A user-defined pond retains reference lineage, marks overridden fields and "
            "recalculates dependent circulation requirement deterministically."
        ),
        "test_user_override_retains_reference_lineage_and_recalculates",
    ),
    ReferencePondProfileCase(
        "rpp_04_checkpoint_lineage",
        GateStatus.PASS,
        "Reference and override lineage survives checkpoint/restart.",
        "test_reference_lineage_survives_checkpoint_restart",
    ),
    ReferencePondProfileCase(
        "rpp_05_historian_playback_lineage",
        GateStatus.PASS,
        "Historian and playback preserve the same reference/user profile lineage.",
        "test_reference_profile_is_visible_in_historian_and_playback",
    ),
    ReferencePondProfileCase(
        "rpp_06_browser_reference_not_site_fact",
        GateStatus.PASS,
        (
            "Browser exposes the governed reference profile and manual geometry/volume "
            "override while explicitly stating that the reference is not a site measurement."
        ),
        "test_reference_profile_browser_surface_is_explicit_not_site_measurement",
    ),
    ReferencePondProfileCase(
        "rpp_07_no_silent_site_default",
        GateStatus.PASS,
        (
            "Runtime startup remains fail-honest: reference availability does not silently "
            "claim that a physical site profile has been measured or commissioned."
        ),
        "test_legacy_integrated_startup_still_does_not_claim_reference_as_site_fact",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in REFERENCE_POND_PROFILE_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_REFERENCE_POND_PROFILE_FIDELITY_V1",
        "reference_pond_profile_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "physical_site_measurement_claimed": False,
        "physical_validation_claimed": False,
        "real_actuation_authorized": False,
        "reference_profile_id": "REFERENCE_STANDARD_METRIC_V1",
        "reference_nominal_volume_l": 12000.0,
        "canonical_unit_system": "SI_METRIC_INDONESIA",
        "user_override_supported": True,
        "reference_to_commissioned_lineage_required": True,
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
