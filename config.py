import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    DATABASE_URI = os.environ.get("DATABASE_URI", "sqlite:///dashboard.db")
    DATABASE_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "instance", "dashboard.db"
    )
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    GITHUB_REPOS = [
        r.strip()
        for r in os.environ.get("GITHUB_REPOS", "").split(",")
        if r.strip()
    ]
    ISSUE_REFRESH_INTERVAL = int(os.environ.get("ISSUE_REFRESH_INTERVAL", "300"))
    AGENT_HEARTBEAT_TIMEOUT = int(os.environ.get("AGENT_HEARTBEAT_TIMEOUT", "60"))


class TestConfig(Config):
    TESTING = True
    DATABASE_PATH = ":memory:"
