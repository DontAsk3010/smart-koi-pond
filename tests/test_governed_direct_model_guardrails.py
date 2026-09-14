from types import SimpleNamespace

import pytest

from smart_koi_pond.dashboard.app import build_integrated_virtual_runtime
from smart_koi_pond.digital_twin.hydraulics import PondDesignProfile
from smart_koi_pond.digital_twin.water_exchange import WaterExchangePondModel
from smart_koi_pond.domain.enums import AvailabilityState
from smart_koi_pond.governance.reconfiguration import ConfigurationTransactionState


def pond_profile(revision: str = "direct-model-r1") -> PondDesignProfile:
    return PondDesignProfile.from_dict(
        {
            "profile_id": "direct-model-governance-test",
            "revision": revision,
            "effective_volume_l": 12_000.0,
            "circulation_turnovers_per_hour_guide": 1.0,
            "biomass_kg": 20.0,
            "feed_kg_per_day": 0.4,
            "provenance": "USER_CONFIGURED_SCENARIO",
            "routes": [
                {
                    "route_id": "main-circulation",
                    "asset_id": "main_pump",
                    "rated_flow_l_min": 240.0,
                    "role": "PRIMARY",
                    "base_throughput_factor": 1.0,
                    "provenance": "USER_CONFIGURED_SCENARIO",
                },
                {
                    "route_id": "backup-circulation",
                    "asset_id": "backup_pump",
                    "rated_flow_l_min": 220.0,
                    "role": "BACKUP",
                    "base_throughput_factor": 1.0,
                    "provenance": "USER_CONFIGURED_SCENARIO",
                },
            ],
        }
    )


def _precheck_event_count(runtime) -> int:
    return sum(event.code == "CONFIG_TRANSACTION_PRECHECK" for event in runtime.events.events)


def test_direct_model_design_profile_is_governed_without_replacing_concrete_model() -> None:
    runtime = build_integrated_virtual_runtime()
    assert isinstance(runtime.model, WaterExchangePondModel)
    parent = runtime.change_control.active_configuration_version
    prechecks = _precheck_event_count(runtime)

    runtime.model.configure_design_profile(pond_profile())

    tx = runtime.change_control.last_transaction
    assert tx is not None
    assert tx.scope == "POND_DESIGN_PROFILE"
    assert tx.parent_version == parent
    assert tx.state == ConfigurationTransactionState.LAST_GOOD
    assert runtime.change_control.active_configuration_version == tx.candidate_version
    assert runtime.change_control.last_good_configuration_version == tx.candidate_version
    assert _precheck_event_count(runtime) == prechecks + 1
    assert isinstance(runtime.model, WaterExchangePondModel)


def test_runtime_design_profile_wrapper_uses_exactly_one_governed_transaction() -> None:
    runtime = build_integrated_virtual_runtime()
    prechecks = _precheck_event_count(runtime)

    runtime.configure_design_profile(pond_profile(), actor="test-engineer")

    tx = runtime.change_control.last_transaction
    assert tx is not None
    assert tx.scope == "POND_DESIGN_PROFILE"
    assert tx.actor == "test-engineer"
    assert tx.state == ConfigurationTransactionState.LAST_GOOD
    assert _precheck_event_count(runtime) == prechecks + 1


def test_direct_model_hydraulic_restriction_is_governed_and_preflighted() -> None:
    runtime = build_integrated_virtual_runtime()
    runtime.model.configure_design_profile(pond_profile())
    parent = runtime.change_control.active_configuration_version
    prechecks = _precheck_event_count(runtime)

    runtime.model.set_hydraulic_restriction("main-circulation", 0.75)

    tx = runtime.change_control.last_transaction
    assert tx is not None
    assert tx.scope == "HYDRAULIC_RESTRICTION:main-circulation"
    assert tx.parent_version == parent
    assert tx.state == ConfigurationTransactionState.LAST_GOOD
    assert runtime.model.hydraulics is not None
    assert runtime.model.hydraulics.route_restriction("main-circulation") == 0.75
    assert _precheck_event_count(runtime) == prechecks + 1

    before = runtime.model.checkpoint_state()
    active_before = runtime.change_control.active_configuration_version
    with pytest.raises(ValueError, match="preflight"):
        runtime.model.set_hydraulic_restriction("missing-route", 0.5)

    rejected = runtime.change_control.last_transaction
    assert rejected is not None
    assert rejected.scope == "HYDRAULIC_RESTRICTION:missing-route"
    assert rejected.state == ConfigurationTransactionState.REJECTED
    assert runtime.change_control.active_configuration_version == active_before
    assert runtime.model.checkpoint_state() == before


def test_chemistry_support_backup_command_does_not_fabricate_circulation_recovery() -> None:
    runtime = build_integrated_virtual_runtime()
    snapshot = SimpleNamespace(
        timestamp=runtime.clock.current,
        commands={
            "backup_pump": SimpleNamespace(
                reason="BIOFILTER_FLOW_SUPPORT",
                accepted=True,
                final_on=True,
            )
        },
        assets={
            "main_pump": SimpleNamespace(availability=AvailabilityState.AVAILABLE),
        },
        verification=[],
    )

    changed = runtime._process_circulation_recovery(snapshot)

    assert changed is False
    assert runtime.recovery_supervisor.active is None
