import sqlite3
import pytest
from models import init_db, get_db_connection, create_agent, get_all_agents, get_agent


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
    agent = create_agent(db, "test-agent", "online")
    assert agent["name"] == "test-agent"
    assert agent["status"] == "online"
    assert agent["id"] is not None


def test_create_duplicate_agent_updates(db):
    create_agent(db, "test-agent", "online")
    agent = create_agent(db, "test-agent", "idle")
    assert agent["status"] == "idle"
    agents = get_all_agents(db)
    assert len(agents) == 1


def test_get_all_agents(db):
    create_agent(db, "agent-1", "online")
    create_agent(db, "agent-2", "idle")
    agents = get_all_agents(db)
    assert len(agents) == 2


def test_get_agent(db):
    created = create_agent(db, "test-agent", "online")
    agent = get_agent(db, created["id"])
    assert agent["name"] == "test-agent"


def test_get_agent_not_found(db):
    agent = get_agent(db, 9999)
    assert agent is None
