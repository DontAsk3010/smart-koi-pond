from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from smart_koi_pond.domain.models import RuntimeSnapshot


@dataclass(slots=True, frozen=True)
class VisualAssetPath:
    asset_id: str
    feedback_on: bool
    availability: str
    effectiveness: float
    motion_active: bool
    verification_status: str | None


@dataclass(slots=True, frozen=True)
class CirculationVisualState:
    measured_total_flow_l_min: float
    flow_motion_active: bool
    primary: VisualAssetPath
    backup: VisualAssetPath
    active_route_ids: tuple[str, ...]
    modeled_route_flows_l_min: dict[str, float]
    route_flow_provenance: str


@dataclass(slots=True, frozen=True)
class AerationVisualState:
    primary: VisualAssetPath
    backup: VisualAssetPath
    active_source_ids: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class WaterManagementVisualState:
    water_level_pct: float
    top_up: VisualAssetPath
    drain: VisualAssetPath
    backwash: VisualAssetPath
    expected_level_direction: str
    discharge_kind: str
    quantitative_discharge_rate_l_min: float | None = None


@dataclass(slots=True, frozen=True)
class MechanicalFiltrationVisualState:
    configured: bool
    provenance: str
    filtered_route_id: str | None
    captured_solids_g: float | None
    suspended_solids_g: float | None
    loading_fraction: float | None
    process_throughput_factor: float | None
    tss_mg_l: float | None
    turbidity_ntu: float | None
    water_clarity_conclusion: str


@dataclass(slots=True, frozen=True)
class ProcessVisualState:
    schema_version: int
    source: str
    run_id: str
    timestamp: str
    simulation_paused: bool
    simulation_acceleration: float
    classification: str
    operating_mode: str
    operating_phase: str
    dissolved_oxygen_mg_l: float
    circulation: CirculationVisualState
    aeration: AerationVisualState
    water_management: WaterManagementVisualState
    mechanical_filtration: MechanicalFiltrationVisualState
    active_alarm_codes: tuple[str, ...]
    limitations: tuple[str, ...]


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _text(value: Any, default: str = "UNKNOWN") -> str:
    if value is None:
        return default
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def _optional_number(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _verification_status(
    snapshot: RuntimeSnapshot | Mapping[str, Any],
    asset_id: str,
) -> str | None:
    tasks = _get(snapshot, "verification", ()) or ()
    statuses = [
        _text(_get(task, "status"), "")
        for task in tasks
        if _get(task, "asset_id") == asset_id
    ]
    if not statuses:
        return None
    priority = (
        "FAILED_RESPONSE",
        "INSUFFICIENT_EVIDENCE",
        "PENDING",
        "VERIFIED_SUCCESS",
        "ABORTED_BY_MODE_CHANGE",
    )
    for status in priority:
        if status in statuses:
            return status
    return statuses[-1]


def _asset_path(
    snapshot: RuntimeSnapshot | Mapping[str, Any],
    asset_id: str,
    *,
    process_motion_allowed: bool,
) -> VisualAssetPath:
    assets = _get(snapshot, "assets", {}) or {}
    asset = assets.get(asset_id) if isinstance(assets, Mapping) else None
    if asset is None:
        return VisualAssetPath(
            asset_id=asset_id,
            feedback_on=False,
            availability="UNSUPPORTED",
            effectiveness=0.0,
            motion_active=False,
            verification_status=None,
        )

    feedback_on = bool(_get(asset, "feedback_on", False))
    effectiveness = max(
        0.0,
        min(1.0, _number(_get(asset, "effectiveness", 1.0), 1.0)),
    )
    availability = _text(_get(asset, "availability"))
    unavailable = availability in {
        "FAILED",
        "UNAVAILABLE",
        "UNAVAILABLE_OFFLINE",
        "UNKNOWN",
        "UNSUPPORTED",
        "MAINTENANCE_UNAVAILABLE",
        "PLANNED_OFF",
    }
    return VisualAssetPath(
        asset_id=asset_id,
        feedback_on=feedback_on,
        availability=availability,
        effectiveness=effectiveness,
        motion_active=(
            process_motion_allowed
            and feedback_on
            and effectiveness > 0.0
            and not unavailable
        ),
        verification_status=_verification_status(snapshot, asset_id),
    )


def _hydraulic_projection(
    snapshot: RuntimeSnapshot | Mapping[str, Any],
) -> tuple[dict[str, float], str, tuple[str, ...]]:
    hydraulics = _get(snapshot, "hydraulics", {}) or {}
    modeled = bool(_get(hydraulics, "per_route_flow_modeled", False))
    routes = _get(hydraulics, "routes", {}) or {}
    if not modeled or not isinstance(routes, Mapping):
        return {}, "UNAVAILABLE", ("NO_PER_ROUTE_FLOW_METERING",)

    route_flows = {
        str(route_id): max(
            0.0,
            _number(_get(route_state, "effective_flow_l_min", 0.0)),
        )
        for route_id, route_state in routes.items()
    }
    provenance = _text(
        _get(hydraulics, "profile_provenance"),
        "MODELED",
    )
    return (
        route_flows,
        provenance,
        ("PER_ROUTE_FLOW_MODELED_NOT_PHYSICALLY_METERED",),
    )


def _filtration_projection(
    snapshot: RuntimeSnapshot | Mapping[str, Any],
) -> tuple[MechanicalFiltrationVisualState, tuple[str, ...], float | None]:
    hydraulics = _get(snapshot, "hydraulics", {}) or {}
    filtration = _get(hydraulics, "mechanical_filtration", {}) or {}
    configured = bool(_get(filtration, "configured", False))
    if not configured:
        return (
            MechanicalFiltrationVisualState(
                configured=False,
                provenance="UNAVAILABLE",
                filtered_route_id=None,
                captured_solids_g=None,
                suspended_solids_g=None,
                loading_fraction=None,
                process_throughput_factor=None,
                tss_mg_l=None,
                turbidity_ntu=None,
                water_clarity_conclusion="NOT_ESTABLISHED",
            ),
            ("NO_QUANTITATIVE_WASTE_OR_SLUDGE_MODEL",),
            None,
        )

    limitations: list[str] = []
    if _get(filtration, "tss_mg_l") is None:
        limitations.append("TSS_UNAVAILABLE")
    if _get(filtration, "turbidity_ntu") is None:
        limitations.append("TURBIDITY_UNAVAILABLE_NO_GOVERNED_BASIS")
    discharge_rate = _optional_number(
        _get(filtration, "backwash_discharge_flow_l_min")
    )
    if discharge_rate is None:
        limitations.append("BACKWASH_DISCHARGE_RATE_UNAVAILABLE")

    return (
        MechanicalFiltrationVisualState(
            configured=True,
            provenance=_text(_get(filtration, "provenance"), "UNAVAILABLE"),
            filtered_route_id=_get(filtration, "filtered_route_id"),
            captured_solids_g=_optional_number(
                _get(filtration, "captured_solids_g")
            ),
            suspended_solids_g=_optional_number(
                _get(filtration, "suspended_solids_g")
            ),
            loading_fraction=_optional_number(_get(filtration, "loading_fraction")),
            process_throughput_factor=_optional_number(
                _get(filtration, "process_throughput_factor")
            ),
            tss_mg_l=_optional_number(_get(filtration, "tss_mg_l")),
            turbidity_ntu=_optional_number(_get(filtration, "turbidity_ntu")),
            water_clarity_conclusion=_text(
                _get(filtration, "water_clarity_conclusion"),
                "NOT_ESTABLISHED",
            ),
        ),
        tuple(limitations),
        discharge_rate,
    )


def project_process_visual(
    snapshot: RuntimeSnapshot | Mapping[str, Any],
) -> ProcessVisualState:
    """Project canonical runtime truth into renderer-ready process state."""

    pond = _get(snapshot, "pond_truth", {}) or {}
    operating = _get(snapshot, "operating_status", {}) or {}
    classification = _get(snapshot, "classification", {}) or {}

    total_flow = max(0.0, _number(_get(pond, "circulation_flow_l_min", 0.0)))
    primary_pump = _asset_path(
        snapshot,
        "main_pump",
        process_motion_allowed=total_flow > 0.0,
    )
    backup_pump = _asset_path(
        snapshot,
        "backup_pump",
        process_motion_allowed=total_flow > 0.0,
    )
    active_routes = tuple(
        path.asset_id
        for path in (primary_pump, backup_pump)
        if path.motion_active
    )
    route_flows, route_provenance, route_limitations = _hydraulic_projection(snapshot)

    primary_aerator = _asset_path(
        snapshot,
        "primary_aerator",
        process_motion_allowed=True,
    )
    backup_aerator = _asset_path(
        snapshot,
        "backup_aerator",
        process_motion_allowed=True,
    )
    active_aeration = tuple(
        path.asset_id
        for path in (primary_aerator, backup_aerator)
        if path.motion_active
    )

    top_up = _asset_path(snapshot, "top_up_valve", process_motion_allowed=True)
    drain = _asset_path(snapshot, "drain_valve", process_motion_allowed=True)
    backwash = _asset_path(snapshot, "backwash_valve", process_motion_allowed=True)

    if top_up.motion_active and drain.motion_active:
        expected_direction = "MIXED_INFLOW_OUTFLOW"
    elif top_up.motion_active:
        expected_direction = "RISING_EXPECTED"
    elif drain.motion_active:
        expected_direction = "FALLING_EXPECTED"
    elif backwash.motion_active:
        expected_direction = "FALLING_IF_BACKWASH_DISCHARGE_QUANTIFIED"
    else:
        expected_direction = "NO_ACTIVE_FILL_DRAIN_COMMAND"

    if drain.motion_active and backwash.motion_active:
        discharge_kind = "DRAIN_AND_BACKWASH"
    elif backwash.motion_active:
        discharge_kind = "BACKWASH"
    elif drain.motion_active:
        discharge_kind = "DRAIN"
    else:
        discharge_kind = "NONE"

    filtration, filtration_limitations, configured_backwash_rate = (
        _filtration_projection(snapshot)
    )
    quantitative_backwash_rate = (
        configured_backwash_rate * backwash.effectiveness
        if backwash.motion_active and configured_backwash_rate is not None
        else None
    )

    alarms = _get(snapshot, "alarms", ()) or ()
    active_alarm_codes = tuple(
        _text(_get(alarm, "code"), "")
        for alarm in alarms
        if _text(_get(alarm, "lifecycle"), "") != "RESOLVED"
    )

    return ProcessVisualState(
        schema_version=2,
        source="CANONICAL_RUNTIME_SNAPSHOT",
        run_id=_text(_get(snapshot, "run_id"), ""),
        timestamp=_text(_get(snapshot, "timestamp"), ""),
        simulation_paused=bool(_get(snapshot, "simulation_paused", False)),
        simulation_acceleration=_number(
            _get(snapshot, "simulation_acceleration", 1.0),
            1.0,
        ),
        classification=_text(_get(classification, "state")),
        operating_mode=_text(_get(snapshot, "operating_mode")),
        operating_phase=_text(_get(operating, "phase")),
        dissolved_oxygen_mg_l=max(
            0.0,
            _number(_get(pond, "dissolved_oxygen_mg_l", 0.0)),
        ),
        circulation=CirculationVisualState(
            measured_total_flow_l_min=total_flow,
            flow_motion_active=bool(active_routes) and total_flow > 0.0,
            primary=primary_pump,
            backup=backup_pump,
            active_route_ids=active_routes,
            modeled_route_flows_l_min=route_flows,
            route_flow_provenance=route_provenance,
        ),
        aeration=AerationVisualState(
            primary=primary_aerator,
            backup=backup_aerator,
            active_source_ids=active_aeration,
        ),
        water_management=WaterManagementVisualState(
            water_level_pct=max(
                0.0,
                min(100.0, _number(_get(pond, "water_level_pct", 0.0))),
            ),
            top_up=top_up,
            drain=drain,
            backwash=backwash,
            expected_level_direction=expected_direction,
            discharge_kind=discharge_kind,
            quantitative_discharge_rate_l_min=quantitative_backwash_rate,
        ),
        mechanical_filtration=filtration,
        active_alarm_codes=active_alarm_codes,
        limitations=(*route_limitations, *filtration_limitations),
    )
