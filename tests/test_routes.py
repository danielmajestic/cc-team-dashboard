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
