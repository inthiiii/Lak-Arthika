"""Tests for the LakArthika API."""

from fastapi.testclient import TestClient

from lak_arthika.api import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """The health endpoint should describe a healthy service."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "LakArthika",
        "environment": "development",
        "version": "0.1.0",
    }
