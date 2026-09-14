import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class IntegratedVirtualPondCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


INTEGRATED_VIRTUAL_POND_MATRIX: tuple[IntegratedVirtualPondCase, ...] = (
    IntegratedVirtualPondCase(
        "ivp_01_honest_startup",
        GateStatus.PASS,
        "Runnable browser entry point starts with process profiles INPUT REQUIRED and no energized equipment rather than demo-only hidden engineering defaults.",
        "test_integrated_entrypoint_starts_honestly_input_required",
    ),
    IntegratedVirtualPondCase(
        "ivp_02_full_stack_binding",
        GateStatus.PASS,
        "Explicit owner/test configuration binds pond profile, hydraulics, biology and mechanical filtration to one canonical runtime publication.",
        "test_full_stack_configuration_becomes_visible_from_canonical_publication",
    ),
    IntegratedVirtualPondCase(
        "ivp_03_unknown_clarity_evidence",
        GateStatus.PASS,
        "TSS may be calculated while turbidity and water-clarity conclusion remain unavailable/not-established without a governed correlation.",
        "test_unknown_turbidity_remains_unavailable_in_visible_state",
    ),
    IntegratedVirtualPondCase(
        "ivp_04_reconfigurable_volume",
        GateStatus.PASS,
        "Owner volume revision recalculates hydraulic requirements in the same running Digital Twin without hardware lock semantics.",
        "test_owner_volume_revision_recalculates_requirement_in_same_runtime",
    ),
    IntegratedVirtualPondCase(
        "ivp_05_environment_disturbance",
        GateStatus.PASS,
        "Engineering water-state disturbances travel through the governed Scenario Controller and become visible in canonical state/classification.",
        "test_environment_disturbance_is_visible_through_canonical_state",
    ),
    IntegratedVirtualPondCase(
        "ivp_06_fault_truth",
        GateStatus.PASS,
        "A failed-off circulation asset removes false process-flow animation and exposes the same failure through runtime and process projection.",
        "test_actuator_fault_removes_false_flow_from_visible_process_state",
    ),
    IntegratedVirtualPondCase(
        "ivp_07_historian_playback",
        GateStatus.PASS,
        "Historian/playback preserves the integrated pond profile, hydraulics and process projection rather than rendering a disconnected report.",
        "test_historian_playback_preserves_integrated_process_state",
    ),
    IntegratedVirtualPondCase(
        "ivp_08_browser_configuration_surface",
        GateStatus.PASS,
        "Browser exposes explicit pond, biology and filtration configuration plus live evidence through canonical API commands with INPUT REQUIRED semantics.",
        "test_browser_surface_exposes_integrated_setup_without_hidden_process_values",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in INTEGRATED_VIRTUAL_POND_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_INTEGRATED_VIRTUAL_POND_BROWSER_V1",
        "integrated_virtual_pond_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "physical_validation_claimed": False,
        "real_actuation_authorized": False,
        "hidden_engineering_defaults_used": False,
        "browser_is_second_control_engine": False,
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
