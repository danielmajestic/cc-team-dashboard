import sqlite3
from datetime import datetime, timezone, timedelta


def init_db(conn):
    """Initialize database schema."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'offline',
            current_task TEXT DEFAULT '',
            last_active TEXT,
            uptime_since TEXT,
            created_at TEXT NOT NULL
        )
    """)
    # Migration: add role column if missing (for existing DBs)
    columns = [col[1] for col in conn.execute("PRAGMA table_info(agents)").fetchall()]
    if 'role' not in columns:
        conn.execute("ALTER TABLE agents ADD COLUMN role TEXT NOT NULL DEFAULT ''")
    conn.commit()


def get_db_connection(db_path):
    """Create a database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def create_agent(conn, name, role="", status="offline"):
    """Create or update an agent. Returns the agent as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    existing = conn.execute(
        "SELECT id FROM agents WHERE name = ?", (name,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE agents SET role = ?, status = ?, last_active = ? WHERE name = ?",
            (role, status, now, name),
        )
        conn.commit()
        return dict(
            conn.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
        )

    conn.execute(
        "INSERT INTO agents (name, role, status, last_active, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, role, status, now, now),
    )
    conn.commit()
    return dict(
        conn.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
    )


def get_all_agents(conn):
    """Return all agents as a list of dicts."""
    rows = conn.execute("SELECT * FROM agents ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def get_agent(conn, agent_id):
    """Return a single agent by ID, or None."""
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    return dict(row) if row else None


def update_heartbeat(conn, agent_id, status=None, current_task=None):
    """Update agent's last_active timestamp. Optionally update status and current_task.
    Returns the updated agent dict, or None if not found."""
    agent = get_agent(conn, agent_id)
    if agent is None:
        return None

    now = datetime.now(timezone.utc).isoformat()
    new_status = status if status is not None else agent["status"]
    new_task = current_task if current_task is not None else agent["current_task"]

    conn.execute(
        "UPDATE agents SET last_active = ?, status = ?, current_task = ? WHERE id = ?",
        (now, new_status, new_task, agent_id),
    )
    conn.commit()
    return get_agent(conn, agent_id)


def check_heartbeat_timeouts(conn, timeout_seconds=60):
    """Mark agents as offline if their last_active is older than timeout_seconds.
    Only affects agents currently marked as 'online' or 'idle'."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)).isoformat()
    conn.execute(
        "UPDATE agents SET status = 'offline' WHERE last_active < ? AND status IN ('online', 'idle')",
        (cutoff,),
    )
    conn.commit()
