import sqlite3
from datetime import datetime, timezone


def init_db(conn):
    """Initialize database schema."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'offline',
            current_task TEXT DEFAULT '',
            last_active TEXT,
            uptime_since TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()


def get_db_connection(db_path):
    """Create a database connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def create_agent(conn, name, status="offline"):
    """Create or update an agent. Returns the agent as a dict."""
    now = datetime.now(timezone.utc).isoformat()
    existing = conn.execute(
        "SELECT id FROM agents WHERE name = ?", (name,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE agents SET status = ?, last_active = ? WHERE name = ?",
            (status, now, name),
        )
        conn.commit()
        return dict(
            conn.execute("SELECT * FROM agents WHERE name = ?", (name,)).fetchone()
        )

    conn.execute(
        "INSERT INTO agents (name, status, last_active, created_at) VALUES (?, ?, ?, ?)",
        (name, status, now, now),
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
