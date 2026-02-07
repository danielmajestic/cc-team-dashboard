import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from models import get_db_connection


@pytest.fixture
def app(tmp_path):
    """Create app with a temp file DB so connections share state."""
    db_path = str(tmp_path / "test.db")
    app = create_app(testing=True, db_path_override=db_path)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


# --- POST /api/agents/register ---

class TestRegisterAgent:
    def test_register_new_agent(self, client):
        resp = client.post("/api/agents/register", json={
            "name": "kat",
            "role": "backend",
            "status": "online"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "kat"
        assert data["role"] == "backend"
        assert data["status"] == "online"
        assert "id" in data

    def test_register_updates_existing_agent(self, client):
        client.post("/api/agents/register", json={
            "name": "kat",
            "role": "backend",
            "status": "online"
        })
        resp = client.post("/api/agents/register", json={
            "name": "kat",
            "role": "backend",
            "status": "idle"
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "idle"

    def test_register_missing_name_returns_400(self, client):
        resp = client.post("/api/agents/register", json={
            "role": "backend",
            "status": "online"
        })
        assert resp.status_code == 400

    def test_register_missing_body_returns_400(self, client):
        resp = client.post("/api/agents/register",
                           content_type="application/json",
                           data="{}")
        assert resp.status_code == 400

    def test_register_defaults_status_to_online(self, client):
        resp = client.post("/api/agents/register", json={
            "name": "sam",
            "role": "frontend"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "online"

    def test_register_defaults_role_to_empty(self, client):
        resp = client.post("/api/agents/register", json={
            "name": "mat"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["role"] == ""


# --- POST /api/agents/<id>/heartbeat ---

class TestHeartbeat:
    def _register(self, client, name="kat"):
        resp = client.post("/api/agents/register", json={
            "name": name,
            "role": "backend",
            "status": "online"
        })
        return resp.get_json()

    def test_heartbeat_updates_last_active(self, client):
        agent = self._register(client)
        resp = client.post(f"/api/agents/{agent['id']}/heartbeat")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "online"
        assert "last_active" in data

    def test_heartbeat_nonexistent_agent_returns_404(self, client):
        resp = client.post("/api/agents/9999/heartbeat")
        assert resp.status_code == 404

    def test_heartbeat_accepts_optional_status(self, client):
        agent = self._register(client)
        resp = client.post(f"/api/agents/{agent['id']}/heartbeat",
                           json={"status": "idle"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "idle"

    def test_heartbeat_accepts_optional_current_task(self, client):
        agent = self._register(client)
        resp = client.post(f"/api/agents/{agent['id']}/heartbeat",
                           json={"current_task": "working on issue #7"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["current_task"] == "working on issue #7"


# --- GET /api/agents ---

class TestListAgents:
    def test_list_empty(self, client):
        resp = client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_list_returns_registered_agents(self, client):
        client.post("/api/agents/register", json={
            "name": "kat", "role": "backend", "status": "online"
        })
        client.post("/api/agents/register", json={
            "name": "sam", "role": "frontend", "status": "idle"
        })
        resp = client.get("/api/agents")
        data = resp.get_json()
        assert len(data) == 2
        names = [a["name"] for a in data]
        assert "kat" in names
        assert "sam" in names

    def test_list_includes_role_field(self, client):
        client.post("/api/agents/register", json={
            "name": "kat", "role": "backend"
        })
        resp = client.get("/api/agents")
        data = resp.get_json()
        assert data[0]["role"] == "backend"


# --- Heartbeat timeout logic ---

class TestHeartbeatTimeout:
    def test_agent_marked_offline_after_timeout(self, app, client):
        """Agent with stale last_active should be marked offline."""
        resp = client.post("/api/agents/register", json={
            "name": "stale-agent", "role": "backend", "status": "online"
        })
        agent = resp.get_json()

        # Manually backdate last_active to 120 seconds ago
        from datetime import datetime, timezone, timedelta
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
        with app.app_context():
            conn = get_db_connection(app.config["DATABASE_PATH"])
            conn.execute(
                "UPDATE agents SET last_active = ? WHERE id = ?",
                (stale_time, agent["id"])
            )
            conn.commit()
            conn.close()

        # GET /api/agents should show this agent as offline
        resp = client.get("/api/agents")
        data = resp.get_json()
        stale = [a for a in data if a["name"] == "stale-agent"][0]
        assert stale["status"] == "offline"

    def test_fresh_agent_stays_online(self, client):
        """Agent with recent heartbeat should remain online."""
        client.post("/api/agents/register", json={
            "name": "fresh-agent", "role": "backend", "status": "online"
        })
        resp = client.get("/api/agents")
        data = resp.get_json()
        fresh = [a for a in data if a["name"] == "fresh-agent"][0]
        assert fresh["status"] == "online"


# --- GET /api/agents/<name>/terminal ---

class TestTerminalEndpoint:
    def test_terminal_returns_tmux_output(self, client):
        """Should return captured tmux pane output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "$ python app.py\nRunning on port 5000\n"

        with patch("app.subprocess.run", return_value=mock_result) as mock_run:
            resp = client.get("/api/agents/sam/terminal")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["name"] == "sam"
            assert "Running on port 5000" in data["output"]
            mock_run.assert_called_once_with(
                ["tmux", "capture-pane", "-p", "-t", "sam", "-S", "-30"],
                capture_output=True, text=True, timeout=5
            )

    def test_terminal_session_not_found(self, client):
        """Should return 404 when tmux session doesn't exist."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "can't find session: noagent"

        with patch("app.subprocess.run", return_value=mock_result):
            resp = client.get("/api/agents/noagent/terminal")
            assert resp.status_code == 404
            data = resp.get_json()
            assert "error" in data

    def test_terminal_invalid_name_returns_400(self, client):
        """Should reject names with special characters."""
        resp = client.get("/api/agents/$(whoami)/terminal")
        assert resp.status_code == 400

    def test_terminal_tmux_not_installed(self, client):
        """Should return 500 when tmux is not available."""
        with patch("app.subprocess.run", side_effect=FileNotFoundError):
            resp = client.get("/api/agents/sam/terminal")
            assert resp.status_code == 500
            data = resp.get_json()
            assert "tmux is not installed" in data["error"]

    def test_terminal_tmux_timeout(self, client):
        """Should return 500 when tmux command hangs."""
        import subprocess
        with patch("app.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="tmux", timeout=5)):
            resp = client.get("/api/agents/sam/terminal")
            assert resp.status_code == 500
            data = resp.get_json()
            assert "timed out" in data["error"]
