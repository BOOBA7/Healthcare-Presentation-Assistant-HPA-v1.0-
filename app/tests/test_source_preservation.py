"""03.2: synthetic originals, date evidence and refusal/restart/bypass coverage."""

import hashlib
import json
import subprocess
import sys

import fitz
import pytest

from app.ai.workflows.graph_state import GraphState
from app.ai.prompt_builders.evidence_context_builder import EvidenceContextBuilder
from app.application.services.source_date_policy import SourceDatePolicy
from app.application.services.source_document import SourceDocument
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.domain.exceptions.workflow_error import WorkflowError
from app.domain.models.resource import Resource
from app.interfaces.api import main as api
from app.interfaces.api.routers import jobs
from fastapi import HTTPException
from app.domain.exceptions.concurrent_modification_error import ConcurrentModificationError
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.tests.source_fixtures import seed_legacy_sources
from app.tests import test_source_lifecycle as lifecycle_fixtures
from app.tests.test_source_lifecycle import snapshot, upload, presentation

workspace = lifecycle_fixtures.workspace


def pdf(text="Publication date: 2024-02-29", *, metadata=None, xml=None):
    with fitz.open() as document:
        document.new_page().insert_text((72, 72), "Synthetic guideline\n" + text)
        document.new_page().insert_text((72, 72), "Synthetic second-page evidence.")
        document.set_metadata(metadata or {"title": "Synthetic guideline", "author": "Synthetic author"})
        if xml:
            document.set_xml_metadata(xml)
        return document.tobytes()


def read(content=None):
    return SourceDocument.read("synthetic.pdf", content or pdf(), "source")


@pytest.mark.parametrize("line,value,precision,kind", [
    ("Publication date: 2024", "2024", "year", "publication"),
    ("Published online: 2024-02", "2024-02", "month", "publication"),
    ("Date de publication: 2024-02-29", "2024-02-29", "day", "publication"),
    ("Mis à jour le 2024-03-01", "2024-03-01", "day", "update"),
    ("Publication date: 2023\nLast updated: 2024", "2024", "year", "update"),
])
def test_explicit_dates_preserve_precision_and_exact_document_evidence(line, value, precision, kind):
    source = read(pdf(line))
    evidence = SourceDatePolicy.require(source)
    assert (evidence.value, evidence.precision, evidence.kind) == (value, precision, kind)
    assert evidence.page == 1
    assert evidence.excerpt in source.extracted_pages[0]["text"]


@pytest.mark.parametrize("text", [
    "No date", "Copyright 2024", "A cited study from 2024", "Created: 2024-01-01",
    "References\nPublication date: 2024", "Publication date: 2023-02-29",
    "Published: 2024-13", "Published: 2999", "Published: 2024-01-00",
    "Published: 2023\nPublished: 2024", "Published: 2024\nUpdated: 2023",
])
def test_date_refusals_leave_no_durable_content(workspace, text):
    client, repository = workspace
    before = snapshot(repository)
    content = pdf(text, metadata={"creationDate": "D:20240101000000", "modDate": "D:20250101000000"})
    response = upload(client, content)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] in {"SOURCE_DATE_REQUIRED", "SOURCE_DATE_CONFLICT"}
    assert snapshot(repository) == before


def test_recognized_scientific_metadata_and_available_bibliography_survive_restart(workspace):
    client, repository = workspace
    xml = '''<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"
        xmlns:dc="http://purl.org/dc/elements/1.1/">
      <rdf:Description><prism:publicationDate>2024-06</prism:publicationDate>
        <dc:publisher>Synthetic publisher</dc:publisher><dc:rights>Synthetic fixture rights</dc:rights>
        <dc:source>Synthetic local corpus</dc:source></rdf:Description></rdf:RDF>'''
    content = pdf("Synthetic undated body", xml=xml)
    assert upload(client, content).status_code == 200
    restored = UserSessionRepository(repository.database_path)
    source = restored.load("synthetic-owner", "demo")[1].resource_library[0]
    assert source._original_content == content
    assert source.metadata.original_sha256 == hashlib.sha256(content).hexdigest()
    assert source.metadata.original_size == len(content)
    assert source.metadata.pdf_metadata["title"] == "Synthetic guideline"
    assert source.metadata.xml_metadata == xml
    assert source.metadata.publisher == "Synthetic publisher"
    assert source.metadata.rights == "Synthetic fixture rights"
    assert source.metadata.provenance == "Synthetic local corpus"
    assert source.metadata.scientific_date.origin == "scientific_metadata"
    assert source.metadata.scientific_date.precision == "month"
    assert source.metadata.scientific_date.page is None
    assert source.extracted_pages[1] == {"page": 2, "text": "Synthetic second-page evidence."}
    response = client.get("/projects/synthetic-owner/demo").json()
    assert "xml_metadata" not in json.dumps(response)
    assert "_original_content" not in source.model_dump_json()
    assert "Synthetic second-page evidence" not in json.dumps(response)
    event = next(item for item in restored.list_events("synthetic-owner", "demo") if item["event_type"] == "RESOURCE_UPLOADED")
    assert event["payload"]["original_sha256"] == source.metadata.original_sha256
    assert event["payload"]["date_policy"] == SourceDatePolicy.VERSION


def test_original_download_is_exact_owner_scoped_and_uncached(workspace):
    client, repository = workspace
    content = pdf()
    resource_id = upload(client, content).json()["resource_id"]
    path = f"/projects/synthetic-owner/demo/resources/{resource_id}/original"
    response = client.get(path)
    assert response.status_code == 200 and response.content == content
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"].startswith("attachment;")
    other = client.post("/auth/register", json={"user_id": "other-synthetic", "password": "synthetic-password"}).json()["token"]
    assert client.get(path, headers={"Authorization": f"Bearer {other}"}).status_code == 403
    client.headers.pop("Authorization")
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("field", ["hash", "date", "page", "original", "title", "rights"])
def test_repository_refuses_forged_original_or_derived_evidence_before_writes(tmp_path, field):
    repository = UserSessionRepository(tmp_path / "sources.sqlite3")
    source = read()
    if field == "hash":
        source.metadata.original_sha256 = "0" * 64
    elif field == "date":
        source.metadata.scientific_date.value = "2025"
    elif field == "page":
        source.extracted_pages[1]["text"] = "Invented synthetic evidence"
    elif field == "original":
        source._original_content = pdf("Published: 2025")
    elif field == "title":
        source.title = "Unsubstantiated title"
    else:
        source.metadata.rights = "Unsupported rights declaration"
    before = snapshot(repository)
    state = GraphState(resource_library=[source])
    with pytest.raises(WorkflowError):
        repository.save_with_event("owner", "project", "thread", state, "RESOURCE_UPLOADED", "owner")
    assert state.project_revision == 0
    assert snapshot(repository) == before


def test_missing_original_cannot_be_bypassed_by_claiming_legacy_origin(tmp_path):
    repository = UserSessionRepository(tmp_path / "sources.sqlite3")
    source = read()
    source._original_content = None
    source.metadata.origin = "legacy"
    before = snapshot(repository)
    with pytest.raises(WorkflowError) as error:
        repository.save("owner", "project", "thread", GraphState(resource_library=[source]))
    assert error.value.code == "SOURCE_ORIGINAL_REQUIRED"
    assert snapshot(repository) == before


def test_undated_legacy_remains_readable_but_cannot_reach_model_or_export(workspace, tmp_path):
    client, repository = workspace
    source = Resource(id="legacy", filename="legacy.pdf", file_type="pdf", is_validated=True,
                      extracted_pages=[{"page": 1, "text": "Undated synthetic guideline"}])
    seed_legacy_sources(repository, GraphState(resource_library=[source]), "synthetic-owner", "demo")
    before = snapshot(repository)
    response = client.get("/projects/synthetic-owner/demo")
    assert response.status_code == 200
    item = response.json()["resource_library"][0]
    assert item["source_blocker"]["code"] == "SOURCE_DATE_REQUIRED"
    assert item["original_available"] is False
    assert client.post("/projects/synthetic-owner/demo/resources/summary").status_code == 409
    assert client.post("/projects/synthetic-owner/demo/resources/discuss", json={"question": "Summarize this guideline"}).status_code == 409
    with pytest.raises(WorkflowError):
        EvidenceContextBuilder().for_overview([source])
    target = tmp_path / "must-not-exist"
    with pytest.raises(WorkflowError):
        ExportPowerPointUseCase().execute(presentation([source]), target)
    assert not target.exists()
    assert snapshot(repository) == before
    reopened = UserSessionRepository(repository.database_path)
    thread, state = reopened.load("synthetic-owner", "demo")
    reopened.save("synthetic-owner", "demo", thread, state)  # ordinary legacy resume stays possible
    assert reopened.load("synthetic-owner", "demo")[1].resource_library[0]._original_content is None


def test_source_metadata_declaration_without_document_support_does_not_satisfy_date_gate():
    source = Resource(id="legacy", filename="dated-2024.pdf", file_type="pdf", is_validated=True,
                      extracted_pages=[{"page": 1, "text": "No publication evidence"}])
    source.metadata.scientific_date = read().metadata.scientific_date
    source.metadata.xml_metadata = '<publicationDate>2024</publicationDate>'
    with pytest.raises(WorkflowError):
        SourceDatePolicy.require(source)


def test_dated_legacy_source_still_requires_its_missing_original():
    source = Resource(id="legacy", filename="legacy.pdf", file_type="pdf", is_validated=True,
                      extracted_pages=[{"page": 1, "text": "Publication date: 2024"}])
    with pytest.raises(WorkflowError) as error:
        SourceDatePolicy.require(source)
    assert error.value.code == "SOURCE_ORIGINAL_REQUIRED"


def test_corrupted_original_after_restart_blocks_download_and_model_context(workspace, monkeypatch):
    client, repository = workspace
    resource_id = upload(client, pdf()).json()["resource_id"]
    with repository._connect() as connection:
        connection.execute("UPDATE project_resources SET original_pdf = ?", (pdf("Published: 2025"),))
    restored = UserSessionRepository(repository.database_path)
    monkeypatch.setattr(api, "get_repository", lambda: restored)
    response = client.get(f"/projects/synthetic-owner/demo/resources/{resource_id}/original")
    assert response.status_code == 409
    assert client.post("/projects/synthetic-owner/demo/resources/summary").status_code == 409


def test_publication_metadata_conflict_and_technical_xmp_dates_are_not_accepted():
    xml = '<root xmlns:p="http://prismstandard.org/namespaces/basic/2.0/"><p:publicationDate>2025</p:publicationDate></root>'
    with pytest.raises(WorkflowError) as error:
        read(pdf("Published: 2024", xml=xml))
    assert error.value.code == "SOURCE_DATE_CONFLICT"
    with pytest.raises(WorkflowError):
        read(pdf("No date", xml='<root xmlns:xmp="http://ns.adobe.com/xap/1.0/"><xmp:CreateDate>2024-01-01</xmp:CreateDate></root>'))


def test_existing_original_cannot_be_overwritten_under_approved_resource_id(tmp_path):
    repository = UserSessionRepository(tmp_path / "sources.sqlite3")
    state = GraphState(resource_library=[read()])
    repository.save("owner", "project", "thread", state)
    before = snapshot(repository)
    state.resource_library = [read(pdf("Published: 2025"))]
    with pytest.raises(WorkflowError) as error:
        repository.save("owner", "project", "thread", state)
    assert error.value.code == "SOURCE_REPLACEMENT_REQUIRED"
    assert snapshot(repository) == before


def test_stale_save_cannot_commit_an_original_or_audit_event(tmp_path):
    repository = UserSessionRepository(tmp_path / "sources.sqlite3")
    thread, state = repository.create_empty("owner", "project")
    stale = state.model_copy(deep=True)
    state.conversation_context.topic = "Newer synthetic context"
    repository.save("owner", "project", thread, state)
    before = snapshot(repository)
    stale.resource_library = [read()]
    with pytest.raises(ConcurrentModificationError):
        repository.save_with_event("owner", "project", thread, stale, "RESOURCE_UPLOADED", "owner")
    assert snapshot(UserSessionRepository(repository.database_path)) == before


def test_process_interruption_rolls_back_original_pages_chunks_and_metadata(tmp_path):
    repository = UserSessionRepository(tmp_path / "sources.sqlite3")
    before = snapshot(repository)
    result = subprocess.run([sys.executable, "-c", """
import os, sys
from pathlib import Path
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.tests.test_source_preservation import read
repository = UserSessionRepository(Path(sys.argv[1]))
connection = repository._connect()
connection.execute('BEGIN IMMEDIATE')
repository._sync_resources(connection, 'owner', 'project', [read()])
os._exit(73)
""", str(repository.database_path)], capture_output=True, timeout=30)
    assert result.returncode == 73, result.stderr.decode()
    assert snapshot(UserSessionRepository(repository.database_path)) == before


def test_legacy_date_gate_cannot_be_bypassed_by_approvals_or_queued_jobs(workspace, monkeypatch):
    client, repository = workspace
    assert client.post("/projects/synthetic-owner/demo/presentation/setup", json={
        "topic": "Synthetic guideline", "audience": "general_practitioner", "presentation_type": "Lecture",
        "language": "English", "duration_minutes": 10, "objective": "Review synthetic evidence",
        "target_slide_count": 5, "special_instructions": "None", "professional_scope": "Teaching within my specialty",
        "is_multidisciplinary": False, "confirmed_within_scope": True,
    }).status_code == 200
    resource_id = upload(client, pdf(
        "Publication date: 2024-02-29\n"
        "Synthetic guideline evidence supports practical clinical review.\n"
        "General practitioner primary care education is addressed.\n"
        "Monitoring and shared decisions provide sufficient detail."
    )).json()["resource_id"]
    base = "/projects/synthetic-owner/demo"
    assert client.post(base + f"/resources/{resource_id}/attach").status_code == 200
    assert client.post(base + "/resources/validate").status_code == 200
    project = client.get(base).json()
    coverage = client.post(base + "/evidence-coverage", json={"expected_revision": project["project_revision"]})
    assert coverage.status_code == 200
    assert coverage.json()["presentation"]["evidence_coverage"]["sufficient"] is True, coverage.json()["presentation"]["evidence_coverage"]["results"]
    work = []
    monkeypatch.setattr(jobs, "submit_job", lambda repository, user, job, domain, task: work.append(task))
    queue = "/api/v1/projects/synthetic-owner/demo/blueprint/jobs"
    assert client.post(queue).status_code == 202
    # Simulate a previously approved legacy database with no date or original.
    with repository._connect() as connection:
        metadata = json.loads(connection.execute("SELECT metadata_json FROM project_resources").fetchone()[0])
        metadata["metadata"].update(origin="legacy", original_sha256=None, original_size=None, scientific_date=None, pdf_metadata={}, xml_metadata=None)
        connection.execute("UPDATE project_resources SET original_pdf = NULL, metadata_json = ?", (json.dumps(metadata),))
        connection.execute("UPDATE project_resource_pages SET page_text = 'Undated synthetic evidence' WHERE page_number = 1")
    before = snapshot(repository)
    assert client.post(queue).status_code == 409
    with pytest.raises(HTTPException) as error:
        work[0](lambda *args: None)
    assert error.value.status_code == 409
    response = client.get(base).json()
    assert response["workflow"]["status"] == "blocked"
    assert response["workflow"]["blockers"][0]["code"] == "SOURCE_DATE_REQUIRED"
    assert snapshot(repository) == before


def test_web_date_evidence_is_escaped_and_has_french_and_english_labels():
    from pathlib import Path
    script = Path("app/interfaces/web/app.js").read_text()
    assert 'escapeHtml(evidence.excerpt)' in script
    assert 'Preuve de date' in script and 'Date evidence' in script
    assert 'Original conservé' in script and 'Original retained' in script
