import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class G0Case:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


G0_HIL_ENTRY_SOFTWARE_MATRIX: tuple[G0Case, ...] = (
    G0Case(
        "g0_01_virtual_provenance_default",
        GateStatus.PASS,
        "Default simulation publication exposes virtual sensor/actuator provenance and authority.",
        "test_default_runtime_publishes_virtual_source_and_authority",
    ),
    G0Case(
        "g0_02_real_io_and_live_mode_gate",
        GateStatus.PASS,
        "Simulation rejects real-I/O claims and LIMITED_LIVE/FULL_LIVE remain closed.",
        "test_simulation_rejects_real_io_claims_and_live_modes_remain_closed",
    ),
    G0Case(
        "g0_03_real_sensor_identity_ordering",
        GateStatus.PASS,
        "Real telemetry is bound to governed device identity and rejects mismatched or non-monotonic data.",
        "test_real_sensor_identity_order_and_duplicate_rules_are_fail_closed",
    ),
    G0Case(
        "g0_04_real_sensor_reconciliation_freshness",
        GateStatus.PASS,
        "Virtual-to-real source transition requires governed binding and post-boundary fresh evidence.",
        "test_real_sensor_switch_requires_binding_and_reconciliation_fresh_sample",
    ),
    G0Case(
        "g0_05_shadow_real_actuator_fail_closed",
        GateStatus.PASS,
        "SHADOW control intent cannot energize a command-inhibited real actuator.",
        "test_shadow_real_actuator_is_inhibited_even_when_control_requests_on",
    ),
    G0Case(
        "g0_06_adapter_defense_in_depth",
        GateStatus.PASS,
        "The real-actuator adapter independently rejects any active command that bypasses runtime authority gating.",
        "test_real_actuator_adapter_itself_rejects_active_commands",
    ),
    G0Case(
        "g0_07_transition_aborts_stale_verification",
        GateStatus.PASS,
        "Source transition aborts pending verification and records auditable configuration evidence.",
        "test_source_transition_aborts_pending_verification_and_is_audited",
    ),
    G0Case(
        "g0_08_restart_real_source_no_stale_observation",
        GateStatus.PASS,
        "Restart preserves real identity/source configuration without replaying cached physical observations.",
        "test_real_source_checkpoint_restores_identity_but_not_cached_observation",
    ),
    G0Case(
        "g0_09_checkpoint_adapter_identity",
        GateStatus.PASS,
        "Checkpoint restore rejects adapter-identity mismatch instead of silently remapping I/O lineage.",
        "test_checkpoint_rejects_adapter_identity_mismatch",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in G0_HIL_ENTRY_SOFTWARE_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_G0_HIL_ENTRY_SOFTWARE_V1",
        "software_entry_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "physical_hil_gate": GateStatus.HOLD,
        "physical_hil_authorized": False,
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
