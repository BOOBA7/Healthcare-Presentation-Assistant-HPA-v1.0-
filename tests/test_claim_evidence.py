import pytest

from app.application.services.claim_evidence import ClaimEvidenceService
from app.domain.models.claim_evidence import EvidenceLink, MedicalClaim
from app.domain.models.slide import Slide
from app.tests.source_fixtures import dated_resource
from app.domain.enums.resource_type import ResourceType
from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.value_objects.presentation_context import PresentationContext
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.domain.exceptions.concurrent_modification_error import ConcurrentModificationError
from fastapi.testclient import TestClient
from app.interfaces.api import main as api
from app.application.use_cases.workflow_steps import EditSlideUseCase
from app.domain.enums.workflow_status import WorkflowStatus


def source(kind=ResourceType.PDF):
    return dated_resource(
        id="source-1", filename="evidence.pdf" if kind == ResourceType.PDF else "evidence.pptx",
        title="Synthetic evidence", file_type=kind, is_validated=True,
        extracted_text="10 mg uncertainty range DOI 10.1000/example https://example.invalid/study",
        extracted_pages=[{"page": 2, "text": "The synthetic intervention used 10 mg (range 8–12 mg). DOI 10.1000/example https://example.invalid/study"}],
    )


def claim(revision=1, text="The intervention used 10 mg"):
    return MedicalClaim(id="claim-1", revision=revision, text=text, value="10", unit="mg", uncertainty="range 8–12 mg")


def link(**changes):
    values = dict(
        id="link-1", revision=1, claim_id="claim-1", claim_revision=1,
        resource_id="source-1", resource_title="Synthetic evidence",
        location_kind="page", location_number=2,
        exact_passage="The synthetic intervention used 10 mg (range 8–12 mg).",
        doi="10.1000/example", url="https://example.invalid/study",
        semantic_review="approved",
    )
    values.update(changes)
    return EvidenceLink(**values)


def test_claim_link_requires_provenance_and_separate_human_relevance_review():
    slide = Slide(slide_number=1, title="Dose")
    ClaimEvidenceService.set_claims(slide, [claim()])
    ClaimEvidenceService.review_link(slide, link(), [source()], "professor")
    assert slide.evidence_verified
    assert slide.evidence_links[0].provenance_verified
    assert slide.evidence_links[0].semantic_reviewed_by == "professor"
    assert slide.claims[0].value == "10" and slide.claims[0].unit == "mg"


@pytest.mark.parametrize("change,message", [
    ({"resource_id": "wrong"}, "unknown resource"),
    ({"location_number": 9}, "does not exist"),
    ({"exact_passage": "A sufficiently long but absent passage"}, "not found"),
    ({"resource_title": "Invented"}, "title"),
    ({"doi": "10.9999/invented"}, "DOI"),
])
def test_wrong_provenance_is_refused(change, message):
    slide = Slide(slide_number=1, title="Dose", claims=[claim()])
    with pytest.raises(ValueError, match=message):
        ClaimEvidenceService.review_link(slide, link(**change), [source()], "professor")


def test_exact_but_semantically_pending_passage_is_not_approved_support():
    slide = Slide(slide_number=1, title="Dose", claims=[claim()])
    ClaimEvidenceService.review_link(slide, link(semantic_review="pending"), [source()], "professor")
    assert slide.evidence_links[0].provenance_verified
    assert not slide.evidence_verified


def test_claim_change_requires_revision_and_invalidates_approval():
    slide = Slide(slide_number=1, title="Dose", claims=[claim()])
    ClaimEvidenceService.review_link(slide, link(), [source()], "professor")
    with pytest.raises(ValueError, match="newer revision"):
        ClaimEvidenceService.set_claims(slide, [claim(text="Changed claim")])
    ClaimEvidenceService.set_claims(slide, [claim(revision=2, text="Changed claim")])
    assert not slide.evidence_verified
    assert slide.evidence_links[0].semantic_review == "pending"


def test_legacy_migration_is_lossless_idempotent_and_unassigned():
    payload = {"slide_number": 1, "title": "Legacy", "evidence_verified": True,
               "reference_details": [{"resource_id": "source-1", "page": 2,
                                       "evidence_excerpt": "The synthetic intervention used 10 mg."}]}
    first = Slide.model_validate(payload)
    second = Slide.model_validate(first.model_dump())
    assert first.legacy_references == second.legacy_references
    assert first.reference_details == payload["reference_details"]
    assert not first.claims and not first.evidence_links
    assert not first.evidence_verified and first.evidence_review_required


def persisted_project(tmp_path):
    repository = UserSessionRepository(tmp_path / "claims.sqlite3")
    context = PresentationContext(topic="Synthetic dose", audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE, language=Language.ENGLISH,
        duration_minutes=10, objective="Review synthetic dosing")
    presentation = CreatePresentationUseCase().execute("Synthetic dose", context)
    presentation.slides = [Slide(slide_number=1, title="Dose")]
    evidence = source()
    presentation.resources = [evidence]
    state = GraphState(presentation=presentation, resource_library=[evidence])
    repository.save("owner", "project", "thread", state)
    return repository, repository.load("owner", "project")[1]


def test_review_persists_across_restart_with_private_atomic_audit(tmp_path):
    repository, state = persisted_project(tmp_path)
    _, saved = repository.review_claim_evidence("owner", "project", state.project_revision, 0,
        [claim()], link(), "owner")
    restarted = UserSessionRepository(repository.database_path)
    _, restored = restarted.load("owner", "project")
    assert restored.presentation.slides[0].evidence_verified
    assert restored.presentation.slides[0].evidence_links[0].exact_passage.startswith("The synthetic")
    event = restarted.list_events("owner", "project")[-1]
    assert event["event_type"] == "CLAIM_EVIDENCE_REVIEWED"
    assert "exact_passage" not in event["payload"]
    assert saved.project_revision == restored.project_revision


def test_review_rejects_stale_revision_and_audit_failure_rolls_back(tmp_path, monkeypatch):
    repository, state = persisted_project(tmp_path)
    with pytest.raises(ConcurrentModificationError):
        repository.review_claim_evidence("owner", "project", state.project_revision - 1, 0,
            [claim()], link(), "owner")
    revision = repository.load("owner", "project")[1].project_revision
    monkeypatch.setattr(repository, "_insert_event", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("synthetic audit failure")))
    with pytest.raises(RuntimeError, match="audit failure"):
        repository.review_claim_evidence("owner", "project", revision, 0, [claim()], link(), "owner")
    restored = repository.load("owner", "project")[1]
    assert restored.project_revision == revision
    assert not restored.presentation.slides[0].claims


def test_direct_save_and_deserialized_object_cannot_forge_approved_support(tmp_path):
    repository, state = persisted_project(tmp_path)
    forged = link(provenance_verified=True, semantic_reviewed_by="forged-reviewer")
    state.presentation.slides[0].claims = [claim()]
    state.presentation.slides[0].evidence_links = [forged]
    state.presentation.slides[0].evidence_verified = True
    with pytest.raises(ValueError, match="claim-evidence review action"):
        repository.save("owner", "project", "thread", state)


def test_api_enforces_owner_and_returns_resolvable_claim_details(tmp_path, monkeypatch):
    repository, state = persisted_project(tmp_path)
    repository.register_user("owner", "owner-safe-password")
    repository.register_user("other", "other-safe-password")
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    client = TestClient(api.app)
    owner = {"Authorization": f"Bearer {repository.create_auth_token('owner')}"}
    other = {"Authorization": f"Bearer {repository.create_auth_token('other')}"}
    body = {"expected_revision": state.project_revision,
            "claims": [claim().model_dump(mode="json")],
            "link": link().model_dump(mode="json")}
    path = "/projects/owner/project/slides/0/claim-evidence"
    assert client.put(path, headers=other, json=body).status_code == 403
    response = client.put(path, headers=owner, json=body)
    assert response.status_code == 200
    slide = response.json()["presentation"]["slides"][0]
    assert slide["claims"][0]["id"] == "claim-1"
    assert slide["evidence_links"][0]["exact_passage"].startswith("The synthetic")


def test_slide_edit_invalidates_claim_revision_and_semantic_approval():
    slide = Slide(slide_number=1, title="Dose", content="Old", claims=[claim()])
    ClaimEvidenceService.review_link(slide, link(), [source()], "owner")
    context = PresentationContext(topic="Synthetic dose", audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE, language=Language.ENGLISH,
        duration_minutes=10, objective="Review synthetic dosing")
    presentation = CreatePresentationUseCase().execute("Synthetic dose", context)
    presentation.slides = [slide]
    presentation.state.workflow_status = WorkflowStatus.AWAITING_SLIDE_APPROVAL
    state = GraphState(presentation=presentation)
    EditSlideUseCase().execute(state, 0, title="Dose", objective="", key_messages=[],
        content="Changed", speaker_notes="", content_origin="user_edited")
    assert slide.claims[0].revision == 2
    assert slide.evidence_links[0].claim_revision == 1
    assert slide.evidence_links[0].semantic_review == "pending"
    assert not slide.evidence_verified
