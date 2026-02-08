import pytest
from app import create_app


@pytest.fixture
def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    app = create_app(testing=True, db_path_override=db_path)
    return app.test_client()


def test_dashboard_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.data


def test_agents_route(client):
    response = client.get("/agents")
    assert response.status_code == 200
    assert b"Agents" in response.data


def test_issues_route(client):
    response = client.get("/issues")
    assert response.status_code == 200
    assert b"Issues" in response.data


def test_nav_links_present_on_dashboard(client):
    response = client.get("/")
    html = response.data.decode()
    assert 'href="/"' in html
    assert 'href="/agents"' in html
    assert 'href="/issues"' in html


def test_dark_theme_css_loaded(client):
    response = client.get("/")
    html = response.data.decode()
    assert "style.css" in html


# --- Milestone 2: Agent Status Panel frontend tests ---


def test_dashboard_has_agent_cards_container(client):
    response = client.get("/")
    html = response.data.decode()
    assert 'id="agent-cards"' in html


def test_dashboard_has_status_filter(client):
    response = client.get("/")
    html = response.data.decode()
    assert 'id="dashboard-status-filter"' in html
    assert 'data-filter="all"' in html
    assert 'data-filter="online"' in html
    assert 'data-filter="busy"' in html
    assert 'data-filter="offline"' in html


def test_dashboard_has_agent_summary_section(client):
    response = client.get("/")
    html = response.data.decode()
    assert "Agent Status" in html
    assert "agent-summary" in html


def test_agents_page_has_table(client):
    response = client.get("/agents")
    html = response.data.decode()
    assert 'id="agent-table"' in html
    assert 'id="agent-table-body"' in html


def test_agents_table_has_correct_columns(client):
    response = client.get("/agents")
    html = response.data.decode()
    for col in ["Name", "Role", "Status", "Current Task", "Last Active", "Uptime"]:
        assert col in html


def test_agents_page_has_status_filter(client):
    response = client.get("/agents")
    html = response.data.decode()
    assert 'id="agents-status-filter"' in html
    assert 'data-filter="all"' in html
    assert 'data-filter="online"' in html
    assert 'data-filter="error"' in html


def test_agents_page_has_loading_message(client):
    response = client.get("/agents")
    html = response.data.decode()
    assert "Loading agents..." in html


def test_dashboard_js_loaded(client):
    response = client.get("/")
    html = response.data.decode()
    assert "dashboard.js" in html


def test_dashboard_loading_message(client):
    response = client.get("/")
    html = response.data.decode()
    assert "Loading agents..." in html


def test_agents_table_wrapped_for_mobile(client):
    response = client.get("/agents")
    html = response.data.decode()
    assert "table-wrap" in html


# --- Terminal live view section ---


def test_agents_page_has_terminal_section(client):
    response = client.get("/agents")
    html = response.data.decode()
    assert 'id="terminal-section"' in html
    assert "Live Terminal Output" in html


def test_agents_page_has_terminal_grid(client):
    response = client.get("/agents")
    html = response.data.decode()
    assert 'id="terminal-grid"' in html


# --- WORKING.md display in agent cards ---


def test_dashboard_js_has_working_md_fetch(client):
    """dashboard.js should contain the fetchWorkingMd function."""
    response = client.get("/static/js/dashboard.js")
    js = response.data.decode()
    assert "fetchWorkingMd" in js
    assert "/working" in js


def test_css_has_working_styles(client):
    """style.css should include working display styles."""
    response = client.get("/static/css/style.css")
    css = response.data.decode()
    assert ".agent-working" in css
    assert ".agent-working-label" in css


def test_dashboard_js_renders_working_container(client):
    """dashboard.js should render working-<id> containers in agent cards."""
    response = client.get("/static/js/dashboard.js")
    js = response.data.decode()
    assert "working-" in js
    assert "agent-working" in js


def test_dashboard_js_uses_content_html(client):
    """dashboard.js should use content_html for rendered markdown."""
    response = client.get("/static/js/dashboard.js")
    js = response.data.decode()
    assert "content_html" in js
    assert "working-md-rendered" in js


def test_css_has_rendered_markdown_styles(client):
    """style.css should include styles for rendered markdown."""
    response = client.get("/static/css/style.css")
    css = response.data.decode()
    assert ".working-md-rendered" in css
    assert ".working-md-rendered h2" in css
    assert ".working-md-rendered strong" in css


class TestHeartbeatToggleUI:
    def test_dashboard_shows_heartbeat_badge_by_default(self, client):
        """Default dashboard should show heartbeat as read-only badge, no toggle button."""
        resp = client.get("/")
        html = resp.data.decode()
        assert 'id="heartbeat-badge"' in html
        assert 'id="toggle-btn"' not in html

    def test_dashboard_shows_toggle_with_admin_param(self, client):
        """Dashboard with correct admin param should include interactive toggle."""
        resp = client.get("/?admin=test-admin-key")
        html = resp.data.decode()
        assert 'data-admin-mode="true"' in html
        assert 'id="toggle-btn"' in html
        assert 'id="heartbeat-badge"' in html

    def test_dashboard_no_toggle_with_wrong_admin_param(self, client):
        """Dashboard with wrong admin param should NOT show toggle."""
        resp = client.get("/?admin=wrong-key")
        html = resp.data.decode()
        assert 'data-admin-mode' not in html
        assert 'id="toggle-btn"' not in html
