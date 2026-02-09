import json
import os
import re
import subprocess
from datetime import datetime, timezone
import markdown
from flask import Flask, render_template, request, jsonify
from config import Config, TestConfig


def create_app(testing=False, db_path_override=None):
    app = Flask(__name__)

    if testing:
        app.config.from_object(TestConfig)
    else:
        app.config.from_object(Config)

    if db_path_override:
        app.config["DATABASE_PATH"] = db_path_override

    # Ensure instance folder exists
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    # Slack user ID -> display name cache
    _slack_user_cache = {}

    def resolve_slack_user(user_id, token, fallback_name=""):
        """Resolve a Slack user ID to a display name via users.info API.

        Results are cached in _slack_user_cache. Falls back to
        fallback_name (e.g. bot_profile.name) or the raw user_id.
        """
        import urllib.request
        import urllib.error

        if user_id in _slack_user_cache:
            return _slack_user_cache[user_id]

        try:
            url = f"https://slack.com/api/users.info?user={user_id}"
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            if data.get("ok"):
                profile = data["user"].get("profile", {})
                name = (profile.get("display_name")
                        or data["user"].get("real_name")
                        or user_id)
                _slack_user_cache[user_id] = name
                return name
        except (urllib.error.URLError, OSError, ValueError, KeyError):
            pass

        resolved = fallback_name or user_id
        _slack_user_cache[user_id] = resolved
        return resolved

    # Channel ID -> team member name for CC-Bridge relay messages
    _channel_agent_map = {
        "C0ACEGVT7CL": "Mat",   # #mat-pm
        "C0AC7G548CV": "Kat",   # #kat-dev
        "C0ABVFJPM9D": "Sam",   # #sam-dev
    }

    def _infer_agent_name(display_name, channel_id, text):
        """Infer team member name from CC-Bridge relay messages.

        Uses channel ID mapping and message text signatures to determine
        the actual sender. Returns display_name unchanged for non-bot messages.
        """
        if display_name != "CC-Bridge":
            return display_name

        # Check for Dan's signature in text first (works across any channel)
        if "Dan (via Claude.ai)" in text:
            return "Dan"

        # Direct channel mapping
        if channel_id in _channel_agent_map:
            return _channel_agent_map[channel_id]

        # Text-based fallback for unmapped channels (e.g. #dan-review)
        for name in ("Mat", "Kat", "Sam", "Dan"):
            if name in text:
                return name

        return "CC-Bridge"

    from models import init_db, get_db_connection

    # Initialize database
    db_conn = get_db_connection(app.config["DATABASE_PATH"])
    init_db(db_conn)
    db_conn.close()

    # --- Template routes ---

    @app.route("/")
    def dashboard():
        admin_key = request.args.get("admin", "")
        configured_key = app.config.get("DASHBOARD_API_KEY", "")
        is_admin = bool(configured_key and admin_key == configured_key)
        return render_template("dashboard.html", is_admin=is_admin)

    @app.route("/agents")
    def agents():
        return render_template("agents.html")

    @app.route("/issues")
    def issues():
        return render_template("issues.html")

    # --- API routes ---

    @app.route("/api/agents/register", methods=["POST"])
    def api_register_agent():
        from models import create_agent

        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400

        role = data.get("role", "")
        status = data.get("status", "online")

        conn = get_db_connection(app.config["DATABASE_PATH"])
        try:
            existing = conn.execute(
                "SELECT id FROM agents WHERE name = ?", (name,)
            ).fetchone()

            agent = create_agent(conn, name, role=role, status=status)
            status_code = 200 if existing else 201
            return jsonify(agent), status_code
        finally:
            conn.close()

    @app.route("/api/agents/<int:agent_id>/heartbeat", methods=["POST"])
    def api_heartbeat(agent_id):
        from models import update_heartbeat

        data = request.get_json(silent=True) or {}
        status = data.get("status")
        current_task = data.get("current_task")

        conn = get_db_connection(app.config["DATABASE_PATH"])
        try:
            agent = update_heartbeat(conn, agent_id, status=status,
                                     current_task=current_task)
            if agent is None:
                return jsonify({"error": "agent not found"}), 404
            return jsonify(agent), 200
        finally:
            conn.close()

    @app.route("/api/agents/<int:agent_id>/working", methods=["GET"])
    def api_working(agent_id):
        from models import get_agent

        conn = get_db_connection(app.config["DATABASE_PATH"])
        try:
            agent = get_agent(conn, agent_id)
            if agent is None:
                return jsonify({"error": "agent not found"}), 404
        finally:
            conn.close()

        agents_base = app.config.get(
            "AGENTS_BASE_PATH",
            os.path.expanduser("~/agents")
        )
        name_lower = agent["name"].lower()
        working_path = os.path.join(agents_base, name_lower, "WORKING.md")

        if not os.path.isfile(working_path):
            return jsonify({"error": "WORKING.md not found"}), 404

        with open(working_path, "r") as f:
            content = f.read()

        content_html = markdown.markdown(content)

        return jsonify({
            "agent_name": agent["name"],
            "content": content,
            "content_html": content_html,
        }), 200

    @app.route("/api/agents/<name>/terminal", methods=["GET"])
    def api_agent_terminal(name):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            return jsonify({"error": "invalid agent name"}), 400

        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-t", name, "-S", "-30"],
                capture_output=True, text=True, timeout=5
            )
        except FileNotFoundError:
            return jsonify({"error": "tmux is not installed"}), 500
        except subprocess.TimeoutExpired:
            return jsonify({"error": "tmux command timed out"}), 500

        if result.returncode != 0:
            return jsonify({"error": "tmux session not found",
                            "detail": result.stderr.strip()}), 404

        return jsonify({"name": name, "output": result.stdout}), 200

    @app.route("/api/agents", methods=["GET"])
    def api_list_agents():
        from models import get_all_agents, check_heartbeat_timeouts

        timeout = app.config.get("AGENT_HEARTBEAT_TIMEOUT", 60)
        conn = get_db_connection(app.config["DATABASE_PATH"])
        try:
            check_heartbeat_timeouts(conn, timeout_seconds=timeout)
            agents = get_all_agents(conn)
            return jsonify(agents), 200
        finally:
            conn.close()

    # --- Heartbeat toggle ---

    @app.route("/api/heartbeat/status", methods=["GET"])
    def api_heartbeat_status():
        hb_file = app.config.get(
            "HEARTBEAT_FILE",
            os.path.expanduser("~/agents/shared/.heartbeat-active")
        )
        try:
            with open(hb_file, "r") as f:
                state = f.read().strip().lower()
            return jsonify({"active": state == "on"}), 200
        except FileNotFoundError:
            return jsonify({"active": False}), 200

    @app.route("/api/heartbeat/toggle", methods=["POST"])
    def api_heartbeat_toggle():
        api_key = app.config.get("DASHBOARD_API_KEY", "")
        if api_key:
            provided = request.headers.get("X-API-Key", "")
            if provided != api_key:
                return jsonify({"error": "forbidden"}), 403

        hb_file = app.config.get(
            "HEARTBEAT_FILE",
            os.path.expanduser("~/agents/shared/.heartbeat-active")
        )
        try:
            with open(hb_file, "r") as f:
                current = f.read().strip().lower()
        except FileNotFoundError:
            current = "off"

        new_state = "off" if current == "on" else "on"
        with open(hb_file, "w") as f:
            f.write(new_state + "\n")

        return jsonify({"active": new_state == "on"}), 200

    # --- Activity feed ---

    @app.route("/api/activity", methods=["GET"])
    def api_activity():
        from models import get_all_agents
        import urllib.request
        import urllib.error

        events = []

        # 1. Git commits
        project_dir = app.config.get(
            "PROJECT_DIR",
            os.path.expanduser("~/projects/cc-team-dashboard")
        )
        try:
            result = subprocess.run(
                ["git", "log", "--format=%h||%an||%s||%aI", "-20"],
                capture_output=True, text=True, timeout=5,
                cwd=project_dir
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    parts = line.split("||", 3)
                    if len(parts) == 4:
                        events.append({
                            "type": "commit",
                            "timestamp": parts[3],
                            "agent": parts[1],
                            "message": f"{parts[0]} {parts[2]}"
                        })
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # 2. Heartbeat events from DB
        conn = get_db_connection(app.config["DATABASE_PATH"])
        try:
            agents = get_all_agents(conn)
            for a in agents:
                if a.get("last_active"):
                    events.append({
                        "type": "heartbeat",
                        "timestamp": a["last_active"],
                        "agent": a["name"],
                        "message": f"Heartbeat from {a['name']} — {a.get('status', 'unknown')}"
                    })
        finally:
            conn.close()

        # 3. Slack messages
        token = app.config.get("SLACK_BOT_TOKEN", "")
        channels = app.config.get("SLACK_CHANNELS", [])
        if token and channels:
            for channel_id in channels:
                try:
                    url = (
                        f"https://slack.com/api/conversations.history"
                        f"?channel={channel_id}&limit=10"
                    )
                    req = urllib.request.Request(url, headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    })
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read().decode())
                    if data.get("ok"):
                        for msg in data.get("messages", []):
                            ts = msg.get("ts", "0")
                            try:
                                dt = datetime.fromtimestamp(
                                    float(ts), tz=timezone.utc
                                ).isoformat()
                            except (ValueError, OSError):
                                dt = ""
                            raw_user = msg.get("user", "unknown")
                            bot_name = (msg.get("bot_profile") or {}).get("name", "")
                            display_name = resolve_slack_user(
                                raw_user, token, fallback_name=bot_name
                            ) if raw_user != "unknown" else "unknown"
                            msg_text = msg.get("text", "")
                            agent_name = _infer_agent_name(
                                display_name, channel_id, msg_text
                            )
                            events.append({
                                "type": "slack",
                                "timestamp": dt,
                                "agent": agent_name,
                                "message": msg_text[:200],
                            })
                except (urllib.error.URLError, OSError, ValueError):
                    pass

        # Sort by timestamp descending
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        return jsonify(events[:20]), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', '0') == '1')
