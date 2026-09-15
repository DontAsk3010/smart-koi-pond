from smart_koi_pond.dashboard.owner_operational_cockpit_ui import (
    OWNER_OPERATIONAL_COCKPIT_SCRIPT,
    OWNER_OPERATIONAL_COCKPIT_STYLE,
)
from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def test_owner_overview_contains_integrated_operational_cockpit() -> None:
    html = COMPOSED_INDEX_HTML
    assert 'id="owner-operational-cockpit-style"' in html
    assert "cockpit.id='ownerOperationalCockpit'" in html
    assert "Live Pond & Process" in html
    assert "Key Parameters" in html
    assert "Active Alarms" in html
    assert "Device Status" in html
    assert "Recent Events" in html
    assert "Quick Scenario & Recovery" in html


def test_primary_and_backup_takeover_are_visually_distinct() -> None:
    script = OWNER_OPERATIONAL_COCKPIT_SCRIPT
    style = OWNER_OPERATIONAL_COCKPIT_STYLE
    assert "PRIMARY CIRCULATION" in script
    assert "BACKUP CIRCULATION" in script
    assert "pathState(primary)" in script
    assert "pathState(backup)" in script
    assert ".oc-route.failed" in style
    assert ".oc-route.backup.active" in style


def test_cockpit_quick_controls_use_existing_governed_commands() -> None:
    script = OWNER_OPERATIONAL_COCKPIT_SCRIPT
    main_fault = (
        "sendCommand('inject_actuator_fault',"
        "{asset_id:'main_pump',mode:'failed_off'},'engineering')"
    )
    main_repair = (
        "sendCommand('clear_actuator_fault',{asset_id:'main_pump'},'engineering')"
    )
    do_fault = (
        "sendCommand('inject_sensor_fault',"
        "{sensor_id:'do',mode:'dropout'},'engineering')"
    )
    assert main_fault in script
    assert main_repair in script
    assert "sendCommand('start_blackout'" in script
    assert "sendCommand('restore_power',{},'operator')" in script
    assert do_fault in script
    assert "sendCommand('clear_sensor_fault',{sensor_id:'do'},'engineering')" in script
    assert "sendCommand('return_to_auto',{},'operator')" in script
    assert "sendCommand('set_acceleration'" in script


def test_cockpit_does_not_create_second_transport_or_fake_health_score() -> None:
    script = OWNER_OPERATIONAL_COCKPIT_SCRIPT
    assert "fetch('/api/command'" not in script
    assert "new WebSocket" not in script
    assert "Pond Health Index" not in script
    assert ">92<" not in script


def test_owner_navigation_leads_with_overview_cockpit() -> None:
    html = COMPOSED_INDEX_HTML
    overview_label = "overview:['Overview'"
    process_label = "process:['Pond Schematic'"
    order = (
        "const ORDER=['overview','process','trends','simulator',"
        "'logic','events','integrated']"
    )
    assert overview_label in html
    assert process_label in html
    assert order in html
