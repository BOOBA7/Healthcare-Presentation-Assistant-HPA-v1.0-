"""Provider-free FR-02 dashboard and resume coverage for slice 02.2."""

from __future__ import annotations

import fitz
from fastapi.testclient import TestClient

from app.domain.exceptions.concurrent_modification_error import ConcurrentModificationError
from app.interfaces.api import main as api
from app.interfaces.storage.user_session_repository import UserSessionRepository


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Synthetic public evidence must not appear in dashboard metadata.")
    document[0].insert_text((72, 40), "Publication date: 2024")
    content = document.tobytes()
    document.close()
    return content


def _context(topic: str) -> dict[str, object]:
    return {
        "topic": topic,
        "audience": "general_practitioner",
        "presentation_type": "Lecture",
        "language": "French",
        "duration_minutes": 15,
        "target_slide_count": 12,
        "objective": "Explain the supplied public evidence to the intended audience.",
        "special_instructions": "Keep the discussion concise.",
        "professional_scope": "Teaching public evidence within my specialty.",
        "is_multidisciplinary": False,
        "confirmed_within_scope": True,
    }


def _workspace(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "dashboard.sqlite3")
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    client = TestClient(api.app)
    registered = client.post(
        "/auth/register",
        json={"user_id": "professor", "password": "synthetic-password"},
    )
    assert registered.status_code == 200
    headers = {"Authorization": f"Bearer {registered.json()['token']}"}
    return client, repository, headers


def test_dashboard_returns_only_persisted_project_metadata_and_resume_data(tmp_path, monkeypatch):
    client, repository, headers = _workspace(tmp_path, monkeypatch)
    for project_id, name, topic in (
        ("cardiology", "Cardiology update", "Heart failure evidence update"),
        ("endocrinology", "Endocrinology review", "Vitamin D evidence review"),
    ):
        assert client.post(
            "/projects",
            headers=headers,
            json={
                "user_id": "professor",
                "project_id": project_id,
                "project_name": name,
                "prototype_declaration": "synthetic",
                "external_processing_acknowledged": True,
            },
        ).status_code == 200
        assert client.post(
            f"/projects/professor/{project_id}/presentation/setup",
            headers=headers,
            json=_context(topic),
        ).status_code == 200

    uploaded = client.post(
        "/resources/pdf/professor/cardiology",
        headers=headers,
        files={"file": ("evidence.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert uploaded.status_code == 200
    resource_id = uploaded.json()["resource_id"]
    assert client.post(
        f"/projects/professor/cardiology/resources/{resource_id}/attach",
        headers=headers,
    ).status_code == 200
    assert client.put(
        "/projects/professor/cardiology/theme",
        headers=headers,
        json={"theme": "academic", "expected_revision": repository.load("professor", "cardiology")[1].project_revision},
    ).status_code == 200

    dashboard = client.get("/users/professor/dashboard", headers=headers)
    assert dashboard.status_code == 200
    payload = dashboard.json()
    assert payload["project_count"] == 2
    cardiology = next(project for project in payload["projects"] if project["id"] == "cardiology")
    assert cardiology["name"] == "Cardiology update"
    assert cardiology["workflow_status"] == "awaiting_resource_validation"
    assert cardiology["context"] == {
        "topic": "Heart failure evidence update",
        "audience": "general_practitioner",
        "presentation_type": "Lecture",
        "language": "French",
        "duration_minutes": 15,
        "target_slide_count": 12,
        "objective": "Explain the supplied public evidence to the intended audience.",
        "special_instructions": "Keep the discussion concise.",
        "professional_scope": "Teaching public evidence within my specialty.",
        "is_multidisciplinary": False,
        "presenter_name": None,
        "presenter_title": None,
        "organization": None,
        "event_name": None,
        "venue": None,
        "presentation_date": None,
    }
    assert cardiology["theme"] == "academic"
    assert cardiology["custom_template_name"] is None
    assert cardiology["resource_count"] == 1
    assert cardiology["resource_types"] == {"pdf": 1}
    assert cardiology["recent_actions"]
    assert cardiology["last_successful_save"]
    assert "Synthetic public evidence" not in dashboard.text

    from app.tests.test_pptx_sources import deck
    template = repository.save_presentation_template(
        "professor", "public-template.pptx", deck(), prototype_declaration="synthetic"
    )
    thread_id, state = repository.load("professor", "cardiology")
    state.presentation.state.blueprint_validated = True
    repository.save("professor", "cardiology", thread_id, state)
    repository.select_presentation_style("professor", "cardiology", state.project_revision, template_id=template["id"])
    styled = client.get("/users/professor/dashboard", headers=headers).json()
    styled_cardiology = next(project for project in styled["projects"] if project["id"] == "cardiology")
    assert styled_cardiology["custom_template_name"] == "public-template.pptx"

    restored = UserSessionRepository(repository.database_path)
    assert restored.project_dashboard("professor") == styled
    resumed = client.get("/projects/professor/cardiology", headers=headers)
    assert resumed.status_code == 200
    assert resumed.json()["presentation"]["context"]["topic"] == "Heart failure evidence update"


def test_dashboard_is_owner_scoped_and_failed_saves_do_not_change_it(tmp_path, monkeypatch):
    client, repository, headers = _workspace(tmp_path, monkeypatch)
    assert client.post(
        "/projects",
        headers=headers,
        json={
            "user_id": "professor",
            "project_id": "draft",
            "project_name": "Draft",
            "prototype_declaration": "synthetic",
            "external_processing_acknowledged": True,
        },
    ).status_code == 200
    before = client.get("/users/professor/dashboard", headers=headers).json()
    thread_id, stale_state = repository.load("professor", "draft")
    _, newer_state = repository.load("professor", "draft")
    repository.save_with_event("professor", "draft", thread_id, newer_state, "SYNTHETIC_NEWER_SAVE", "user")
    try:
        repository.save_with_event("professor", "draft", thread_id, stale_state, "STALE_SAVE", "user")
    except ConcurrentModificationError:
        pass
    else:
        raise AssertionError("A stale write must be rejected.")
    after = client.get("/users/professor/dashboard", headers=headers).json()
    assert all(action["event_type"] != "STALE_SAVE" for action in after["projects"][0]["recent_actions"])
    assert after["projects"][0]["recent_actions"][0]["event_type"] == "SYNTHETIC_NEWER_SAVE"
    assert after["projects"][0]["last_successful_save"] >= before["projects"][0]["last_successful_save"]

    other = client.post(
        "/auth/register",
        json={"user_id": "other", "password": "other-synthetic-password"},
    )
    assert other.status_code == 200
    denied = client.get(
        "/users/professor/dashboard",
        headers={"Authorization": f"Bearer {other.json()['token']}"},
    )
    assert denied.status_code == 403


def test_dashboard_web_contract_contains_french_english_resume_and_safe_rendering():
    script = open("app/interfaces/web/app.js").read()
    markup = open("app/interfaces/web/index.html").read()

    assert "/users/${endpoint(state.userId)}/dashboard" in script
    assert 'data-resume-project="${escapeHtml(project.id)}"' in script
    assert "function renderDashboard()" in script
    assert "formatDashboardTime" in script
    assert 'personalDashboard:"Personal dashboard"' in script
    assert 'personalDashboard:"Tableau de bord personnel"' in script
    assert 'id="project-dashboard"' in markup
    assert "20260915-dashboard-v1" in markup
