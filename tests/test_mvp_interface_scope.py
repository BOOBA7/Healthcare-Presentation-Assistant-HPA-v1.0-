"""Slice 01.3: static `/app` scope and existing-profile resume evidence."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.domain.models.user_profile import UserProfile
from app.interfaces.api import main as api
from app.interfaces.storage.user_session_repository import UserSessionRepository


def test_app_exposes_only_professor_and_french_english_controls():
    html = Path("app/interfaces/web/index.html").read_text()
    script = Path("app/interfaces/web/app.js").read_text()

    assert 'id="auth-role"' not in html
    assert 'id="user-role"' not in html
    assert 'value="ar"' not in html
    assert 'const roles = ["professor_medicine"]' in script
    assert 'body.professional_role = "professor_medicine"' in script
    assert 'return state.profile.preferred_language === "fr" ? "fr" : "en"' in script
    assert 'optionList(["English", "French"]' in script
    assert 'id="evidence-context-mode"' not in script
    assert "async function saveEvidenceSettings" not in script


def test_existing_profile_and_project_resume_without_silent_profile_rewrite(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "mvp-ui.sqlite3")
    old_profile = UserProfile(professional_role="resident_physician", preferred_language="ar")
    repository.register_user("existing-user", "existing-safe-password", old_profile)
    repository.create_empty("existing-user", "resumed-project", "Existing Project")
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    client = TestClient(api.app)

    login = client.post(
        "/auth/login",
        json={"user_id": "existing-user", "password": "existing-safe-password"},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert login.status_code == 200
    assert client.get("/users/existing-user/projects", headers=headers).json()["projects"] == [
        {"id": "resumed-project", "name": "Existing Project"}
    ]
    assert client.get("/projects/existing-user/resumed-project", headers=headers).status_code == 200
    assert repository.get_user_profile("existing-user") == old_profile


def test_backend_evidence_mode_remains_server_controlled_for_existing_clients(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "mvp-evidence.sqlite3")
    repository.register_user("api-client", "api-client-password")
    thread_id, state = repository.create_empty("api-client", "api-project")
    state.prototype_declaration = "synthetic"
    repository.save("api-client", "api-project", thread_id, state)
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    client = TestClient(api.app)
    token = client.post(
        "/auth/login", json={"user_id": "api-client", "password": "api-client-password"}
    ).json()["token"]

    response = client.put(
        "/projects/api-client/api-project/evidence-settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"evidence_context_mode": "direct_bounded"},
    )

    assert response.status_code == 200
    assert response.json()["evidence_context_mode"] == "direct_bounded"
