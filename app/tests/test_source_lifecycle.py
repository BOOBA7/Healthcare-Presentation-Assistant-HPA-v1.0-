"""03.1 provider-free public/synthetic ingestion and persistence evidence."""

import json

import fitz
import pytest
from fastapi.testclient import TestClient

from app.ai.workflows.graph_state import GraphState
from app.application.services.prototype_policy import PrototypePolicy
from app.application.services.source_screening import SourceScreening
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.domain.enums.resource_type import ResourceType
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource
from app.domain.models.source_metadata import SourceAsset, SourceLocation
from app.domain.value_objects.presentation_context import PresentationContext
from app.interfaces.api import main as api
from app.interfaces.storage.user_session_repository import UserSessionRepository


def pdf(kind="plain"):
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), "Synthetic teaching evidence.\nPublication date: 2024")
        if kind == "metadata":
            document.set_metadata({"subject": "Confidential professional document"})
        if kind == "xml":
            document.set_xml_metadata("<metadata>Patient case: synthetic example</metadata>")
        if kind == "annotation":
            page.add_text_annot((72, 100), "Synthetic note")
        if kind == "attachment":
            document.embfile_add("synthetic.txt", b"Synthetic attachment")
        if kind == "blank_page":
            document.new_page()
        if kind == "drawing":
            page.draw_rect(fitz.Rect(50, 100, 100, 150))
        if kind == "image":
            pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), False)
            pixmap.clear_with(255)
            page.insert_image(fitz.Rect(50, 100, 100, 150), pixmap=pixmap)
        return document.tobytes()


def resource():
    return ExtractPdfResourceUseCase().execute("synthetic.pdf", pdf(), prototype_declaration="synthetic")


def snapshot(repository):
    with repository._connect() as connection:
        return "\n".join(connection.iterdump())


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    monkeypatch.setattr(api, "get_agent", lambda: pytest.fail("No external provider allowed"))
    client = TestClient(api.app)
    token = client.post("/auth/register", json={"user_id": "synthetic-owner", "password": "synthetic-password"}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.post("/projects", json={
        "user_id": "synthetic-owner", "project_id": "demo",
        "prototype_declaration": "synthetic", "external_processing_acknowledged": True,
    }).status_code == 200
    return client, repository


def upload(client, content):
    return client.post("/resources/pdf/synthetic-owner/demo", files={"file": ("synthetic.pdf", content, "application/pdf")})


def test_memory_import_restart_and_audit_with_atomic_original_bytes(workspace, monkeypatch):
    client, repository = workspace
    monkeypatch.setattr("starlette.formparsers.SpooledTemporaryFile", lambda **kwargs: pytest.fail("Upload spooled before screening"))
    response = upload(client, pdf())
    assert response.status_code == 200, response.text
    restored = UserSessionRepository(repository.database_path)
    source = restored.load("synthetic-owner", "demo")[1].resource_library[0]
    assert source.metadata.origin == "pdf_memory_import"
    assert source.metadata.media_type == "application/pdf"
    assert source.metadata.locations == [SourceLocation(kind="page", number=1)]
    assert source.extracted_pages == [{"page": 1, "text": "Synthetic teaching evidence.\nPublication date: 2024"}]
    assert source.path is None and source.metadata.assets == []
    event = next(event for event in restored.list_events("synthetic-owner", "demo") if event["event_type"] == "RESOURCE_UPLOADED")
    assert event["payload"]["screening_policy"] == SourceScreening.VERSION
    assert not list(repository.database_path.parent.rglob("*.pdf"))
    assert source._original_content.startswith(b"%PDF")


@pytest.mark.parametrize("kind", ["metadata", "xml", "annotation", "attachment", "blank_page", "drawing", "image", "invalid"])
def test_api_refusal_changes_no_database_rows_or_files(workspace, kind):
    client, repository = workspace
    before = snapshot(repository)
    files = set(repository.database_path.parent.rglob("*"))
    response = upload(client, b"invalid" if kind == "invalid" else pdf(kind))
    assert response.status_code == 422, response.text
    assert snapshot(repository) == before
    assert set(repository.database_path.parent.rglob("*")) == files


def test_screening_exception_is_safe_and_leaves_no_write(workspace, monkeypatch):
    client, repository = workspace
    before = snapshot(repository)

    def unavailable(*args, **kwargs):
        raise RuntimeError("Synthetic private diagnostic must not escape")

    monkeypatch.setattr(fitz.Page, "get_text", unavailable)
    response = upload(client, pdf())
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SOURCE_SCREENING_INCOMPLETE"
    assert "diagnostic" not in response.text
    assert snapshot(repository) == before


@pytest.mark.parametrize("entry", ["save", "save_with_event", "sync"])
@pytest.mark.parametrize("surface", ["text", "page", "metadata", "asset", "malformed"])
def test_repository_bypasses_are_refused_before_any_sql_write(tmp_path, entry, surface):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    safe = resource()
    state = GraphState(resource_library=[safe])
    repository.save("owner", "demo", "thread", state)
    before = snapshot(repository)
    candidate = resource()
    if surface == "text":
        candidate.extracted_text = "Confidential professional document"
    elif surface == "page":
        candidate.extracted_pages[0]["text"] = "Patient case: synthetic example"
    elif surface == "metadata":
        candidate.metadata.extensions["custom"] = "Patient ID: SYNTHETIC"
    elif surface == "asset":
        candidate.metadata.assets = [SourceAsset(id="image", kind="image", location=SourceLocation(kind="page", number=1))]
    else:
        candidate.extracted_pages[0]["page"] = "unchecked"
    # Even an is_validated=True record from the normal extractor must be rechecked.
    state.resource_library = [candidate]
    revision = state.project_revision
    with pytest.raises(WorkflowError):
        if entry == "sync":
            with repository._connect() as connection:
                try:
                    repository._sync_resources(connection, "owner", "demo", [candidate])
                finally:
                    assert connection.total_changes == 0
        elif entry == "save":
            repository.save("owner", "demo", "thread", state)
        else:
            repository.save_with_event("owner", "demo", "thread", state, "RESOURCE_UPLOADED", "owner")
    assert state.project_revision == revision
    assert snapshot(repository) == before


def test_repository_screening_failure_is_closed(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    state = GraphState(resource_library=[resource()])
    before = snapshot(repository)

    def unavailable(*args):
        raise RuntimeError("Unavailable")

    monkeypatch.setattr(PrototypePolicy, "screen", unavailable)
    with pytest.raises(WorkflowError, match="screening could not complete"):
        repository.save("owner", "demo", "thread", state)
    assert snapshot(repository) == before


def test_legacy_normalized_json_migrates_lazily_without_fabricated_evidence(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    legacy = {"id": "old", "filename": "old.pdf", "file_type": "pdf", "title": "Old source", "is_validated": False}
    repository.save("owner", "demo", "thread", GraphState())
    with repository._connect() as connection:
        connection.execute("INSERT INTO project_resources (user_id, project_id, resource_id, metadata_json, content_hash) VALUES (?, ?, ?, ?, ?)", ("owner", "demo", "old", json.dumps(legacy), "old-hash"))
        connection.execute("INSERT INTO project_resource_pages VALUES (?, ?, ?, ?, ?)", ("owner", "demo", "old", 7, "Historical synthetic text"))
    repository = UserSessionRepository(repository.database_path)
    # 03.3 startup adds the owner library; ordinary reads remain write-free.
    before = snapshot(repository)
    thread, state = repository.load("owner", "demo")
    source = state.resource_library[0]
    assert source.metadata.origin == "legacy"
    assert source.metadata.locations == [SourceLocation(kind="page", number=7)]
    assert source.metadata.author is None and source.metadata.provenance is None
    assert not source.is_validated and source.path is None
    assert snapshot(repository) == before  # Reading never writes or auto-approves.
    repository.save("owner", "demo", thread, state)
    reopened = UserSessionRepository(repository.database_path).load("owner", "demo")[1]
    assert reopened.resource_library[0] == source
    assert repository.load_resource_chunks("owner", "demo")[0].page == 7


def test_legacy_model_and_asset_descriptors_are_extensible():
    legacy = Resource.model_validate({"id": "old", "filename": "old.pdf", "file_type": "pdf", "extracted_text": "Historical synthetic text"})
    assert legacy.metadata.locations == []  # No invented exact page.
    assert legacy.metadata.origin == "legacy"
    descriptor = SourceAsset(id="future-table", kind="table", location=SourceLocation(kind="slide", number=3), rights="Unknown")
    assert SourceAsset.model_validate_json(descriptor.model_dump_json()) == descriptor


def test_malformed_and_oversized_multipart_never_persists(workspace, monkeypatch):
    client, repository = workspace
    before = snapshot(repository)
    assert client.post("/resources/pdf/synthetic-owner/demo", content=b"broken", headers={"Content-Type": "multipart/form-data; boundary=missing"}).status_code == 422
    monkeypatch.setattr(SourceScreening, "MAX_BYTES", 100)
    assert upload(client, b"x" * (100 + 65537)).status_code == 413
    assert snapshot(repository) == before


def presentation(sources):
    result = CreatePresentationUseCase().execute(
        title="Synthetic teaching",
        context=PresentationContext(topic="Synthetic topic", audience="Specialist", presentation_type="Lecture", duration_minutes=10, objective="Teaching"),
    )
    result.resources = sources
    return result


def test_selection_payload_cannot_hide_behind_safe_library_copy(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    safe = resource()
    altered = safe.model_copy(deep=True)
    altered.extracted_pages[0]["text"] = "Confidential professional document"
    state = GraphState(resource_library=[safe], presentation=presentation([altered]))
    before = snapshot(repository)
    with pytest.raises(WorkflowError):
        repository.save("owner", "demo", "thread", state)
    assert snapshot(repository) == before


def test_embedded_legacy_snapshot_migrates_and_preserves_selection(tmp_path):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    source = resource()
    state = GraphState(presentation=presentation([source]))
    payload = state.model_dump(mode="json")
    payload.pop("resource_library")
    payload["presentation"]["resources"][0].pop("metadata")
    repository.save("owner", "demo", "thread", GraphState())
    with repository._connect() as connection:
        connection.execute("UPDATE project_sessions SET state_json = ?", (json.dumps(payload),))
    thread, migrated = repository.load("owner", "demo")
    assert migrated.resource_library[0].metadata.origin == "legacy"
    assert migrated.resource_library[0].extracted_pages == source.extracted_pages
    repository.save("owner", "demo", thread, migrated)
    restored = UserSessionRepository(repository.database_path).load("owner", "demo")[1]
    assert restored.presentation.resources[0].id == source.id
    assert restored.presentation.resources[0].metadata.scientific_date == restored.resource_library[0].metadata.scientific_date
    assert restored.presentation.resources[0].extracted_pages == []


@pytest.mark.parametrize("surface", ["path", "empty", "unsupported"])
def test_uninspectable_direct_sources_are_refused(tmp_path, surface):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    candidate = resource()
    if surface == "path":
        candidate.path = "/uninspected/source.pdf"
    elif surface == "empty":
        candidate.extracted_text = None
        candidate.extracted_pages = []
    else:
        candidate.file_type = ResourceType.PPTX
    before = snapshot(repository)
    with pytest.raises(WorkflowError):
        repository.save("owner", "demo", "thread", GraphState(resource_library=[candidate]))
    assert snapshot(repository) == before


def test_failed_audit_rolls_back_source_pages_chunks_and_project(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "source.sqlite3")
    before = snapshot(repository)

    def fail(*args):
        raise RuntimeError("Synthetic audit write failure")

    monkeypatch.setattr(repository, "_insert_event", fail)
    with pytest.raises(RuntimeError):
        repository.save_with_event("owner", "demo", "thread", GraphState(resource_library=[resource()]), "RESOURCE_UPLOADED", "owner")
    assert snapshot(UserSessionRepository(repository.database_path)) == before
