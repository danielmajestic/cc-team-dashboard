import pytest
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


# --- GET /api/agents/<id>/working ---

class TestWorkingEndpoint:
    def _register(self, client, name="Kat"):
        resp = client.post("/api/agents/register", json={
            "name": name, "role": "backend", "status": "online"
        })
        return resp.get_json()

    def test_working_returns_file_content(self, app, client, tmp_path):
        """Should return WORKING.md content for a registered agent."""
        agent = self._register(client, "Kat")

        # Create a fake WORKING.md
        agent_dir = tmp_path / "kat"
        agent_dir.mkdir()
        working_file = agent_dir / "WORKING.md"
        working_file.write_text("## Current Task\nWorking on issue #7\n")

        app.config["AGENTS_BASE_PATH"] = str(tmp_path)

        resp = client.get(f"/api/agents/{agent['id']}/working")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "content" in data
        assert "Working on issue #7" in data["content"]
        assert data["agent_name"] == "Kat"

    def test_working_nonexistent_agent_returns_404(self, client):
        """Should return 404 for unknown agent ID."""
        resp = client.get("/api/agents/9999/working")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_working_missing_file_returns_404(self, app, client, tmp_path):
        """Should return 404 if WORKING.md doesn't exist for the agent."""
        agent = self._register(client, "Kat")
        app.config["AGENTS_BASE_PATH"] = str(tmp_path)

        resp = client.get(f"/api/agents/{agent['id']}/working")
        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data

    def test_working_uses_lowercase_agent_name(self, app, client, tmp_path):
        """Should map agent name to lowercase directory."""
        agent = self._register(client, "Sam")

        agent_dir = tmp_path / "sam"
        agent_dir.mkdir()
        (agent_dir / "WORKING.md").write_text("Sam's work log")

        app.config["AGENTS_BASE_PATH"] = str(tmp_path)

        resp = client.get(f"/api/agents/{agent['id']}/working")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["content"] == "Sam's work log"
        assert data["agent_name"] == "Sam"
