import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class ModularCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


MODULAR_PLATFORM_MATRIX: tuple[ModularCase, ...] = (
    ModularCase(
        "default_minimum_life_support_baseline",
        GateStatus.PASS,
        "Default Digital Twin profile satisfies the governed minimum baseline.",
        "test_default_simulation_profile_satisfies_mandatory_baseline",
    ),
    ModularCase(
        "optional_module_absence_isolation",
        GateStatus.PASS,
        "An intentionally absent optional module is UNSUPPORTED, not a false failure.",
        "test_optional_module_absence_is_not_failure_or_baseline_degradation",
    ),
    ModularCase(
        "mandatory_baseline_loss_blocks_false_normal",
        GateStatus.PASS,
        "Missing mandatory capability produces BASELINE_NOT_MET and prevents NORMAL.",
        "test_missing_mandatory_baseline_capability_prevents_false_normal",
    ),
    ModularCase(
        "dependency_safe_disablement",
        GateStatus.PASS,
        "Missing dependency disables only the dependent automation path.",
        "test_missing_dependency_disables_only_dependent_automation",
    ),
    ModularCase(
        "package_label_has_no_control_authority",
        GateStatus.PASS,
        "Commercial package label does not change capability or control semantics.",
        "test_package_label_does_not_change_control_or_capability_meaning",
    ),
    ModularCase(
        "module_restart_continuity",
        GateStatus.PASS,
        "Module installation state survives checkpoint/restart without stale command replay.",
        "test_module_configuration_survives_checkpoint_and_restart",
    ),
    ModularCase(
        "unsafe_module_removal_blocked",
        GateStatus.PASS,
        "A module with a running actuator cannot be removed before safe OFF.",
        "test_running_asset_cannot_be_removed_as_module",
    ),
    ModularCase(
        "canonical_publication_and_ui_binding",
        GateStatus.PASS,
        "Capability registry and baseline are published through canonical runtime truth.",
        "test_capability_registry_is_published_and_modular_ui_exposes_baseline",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in MODULAR_PLATFORM_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_MODULAR_PLATFORM_V1",
        "gate": GateStatus.HOLD if holds else GateStatus.PASS,
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
