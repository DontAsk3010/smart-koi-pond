import argparse
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path


class GateStatus(StrEnum):
    PASS = "PASS"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class SourceWaterExchangeCase:
    case_id: str
    status: GateStatus
    evidence: str
    test_reference: str


SOURCE_WATER_EXCHANGE_MATRIX: tuple[SourceWaterExchangeCase, ...] = (
    SourceWaterExchangeCase(
        "swe_01_discharge_concentration_invariance",
        GateStatus.PASS,
        (
            "Well-mixed discharge reduces water and dissolved mass proportionally "
            "without fabricating a concentration change."
        ),
        "test_discharge_only_preserves_well_mixed_dissolved_concentrations",
    ),
    SourceWaterExchangeCase(
        "swe_02_lower_source_dilution",
        GateStatus.PASS,
        "Lower-nitrate replacement water dilutes elevated pond nitrate by mass balance.",
        "test_lower_nitrate_source_water_dilutes_pond_nitrate",
    ),
    SourceWaterExchangeCase(
        "swe_03_higher_source_increase",
        GateStatus.PASS,
        "Higher-nitrate replacement water can increase pond nitrate after mixing.",
        "test_higher_nitrate_source_water_can_raise_pond_nitrate",
    ),
    SourceWaterExchangeCase(
        "swe_04_unknown_source_no_fabrication",
        GateStatus.PASS,
        (
            "Unknown source-water chemistry remains unavailable after mixing rather "
            "than being guessed from the source type label."
        ),
        "test_unknown_source_chemistry_is_not_fabricated_after_refill",
    ),
    SourceWaterExchangeCase(
        "swe_05_supported_multi_parameter_mixing",
        GateStatus.PASS,
        (
            "Temperature, DO, TAN and alkalinity follow source-backed volume/mass "
            "mixing when the corresponding source evidence exists."
        ),
        "test_temperature_do_kh_and_tan_follow_supported_source_water_mixing",
    ),
    SourceWaterExchangeCase(
        "swe_06_ph_model_boundary",
        GateStatus.PASS,
        (
            "pH is not arithmetically averaged; the modeled response is explicitly "
            "simplified, buffering-aware and not a laboratory-equilibrium claim."
        ),
        "test_ph_uses_explicit_simplified_buffer_model_not_linear_average",
    ),
    SourceWaterExchangeCase(
        "swe_07_backwash_refill_chemistry",
        GateStatus.PASS,
        (
            "Backwash discharge and replacement-water refill remain separate physical "
            "mechanisms and produce source-dependent chemistry after mixing."
        ),
        "test_backwash_discharge_plus_refill_changes_nitrate_by_source_mix",
    ),
    SourceWaterExchangeCase(
        "swe_08_checkpoint_continuity",
        GateStatus.PASS,
        "Source-water identity, provenance and chemistry survive governed restart.",
        "test_source_water_profile_survives_runtime_checkpoint_restart",
    ),
    SourceWaterExchangeCase(
        "swe_09_role_audit_publication",
        GateStatus.PASS,
        (
            "Source-water configuration is engineering-role gated, audited and "
            "published through canonical runtime state."
        ),
        "test_service_configuration_is_role_gated_audited_and_published",
    ),
    SourceWaterExchangeCase(
        "swe_10_historian_browser_binding",
        GateStatus.PASS,
        (
            "Historian/playback and browser presentation use the same canonical "
            "water-exchange state rather than a frontend chemistry calculator."
        ),
        "test_historian_playback_and_browser_surface_use_canonical_exchange_state",
    ),
    SourceWaterExchangeCase(
        "swe_11_governed_backwash_asset",
        GateStatus.PASS,
        (
            "Browser backwash uses the governed backwash-valve workflow without "
            "inventing a mechanical-filter actuator."
        ),
        "test_source_water_ui_backwash_uses_real_backwash_valve_workflow",
    ),
    SourceWaterExchangeCase(
        "swe_12_explicit_dissolved_mass_conservation",
        GateStatus.PASS,
        (
            "Numerical nitrate mass before discharge equals remaining plus removed mass, "
            "and post-refill mass equals remaining plus incoming source-water mass."
        ),
        "test_explicit_nitrate_mass_is_conserved_across_discharge_and_refill",
    ),
    SourceWaterExchangeCase(
        "swe_13_governed_water_change_end_to_end",
        GateStatus.PASS,
        (
            "The WATER_CHANGE workflow drives drain/refill actuator ownership through "
            "the same mass-balance model and returns to NORMAL_AUTO after recovery."
        ),
        "test_governed_water_change_workflow_drives_real_mass_balance_path",
    ),
)


def matrix_payload() -> dict[str, object]:
    cases = [asdict(case) for case in SOURCE_WATER_EXCHANGE_MATRIX]
    holds = [case for case in cases if case["status"] == GateStatus.HOLD]
    return {
        "schema_version": 1,
        "matrix": "SMART_KOI_POND_SOURCE_WATER_EXCHANGE_FIDELITY_V1",
        "source_water_exchange_gate": GateStatus.HOLD if holds else GateStatus.PASS,
        "physical_validation_claimed": False,
        "real_actuation_authorized": False,
        "high_risk_automatic_chemical_dosing_authorized": False,
        "source_type_implies_chemistry": False,
        "well_mixed_discharge_assumption_explicit": True,
        "ph_laboratory_equilibrium_claimed": False,
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
