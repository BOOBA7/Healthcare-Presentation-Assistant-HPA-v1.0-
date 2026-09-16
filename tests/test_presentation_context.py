"""FR-03 / slice 02.1: explicit synthetic context and durable human attestations."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.interfaces.api import main as api
from app.interfaces.api.routers import jobs
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.application.services.presentation_context_policy import PresentationContextPolicy
from app.application.services.production_evidence_gate import ProductionEvidenceGate
from app.domain.exceptions.workflow_error import WorkflowError


CONTEXT = {
    "topic": "Public teaching example", "audience": "general_practitioner",
    "presentation_type": "Lecture", "language": "French", "duration_minutes": 15,
    "objective": "Explain and compare the supplied public sources.",
    "target_slide_count": 12, "special_instructions": "None",
    "professional_scope": "Teaching public evidence within my specialty.",
    "is_multidisciplinary": True, "confirmed_within_scope": True,
    "confirmed_multidisciplinary": True,
}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "context.sqlite3")
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    def no_provider(*args, **kwargs):
        pytest.fail("This context operation must not access a provider")
    monkeypatch.setattr(api, "get_agent", no_provider)
    client = TestClient(api.app)
    token = client.post("/auth/register", json={
        "user_id": "professor", "password": "synthetic-password",
        "professional_role": "professor_medicine", "preferred_language": "fr",
    }).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.post("/projects", json={
        "user_id": "professor", "project_id": "teaching", "prototype_declaration": "synthetic",
        "external_processing_acknowledged": True,
    }).status_code == 200
    return client, repository, "/projects/professor/teaching"


@pytest.mark.parametrize("field", list(CONTEXT))
def test_missing_required_fields_are_refused_without_state_or_approval(workspace, field):
    client, repository, path = workspace
    body = {key: value for key, value in CONTEXT.items() if key != field}
    # Competence confirmation has a false default, which still fails for multidisciplinary input.
    response = client.post(path + "/presentation/setup", json=body)
    assert response.status_code in (409, 422)
    assert repository.load("professor", "teaching")[1].presentation is None
    assert len(repository.list_events("professor", "teaching")) == 2


@pytest.mark.parametrize("field,value", [
    ("topic", "   "), ("objective", "\n"), ("special_instructions", " "),
    ("professional_scope", "            "), ("target_slide_count", 0),
    ("target_slide_count", 201), ("target_slide_count", True), ("target_slide_count", 1.5),
    ("duration_minutes", 0), ("duration_minutes", 481),
    ("is_multidisciplinary", "false"), ("confirmed_within_scope", False),
    ("confirmed_within_scope", "true"), ("confirmed_multidisciplinary", False),
])
def test_api_cannot_bypass_context_validation(workspace, field, value):
    client, repository, path = workspace
    response = client.post(path + "/presentation/setup", json={**CONTEXT, field: value})
    assert response.status_code in (409, 422)
    assert repository.load("professor", "teaching")[1].presentation is None


@pytest.mark.parametrize("language,multidisciplinary", [("French", True), ("English", False)])
def test_confirmation_is_bound_to_actor_context_and_restart(workspace, language, multidisciplinary):
    client, repository, path = workspace
    body = {**CONTEXT, "language": language, "is_multidisciplinary": multidisciplinary,
            "confirmed_multidisciplinary": multidisciplinary}
    response = client.post(path + "/presentation/setup", json=body)
    assert response.status_code == 200
    assert response.json()["workflow"]["next_action"]["action"] == "select_resource"
    state = repository.load("professor", "teaching")[1]
    PresentationContextPolicy.require(state.presentation)
    declaration = state.presentation.professional_scope_declaration
    assert declaration.actor_user_id == "professor"
    assert declaration.declared_at.tzinfo is not None
    assert declaration.context_digest == PresentationContextPolicy.digest(state.presentation.context)
    restored = UserSessionRepository(repository.database_path).load("professor", "teaching")[1]
    assert restored.presentation == state.presentation
    event = repository.list_events("professor", "teaching")[0]
    assert event["payload"]["actor_user_id"] == "professor"
    assert event["payload"]["approval"] is True
    assert event["payload"]["context_digest"] == declaration.context_digest
    assert event["payload"]["confirmed_multidisciplinary"] is multidisciplinary
    assert "professional_scope" not in event["payload"]  # no duplicate raw explanation
    assert client.post(path + "/presentation/setup", json=body).status_code == 409


def test_legacy_resume_completion_preserves_progress_and_blocks_bypasses(workspace):
    client, repository, path = workspace
    assert client.post(path + "/presentation/setup", json=CONTEXT).status_code == 200
    thread, state = repository.load("professor", "teaching")
    state.presentation.context.target_slide_count = None
    state.presentation.context.special_instructions = None
    state.presentation.professional_scope_declaration = None
    state.presentation.state.resources_validated = True
    repository.save("professor", "teaching", thread, state)
    before = repository.load("professor", "teaching")[1]
    resumed = client.get(path)
    assert resumed.status_code == 200
    assert resumed.json()["workflow"]["blockers"][0]["code"] == "PRESENTATION_CONTEXT_REQUIRED"
    assert resumed.json()["workflow"]["next_action"] == {
        "action": "setup_presentation",
        "message": resumed.json()["workflow"]["blockers"][0]["message"],
        "blocker_code": "PRESENTATION_CONTEXT_REQUIRED",
    }
    assert client.post(path + "/resources/validate").status_code == 409
    assert client.post("/api/v1" + path + "/blueprint/jobs").status_code == 409
    with pytest.raises(HTTPException) as refused:
        jobs._load_workflow_state(repository, "professor", "teaching")
    assert refused.value.detail["code"] == "PRESENTATION_CONTEXT_REQUIRED"
    assert ProductionEvidenceGate().block_reason(before, "Explain the evidence")
    assert client.post(path + "/presentation/setup", json={**CONTEXT, "topic": "Replacement"}).status_code == 409
    assert client.post(path + "/presentation/setup", json=CONTEXT).status_code == 200
    after = repository.load("professor", "teaching")[1]
    assert after.presentation.id == before.presentation.id
    assert after.presentation.state.resources_validated is True
    assert after.presentation.state.workflow_status == before.presentation.state.workflow_status
    assert after.presentation.slides == before.presentation.slides
    assert after.presentation.context == after.presentation.state.context == after.presentation_context
    PresentationContextPolicy.require(after.presentation)
    assert repository.list_events("professor", "teaching")[0]["event_type"] == "PRESENTATION_CONTEXT_COMPLETED"


def test_changed_context_invalidates_confirmation_even_with_legacy_scope_text(workspace):
    client, repository, path = workspace
    assert client.post(path + "/presentation/setup", json=CONTEXT).status_code == 200
    thread, state = repository.load("professor", "teaching")
    state.presentation.context.objective = "Different learning objectives"
    state.presentation.professional_scope = "Previously confirmed legacy text"
    with pytest.raises(WorkflowError):
        PresentationContextPolicy.require(state.presentation)
    repository.save("professor", "teaching", thread, state)
    assert client.post(path + "/resources/validate").status_code == 409


def test_failed_atomic_save_never_records_confirmation(workspace, monkeypatch):
    client, repository, path = workspace
    def fail_save(*args, **kwargs):
        raise WorkflowError("SYNTHETIC_SAVE_FAILURE", "Synthetic storage failure")
    monkeypatch.setattr(repository, "save_with_event", fail_save)
    response = client.post(path + "/presentation/setup", json=CONTEXT)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SYNTHETIC_SAVE_FAILURE"
    assert repository.load("professor", "teaching")[1].presentation is None
    assert len(repository.list_events("professor", "teaching")) == 2


def test_direct_generation_boundaries_reject_unconfirmed_context(workspace):
    from app.ai.chains.blueprint_chain import BlueprintChain
    from app.ai.chains.slide_chain import SlideChain

    client, repository, path = workspace
    assert client.post(path + "/presentation/setup", json=CONTEXT).status_code == 200
    presentation = repository.load("professor", "teaching")[1].presentation
    presentation.professional_scope_declaration = None
    # Bypass constructors: any access to an LLM or prompt builder would fail this test.
    with pytest.raises(WorkflowError):
        BlueprintChain.__new__(BlueprintChain).invoke(presentation)
    with pytest.raises(WorkflowError):
        SlideChain.__new__(SlideChain).invoke(presentation, None)


def test_api_cannot_supply_the_confirmation_identity_or_timestamp(workspace):
    client, repository, path = workspace
    response = client.post(path + "/presentation/setup", json={
        **CONTEXT, "actor_user_id": "impostor", "declared_at": "2000-01-01T00:00:00Z",
        "professional_scope_declaration": {"actor_user_id": "impostor"},
    })
    assert response.status_code == 200
    declaration = repository.load("professor", "teaching")[1].presentation.professional_scope_declaration
    assert declaration.actor_user_id == "professor"
    assert declaration.declared_at.year != 2000


def test_concurrent_context_save_cannot_overwrite_newer_work(workspace, monkeypatch):
    client, repository, path = workspace
    original = repository.save_with_event
    def concurrent_save(user_id, project_id, thread, state, *args, **kwargs):
        current_thread, current = repository.load(user_id, project_id)
        current.conversation_memory_summary = "Newer synthetic human work"
        repository.save(user_id, project_id, current_thread, current)
        return original(user_id, project_id, thread, state, *args, **kwargs)
    monkeypatch.setattr(repository, "save_with_event", concurrent_save)
    response = client.post(path + "/presentation/setup", json=CONTEXT)
    assert response.status_code == 409
    current = repository.load("professor", "teaching")[1]
    assert current.conversation_memory_summary == "Newer synthetic human work"
    assert current.presentation is None
    assert len(repository.list_events("professor", "teaching")) == 2


def test_web_form_exposes_explicit_context_in_both_mvp_languages():
    from pathlib import Path

    script = Path("app/interfaces/web/app.js").read_text()
    for selector in ("setup-slides", "setup-instructions", "setup-scope", "setup-multidisciplinary",
                     "setup-scope-confirmed", "setup-competence"):
        assert f'id="{selector}"' in script
    assert 'setupSlides:"Target slide count' in script
    assert 'setupSlides:"Nombre de slides' in script
    assert 'setupChoose:"Choose explicitly"' in script
    assert 'setupChoose:"Choisissez explicitement"' in script
    assert 'id="setup-scope-confirmed" type="checkbox" checked' not in script
    assert 'id="setup-competence" type="checkbox" checked' not in script


def test_web_displays_server_owned_next_action_and_blockers_in_french_and_english():
    from pathlib import Path

    script = Path("app/interfaces/web/app.js").read_text()
    assert "function nextActionLabel(action)" in script
    assert "workflow.next_action" in script
    assert 'nextAllowedAction:"Next allowed action"' in script
    assert 'nextAllowedAction:"Prochaine action autorisée"' in script
    assert "blockers.map(blocker" in script
