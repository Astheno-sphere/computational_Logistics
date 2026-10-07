from fastapi.testclient import TestClient

from agentsociety2 import __version__
from agentsociety2.backend.app import app


def test_root_returns_service_metadata():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert app.version == __version__
    assert body.get("version") == __version__
    assert body.get("status") == "running"
    assert "endpoints" in body


def test_health_returns_healthy():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
