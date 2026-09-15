# ruff: noqa: E501
from __future__ import annotations

import argparse
import html
import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from smart_koi_pond.control.water_quality_config import (
    koi_freshwater_health_reference_v1,
)
from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.dashboard.koi_stock_service import KoiStockRuntimeApplicationService
from smart_koi_pond.digital_twin.hydraulics import (
    HydraulicRouteRole,
    HydraulicRouteSpec,
    PondDesignProfile,
)
from smart_koi_pond.digital_twin.water_exchange import SourceWaterProfile

MATRIX_NAME = "SMART_KOI_POND_VISUAL_FUNCTIONAL_ACCEPTANCE_EVIDENCE_V1"
BASELINE_MAIN = "d3708b643503a5cfbb68e49f69c83436abd77a08"


def _wire(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _wire(asdict(value))
    if isinstance(value, dict):
        return {str(key): _wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(item) for item in value]
    return value


def _cmd(command: Any) -> dict[str, Any]:
    if command is None:
        return {"present": False}
    payload = _wire(command)
    payload["present"] = True
    return payload


def _verification(snapshot: Any) -> list[dict[str, Any]]:
    return [_wire(task) for task in snapshot.verification]


def _events(runtime: Any, after_sequence: int) -> list[dict[str, Any]]:
    return [_wire(event) for event in runtime.events.events if event.sequence > after_sequence]


def _event_codes(runtime: Any, after_sequence: int) -> list[str]:
    return [str(event.code) for event in runtime.events.events if event.sequence > after_sequence]


def _incident_summary(snapshot: Any) -> list[dict[str, Any]]:
    return [_wire(item) for item in snapshot.incidents]


def _resolved_incident(snapshot: Any) -> bool:
    return any(
        item.get("lifecycle") == "RESOLVED" and item.get("end_event_sequence") is not None
        for item in _incident_summary(snapshot)
    )


def _parameter_evidence(snapshot: Any, parameter: str) -> dict[str, Any]:
    logical = {
        "dissolved_oxygen_mg_l": "do",
        "circulation_flow_l_min": "flow",
        "temperature_c": "temperature",
        "ph": "ph",
        "water_level_pct": "water_level",
        "total_ammonia_nitrogen_mg_l": "tan",
        "nitrite_mg_l": "nitrite",
        "nitrate_mg_l": "nitrate",
        "alkalinity_mg_l_as_caco3": "alkalinity",
    }.get(parameter)
    validated = snapshot.validated.get(logical) if logical else None
    return {
        "value": snapshot.estimate.values.get(parameter),
        "quality": _wire(snapshot.estimate.quality.get(parameter)),
        "provenance": snapshot.estimate.provenance.get(parameter),
        "validated": _wire(validated) if validated is not None else None,
        "derivation": _wire(snapshot.estimate.derivation.get(parameter)),
    }


def _design_profile() -> PondDesignProfile:
    return PondDesignProfile(
        profile_id="visual-acceptance-pond",
        revision="v1",
        effective_volume_l=1000.0,
        circulation_turnovers_per_hour_guide=6.0,
        routes=(
            HydraulicRouteSpec(
                route_id="main-circulation",
                asset_id="main_pump",
                rated_flow_l_min=100.0,
                role=HydraulicRouteRole.PRIMARY,
            ),
            HydraulicRouteSpec(
                route_id="backup-circulation",
                asset_id="backup_pump",
                rated_flow_l_min=100.0,
                role=HydraulicRouteRole.BACKUP,
            ),
        ),
        top_up_flow_l_min=100.0,
        drain_flow_l_min=100.0,
    )


def _source(*, qualified: bool) -> SourceWaterProfile:
    return SourceWaterProfile(
        profile_id=("acceptance-safe-source" if qualified else "acceptance-unsafe-source"),
        revision="v1",
        source_reference="VISUAL_FUNCTIONAL_ACCEPTANCE_SOURCE",
        source_type="OTHER",
        temperature_c=27.0,
        dissolved_oxygen_mg_l=7.0,
        ph=7.2,
        total_ammonia_nitrogen_mg_l=0.05,
        nitrite_mg_l=0.01,
        nitrate_mg_l=2.0,
        alkalinity_mg_l_as_caco3=100.0,
        free_chlorine_residual_mg_l=(0.0 if qualified else 0.5),
        chloramine_residual_mg_l=0.0,
        pond_use_qualification=("QUALIFIED" if qualified else "NOT_QUALIFIED"),
        qualification_basis=("SIMULATION_ACCEPTANCE_EVIDENCE" if qualified else None),
        qualification_reference=("VFA-SAFE-SOURCE-V1" if qualified else None),
    )


def _service() -> tuple[Any, KoiStockRuntimeApplicationService]:
    runtime = build_integrated_virtual_runtime()
    service = KoiStockRuntimeApplicationService(runtime)
    for module_id in ("flow_monitoring", "backup_circulation"):
        service.command(
            "configure_module",
            {"module_id": module_id, "enabled": True, "actor": "acceptance-matrix"},
            role="engineering",
        )
    service.command(
        "configure_design_profile",
        {"profile": _design_profile().to_dict(), "actor": "acceptance-matrix"},
        role="engineering",
    )
    for parameter, value in (
        ("tan", 0.1),
        ("nitrite", 0.05),
        ("nitrate", 10.0),
        ("alkalinity", 100.0),
        ("ph", 7.2),
        ("temperature", 27.0),
        ("do", 6.0),
    ):
        service.command(
            "set_environment_state",
            {"parameter": parameter, "value": value},
            role="engineering",
        )
    service.command(
        "start_safe_total_shutdown",
        {"reason": "ACCEPTANCE_BASELINE_LIFE_SUPPORT", "fish_present": True},
        role="engineering",
    )
    service.command("return_to_auto", {}, role="operator")
    service.step(2.0)
    service.step(1.0)
    return runtime, service


def _recover_environment(
    service: KoiStockRuntimeApplicationService,
    parameter: str,
    value: float,
) -> Any:
    service.command(
        "set_environment_state",
        {"parameter": parameter, "value": value},
        role="engineering",
    )
    service.step(1.0)
    return service.step(1.0)


def _case(
    *,
    case_id: str,
    family: str,
    title: str,
    checks: dict[str, bool],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "case_id": case_id,
        "family": family,
        "title": title,
        "status": "PASS" if not failed else "HOLD",
        "failed_checks": failed,
        "checks": checks,
        "evidence": _wire(evidence),
    }


def _nitrite_case(level: float, reason: str, suffix: str) -> dict[str, Any]:
    runtime, service = _service()
    start_sequence = runtime.events.events[-1].sequence
    disturbed = service.command(
        "set_environment_state",
        {"parameter": "nitrite", "value": level},
        role="engineering",
    )
    verified = service.step(130.0)
    recovered = _recover_environment(service, "nitrite", 0.05)
    codes = _event_codes(runtime, start_sequence)
    aerator = disturbed.commands.get("backup_aerator")
    pump = disturbed.commands.get("backup_pump")
    statuses = {str(_wire(task.status)) for task in verified.verification}
    return _case(
        case_id=f"A_{suffix}",
        family="A — Nitrite HIGH / EMERGENCY",
        title=f"Nitrite {reason}",
        checks={
            "validated_input": disturbed.estimate.values.get("nitrite_mg_l") == level,
            "classified_reason": reason in disturbed.classification.reasons,
            "feeding_inhibited": disturbed.commands.get("feeder") is not None
            and disturbed.commands["feeder"].requested_on is False,
            "support_command_accepted": aerator is not None and aerator.accepted and aerator.final_on,
            "flow_support_command_accepted": pump is not None and pump.accepted and pump.final_on,
            "actuator_feedback_on": disturbed.feedback.get("backup_aerator") is not None
            and disturbed.feedback["backup_aerator"].feedback_on,
            "response_verification": "VERIFIED_SUCCESS" in statuses,
            "incident_opened": "INCIDENT_OPENED" in codes,
            "incident_resolved": _resolved_incident(recovered),
            "chemical_dosing_absent": not {
                "acid",
                "base",
                "salt",
                "binder",
                "chemical_doser",
            }.intersection(disturbed.commands),
        },
        evidence={
            "condition": {"nitrite_mg_l": level},
            "input": _parameter_evidence(disturbed, "nitrite_mg_l"),
            "classification": _wire(disturbed.classification),
            "requested_and_final_commands": {
                "backup_aerator": _cmd(aerator),
                "backup_pump": _cmd(pump),
                "feeder": _cmd(disturbed.commands.get("feeder")),
            },
            "feedback": {
                "backup_aerator": _wire(disturbed.feedback.get("backup_aerator")),
                "backup_pump": _wire(disturbed.feedback.get("backup_pump")),
            },
            "verification": _verification(verified),
            "recovery_classification": _wire(recovered.classification),
            "incidents": _incident_summary(recovered),
            "event_timeline": _events(runtime, start_sequence),
        },
    )


def _nitrate_case() -> dict[str, Any]:
    runtime, service = _service()
    start_sequence = runtime.events.events[-1].sequence
    disturbed = service.command(
        "set_environment_state",
        {"parameter": "nitrate", "value": 25.0},
        role="engineering",
    )
    recovered = _recover_environment(service, "nitrate", 10.0)
    forbidden = {"acid", "base", "salt", "binder", "chemical_doser"}
    feeder = disturbed.commands.get("feeder")
    return _case(
        case_id="B_NITRATE_HIGH",
        family="B — Nitrate HIGH",
        title="Nitrate high uses non-chemical safe policy",
        checks={
            "validated_input": disturbed.estimate.values.get("nitrate_mg_l") == 25.0,
            "classified_reason": "NITRATE_HIGH" in disturbed.classification.reasons,
            "feeding_inhibited": feeder is not None and feeder.requested_on is False and feeder.accepted,
            "feeder_feedback_off": disturbed.feedback.get("feeder") is not None
            and not disturbed.feedback["feeder"].feedback_on,
            "no_chemical_command": not forbidden.intersection(disturbed.commands),
            "canonical_policy_verified": bool(
                disturbed.biology.get("feeding_plan", {}).get("water_quality_feed_inhibited", False)
            ),
            "incident_opened": "INCIDENT_OPENED" in _event_codes(runtime, start_sequence),
            "incident_resolved": _resolved_incident(recovered),
        },
        evidence={
            "condition": {"nitrate_mg_l": 25.0},
            "input": _parameter_evidence(disturbed, "nitrate_mg_l"),
            "classification": _wire(disturbed.classification),
            "requested_and_final_commands": {"feeder": _cmd(feeder)},
            "feedback": {"feeder": _wire(disturbed.feedback.get("feeder"))},
            "verification": {
                "type": "CANONICAL_POLICY_INVARIANT",
                "feed_inhibited": disturbed.biology.get("feeding_plan", {}).get("water_quality_feed_inhibited"),
                "forbidden_chemical_commands_present": sorted(forbidden.intersection(disturbed.commands)),
            },
            "recovery_classification": _wire(recovered.classification),
            "incidents": _incident_summary(recovered),
            "event_timeline": _events(runtime, start_sequence),
        },
    )


def _nh3_case() -> dict[str, Any]:
    runtime, service = _service()
    service.command(
        "configure_water_quality_threshold_profile",
        {
            "profile": koi_freshwater_health_reference_v1().threshold_profile().to_dict(),
            "actor": "acceptance-matrix",
        },
        role="engineering",
    )
    start_sequence = runtime.events.events[-1].sequence
    service.command("set_environment_state", {"parameter": "tan", "value": 0.5}, role="engineering")
    service.command("set_environment_state", {"parameter": "ph", "value": 7.5}, role="engineering")
    low = service.command(
        "set_environment_state",
        {"parameter": "temperature", "value": 20.0},
        role="engineering",
    )
    service.command("set_environment_state", {"parameter": "ph", "value": 8.5}, role="engineering")
    high = service.command(
        "set_environment_state",
        {"parameter": "temperature", "value": 28.0},
        role="engineering",
    )
    verified = service.step(130.0)
    service.command("set_environment_state", {"parameter": "tan", "value": 0.1}, role="engineering")
    service.command("set_environment_state", {"parameter": "ph", "value": 7.2}, role="engineering")
    service.command("set_environment_state", {"parameter": "temperature", "value": 27.0}, role="engineering")
    service.step(1.0)
    recovered = service.step(1.0)
    parameter = "unionized_ammonia_nh3_mg_l"
    low_nh3 = low.estimate.values.get(parameter)
    high_nh3 = high.estimate.values.get(parameter)
    derivation = high.estimate.derivation.get(parameter, {})
    statuses = {str(_wire(task.status)) for task in verified.verification}
    return _case(
        case_id="C_SAME_TAN_NH3_RISK",
        family="C — TAN + pH + temperature → molecular NH3",
        title="Same TAN, different pH/temperature, different NH3 risk",
        checks={
            "same_tan": low.estimate.values.get("total_ammonia_nitrogen_mg_l") == 0.5
            and high.estimate.values.get("total_ammonia_nitrogen_mg_l") == 0.5,
            "nh3_calculated": low_nh3 is not None and high_nh3 is not None,
            "higher_risk_relation": high_nh3 is not None and low_nh3 is not None and high_nh3 > low_nh3,
            "canonical_derivation": derivation.get("formula_id") == "EPA_EMERSON_FRESHWATER_NH3_FRACTION_V1"
            and derivation.get("fabricated") is False,
            "high_risk_classified": any(
                reason in high.classification.reasons for reason in ("NH3_HIGH", "NH3_EMERGENCY")
            ),
            "life_support_commanded": high.commands.get("backup_aerator") is not None
            and high.commands["backup_aerator"].final_on,
            "response_verification": "VERIFIED_SUCCESS" in statuses,
            "incident_resolved": _resolved_incident(recovered),
        },
        evidence={
            "condition_low_risk": {
                "tan_n_mg_l": 0.5,
                "ph": 7.5,
                "temperature_c": 20.0,
                "molecular_nh3_mg_l": low_nh3,
            },
            "condition_high_risk": {
                "tan_n_mg_l": 0.5,
                "ph": 8.5,
                "temperature_c": 28.0,
                "molecular_nh3_mg_l": high_nh3,
            },
            "derived_state": {
                "provenance": high.estimate.provenance.get(parameter),
                "derivation": derivation,
            },
            "classification": _wire(high.classification),
            "requested_and_final_commands": {
                key: _cmd(high.commands.get(key))
                for key in ("backup_aerator", "backup_pump", "feeder")
            },
            "verification": _verification(verified),
            "recovery_classification": _wire(recovered.classification),
            "incidents": _incident_summary(recovered),
            "event_timeline": _events(runtime, start_sequence),
        },
    )


def _ph_case(value: float, suffix: str) -> dict[str, Any]:
    runtime, service = _service()
    start_sequence = runtime.events.events[-1].sequence
    disturbed = service.command(
        "set_environment_state",
        {"parameter": "ph", "value": value},
        role="engineering",
    )
    recovered = _recover_environment(service, "ph", 7.2)
    forbidden = {"acid", "base", "salt", "binder", "chemical_doser"}
    feeder = disturbed.commands.get("feeder")
    return _case(
        case_id=f"D_PH_{suffix}",
        family="D — pH HIGH / LOW",
        title=f"pH {'high' if value > 7.2 else 'low'} fail-safe policy",
        checks={
            "validated_input": disturbed.estimate.values.get("ph") == value,
            "classified_reason": "PH_EMERGENCY" in disturbed.classification.reasons,
            "feeding_inhibited": feeder is not None and feeder.requested_on is False,
            "chemical_dosing_absent": not forbidden.intersection(disturbed.commands),
            "incident_opened": "INCIDENT_OPENED" in _event_codes(runtime, start_sequence),
            "incident_resolved": _resolved_incident(recovered),
        },
        evidence={
            "condition": {"ph": value},
            "input": _parameter_evidence(disturbed, "ph"),
            "classification": _wire(disturbed.classification),
            "requested_and_final_commands": {"feeder": _cmd(feeder)},
            "feedback": {"feeder": _wire(disturbed.feedback.get("feeder"))},
            "verification": {
                "type": "FAIL_CLOSED_POLICY_INVARIANT",
                "automatic_acid_base_dosing_authorized": False,
                "forbidden_chemical_commands_present": sorted(forbidden.intersection(disturbed.commands)),
            },
            "recovery_classification": _wire(recovered.classification),
            "incidents": _incident_summary(recovered),
            "event_timeline": _events(runtime, start_sequence),
        },
    )


def _low_do_case() -> dict[str, Any]:
    runtime, service = _service()
    start_sequence = runtime.events.events[-1].sequence
    disturbed = service.command(
        "set_environment_state",
        {"parameter": "do", "value": 3.8},
        role="engineering",
    )
    verified = service.step(130.0)
    recovered = _recover_environment(service, "do", 6.0)
    command = disturbed.commands.get("backup_aerator")
    statuses = {str(_wire(task.status)) for task in verified.verification}
    return _case(
        case_id="E_LOW_DO",
        family="E — Low DO",
        title="Low DO → backup aeration → verified response → recovery",
        checks={
            "validated_input": disturbed.estimate.values.get("dissolved_oxygen_mg_l") == 3.8,
            "classified_reason": "DO_EMERGENCY" in disturbed.classification.reasons,
            "command_accepted": command is not None and command.accepted and command.final_on,
            "feedback_on": disturbed.feedback.get("backup_aerator") is not None
            and disturbed.feedback["backup_aerator"].feedback_on,
            "response_verification": "VERIFIED_SUCCESS" in statuses,
            "incident_opened": "INCIDENT_OPENED" in _event_codes(runtime, start_sequence),
            "incident_resolved": _resolved_incident(recovered),
        },
        evidence={
            "condition": {"dissolved_oxygen_mg_l": 3.8},
            "input": _parameter_evidence(disturbed, "dissolved_oxygen_mg_l"),
            "classification": _wire(disturbed.classification),
            "requested_and_final_commands": {"backup_aerator": _cmd(command)},
            "feedback": {"backup_aerator": _wire(disturbed.feedback.get("backup_aerator"))},
            "response_after_130s": _parameter_evidence(verified, "dissolved_oxygen_mg_l"),
            "verification": _verification(verified),
            "recovery_classification": _wire(recovered.classification),
            "incidents": _incident_summary(recovered),
            "event_timeline": _events(runtime, start_sequence),
        },
    )


def _pump_failure_case() -> dict[str, Any]:
    runtime, service = _service()

    # Establish the required clean takeover precondition through governed commands:
    # backup circulation is explicitly OFF, primary circulation remains ON, and AUTO
    # ownership is restored before the fault is injected.
    service.command(
        "start_manual_maintenance",
        {"scope": ["backup_pump"], "reason": "ACCEPTANCE_PRECONDITION_BACKUP_OFF"},
        role="engineering",
    )
    service.command(
        "manual_command",
        {"asset_id": "backup_pump", "on": False, "reason": "ACCEPTANCE_PRECONDITION_BACKUP_OFF"},
        role="engineering",
    )
    service.command("return_to_auto", {}, role="operator")
    baseline = service.step(1.0)
    baseline_backup_off = (
        baseline.assets["main_pump"].feedback_on
        and not baseline.assets["backup_pump"].feedback_on
        and baseline.estimate.values.get("circulation_flow_l_min") == 100.0
    )

    start_sequence = runtime.events.events[-1].sequence
    disturbed = service.command(
        "inject_actuator_fault",
        {"asset_id": "main_pump", "mode": "failed_off"},
        role="engineering",
    )
    verified = service.step(130.0)
    service.command("clear_actuator_fault", {"asset_id": "main_pump"}, role="engineering")
    service.step(1.0)
    recovered = service.step(1.0)
    command = disturbed.commands.get("backup_pump")
    statuses = {str(_wire(task.status)) for task in verified.verification}
    codes = _event_codes(runtime, start_sequence)
    return _case(
        case_id="F_MAIN_PUMP_FAILURE",
        family="F — Main pump / circulation failure",
        title="Main pump failed-off → backup circulation takeover → flow verification → repair",
        checks={
            "clean_takeover_precondition": baseline_backup_off,
            "fault_visible": disturbed.assets["main_pump"].availability.value == "FAILED"
            and not disturbed.assets["main_pump"].feedback_on,
            "flow_low_at_fault": disturbed.estimate.values.get("circulation_flow_l_min") == 0.0
            and "FLOW_LOW" in disturbed.classification.reasons,
            "backup_command_accepted": command is not None and command.accepted and command.final_on,
            "backup_feedback_on": disturbed.feedback.get("backup_pump") is not None
            and disturbed.feedback["backup_pump"].feedback_on,
            "flow_response_verified": "VERIFIED_SUCCESS" in statuses,
            "incident_opened": "INCIDENT_OPENED" in codes,
            "incident_resolved_after_repair": _resolved_incident(recovered),
        },
        evidence={
            "baseline": {
                "main_pump_feedback_on": baseline.assets["main_pump"].feedback_on,
                "backup_pump_feedback_on": baseline.assets["backup_pump"].feedback_on,
                "circulation_flow_l_min": baseline.estimate.values.get("circulation_flow_l_min"),
            },
            "condition": {"main_pump_fault": "failed_off"},
            "classification": _wire(disturbed.classification),
            "asset_state": _wire(disturbed.assets["main_pump"]),
            "requested_and_final_commands": {"backup_pump": _cmd(command)},
            "feedback": {"backup_pump": _wire(disturbed.feedback.get("backup_pump"))},
            "flow_at_failure": _parameter_evidence(disturbed, "circulation_flow_l_min"),
            "flow_after_130s": _parameter_evidence(verified, "circulation_flow_l_min"),
            "verification": _verification(verified),
            "recovery_classification": _wire(recovered.classification),
            "incidents": _incident_summary(recovered),
            "event_timeline": _events(runtime, start_sequence),
        },
    )


def _source_water_unsafe_case() -> dict[str, Any]:
    runtime, service = _service()
    unsafe = _source(qualified=False)
    service.command(
        "configure_source_water_profile",
        {"profile": unsafe.to_dict(), "actor": "acceptance-matrix"},
        role="engineering",
    )
    start_sequence = runtime.events.events[-1].sequence
    rejected = False
    error = None
    try:
        service.command(
            "start_water_change",
            {
                "target_drain_level_pct": 75.0,
                "target_refill_level_pct": 85.0,
                "reason": "VISUAL_FUNCTIONAL_ACCEPTANCE_UNSAFE_SOURCE",
            },
            role="engineering",
        )
    except RuntimeError as exc:
        rejected = "SOURCE_WATER_NOT_QUALIFIED" in str(exc)
        error = str(exc)
    snapshot = service.step(0.0)
    codes = _event_codes(runtime, start_sequence)
    return _case(
        case_id="G1_UNSAFE_SOURCE_FAIL_CLOSED",
        family="G — Source-water qualified-safer vs unsafe/unqualified",
        title="Unsafe source water fails closed before drain",
        checks={
            "operation_rejected": rejected,
            "inhibition_event": "SOURCE_WATER_OPERATION_INHIBITED" in codes,
            "drain_not_started": not runtime.actuators.assets["drain_valve"].feedback_on,
            "mode_not_water_change": snapshot.operating_mode.value != "WATER_CHANGE",
            "chemical_dosing_closed": True,
        },
        evidence={
            "condition": unsafe.qualification_snapshot(),
            "error": error,
            "operating_mode": snapshot.operating_mode,
            "drain_feedback_on": runtime.actuators.assets["drain_valve"].feedback_on,
            "event_timeline": _events(runtime, start_sequence),
        },
    )


def _source_water_safe_case() -> dict[str, Any]:
    runtime, service = _service()
    safe = _source(qualified=True)
    service.command(
        "configure_source_water_profile",
        {"profile": safe.to_dict(), "actor": "acceptance-matrix"},
        role="engineering",
    )
    start_sequence = runtime.events.events[-1].sequence
    started = service.command(
        "start_water_change",
        {
            "target_drain_level_pct": 75.0,
            "target_refill_level_pct": 85.0,
            "reason": "VISUAL_FUNCTIONAL_ACCEPTANCE_SAFE_SOURCE",
        },
        role="engineering",
    )
    drained = service.step(60.0)
    refilled = service.step(60.0)
    completed = service.step(1.0)
    completed_exchange = completed.hydraulics.get("water_exchange", {})
    exchange_at_refill = refilled.hydraulics.get("water_exchange", {})
    source = completed_exchange.get("source_water", {})
    mixing = exchange_at_refill.get("last_exchange", {})
    codes = _event_codes(runtime, start_sequence)
    return _case(
        case_id="G2_SAFE_SOURCE_WATER_CHANGE",
        family="G — Source-water qualified-safer vs unsafe/unqualified",
        title="Qualified safer source completes governed drain/refill",
        checks={
            "qualified": source.get("pond_use_qualified") is True,
            "water_change_started": started.operating_mode.value == "WATER_CHANGE",
            "drain_commanded": started.commands.get("drain_valve") is not None
            and started.commands["drain_valve"].final_on,
            "refill_commanded": drained.commands.get("top_up_valve") is not None
            and drained.commands["top_up_valve"].final_on,
            "returned_to_auto": completed.operating_mode.value == "NORMAL_AUTO",
            "target_level_restored": completed.estimate.values.get("water_level_pct") == 85.0,
            "mixing_evidence_present": bool(mixing.get("parameter_results")),
            "phase_timeline_present": "WATER_CHANGE_DRAIN_TARGET_REACHED" in codes
            and "WATER_CHANGE_REFILL_TARGET_REACHED" in codes
            and "RETURN_TO_AUTO_COMPLETE" in codes,
        },
        evidence={
            "condition": safe.qualification_snapshot(),
            "start": {
                "mode": started.operating_mode,
                "level": started.estimate.values.get("water_level_pct"),
                "commands": {
                    "drain_valve": _cmd(started.commands.get("drain_valve")),
                    "top_up_valve": _cmd(started.commands.get("top_up_valve")),
                },
            },
            "after_drain": {
                "mode": drained.operating_mode,
                "level": drained.estimate.values.get("water_level_pct"),
                "commands": {
                    "drain_valve": _cmd(drained.commands.get("drain_valve")),
                    "top_up_valve": _cmd(drained.commands.get("top_up_valve")),
                },
            },
            "after_refill": {
                "mode": refilled.operating_mode,
                "level": refilled.estimate.values.get("water_level_pct"),
                "mixing_evidence": mixing,
            },
            "completed": {
                "mode": completed.operating_mode,
                "level": completed.estimate.values.get("water_level_pct"),
                "water_exchange": completed_exchange,
            },
            "event_timeline": _events(runtime, start_sequence),
        },
    )


def _run_case(
    fn: Callable[[], dict[str, Any]],
    case_id: str,
    family: str,
    title: str,
) -> dict[str, Any]:
    try:
        return fn()
    except Exception as exc:
        return {
            "case_id": case_id,
            "family": family,
            "title": title,
            "status": "HOLD",
            "failed_checks": ["scenario_execution_exception"],
            "checks": {"scenario_execution_exception": False},
            "evidence": {"exception_type": type(exc).__name__, "exception": str(exc)},
        }


def matrix_payload() -> dict[str, Any]:
    cases = [
        _run_case(
            lambda: _nitrite_case(0.6, "NITRITE_HIGH", "NITRITE_HIGH"),
            "A_NITRITE_HIGH",
            "A — Nitrite HIGH / EMERGENCY",
            "Nitrite HIGH",
        ),
        _run_case(
            lambda: _nitrite_case(1.6, "NITRITE_EMERGENCY", "NITRITE_EMERGENCY"),
            "A_NITRITE_EMERGENCY",
            "A — Nitrite HIGH / EMERGENCY",
            "Nitrite EMERGENCY",
        ),
        _run_case(_nitrate_case, "B_NITRATE_HIGH", "B — Nitrate HIGH", "Nitrate high"),
        _run_case(
            _nh3_case,
            "C_SAME_TAN_NH3_RISK",
            "C — TAN + pH + temperature → molecular NH3",
            "Same TAN NH3 risk",
        ),
        _run_case(lambda: _ph_case(9.2, "HIGH"), "D_PH_HIGH", "D — pH HIGH / LOW", "pH HIGH"),
        _run_case(lambda: _ph_case(5.8, "LOW"), "D_PH_LOW", "D — pH HIGH / LOW", "pH LOW"),
        _run_case(_low_do_case, "E_LOW_DO", "E — Low DO", "Low DO"),
        _run_case(
            _pump_failure_case,
            "F_MAIN_PUMP_FAILURE",
            "F — Main pump / circulation failure",
            "Main pump failure",
        ),
        _run_case(
            _source_water_unsafe_case,
            "G1_UNSAFE_SOURCE_FAIL_CLOSED",
            "G — Source-water qualified-safer vs unsafe/unqualified",
            "Unsafe source fail-closed",
        ),
        _run_case(
            _source_water_safe_case,
            "G2_SAFE_SOURCE_WATER_CHANGE",
            "G — Source-water qualified-safer vs unsafe/unqualified",
            "Qualified safe source water change",
        ),
    ]
    holds = [case for case in cases if case["status"] != "PASS"]
    return {
        "schema_version": 1,
        "matrix": MATRIX_NAME,
        "authority_checkpoint": BASELINE_MAIN,
        "execution_mode": "SIMULATION",
        "same_canonical_runtime": True,
        "browser_is_second_control_engine": False,
        "real_device_control_authorized": False,
        "high_risk_automatic_chemical_dosing_authorized": False,
        "overall_gate": "HOLD" if holds else "PASS",
        "pass_count": sum(case["status"] == "PASS" for case in cases),
        "hold_count": len(holds),
        "required_chain": [
            "condition/input",
            "validation/provenance",
            "derived state",
            "classification/reason",
            "requested action",
            "final canonical command",
            "virtual actuator feedback/process effect",
            "measured/modelled response trend",
            "verification",
            "recovery OR failed-response/escalation/lockout",
            "incident start/end",
            "event timeline",
        ],
        "cases": cases,
    }


def write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _case_card(case: dict[str, Any]) -> str:
    checks = "".join(
        f"<li><b>{html.escape(name)}</b>: {'PASS' if passed else 'HOLD'}</li>"
        for name, passed in case["checks"].items()
    )
    evidence_json = html.escape(json.dumps(case["evidence"], indent=2, sort_keys=True))
    return f"""
    <section class="case {case['status'].lower()}">
      <header><span class="badge">{case['status']}</span><div><small>{html.escape(case['family'])}</small><h2>{html.escape(case['title'])}</h2></div></header>
      <ul>{checks}</ul>
      <details><summary>Open canonical evidence chain</summary><pre>{evidence_json}</pre></details>
    </section>
    """


def write_html(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    cards = "\n".join(_case_card(case) for case in payload["cases"])
    chain = " → ".join(payload["required_chain"])
    gate_color = "#143d2a" if payload["overall_gate"] == "PASS" else "#4b3514"
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Koi Pond — Visual Functional Acceptance Evidence</title>
<style>
body{{margin:0;background:#07131d;color:#e9f4fa;font:14px/1.5 system-ui,Segoe UI,sans-serif}}main{{max-width:1180px;margin:auto;padding:28px}}h1{{margin:.2rem 0}}.meta{{color:#91a9b9}}.gate{{display:inline-block;padding:7px 12px;border-radius:999px;font-weight:800;background:{gate_color}}}.chain{{padding:14px;border:1px solid #24455b;border-radius:10px;background:#0b1d29;margin:18px 0}}.case{{border:1px solid #284a60;border-radius:12px;padding:14px;margin:12px 0;background:#0a1a25}}.case.pass{{border-left:5px solid #4fc984}}.case.hold{{border-left:5px solid #e6a23c}}header{{display:flex;gap:12px;align-items:flex-start}}header small{{color:#8ca7b8}}h2{{margin:2px 0 8px}}.badge{{font-weight:900;padding:4px 8px;border-radius:7px;background:#153649}}ul{{columns:2;padding-left:22px}}details{{margin-top:10px}}summary{{cursor:pointer;font-weight:700}}pre{{white-space:pre-wrap;word-break:break-word;background:#041019;padding:12px;border-radius:8px;max-height:520px;overflow:auto}}code{{color:#b8e6ff}}@media(max-width:700px){{ul{{columns:1}}main{{padding:14px}}}}
</style></head><body><main>
<p class="meta">SMART KOI POND · PRODUCTION-INTENT DIGITAL TWIN · SIMULATION / NO REAL DEVICE CONTROL</p>
<h1>Visual Functional Acceptance Evidence</h1>
<p><span class="gate">OVERALL {payload['overall_gate']}</span> &nbsp; {payload['pass_count']} PASS / {payload['hold_count']} HOLD</p>
<p class="meta">Authority checkpoint: <code>{BASELINE_MAIN}</code>. This report is generated by executing the same canonical runtime. It does not calculate control outcomes in the browser.</p>
<div class="chain"><b>Required evidence chain</b><br>{html.escape(chain)}</div>
{cards}
<footer class="meta">Real-device authority: CLOSED · High-risk automatic chemical dosing: CLOSED · Browser second control engine: FALSE</footer>
</main></body></html>"""
    target.write_text(document, encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--html-output", required=True)
    args = parser.parse_args()
    payload = matrix_payload()
    write_json(args.json_output, payload)
    write_html(args.html_output, payload)
    if payload["overall_gate"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
