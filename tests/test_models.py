import sqlite3
import pytest
from datetime import datetime, timezone, timedelta
from models import (
    init_db, get_db_connection, create_agent, get_all_agents, get_agent,
    update_heartbeat, check_heartbeat_timeouts,
)


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    yield conn
    conn.close()


def test_init_db_creates_agents_table(db):
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='agents'"
    )
    assert cursor.fetchone() is not None


def test_create_agent(db):
    agent = create_agent(db, "test-agent", role="backend", status="online")
    assert agent["name"] == "test-agent"
    assert agent["role"] == "backend"
    assert agent["status"] == "online"
    assert agent["id"] is not None


def test_create_duplicate_agent_updates(db):
    create_agent(db, "test-agent", role="backend", status="online")
    agent = create_agent(db, "test-agent", role="backend", status="idle")
    assert agent["status"] == "idle"
    agents = get_all_agents(db)
    assert len(agents) == 1


def test_get_all_agents(db):
    create_agent(db, "agent-1", status="online")
    create_agent(db, "agent-2", status="idle")
    agents = get_all_agents(db)
    assert len(agents) == 2


def test_get_agent(db):
    created = create_agent(db, "test-agent", status="online")
    agent = get_agent(db, created["id"])
    assert agent["name"] == "test-agent"


def test_get_agent_not_found(db):
    agent = get_agent(db, 9999)
    assert agent is None


def test_update_heartbeat(db):
    agent = create_agent(db, "test-agent", status="online")
    old_active = agent["last_active"]
    updated = update_heartbeat(db, agent["id"])
    assert updated["last_active"] >= old_active


def test_update_heartbeat_with_status(db):
    agent = create_agent(db, "test-agent", status="online")
    updated = update_heartbeat(db, agent["id"], status="idle")
    assert updated["status"] == "idle"


def test_update_heartbeat_with_current_task(db):
    agent = create_agent(db, "test-agent", status="online")
    updated = update_heartbeat(db, agent["id"], current_task="fixing bug #42")
    assert updated["current_task"] == "fixing bug #42"


def test_update_heartbeat_nonexistent(db):
    result = update_heartbeat(db, 9999)
    assert result is None


def test_check_heartbeat_timeouts(db):
    agent = create_agent(db, "stale-agent", status="online")
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    db.execute("UPDATE agents SET last_active = ? WHERE id = ?", (stale_time, agent["id"]))
    db.commit()
    check_heartbeat_timeouts(db, timeout_seconds=60)
    updated = get_agent(db, agent["id"])
    assert updated["status"] == "offline"


def test_check_heartbeat_timeouts_skips_fresh(db):
    agent = create_agent(db, "fresh-agent", status="online")
    check_heartbeat_timeouts(db, timeout_seconds=60)
    updated = get_agent(db, agent["id"])
    assert updated["status"] == "online"


def test_check_heartbeat_timeouts_skips_already_offline(db):
    agent = create_agent(db, "offline-agent", status="offline")
    stale_time = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    db.execute("UPDATE agents SET last_active = ? WHERE id = ?", (stale_time, agent["id"]))
    db.commit()
    check_heartbeat_timeouts(db, timeout_seconds=60)
    updated = get_agent(db, agent["id"])
    assert updated["status"] == "offline"
