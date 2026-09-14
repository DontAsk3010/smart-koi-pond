import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class GovernedRecoveryCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


GOVERNED_RECOVERY_MATRIX: tuple[GovernedRecoveryCase, ...] = (
    GovernedRecoveryCase(
        "grr_01_atomic_preflight",
        GateStatus.PASS,
        "Failed configuration preflight leaves the active model/configuration unchanged.",
        "test_failed_preflight_is_atomic_and_does_not_mutate_model",
    ),
    GovernedRecoveryCase(
        "grr_02_parent_last_good_lineage",
        GateStatus.PASS,
        (
            "Successful material configuration preserves parent lineage and promotes "
            "LAST_GOOD only after verification."
        ),
        "test_successful_configuration_has_parent_and_last_good_lineage",
    ),
    GovernedRecoveryCase(
        "grr_03_config_verify_rollback",
        GateStatus.PASS,
        (
            "Failed post-activation configuration verification restores the compatible "
            "last-good state."
        ),
        "test_failed_post_activation_verification_rolls_back_to_last_good",
    ),
    GovernedRecoveryCase(
        "grr_04_staged_software_last_good",
        GateStatus.PASS,
        (
            "Software candidate remains STAGED until deployment execution plus "
            "verification passes before LAST_GOOD promotion."
        ),
        "test_software_update_is_staged_then_verified_before_last_good",
    ),
    GovernedRecoveryCase(
        "grr_05_failed_software_rollback",
        GateStatus.PASS,
        (
            "Failed software verification invokes the injected rollback path and does not "
            "promote the candidate."
        ),
        "test_failed_software_verification_rolls_back_and_does_not_promote_candidate",
    ),
    GovernedRecoveryCase(
        "grr_06_existing_control_fallback_verification",
        GateStatus.PASS,
        (
            "Primary circulation failure uses the existing backup-pump arbitration path "
            "and requires process verification before RECOVERED."
        ),
        "test_primary_pump_failure_recovers_through_existing_backup_and_process_verification",
    ),
    GovernedRecoveryCase(
        "grr_07_bounded_retry_lockout",
        GateStatus.PASS,
        (
            "Unavailable fallback is retried only within the governed limit and terminates "
            "in visible LOCKED_OUT state."
        ),
        "test_unavailable_fallback_uses_bounded_retry_then_terminal_lockout",
    ),
    GovernedRecoveryCase(
        "grr_08_restart_reconciliation",
        GateStatus.PASS,
        (
            "Restart during recovery returns to reconciliation with de-energized outputs "
            "and no stale verification success."
        ),
        "test_recovery_supervisor_restart_requires_reconciliation_not_stale_success",
    ),
    GovernedRecoveryCase(
        "grr_09_publication_historian_visibility",
        GateStatus.PASS,
        (
            "Configuration and recovery lifecycle state is visible in canonical "
            "publication and historian frames."
        ),
        "test_publication_and_historian_expose_governed_change_and_recovery_state",
    ),
    GovernedRecoveryCase(
        "grr_10_non_escalation_boundary",
        GateStatus.PASS,
        (
            "Recovery cannot elevate execution/actuator authority or enable high-risk "
            "chemical dosing and infinite retry is prohibited."
        ),
        "test_recovery_cannot_escalate_real_authority_or_enable_high_risk_dosing",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in GOVERNED_RECOVERY_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_GOVERNED_RECONFIGURATION_SELF_RECOVERY_V1",
        "governed_recovery_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "handbook_authority": "V0.16_SECTION_43",
        "second_control_engine_created": False,
        "infinite_retry_allowed": False,
        "physical_validation_claimed": False,
        "real_actuation_authorized": False,
        "high_risk_automatic_chemical_dosing_authorized": False,
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
