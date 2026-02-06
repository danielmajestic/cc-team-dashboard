import pytest
from app import create_app


@pytest.fixture
def app():
    app = create_app(testing=True)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_app_exists(app):
    assert app is not None


def test_app_is_testing(app):
    assert app.config["TESTING"] is True


def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
