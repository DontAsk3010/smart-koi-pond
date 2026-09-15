from smart_koi_pond.dashboard.webapp import COMPOSED_INDEX_HTML


def test_owner_navigation_is_permanent_left_sidebar_on_desktop() -> None:
    html = COMPOSED_INDEX_HTML
    assert 'id="owner-sidebar-navigation-style"' in html
    assert "classList.add('owner-sidebar')" in html
    assert "--owner-sidebar-width:208px" in html
    assert "position:fixed;left:0;top:0;bottom:0" in html


def test_owner_sidebar_uses_existing_governed_views_only() -> None:
    html = COMPOSED_INDEX_HTML
    assert "overview:['Overview'" in html
    assert "process:['Pond Schematic'" in html
    assert "trends:['Trends & Graphs'" in html
    assert "simulator:['Scenario Simulator'" in html
    assert "logic:['Control Logic'" in html
    assert "events:['Event Log'" in html
    assert "integrated:['Settings / Configuration'" in html
    assert "canonical runtime remains authoritative" in html


def test_sidebar_does_not_add_control_api_or_second_runtime() -> None:
    html = COMPOSED_INDEX_HTML
    sidebar_start = html.index("owner-sidebar-navigation-style")
    sidebar_end = html.index("</style>", sidebar_start)
    sidebar_style = html[sidebar_start:sidebar_end]
    assert "/api/command" not in sidebar_style
    assert "sendCommand(" not in sidebar_style
