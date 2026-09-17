"""Slice 01.2: local-account recovery, ownership and loopback defaults."""

from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.interfaces.api import main as api
from app.interfaces.storage.user_session_repository import UserSessionRepository


def _pdf_bytes() -> bytes:
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Synthetic public evidence.")
    document[0].insert_text((72, 40), "Publication date: 2024")
    content = document.tobytes()
    document.close()
    return content


def _pptx_bytes() -> bytes:
    from app.tests.test_pptx_sources import deck
    return deck()


@pytest.fixture
def two_accounts(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "accounts.sqlite3")
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    client = TestClient(api.app)

    tokens = {}
    for user_id in ("owner", "other"):
        registered = client.post(
            "/auth/register",
            json={"user_id": user_id, "password": f"{user_id}-safe-password"},
        )
        assert registered.status_code == 200
        tokens[user_id] = registered.json()["token"]

    owner_headers = {"Authorization": f"Bearer {tokens['owner']}"}
    created = client.post(
        "/projects",
        headers=owner_headers,
        json={
            "user_id": "owner",
            "project_id": "private-project",
            "prototype_declaration": "synthetic",
            "external_processing_acknowledged": True,
        },
    )
    assert created.status_code == 200
    uploaded = client.post(
        "/resources/pdf/owner/private-project",
        headers=owner_headers,
        files={"file": ("evidence.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert uploaded.status_code == 200
    template = client.post(
        "/users/owner/templates",
        headers=owner_headers,
        files={"file": ("synthetic.pptx", _pptx_bytes(), "application/octet-stream")},
        data={"prototype_declaration": "synthetic", "external_processing_acknowledged": "true"},
    )
    assert template.status_code == 200
    repository.create_job("owner", "private-project", "conversation")
    return client, repository, {"Authorization": f"Bearer {tokens['other']}"}, uploaded.json()["resource_id"]


def test_reset_route_is_absent_and_cannot_change_an_account(two_accounts):
    client, repository, _, _ = two_accounts

    response = client.post(
        "/auth/reset-password",
        json={"user_id": "owner", "password": "replacement-password"},
    )

    assert response.status_code == 404
    assert repository.authenticate_user("owner", "owner-safe-password")
    assert not repository.authenticate_user("owner", "replacement-password")


def test_unauthenticated_requests_cannot_reach_private_account_routes(two_accounts):
    client, _, _, resource_id = two_accounts

    routes = (
        ("get", "/users/owner/projects"),
        ("get", "/users/owner/templates"),
        ("get", "/projects/owner/private-project"),
        ("get", "/projects/owner/private-project/audit-events"),
        ("post", f"/projects/owner/private-project/resources/{resource_id}/attach"),
        ("post", "/api/v1/projects/owner/private-project/blueprint/jobs"),
        ("get", "/api/v1/jobs/owner/not-a-job"),
        ("get", "/presentations/owner/private-project/export/pptx"),
    )
    for method, path in routes:
        response = getattr(client, method)(path)
        assert response.status_code == 401, path


def test_second_synthetic_user_cannot_access_projects_resources_templates_jobs_events_or_exports(two_accounts):
    client, repository, other_headers, resource_id = two_accounts
    job_id = repository.active_job("owner", "private-project")["job_id"]

    read_paths = (
        "/users/owner/projects",
        "/users/owner/templates",
        "/projects/owner/private-project",
        "/projects/owner/private-project/audit-events",
        f"/api/v1/jobs/owner/{job_id}",
        "/presentations/owner/private-project/export/pptx",
    )
    for path in read_paths:
        assert client.get(path, headers=other_headers).status_code == 403, path

    mutating = (
        ("post", "/resources/pdf/owner/private-project", {"files": {"file": ("other.pdf", _pdf_bytes(), "application/pdf")}}),
        ("post", f"/projects/owner/private-project/resources/{resource_id}/attach", {}),
        ("delete", f"/projects/owner/private-project/resources/{resource_id}", {}),
        ("post", "/api/v1/projects/owner/private-project/blueprint/jobs", {}),
        ("post", "/api/v1/conversations/jobs", {"json": {"user_id": "owner", "project_id": "private-project", "message": "Synthetic request."}}),
    )
    for method, path, options in mutating:
        assert getattr(client, method)(path, headers=other_headers, **options).status_code == 403, path

    assert repository.load("owner", "private-project") is not None
    assert repository.list_presentation_templates("other") == []


def test_local_server_configuration_rejects_network_bind_addresses():
    assert Settings(_env_file=None).local_bind_host == "127.0.0.1"
    assert Settings(LOCAL_BIND_HOST="::1", _env_file=None).local_bind_host == "::1"
    with pytest.raises(ValidationError, match="loopback"):
        Settings(LOCAL_BIND_HOST="0.0.0.0", _env_file=None)

    main_source = Path(api.__file__).read_text()
    readme = Path("README.md").read_text()
    assert 'host=settings.local_bind_host' in main_source
    assert "uvicorn app.interfaces.api.main:app --host 127.0.0.1 --reload" in readme
