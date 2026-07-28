from fastapi.testclient import TestClient

from app.interfaces.api.main import app


def test_versioned_health_endpoint_is_available_without_model_access():
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "api_version": "v1"}


def test_observability_endpoint_returns_safe_counters_only():
    client = TestClient(app)

    response = client.get("/api/v1/observability/summary")

    assert response.status_code == 200
    assert isinstance(response.json()["counters"], dict)
