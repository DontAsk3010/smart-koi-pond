from smart_koi_pond.scenarios.visual_functional_acceptance_matrix import (
    matrix_payload,
    write_html,
    write_json,
)


def test_visual_functional_acceptance_executes_all_required_families():
    payload = matrix_payload()
    families = {case["family"][0] for case in payload["cases"]}
    assert families == set("ABCDEFG")
    assert payload["same_canonical_runtime"] is True
    assert payload["browser_is_second_control_engine"] is False
    assert payload["real_device_control_authorized"] is False
    assert payload["high_risk_automatic_chemical_dosing_authorized"] is False
    assert payload["hold_count"] == 0, [
        (case["case_id"], case["failed_checks"], case["evidence"])
        for case in payload["cases"]
        if case["status"] != "PASS"
    ]
    assert payload["overall_gate"] == "PASS"


def test_visual_report_and_json_are_human_and_machine_readable(tmp_path):
    payload = matrix_payload()
    json_path = write_json(tmp_path / "visual-functional-acceptance.json", payload)
    html_path = write_html(tmp_path / "visual-functional-acceptance.html", payload)

    json_text = json_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")
    assert "SMART_KOI_POND_VISUAL_FUNCTIONAL_ACCEPTANCE_EVIDENCE_V1" in json_text
    assert "OVERALL PASS" in html_text
    assert "Open canonical evidence chain" in html_text
    assert "Real-device authority: CLOSED" in html_text
    assert "High-risk automatic chemical dosing: CLOSED" in html_text
