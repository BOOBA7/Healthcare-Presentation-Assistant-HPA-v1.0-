from fastapi.testclient import TestClient
import fitz

from app.interfaces.api import main as api
from app.interfaces.storage.user_session_repository import UserSessionRepository


app = api.app


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


def test_authenticated_project_resource_lifecycle_is_durable_and_hides_pdf_text(tmp_path, monkeypatch):
    """Exercise registration, Project storage, PDF persistence, and deletion together.

    The test deliberately uses the real repository and HTTP routes, but no LLM.
    It proves the product path stays deterministic and that API responses never
    expose the extracted source text stored in the dedicated resource tables.
    """
    repository = UserSessionRepository(tmp_path / "hpa.sqlite3")
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    client = TestClient(app)

    registration = client.post(
        "/auth/register",
        json={"user_id": "clinician", "password": "safe-local-password"},
    )
    assert registration.status_code == 200
    headers = {"Authorization": f"Bearer {registration.json()['token']}"}

    created = client.post(
        "/projects",
        headers=headers,
        json={"user_id": "clinician", "project_id": "review-1", "project_name": "Clinical review"},
    )
    assert created.status_code == 200

    document = fitz.open()
    page = document.new_page()
    source_text = "Clinical evidence must remain within the uploaded Project PDF."
    page.insert_text((72, 72), source_text)
    pdf_bytes = document.tobytes()
    document.close()
    uploaded = client.post(
        "/resources/pdf/clinician/review-1",
        headers=headers,
        files={"file": ("evidence.pdf", pdf_bytes, "application/pdf")},
    )
    assert uploaded.status_code == 200
    resource_id = uploaded.json()["resource_id"]

    project = client.get("/projects/clinician/review-1", headers=headers)
    assert project.status_code == 200
    assert project.json()["resource_library"][0]["id"] == resource_id
    assert source_text not in project.text

    deleted = client.delete(f"/projects/clinician/review-1/resources/{resource_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/projects/clinician/review-1", headers=headers).json()["resource_library"] == []
    events = client.get("/projects/clinician/review-1/audit-events", headers=headers).json()["events"]
    assert {event["event_type"] for event in events} >= {"PROJECT_CREATED", "RESOURCE_UPLOADED", "RESOURCE_DELETED"}
