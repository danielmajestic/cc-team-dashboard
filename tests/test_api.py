import io
import json
import time
import urllib.error
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

        resp = client.post("/api/heartbeat/toggle",
                           headers={"X-API-Key": "test-admin-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is False
        assert hb_file.read_text().strip() == "off"

    def test_toggle_flips_off_to_on(self, app, client, tmp_path):
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("off\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)

        resp = client.post("/api/heartbeat/toggle",
                           headers={"X-API-Key": "test-admin-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is True
        assert hb_file.read_text().strip() == "on"

    def test_toggle_creates_file_when_missing(self, app, client, tmp_path):
        hb_file = tmp_path / ".heartbeat-active"
        app.config["HEARTBEAT_FILE"] = str(hb_file)

        resp = client.post("/api/heartbeat/toggle",
                           headers={"X-API-Key": "test-admin-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is True
        assert hb_file.read_text().strip() == "on"


class TestHeartbeatToggleAuth:
    def test_toggle_requires_api_key(self, app, client, tmp_path):
        """Toggle should reject requests without valid API key."""
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("off\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)
        app.config["DASHBOARD_API_KEY"] = "secret-key"

        resp = client.post("/api/heartbeat/toggle")
        assert resp.status_code == 403

    def test_toggle_accepts_valid_api_key_header(self, app, client, tmp_path):
        """Toggle should work with valid X-API-Key header."""
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("off\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)
        app.config["DASHBOARD_API_KEY"] = "secret-key"

        resp = client.post("/api/heartbeat/toggle",
                           headers={"X-API-Key": "secret-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is True

    def test_toggle_rejects_wrong_api_key(self, app, client, tmp_path):
        """Toggle should reject incorrect API key."""
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("off\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)
        app.config["DASHBOARD_API_KEY"] = "secret-key"

        resp = client.post("/api/heartbeat/toggle",
                           headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403

    def test_toggle_works_without_key_configured(self, app, client, tmp_path):
        """When no DASHBOARD_API_KEY is set, toggle should work without auth."""
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("off\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)
        app.config["DASHBOARD_API_KEY"] = ""

        resp = client.post("/api/heartbeat/toggle")
        assert resp.status_code == 200


# --- GET /api/activity ---

class TestActivityFeed:
    def test_activity_returns_git_commits(self, app, client):
        # Disable Slack so real messages don't crowd out mock commits
        app.config["SLACK_BOT_TOKEN"] = ""
        app.config["SLACK_CHANNELS"] = []

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "abc1234||Dan||Initial commit||2025-01-15T10:00:00+00:00\n"
            "def5678||Kat||Add models||2025-01-15T09:00:00+00:00\n"
        )

        with patch("subprocess.run", return_value=mock_result):
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

    def test_no_resolution_without_token(self, app, client):
        """When SLACK_BOT_TOKEN is empty, user IDs should pass through as-is."""
        app.config["SLACK_BOT_TOKEN"] = ""
        app.config["SLACK_CHANNELS"] = []

        # Without token, no Slack events are fetched at all
        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            resp = client.get("/api/activity")
            data = resp.get_json()
            slack_events = [e for e in data if e["type"] == "slack"]
            assert len(slack_events) == 0

    def test_handles_api_ok_false(self, app, client):
        """Should fall back to raw ID when Slack API returns ok=false."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C123"]

        slack_history = self._make_slack_response([
            {"user": "U0EEE", "text": "test", "ts": "1705312800.000"}
        ])

        error_resp_data = json.dumps({"ok": False, "error": "user_not_found"}).encode()
        error_resp = MagicMock()
        error_resp.read.return_value = error_resp_data
        error_resp.__enter__ = lambda s: s
        error_resp.__exit__ = MagicMock(return_value=False)

        def urlopen_side_effect(req, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else req.get_full_url()
            if "users.info" in url:
                return error_resp
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                slack_events = [e for e in data if e["type"] == "slack"]
                assert slack_events[0]["agent"] == "U0EEE"

    def test_bot_message_uses_bot_profile_name(self, app, client):
        """Bot messages should show bot_profile.name when users.info fails."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C123"]

        slack_history = self._make_slack_response([
            {
                "user": "U0AAA5ZK6EB",
                "text": "hello from bot",
                "ts": "1705312800.000",
                "bot_id": "B0AAN6PNC5T",
                "bot_profile": {
                    "name": "CC-Bridge",
                    "id": "B0AAN6PNC5T",
                },
            }
        ])

        def urlopen_side_effect(req, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else req.get_full_url()
            if "users.info" in url:
                import urllib.error
                raise urllib.error.URLError("missing_scope")
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                slack_events = [e for e in data if e["type"] == "slack"]
                assert len(slack_events) == 1
                assert slack_events[0]["agent"] == "CC-Bridge"

    def test_bot_message_without_bot_profile_falls_back_to_id(self, app, client):
        """Bot messages without bot_profile should fall back to raw user ID."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C123"]

        slack_history = self._make_slack_response([
            {
                "user": "U0FFF",
                "text": "orphan bot msg",
                "ts": "1705312800.000",
            }
        ])

        def urlopen_side_effect(req, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else req.get_full_url()
            if "users.info" in url:
                import urllib.error
                raise urllib.error.URLError("missing_scope")
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                slack_events = [e for e in data if e["type"] == "slack"]
                assert slack_events[0]["agent"] == "U0FFF"


# --- CC-Bridge display name inference ---

class TestCCBridgeDisplayName:
    """CC-Bridge bot messages should show team member names based on channel/text."""

    def _make_slack_response(self, messages):
        slack_resp = json.dumps({"ok": True, "messages": messages}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = slack_resp
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def _get_slack_events(self, app, client, channel_id, messages):
        """Helper: fetch activity with a CC-Bridge bot message in a given channel."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = [channel_id]

        slack_history = self._make_slack_response(messages)

        def urlopen_side_effect(req, **kwargs):
            url = req.full_url if hasattr(req, 'full_url') else req.get_full_url()
            if "users.info" in url:
                import urllib.error
                raise urllib.error.URLError("missing_scope")
            return slack_history

        with patch("app.subprocess.run",
                   return_value=MagicMock(returncode=1, stdout="")):
            with patch("urllib.request.urlopen",
                       side_effect=urlopen_side_effect):
                resp = client.get("/api/activity")
                data = resp.get_json()
                return [e for e in data if e["type"] == "slack"]

    def _bot_msg(self, text):
        return {
            "user": "U0AAA5ZK6EB", "text": text, "ts": "1705312800.000",
            "bot_id": "B0AAN6PNC5T",
            "bot_profile": {"name": "CC-Bridge", "id": "B0AAN6PNC5T"},
        }

    # --- Text signatures win over channel ---

    def test_sam_signature_in_mat_pm_shows_sam(self, app, client):
        """Sam posting in #mat-pm should show Sam, not Mat."""
        events = self._get_slack_events(
            app, client, "C0ACEGVT7CL",
            [self._bot_msg("Sam here — frontend tests all green")]
        )
        assert events[0]["agent"] == "Sam"

    def test_kat_signature_in_sam_dev_shows_kat(self, app, client):
        """Kat posting in #sam-dev should show Kat, not Sam."""
        events = self._get_slack_events(
            app, client, "C0ABVFJPM9D",
            [self._bot_msg("Kat: API endpoint is ready for you")]
        )
        assert events[0]["agent"] == "Kat"

    def test_dan_via_claude_signature_shows_dan(self, app, client):
        events = self._get_slack_events(
            app, client, "C0AC7G6S03F",
            [self._bot_msg("Looks good! — Dan (via Claude.ai)")]
        )
        assert events[0]["agent"] == "Dan"

    def test_mat_emdash_signature_shows_mat(self, app, client):
        events = self._get_slack_events(
            app, client, "C999UNKNOWN",
            [self._bot_msg("Sprint planning tomorrow — Mat \u2014 let me know")]
        )
        assert events[0]["agent"] == "Mat"

    def test_sam_here_signature_shows_sam(self, app, client):
        events = self._get_slack_events(
            app, client, "C0AC7G548CV",
            [self._bot_msg("Sam here, I need the new schema")]
        )
        assert events[0]["agent"] == "Sam"

    # --- Channel fallback when no signature ---

    def test_no_signature_in_mat_pm_falls_back_to_mat(self, app, client):
        """No signature in #mat-pm should fall back to Mat."""
        events = self._get_slack_events(
            app, client, "C0ACEGVT7CL", [self._bot_msg("task update")]
        )
        assert events[0]["agent"] == "Mat"

    def test_no_signature_in_kat_dev_falls_back_to_kat(self, app, client):
        events = self._get_slack_events(
            app, client, "C0AC7G548CV", [self._bot_msg("backend ready")]
        )
        assert events[0]["agent"] == "Kat"

    def test_no_signature_in_sam_dev_falls_back_to_sam(self, app, client):
        events = self._get_slack_events(
            app, client, "C0ABVFJPM9D", [self._bot_msg("frontend done")]
        )
        assert events[0]["agent"] == "Sam"

    # --- Fallback to CC-Bridge ---

    def test_bot_unknown_channel_no_signature_shows_cc_bridge(self, app, client):
        """CC-Bridge in unmapped channel with no signature stays CC-Bridge."""
        events = self._get_slack_events(
            app, client, "C999UNKNOWN",
            [self._bot_msg("system health check passed")]
        )
        assert events[0]["agent"] == "CC-Bridge"

    def test_non_bot_user_unaffected(self, app, client):
        """Real user messages should not be altered by inference."""
        app.config["SLACK_BOT_TOKEN"] = "xoxb-test"
        app.config["SLACK_CHANNELS"] = ["C0ACEGVT7CL"]

        slack_history = self._make_slack_response([
            {"user": "U0REALUSER", "text": "hello", "ts": "1705312800.000"}
        ])
        user_info_data = json.dumps({
            "ok": True,
            "user": {"real_name": "Alice", "profile": {"display_name": "Alice"}},
        }).encode()
        user_info = MagicMock()
        user_info.read.return_value = user_info_data
        user_info.__enter__ = lambda s: s
        user_info.__exit__ = MagicMock(return_value=False)

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
                assert slack_events[0]["agent"] == "Alice"


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


# --- GET /api/issues ---

class TestIssuesEndpoint:
    """Tests for the GitHub Issues API endpoint."""

    def _make_github_response(self, data):
        """Build a mock urlopen context manager returning JSON data."""
        resp_bytes = json.dumps(data).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = resp_bytes
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def _sample_issue(self, number=1, title="Test issue", labels=None,
                      assignee=None, pull_request=None):
        """Build a sample GitHub issue payload."""
        issue = {
            "id": 100 + number,
            "number": number,
            "title": title,
            "state": "open",
            "html_url": f"https://github.com/owner/repo/issues/{number}",
            "labels": labels or [],
            "assignee": {"login": assignee} if assignee else None,
            "created_at": "2026-02-01T10:00:00Z",
            "updated_at": "2026-02-08T10:00:00Z",
        }
        if pull_request is not None:
            issue["pull_request"] = pull_request
        return issue

    def test_issues_returns_empty_without_token(self, app, client):
        """Should return empty list when GITHUB_TOKEN is not set."""
        app.config["GITHUB_TOKEN"] = ""
        app.config["GITHUB_REPOS"] = ["owner/repo"]
        # Reset cache
        resp = client.get("/api/issues")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == []

    def test_issues_returns_mapped_issues(self, app, client):
        """Should return issues with correct column mapping."""
        app.config["GITHUB_TOKEN"] = "test-token"
        app.config["GITHUB_REPOS"] = ["owner/repo"]

        issues_data = [
            self._sample_issue(1, "Bug fix", labels=[{"name": "in progress"}]),
            self._sample_issue(2, "New feature", assignee="alice"),
            self._sample_issue(3, "Unassigned task"),
        ]
        mock_resp = self._make_github_response(issues_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get("/api/issues")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data) == 3

            columns = {d["title"]: d["column"] for d in data}
            assert columns["Bug fix"] == "In Progress"
            assert columns["New feature"] == "Assigned"
            assert columns["Unassigned task"] == "Inbox"

    def test_issues_skips_pull_requests(self, app, client):
        """Should filter out pull requests from results."""
        app.config["GITHUB_TOKEN"] = "test-token"
        app.config["GITHUB_REPOS"] = ["owner/repo"]

        issues_data = [
            self._sample_issue(1, "Real issue"),
            self._sample_issue(2, "A PR", pull_request={"url": "https://..."}),
        ]
        mock_resp = self._make_github_response(issues_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get("/api/issues")
            data = resp.get_json()
            assert len(data) == 1
            assert data[0]["title"] == "Real issue"

    def test_issues_maps_review_labels(self, app, client):
        """Should map review-related labels to Review column."""
        app.config["GITHUB_TOKEN"] = "test-token"
        app.config["GITHUB_REPOS"] = ["owner/repo"]

        issues_data = [
            self._sample_issue(1, "Needs review", labels=[{"name": "review"}]),
            self._sample_issue(2, "In review", labels=[{"name": "needs review"}]),
        ]
        mock_resp = self._make_github_response(issues_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get("/api/issues")
            data = resp.get_json()
            assert all(d["column"] == "Review" for d in data)

    def test_issues_maps_done_labels(self, app, client):
        """Should map done-related labels to Done column."""
        app.config["GITHUB_TOKEN"] = "test-token"
        app.config["GITHUB_REPOS"] = ["owner/repo"]

        issues_data = [
            self._sample_issue(1, "Completed task", labels=[{"name": "done"}]),
        ]
        mock_resp = self._make_github_response(issues_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get("/api/issues")
            data = resp.get_json()
            assert data[0]["column"] == "Done"

    def test_issues_includes_labels_list(self, app, client):
        """Should include label objects with name and color in response."""
        app.config["GITHUB_TOKEN"] = "test-token"
        app.config["GITHUB_REPOS"] = ["owner/repo"]

        issues_data = [
            self._sample_issue(1, "Labeled", labels=[
                {"name": "bug", "color": "d73a4a"},
                {"name": "in progress", "color": "0075ca"}
            ]),
        ]
        mock_resp = self._make_github_response(issues_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get("/api/issues")
            data = resp.get_json()
            label_names = [l["name"] for l in data[0]["labels"]]
            assert "bug" in label_names
            assert "in progress" in label_names
            assert data[0]["labels"][0]["color"] == "d73a4a"

    def test_issues_includes_repo_name(self, app, client):
        """Should include repo full name in response."""
        app.config["GITHUB_TOKEN"] = "test-token"
        app.config["GITHUB_REPOS"] = ["owner/myrepo"]

        issues_data = [self._sample_issue(1, "Test")]
        mock_resp = self._make_github_response(issues_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get("/api/issues")
            data = resp.get_json()
            assert data[0]["repo"] == "owner/myrepo"

    def test_issues_caches_results(self, app, client):
        """Should cache results and not re-fetch within TTL."""
        app.config["GITHUB_TOKEN"] = "test-token"
        app.config["GITHUB_REPOS"] = ["owner/repo"]
        app.config["ISSUE_REFRESH_INTERVAL"] = 300

        issues_data = [self._sample_issue(1, "Cached issue")]
        mock_resp = self._make_github_response(issues_data)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_url:
            # First call - fetches from API
            resp1 = client.get("/api/issues")
            assert resp1.status_code == 200
            call_count_1 = mock_url.call_count

            # Second call - should use cache
            resp2 = client.get("/api/issues")
            assert resp2.status_code == 200
            assert mock_url.call_count == call_count_1  # no new calls

            data = resp2.get_json()
            assert len(data) == 1
            assert data[0]["title"] == "Cached issue"

    def test_issues_handles_github_api_error(self, app, client):
        """Should return empty list on GitHub API failure."""
        app.config["GITHUB_TOKEN"] = "test-token"
        app.config["GITHUB_REPOS"] = ["owner/repo"]

        with patch("urllib.request.urlopen",
                   side_effect=urllib.error.URLError("network error")):
            resp = client.get("/api/issues")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data == []

    def test_issues_response_fields(self, app, client):
        """Should include all expected fields in issue objects."""
        app.config["GITHUB_TOKEN"] = "test-token"
        app.config["GITHUB_REPOS"] = ["owner/repo"]

        issues_data = [
            self._sample_issue(42, "Complete issue", assignee="bob",
                              labels=[{"name": "in progress"}]),
        ]
        mock_resp = self._make_github_response(issues_data)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get("/api/issues")
            data = resp.get_json()
            issue = data[0]
            assert issue["number"] == 42
            assert issue["title"] == "Complete issue"
            assert issue["assignee"] == "bob"
            assert issue["column"] == "In Progress"
            assert issue["repo"] == "owner/repo"
            assert "url" in issue
            assert "created_at" in issue
            assert "updated_at" in issue


# --- GET /api/dispatch/status ---

class TestDispatchStatus:
    def test_status_returns_on(self, app, client, tmp_path):
        dispatch_file = tmp_path / "dispatch-enabled.txt"
        dispatch_file.write_text("on\n")
        app.config["DISPATCH_FILE"] = str(dispatch_file)

        resp = client.get("/api/dispatch/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "on"

    def test_status_returns_off(self, app, client, tmp_path):
        dispatch_file = tmp_path / "dispatch-enabled.txt"
        dispatch_file.write_text("off\n")
        app.config["DISPATCH_FILE"] = str(dispatch_file)

        resp = client.get("/api/dispatch/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "off"

    def test_status_returns_off_when_file_missing(self, app, client, tmp_path):
        app.config["DISPATCH_FILE"] = str(tmp_path / "nonexistent")

        resp = client.get("/api/dispatch/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "off"


# --- POST /api/dispatch/toggle ---

class TestDispatchToggle:
    def test_toggle_flips_on_to_off(self, app, client, tmp_path):
        dispatch_file = tmp_path / "dispatch-enabled.txt"
        dispatch_file.write_text("on\n")
        app.config["DISPATCH_FILE"] = str(dispatch_file)

        resp = client.post("/api/dispatch/toggle",
                           headers={"X-API-Key": "test-admin-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "off"
        assert dispatch_file.read_text().strip() == "off"

    def test_toggle_flips_off_to_on(self, app, client, tmp_path):
        dispatch_file = tmp_path / "dispatch-enabled.txt"
        dispatch_file.write_text("off\n")
        app.config["DISPATCH_FILE"] = str(dispatch_file)

        resp = client.post("/api/dispatch/toggle",
                           headers={"X-API-Key": "test-admin-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "on"
        assert dispatch_file.read_text().strip() == "on"

    def test_toggle_creates_file_when_missing(self, app, client, tmp_path):
        dispatch_file = tmp_path / "dispatch-enabled.txt"
        app.config["DISPATCH_FILE"] = str(dispatch_file)

        resp = client.post("/api/dispatch/toggle",
                           headers={"X-API-Key": "test-admin-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "on"
        assert dispatch_file.read_text().strip() == "on"

    def test_toggle_requires_api_key(self, app, client, tmp_path):
        dispatch_file = tmp_path / "dispatch-enabled.txt"
        dispatch_file.write_text("off\n")
        app.config["DISPATCH_FILE"] = str(dispatch_file)
        app.config["DASHBOARD_API_KEY"] = "secret-key"

        resp = client.post("/api/dispatch/toggle")
        assert resp.status_code == 403

    def test_toggle_rejects_wrong_api_key(self, app, client, tmp_path):
        dispatch_file = tmp_path / "dispatch-enabled.txt"
        dispatch_file.write_text("off\n")
        app.config["DISPATCH_FILE"] = str(dispatch_file)
        app.config["DASHBOARD_API_KEY"] = "secret-key"

        resp = client.post("/api/dispatch/toggle",
                           headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 403


# --- Heartbeat toggle syncs dispatch ---

class TestHeartbeatSyncsDispatch:
    def test_heartbeat_toggle_also_updates_dispatch(self, app, client, tmp_path):
        """Toggling heartbeat should also update dispatch-enabled.txt."""
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("on\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)

        dispatch_file = tmp_path / "dispatch-enabled.txt"
        dispatch_file.write_text("on\n")
        app.config["DISPATCH_FILE"] = str(dispatch_file)

        resp = client.post("/api/heartbeat/toggle",
                           headers={"X-API-Key": "test-admin-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is False

        # Dispatch file should also be "off"
        assert dispatch_file.read_text().strip() == "off"

    def test_heartbeat_toggle_on_also_enables_dispatch(self, app, client, tmp_path):
        """Toggling heartbeat on should also enable dispatch."""
        hb_file = tmp_path / ".heartbeat-active"
        hb_file.write_text("off\n")
        app.config["HEARTBEAT_FILE"] = str(hb_file)

        dispatch_file = tmp_path / "dispatch-enabled.txt"
        dispatch_file.write_text("off\n")
        app.config["DISPATCH_FILE"] = str(dispatch_file)

        resp = client.post("/api/heartbeat/toggle",
                           headers={"X-API-Key": "test-admin-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is True

        assert dispatch_file.read_text().strip() == "on"
