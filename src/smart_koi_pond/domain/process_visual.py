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


def project_process_visual(
    snapshot: RuntimeSnapshot | Mapping[str, Any],
) -> ProcessVisualState:
    """Project canonical runtime truth into renderer-ready process state.

    This projection never creates control decisions. It exposes only process motion that can
    be supported by the current runtime snapshot. Where the model does not provide a
    quantitative state (for example sludge mass or backwash discharge rate), the projection
    keeps that value unavailable rather than inventing it.
    """

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

    alarms = _get(snapshot, "alarms", ()) or ()
    active_alarm_codes = tuple(
        _text(_get(alarm, "code"), "")
        for alarm in alarms
        if _text(_get(alarm, "lifecycle"), "") != "RESOLVED"
    )

    return ProcessVisualState(
        schema_version=1,
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
            quantitative_discharge_rate_l_min=None,
        ),
        active_alarm_codes=active_alarm_codes,
        limitations=(
            "NO_QUANTITATIVE_WASTE_OR_SLUDGE_MODEL",
            "NO_PER_ROUTE_FLOW_METERING",
            "BACKWASH_DISCHARGE_RATE_NOT_MODELED",
        ),
    )
