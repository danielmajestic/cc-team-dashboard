import io
import json
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


@pytest.fixture
def authed_client(app):
    """Test client that sends the API key header on every request."""
    client = app.test_client()
    client.environ_base = {"HTTP_X_API_KEY": "test-api-key"}
    return client


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


# --- GET /api/heartbeat/status ---

class TestHeartbeatStatus:
    def test_status_returns_active_true_when_on(self, app, client, tmp_path):
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("on\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)

        resp = client.get("/api/heartbeat/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is True

    def test_status_returns_active_false_when_off(self, app, client, tmp_path):
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("off\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)

        resp = client.get("/api/heartbeat/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is False

    def test_status_returns_false_when_file_missing(self, app, client, tmp_path):
        app.config["HEARTBEAT_FILE"] = str(tmp_path / "nonexistent")

        resp = client.get("/api/heartbeat/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is False


# --- POST /api/heartbeat/toggle ---

class TestHeartbeatToggle:
    def test_toggle_flips_on_to_off(self, app, client, tmp_path):
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("on\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)

        resp = client.post("/api/heartbeat/toggle")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is False
        assert hb_file.read_text().strip() == "off"

    def test_toggle_flips_off_to_on(self, app, client, tmp_path):
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("off\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)

        resp = client.post("/api/heartbeat/toggle")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is True
        assert hb_file.read_text().strip() == "on"

    def test_toggle_creates_file_when_missing(self, app, client, tmp_path):
        hb_file = tmp_path / ".heartbeat-active"
        app.config["HEARTBEAT_FILE"] = str(hb_file)

        resp = client.post("/api/heartbeat/toggle")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is True
        assert hb_file.read_text().strip() == "on"


# --- GET /api/activity ---

class TestActivityFeed:
    def test_activity_returns_git_commits(self, app, client):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "abc1234||Dan||Initial commit||2025-01-15T10:00:00+00:00\n"
            "def5678||Kat||Add models||2025-01-15T09:00:00+00:00\n"
        )

        with patch("app.subprocess.run", return_value=mock_result):
            resp = client.get("/api/activity")
            assert resp.status_code == 200
            data = resp.get_json()
            commits = [e for e in data if e["type"] == "commit"]
            assert len(commits) == 2
            assert "abc1234" in commits[0]["message"]
            assert commits[0]["agent"] == "Dan"

    def test_activity_returns_heartbeat_events(self, app, client):
        # Register an agent first
        client.post("/api/agents/register", json={
            "name": "kat", "role": "backend", "status": "online"
        })

        with patch("app.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            resp = client.get("/api/activity")
            assert resp.status_code == 200
            data = resp.get_json()
            heartbeats = [e for e in data if e["type"] == "heartbeat"]
            assert len(heartbeats) >= 1
            assert heartbeats[0]["agent"] == "kat"

    def test_activity_sorted_by_timestamp_desc(self, app, client):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "aaa1111||Dan||Older commit||2025-01-10T08:00:00+00:00\n"
            "bbb2222||Kat||Newer commit||2025-01-15T12:00:00+00:00\n"
        )

        with patch("app.subprocess.run", return_value=mock_result):
            resp = client.get("/api/activity")
            assert resp.status_code == 200
            data = resp.get_json()
            if len(data) >= 2:
                assert data[0]["timestamp"] >= data[1]["timestamp"]

    def test_activity_handles_git_failure(self, app, client):
        """Should return events even if git fails."""
        with patch("app.subprocess.run",
                   side_effect=FileNotFoundError):
            resp = client.get("/api/activity")
            assert resp.status_code == 200

    def test_activity_returns_max_20(self, app, client):
        lines = ""
        for i in range(25):
            lines += f"abc{i:04d}||Dan||Commit {i}||2025-01-{15 - (i % 15):02d}T10:00:00+00:00\n"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = lines

        with patch("app.subprocess.run", return_value=mock_result):
            resp = client.get("/api/activity")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data) <= 20


# --- Slack user ID resolution ---

class TestSlackUserResolution:
    def _make_slack_response(self, messages):
        """Build a mock urlopen context manager returning Slack messages."""
        slack_resp = json.dumps({
            "ok": True,
            "messages": messages,
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = slack_resp
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def _make_user_info_response(self, display_name="", real_name=""):
        """Build a mock urlopen context manager returning users.info data."""
        user_resp = json.dumps({
            "ok": True,
            "user": {
                "real_name": real_name,
                "profile": {"display_name": display_name},
            },
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = user_resp
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_resolves_user_id_to_display_name(self, app, client):
        """Slack events should show display_name instead of raw user ID."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C123"]

        slack_history = self._make_slack_response([
            {"user": "U0AAA5ZK6EB", "text": "hello", "ts": "1705312800.000"}
        ])
        user_info = self._make_user_info_response(display_name="Alice")

        def urlopen_side_effect(req, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else req.get_full_url()
            if "users.info" in url:
                return user_info
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                slack_events = [e for e in data if e["type"] == "slack"]
                assert len(slack_events) == 1
                assert slack_events[0]["agent"] == "Alice"

    def test_falls_back_to_real_name(self, app, client):
        """Should use real_name when display_name is empty."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C123"]

        slack_history = self._make_slack_response([
            {"user": "U0BBB", "text": "hi", "ts": "1705312800.000"}
        ])
        user_info = self._make_user_info_response(display_name="", real_name="Bob Smith")

        def urlopen_side_effect(req, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else req.get_full_url()
            if "users.info" in url:
                return user_info
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                slack_events = [e for e in data if e["type"] == "slack"]
                assert slack_events[0]["agent"] == "Bob Smith"

    def test_falls_back_to_raw_id_on_api_failure(self, app, client):
        """Should use raw user ID if users.info API fails."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C123"]

        slack_history = self._make_slack_response([
            {"user": "U0CCC", "text": "hey", "ts": "1705312800.000"}
        ])

        call_count = [0]

        def urlopen_side_effect(req, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else req.get_full_url()
            if "users.info" in url:
                import urllib.error
                raise urllib.error.URLError("network error")
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                slack_events = [e for e in data if e["type"] == "slack"]
                assert slack_events[0]["agent"] == "U0CCC"

    def test_caches_resolved_users(self, app, client):
        """Should only call users.info once per unique user ID."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C123"]

        slack_history = self._make_slack_response([
            {"user": "U0DDD", "text": "msg1", "ts": "1705312800.000"},
            {"user": "U0DDD", "text": "msg2", "ts": "1705312801.000"},
        ])
        user_info = self._make_user_info_response(display_name="Dave")

        urlopen_calls = []

        def urlopen_side_effect(req, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else req.get_full_url()
            urlopen_calls.append(url)
            if "users.info" in url:
                return user_info
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                slack_events = [e for e in data if e["type"] == "slack"]
                assert len(slack_events) == 2
                assert all(e["agent"] == "Dave" for e in slack_events)
                # users.info should only be called once (not twice)
                user_info_calls = [u for u in urlopen_calls if "users.info" in u]
                assert len(user_info_calls) == 1


# --- WORKING.md HTML rendering ---

class TestWorkingHtmlRendering:
    def _register(self, client, name="Kat"):
        resp = client.post("/api/agents/register", json={
            "name": name, "role": "backend", "status": "online"
        })
        return resp.get_json()

    def test_working_returns_html_content(self, app, client, tmp_path):
        """Should return content_html with rendered markdown."""
        agent = self._register(client, "Kat")
        agent_dir = tmp_path / "kat"
        agent_dir.mkdir()
        (agent_dir / "WORKING.md").write_text("## Current Task\n**Working** on issue #7\n")
        app.config["AGENTS_BASE_PATH"] = str(tmp_path)

        resp = client.get(f"/api/agents/{agent['id']}/working")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "content_html" in data
        assert "<h2>" in data["content_html"]
        assert "<strong>Working</strong>" in data["content_html"]

    def test_working_still_returns_raw_content(self, app, client, tmp_path):
        """Should still return raw content alongside HTML."""
        agent = self._register(client, "Kat")
        agent_dir = tmp_path / "kat"
        agent_dir.mkdir()
        (agent_dir / "WORKING.md").write_text("plain text")
        app.config["AGENTS_BASE_PATH"] = str(tmp_path)

        resp = client.get(f"/api/agents/{agent['id']}/working")
        data = resp.get_json()
        assert data["content"] == "plain text"
        assert "content_html" in data

    def test_working_renders_lists(self, app, client, tmp_path):
        """Should render markdown lists as HTML."""
        agent = self._register(client, "Kat")
        agent_dir = tmp_path / "kat"
        agent_dir.mkdir()
        (agent_dir / "WORKING.md").write_text("- item one\n- item two\n")
        app.config["AGENTS_BASE_PATH"] = str(tmp_path)

        resp = client.get(f"/api/agents/{agent['id']}/working")
        data = resp.get_json()
        assert "<ul>" in data["content_html"]
        assert "<li>" in data["content_html"]


# --- API key authentication for write endpoints ---

class TestApiKeyAuth:
    """Write endpoints should require X-API-Key header when DASHBOARD_API_KEY is set."""

    def test_register_rejected_without_api_key(self, app, client):
        app.config["DASHBOARD_API_KEY"] = "test-api-key"
        resp = client.post("/api/agents/register", json={
            "name": "kat", "role": "backend", "status": "online"
        })
        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data

    def test_register_rejected_with_wrong_api_key(self, app, client):
        app.config["DASHBOARD_API_KEY"] = "test-api-key"
        resp = client.post("/api/agents/register",
                           json={"name": "kat", "role": "backend"},
                           headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_register_accepted_with_correct_api_key(self, app, authed_client):
        app.config["DASHBOARD_API_KEY"] = "test-api-key"
        resp = authed_client.post("/api/agents/register", json={
            "name": "kat", "role": "backend", "status": "online"
        })
        assert resp.status_code == 201

    def test_heartbeat_rejected_without_api_key(self, app, authed_client, client):
        app.config["DASHBOARD_API_KEY"] = "test-api-key"
        # Register with auth
        resp = authed_client.post("/api/agents/register", json={
            "name": "kat", "role": "backend", "status": "online"
        })
        agent_id = resp.get_json()["id"]
        # Heartbeat without auth
        resp = client.post(f"/api/agents/{agent_id}/heartbeat")
        assert resp.status_code == 401

    def test_heartbeat_accepted_with_api_key(self, app, authed_client):
        app.config["DASHBOARD_API_KEY"] = "test-api-key"
        resp = authed_client.post("/api/agents/register", json={
            "name": "kat", "role": "backend", "status": "online"
        })
        agent_id = resp.get_json()["id"]
        resp = authed_client.post(f"/api/agents/{agent_id}/heartbeat")
        assert resp.status_code == 200

    def test_toggle_rejected_without_api_key(self, app, client):
        app.config["DASHBOARD_API_KEY"] = "test-api-key"
        resp = client.post("/api/heartbeat/toggle")
        assert resp.status_code == 401

    def test_toggle_accepted_with_api_key(self, app, authed_client, tmp_path):
        app.config["DASHBOARD_API_KEY"] = "test-api-key"
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("off\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)
        resp = authed_client.post("/api/heartbeat/toggle")
        assert resp.status_code == 200

    def test_read_endpoints_open_without_api_key(self, app, client):
        """GET endpoints should remain public even when API key is configured."""
        app.config["DASHBOARD_API_KEY"] = "test-api-key"
        # GET /api/agents should work without auth
        resp = client.get("/api/agents")
        assert resp.status_code == 200

    def test_no_auth_required_when_key_not_set(self, app, client):
        """When DASHBOARD_API_KEY is empty, write endpoints should be open."""
        app.config["DASHBOARD_API_KEY"] = ""
        resp = client.post("/api/agents/register", json={
            "name": "kat", "role": "backend", "status": "online"
        })
        assert resp.status_code == 201


# --- Slack message sanitization ---

class TestSlackMessageSanitization:
    """Slack messages in activity feed should have tokens/secrets stripped."""

    def _make_slack_response(self, messages):
        slack_resp = json.dumps({
            "ok": True,
            "messages": messages,
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = slack_resp
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_slack_token_stripped_from_messages(self, app, client):
        """Messages containing xoxb/xoxp tokens should have them redacted."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C123"]

        slack_history = self._make_slack_response([
            {"user": "unknown", "text": "token is xoxb-1234-5678-abcdef", "ts": "1705312800.000"}
        ])

        def urlopen_side_effect(req, **kwargs):
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                slack_events = [e for e in data if e["type"] == "slack"]
                assert len(slack_events) == 1
                assert "xoxb-" not in slack_events[0]["message"]

    def test_long_hex_strings_redacted(self, app, client):
        """Long hex strings that could be secrets should be redacted."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C123"]

        slack_history = self._make_slack_response([
            {"user": "unknown", "text": "key=0042a64ff953023b828368655b6f503733a25b9296e3d4f1", "ts": "1705312800.000"}
        ])

        def urlopen_side_effect(req, **kwargs):
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                slack_events = [e for e in data if e["type"] == "slack"]
                assert "0042a64ff953023b" not in slack_events[0]["message"]
