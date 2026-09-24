"""NFR-04 / slice 01.1: synthetic, provider-free boundary and bypass evidence."""

from io import BytesIO
from zipfile import ZipFile

import fitz
import pytest
from fastapi import HTTPException
from app.interfaces.api import job_runner
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage

from app.ai.llm import llm
from app.ai.workflows.graph_state import GraphState
from app.application.services.prototype_policy import PrototypePolicy
from app.application.use_cases.extract_pdf_resource import ExtractPdfResourceUseCase
from app.application.use_cases.summarize_resources import SummarizeResourcesUseCase
from app.domain.exceptions.workflow_error import WorkflowError
from app.interfaces.api import main as api
from app.interfaces.api.routers import jobs
from app.interfaces.storage.user_session_repository import UserSessionRepository


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "prototype.sqlite3")
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    monkeypatch.setattr(api, "get_agent", lambda: pytest.fail("Provider must not be constructed"))
    client = TestClient(api.app)
    token = client.post("/auth/register", json={"user_id": "synthetic-owner", "password": "synthetic-password"}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client, repository


def declare(client, **extra):
    return client.post("/projects", json={
        "user_id": "synthetic-owner", "project_id": "demo",
        "prototype_declaration": "synthetic", "external_processing_acknowledged": True,
        **extra,
    })


def pdf(text):
    with fitz.open() as document:
        document.new_page().insert_text((72, 72), text)
        document[0].insert_text((72, 40), "Publication date: 2024")
        return document.tobytes()


def test_declaration_is_required_and_survives_restart_with_audit(workspace):
    client, repository = workspace
    assert client.post("/projects", json={"user_id": "synthetic-owner", "project_id": "demo"}).status_code == 200
    response = client.post("/resources/pdf/synthetic-owner/demo", files={"file": ("source.pdf", pdf("Synthetic guideline."), "application/pdf")})
    assert response.status_code == 409
    assert repository.load("synthetic-owner", "demo")[1].resource_library == []
    assert declare(client, external_processing_acknowledged=False).status_code == 409
    assert declare(client).status_code == 200
    restored = UserSessionRepository(repository.database_path)
    assert restored.load("synthetic-owner", "demo")[1].prototype_declaration == "synthetic"
    event = next(e for e in restored.list_events("synthetic-owner", "demo") if e["event_type"] == "PROTOTYPE_DECLARATION_RECORDED")
    assert event["payload"]["actor_user_id"] == "synthetic-owner"
    assert event["payload"]["external_processing_acknowledged"] is True
    assert event["created_at"]
    response = client.post("/resources/pdf/synthetic-owner/demo", files={"file": ("source.pdf", pdf("Synthetic guideline published in 2024."), "application/pdf")})
    assert response.status_code == 200
    project = client.get("/projects/synthetic-owner/demo").json()
    assert "external model provider" in project["external_processing_disclosure"]
    assert "cannot guarantee anonymisation" in project["external_processing_disclosure"]


@pytest.mark.parametrize("declaration", ["professional", "patient_case", "anonymised", ""])
def test_forbidden_declaration_creates_no_project(workspace, declaration):
    client, repository = workspace
    assert declare(client, prototype_declaration=declaration).status_code == 409
    assert repository.load("synthetic-owner", "demo") is None


@pytest.mark.parametrize("text", [
    "Patient case: synthetic narrative.",
    "Cas clinique : exemple.",
    "Confidential professional document.",
])
def test_direct_chat_is_blocked_but_uploaded_resource_findings_are_advisory(workspace, text):
    client, repository = workspace
    assert declare(client).status_code == 200
    response = client.post("/chat", json={"user_id": "synthetic-owner", "project_id": "demo", "message": text})
    assert response.status_code == 409
    response = client.post("/resources/pdf/synthetic-owner/demo", files={"file": ("source.pdf", pdf(text), "application/pdf")})
    assert response.status_code == 200
    resource = repository.load("synthetic-owner", "demo")[1].resource_library[0]
    assert resource.metadata.privacy_decision == "authorized"
    assert resource.metadata.privacy_finding_categories


@pytest.mark.parametrize("acknowledged", [False, True])
def test_patient_flag_cannot_be_enabled_via_direct_api(workspace, acknowledged):
    client, repository = workspace
    declare(client)
    response = client.put("/projects/synthetic-owner/demo/evidence-settings", json={"patient_case_mode": True, "patient_case_acknowledged": acknowledged})
    assert response.status_code == 409
    assert not repository.load("synthetic-owner", "demo")[1].patient_case_mode


def test_legacy_patient_state_cannot_be_redeclared_or_processed_after_restart(workspace, monkeypatch):
    client, repository = workspace
    declare(client)
    thread, state = repository.load("synthetic-owner", "demo")
    state.patient_case_mode = True
    state.patient_case_acknowledged = True
    repository.save("synthetic-owner", "demo", thread, state)
    restored = UserSessionRepository(repository.database_path)
    monkeypatch.setattr(api, "get_repository", lambda: restored)
    assert client.get("/projects/synthetic-owner/demo").status_code == 200
    assert declare(client).status_code == 409
    for path in ["/projects/synthetic-owner/demo/resources/summary", "/api/v1/projects/synthetic-owner/demo/blueprint/jobs"]:
        assert client.post(path).status_code == 409
    assert client.post("/chat", json={"user_id": "synthetic-owner", "project_id": "demo", "message": "Outline the supplied evidence."}).status_code == 409
    assert restored.load("synthetic-owner", "demo")[1].patient_case_mode


def test_queued_job_reloads_policy_before_model_or_message_storage(workspace, monkeypatch):
    client, repository = workspace
    declare(client)
    captured = []
    monkeypatch.setattr(jobs, "submit_job", lambda repository, user, job, domain, work: captured.append(work))
    response = client.post("/api/v1/conversations/jobs", json={"user_id": "synthetic-owner", "project_id": "demo", "message": "Outline the evidence."})
    assert response.status_code == 202
    thread, state = repository.load("synthetic-owner", "demo")
    state.patient_case_mode = True
    repository.save("synthetic-owner", "demo", thread, state)
    with pytest.raises(HTTPException) as caught:
        captured[0](lambda *args: None)
    assert caught.value.status_code == 409

    class ImmediateExecutor:
        def submit(self, work):
            work()

    monkeypatch.setattr(job_runner, "_executor", ImmediateExecutor())
    job_id = response.json()["job_id"]
    job_runner.submit(repository, "synthetic-owner", job_id, "conversation", captured[0])
    assert repository.get_job("synthetic-owner", job_id)["status"] == "failed"
    assert repository.load("synthetic-owner", "demo")[1].conversation_history == []
    with pytest.raises(HTTPException):
        jobs._load_workflow_state(repository, "synthetic-owner", "demo")


def test_shared_ingestion_and_model_use_cases_fail_closed(monkeypatch):
    monkeypatch.setattr("app.application.use_cases.summarize_resources.get_llm", lambda: pytest.fail("Provider invoked"))
    for declaration in [None, "professional"]:
        with pytest.raises(WorkflowError):
            ExtractPdfResourceUseCase().execute("source.pdf", pdf("Synthetic guideline."), prototype_declaration=declaration)
        with pytest.raises(WorkflowError):
            SummarizeResourcesUseCase().execute([], prototype_declaration=declaration)
    with pytest.raises(WorkflowError):
        PrototypePolicy.state(GraphState(patient_case_mode=True, prototype_declaration="synthetic"))


@pytest.mark.parametrize("provider,adapter", [("openai", "ChatOpenAI"), ("gemini", "ChatGoogleGenerativeAI")])
def test_cached_provider_rechecks_mode_and_prompt_before_invocation(monkeypatch, provider, adapter):
    settings = llm.get_settings().model_copy(update={"execution_mode": "public_prototype", "llm_provider": provider})
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr("app.application.services.prototype_policy.get_settings", lambda: settings)
    monkeypatch.setattr(llm, adapter, lambda **kwargs: FakeListChatModel(responses=["Allowed", "Never"], callbacks=kwargs["callbacks"]))
    llm._configured_llm.cache_clear()
    try:
        model = llm.get_llm()
        assert model.invoke([HumanMessage(content="Summarize a synthetic guideline.")]).content == "Allowed"
        assert model.i == 1
        with pytest.raises(WorkflowError):
            model.invoke([HumanMessage(content="Confidential patient case.")])
        assert model.i == 1
        settings.execution_mode = "professional"
        with pytest.raises(WorkflowError):
            llm.get_llm()
        with pytest.raises(WorkflowError):
            model.invoke([HumanMessage(content="Synthetic guideline.")])
        assert model.i == 1
    finally:
        llm._configured_llm.cache_clear()


def test_template_ingestion_requires_declaration_and_screens_notes(workspace):
    client, repository = workspace
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("ppt/presentation.xml", "<presentation/>")
        archive.writestr("ppt/notesSlides/notesSlide1.xml", "<notes>Confidential patient case.</notes>")
    files = {"file": ("template.pptx", buffer.getvalue(), "application/octet-stream")}
    assert client.post("/users/synthetic-owner/templates", files=files).status_code == 422
    response = client.post("/users/synthetic-owner/templates", files=files, data={"prototype_declaration": "synthetic", "external_processing_acknowledged": "true"})
    assert response.status_code == 409
    assert repository.list_presentation_templates("synthetic-owner") == []
    assert list(repository.templates_path.iterdir()) == []


def test_synthetic_template_declaration_survives_restart_and_legacy_is_unavailable(workspace):
    client, repository = workspace
    from app.tests.test_pptx_sources import deck
    buffer = BytesIO(deck())
    response = client.post(
        "/users/synthetic-owner/templates",
        files={"file": ("synthetic.pptx", buffer.getvalue(), "application/octet-stream")},
        data={"prototype_declaration": "synthetic", "external_processing_acknowledged": "true"},
    )
    assert response.status_code == 200
    template_id = response.json()["id"]
    restored = UserSessionRepository(repository.database_path)
    assert restored.presentation_template_source("synthetic-owner", template_id)._original_content == buffer.getvalue()
    # Simulate metadata from before declaration support; never auto-approve it.
    with restored._connect() as connection:
        connection.execute("UPDATE presentation_templates SET prototype_declaration = NULL WHERE template_id = ?", (template_id,))
    assert restored.presentation_template_source("synthetic-owner", template_id) is None
