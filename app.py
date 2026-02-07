import os
import re
import subprocess
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

    from models import init_db, get_db_connection

    # Initialize database
    db_conn = get_db_connection(app.config["DATABASE_PATH"])
    init_db(db_conn)
    db_conn.close()

    # --- Template routes ---

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
