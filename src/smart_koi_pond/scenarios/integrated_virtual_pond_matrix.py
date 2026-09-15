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
        (
            "Runnable browser entry point starts with process profiles INPUT REQUIRED "
            "and no energized equipment rather than hidden engineering defaults."
        ),
        "test_integrated_entrypoint_starts_honestly_input_required",
    ),
    IntegratedVirtualPondCase(
        "ivp_02_full_stack_binding",
        GateStatus.PASS,
        (
            "Explicit owner/test configuration binds pond profile, hydraulics, biology "
            "and mechanical filtration to one canonical runtime publication."
        ),
        "test_full_stack_configuration_becomes_visible_from_canonical_publication",
    ),
    IntegratedVirtualPondCase(
        "ivp_03_unknown_clarity_evidence",
        GateStatus.PASS,
        (
            "TSS may be calculated while turbidity and water-clarity conclusion remain "
            "unavailable/not-established without a governed correlation."
        ),
        "test_unknown_turbidity_remains_unavailable_in_visible_state",
    ),
    IntegratedVirtualPondCase(
        "ivp_04_reconfigurable_volume",
        GateStatus.PASS,
        (
            "Owner volume revision recalculates hydraulic requirements in the same "
            "running Digital Twin without hardware lock semantics."
        ),
        "test_owner_volume_revision_recalculates_requirement_in_same_runtime",
    ),
    IntegratedVirtualPondCase(
        "ivp_05_environment_disturbance",
        GateStatus.PASS,
        (
            "Engineering water-state disturbances travel through the governed Scenario "
            "Controller and become visible in canonical state/classification."
        ),
        "test_environment_disturbance_is_visible_through_canonical_state",
    ),
    IntegratedVirtualPondCase(
        "ivp_06_fault_truth",
        GateStatus.PASS,
        (
            "A failed-off circulation asset removes false process-flow animation and "
            "exposes the same failure through runtime and process projection."
        ),
        "test_actuator_fault_removes_false_flow_from_visible_process_state",
    ),
    IntegratedVirtualPondCase(
        "ivp_07_historian_playback",
        GateStatus.PASS,
        (
            "Historian/playback preserves the integrated pond profile, hydraulics and "
            "process projection rather than rendering a disconnected report."
        ),
        "test_historian_playback_preserves_integrated_process_state",
    ),
    IntegratedVirtualPondCase(
        "ivp_08_browser_configuration_surface",
        GateStatus.PASS,
        (
            "Browser exposes explicit pond, biology and filtration configuration plus "
            "live evidence through canonical API commands with INPUT REQUIRED semantics."
        ),
        "test_browser_surface_exposes_integrated_setup_without_hidden_process_values",
    ),
    IntegratedVirtualPondCase(
        "ivp_09_governed_backwash",
        GateStatus.PASS,
        (
            "Filter-clean action uses the governed backwash-valve workflow and does not "
            "invent a non-existent mechanical-filter actuator asset."
        ),
        "test_governed_backwash_uses_backwash_valve_without_fake_filter_asset",
    ),
    IntegratedVirtualPondCase(
        "ivp_10_fail_honest_unavailable_values",
        GateStatus.PASS,
        (
            "Missing DO, circulation flow, water level and other unavailable process "
            "evidence remain unavailable rather than becoming synthetic zero/defaults."
        ),
        "test_process_visual_preserves_unavailable_core_values_instead_of_false_zero",
    ),
    IntegratedVirtualPondCase(
        "ivp_11_governed_recovery_visibility",
        GateStatus.PASS,
        (
            "Canonical active/LAST_GOOD configuration and bounded recovery state survive "
            "historian playback without granting browser-side control authority."
        ),
        "test_governance_snapshot_state_is_preserved_in_historian_playback",
    ),
    IntegratedVirtualPondCase(
        "ivp_12_source_water_fail_closed",
        GateStatus.PASS,
        (
            "Unqualified source water fails closed before WATER_CHANGE drain and cannot "
            "silently become a safe refill source from its source-type label."
        ),
        "test_water_change_rejects_unqualified_source_before_drain_phase",
    ),
    IntegratedVirtualPondCase(
        "ivp_13_equipment_process_drilldown",
        GateStatus.PASS,
        (
            "Interactive equipment/process drill-down reads only canonical snapshot and "
            "loaded event evidence and does not create a second command/control path."
        ),
        "test_drilldown_reads_only_canonical_snapshot_and_loaded_event_evidence",
    ),
    IntegratedVirtualPondCase(
        "ivp_14_synchronized_trends_events",
        GateStatus.PASS,
        (
            "Historian-backed trends preserve unavailable-value gaps and synchronize "
            "canonical event markers plus point-in-time playback cursor evidence."
        ),
        "test_trend_markers_and_playback_cursor_use_canonical_time_evidence",
    ),
    IntegratedVirtualPondCase(
        "ivp_15_incident_recovery_story",
        GateStatus.PASS,
        (
            "Incident recovery story is incident-bounded and point-in-time safe; future "
            "evidence is hidden during playback and missing stages are not inferred."
        ),
        "test_incident_story_is_point_in_time_and_hides_future_playback_evidence",
    ),
    IntegratedVirtualPondCase(
        "ivp_16_filtration_backwash_causality",
        GateStatus.PASS,
        (
            "Filter-loading, hydraulic consequence, backwash removal/water loss and "
            "playback evidence remain canonical without equating valve state to success."
        ),
        "test_mechanical_process_evidence_survives_governed_backwash_and_playback",
    ),
    IntegratedVirtualPondCase(
        "ivp_17_route_flow_no_false_zero",
        GateStatus.PASS,
        (
            "A modeled route whose effective-flow value is absent remains UNAVAILABLE "
            "instead of being projected as a false zero-flow observation."
        ),
        "test_missing_modeled_route_flow_remains_unavailable_not_false_zero",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in INTEGRATED_VIRTUAL_POND_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 2,
        "matrix": "SMART_KOI_POND_INTEGRATED_VIRTUAL_POND_BROWSER_V1",
        "acceptance_revision": "FINAL_INTEGRATED_VIRTUAL_ACCEPTANCE_V2",
        "integrated_virtual_pond_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "physical_validation_claimed": False,
        "real_actuation_authorized": False,
        "high_risk_automatic_chemical_dosing_authorized": False,
        "hidden_engineering_defaults_used": False,
        "browser_is_second_control_engine": False,
        "historian_playback_is_read_only": True,
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
