from smart_koi_pond.scenarios.integrated_virtual_pond_matrix import matrix_payload


def test_final_integrated_virtual_acceptance_matrix_covers_all_hardening_surfaces() -> None:
    payload = matrix_payload()
    references = {case["test_reference"] for case in payload["cases"]}

    assert payload["schema_version"] == 2
    assert payload["acceptance_revision"] == "FINAL_INTEGRATED_VIRTUAL_ACCEPTANCE_V2"
    assert payload["integrated_virtual_pond_gate"] == "PASS"
    assert payload["pass_count"] == 17
    assert payload["hold_count"] == 0
    assert payload["physical_validation_claimed"] is False
    assert payload["real_actuation_authorized"] is False
    assert payload["high_risk_automatic_chemical_dosing_authorized"] is False
    assert payload["hidden_engineering_defaults_used"] is False
    assert payload["browser_is_second_control_engine"] is False
    assert payload["historian_playback_is_read_only"] is True

    assert {
        "test_process_visual_preserves_unavailable_core_values_instead_of_false_zero",
        "test_governance_snapshot_state_is_preserved_in_historian_playback",
        "test_water_change_rejects_unqualified_source_before_drain_phase",
        "test_drilldown_reads_only_canonical_snapshot_and_loaded_event_evidence",
        "test_trend_markers_and_playback_cursor_use_canonical_time_evidence",
        "test_incident_story_is_point_in_time_and_hides_future_playback_evidence",
        "test_mechanical_process_evidence_survives_governed_backwash_and_playback",
        "test_missing_modeled_route_flow_remains_unavailable_not_false_zero",
    }.issubset(references)
