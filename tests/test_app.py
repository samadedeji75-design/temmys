import pytest

from app import create_app


@pytest.fixture()
def client():
    app = create_app("testing")
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


def test_app_factory_creates_app(client):
    assert client is not None
    assert client.application.config["TESTING"] is True


def test_homepage_loads(client):
    response = client.get("/")
    # The home page sends visitors to the portal login.
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
