"""FR-14/15/17: deterministic, provider-free evidence-safe slide generation."""

import pytest
from fastapi.testclient import TestClient

from app.ai.mappers.slide_mapper import SlideMapper
from app.ai.schemas.slide_schema import SlideReferenceSchema, SlideSchema
from app.application.use_cases.generate_slides import GenerateSlidesUseCase
from app.application.services.presentation_context_policy import PresentationContextPolicy
from app.application.validators.evidence_provenance_validator import EvidenceProvenanceValidator
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.enums.resource_type import ResourceType
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.validation_error import ValidationError
from app.domain.models.blueprint import Blueprint
from app.domain.models.professional_scope_declaration import ProfessionalScopeDeclaration
from app.domain.models.slide_outline import SlideOutline
from app.domain.value_objects.presentation_context import PresentationContext
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.ai.workflows.graph_state import GraphState
from app.interfaces.api import main as api
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.tests.source_fixtures import dated_resource


PASSAGE_A = "Synthetic response was 10 mg; the comparison reports no benefit and uncertainty remains."
PASSAGE_B = "Synthetic response was 12 mg; the comparison reports benefit and uncertainty remains."


def resource(identifier="source-a", passage=PASSAGE_A):
    return dated_resource(
        id=identifier,
        filename=f"{identifier}.pdf",
        title=f"Synthetic {identifier}",
        file_type=ResourceType.PDF,
        extracted_text=passage,
        extracted_pages=[{"page": 1, "text": passage}],
        is_validated=True,
    )


def reference(identifier, claim_id, passage, **changes):
    values = {
        "title": f"Synthetic {identifier}",
        "source": "Synthetic fixture",
        "year": 2024,
        "resource_id": identifier,
        "page": 1,
        "evidence_excerpt": passage,
        "claim_id": claim_id,
        "claim_text": "The synthetic response was reported.",
    }
    values.update(changes)
    return SlideReferenceSchema(**values)


def schema(number=1, references=None, note_references=None):
    return SlideSchema(
        slide_number=number,
        title="Synthetic result",
        objective="Review supplied synthetic evidence",
        key_messages=["The synthetic response was reported."],
        content="The synthetic response was reported.",
        speaker_notes="Explain only the supplied synthetic response.",
        references=references or [reference("source-a", "claim-a", PASSAGE_A)],
        speaker_note_references=note_references
        or [reference("source-a", "note-a", PASSAGE_A, claim_text="The supplied comparison reports uncertainty.")],
    )


def presentation(outline_count=1):
    context = PresentationContext(
        topic="Synthetic response",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=10,
        objective="Review supplied synthetic evidence",
        target_slide_count=10,
        special_instructions="Use only supplied synthetic evidence.",
        professional_scope="Teaching within my specialist scope.",
        is_multidisciplinary=False,
        confirmed_within_scope=True,
    )
    result = CreatePresentationUseCase().execute("Synthetic response", context)
    result.blueprint = Blueprint(
        title="Synthetic blueprint",
        learning_objective="Review evidence",
        target_number_of_slides=outline_count,
        storytelling="Evidence then conclusion",
        slides=[
            SlideOutline(
                slide_number=index,
                title=f"Synthetic result {index}",
                objective="Review supplied synthetic evidence",
                key_message="Synthetic response evidence",
            )
            for index in range(1, outline_count + 1)
        ],
        is_validated=True,
    )
    result.state.blueprint_validated = True
    result.state.workflow_status = WorkflowStatus.SLIDE_GENERATION
    result.professional_scope_declaration = ProfessionalScopeDeclaration(
        actor_user_id="owner",
        context_digest=PresentationContextPolicy.digest(result.context),
        is_multidisciplinary=False,
        confirmed_within_scope=True,
        declared_role="Synthetic specialist",
        delivery_purpose="Provider-free synthetic test presentation.",
    )
    return result


def test_claims_and_notes_keep_separate_exact_provenance_and_pending_note_approval():
    slide = SlideMapper().to_domain(schema())
    EvidenceProvenanceValidator().validate_slide(slide, [resource()], require_claims=True)

    assert slide.evidence_links[0].exact_passage == PASSAGE_A
    assert slide.speaker_note.evidence_links[0].exact_passage == PASSAGE_A
    assert slide.evidence_links[0].id != slide.speaker_note.evidence_links[0].id
    assert slide.evidence_links[0].provenance_verified
    assert slide.speaker_note.evidence_links[0].provenance_verified
    assert not slide.evidence_verified
    assert not slide.speaker_note.is_approved


def test_missing_value_is_preserved_but_an_extrapolated_value_is_rejected():
    missing = reference(
        "source-a",
        "claim-a",
        PASSAGE_A,
        claim_value=None,
        claim_unit=None,
        missing_value=True,
        claim_uncertainty="The requested value is absent from the supplied evidence.",
    )
    slide = SlideMapper().to_domain(schema(references=[missing]))
    EvidenceProvenanceValidator().validate_slide(slide, [resource()], require_claims=True)
    assert slide.claims[0].missing_value and slide.claims[0].value is None

    invented = missing.model_copy(
        update={"missing_value": False, "claim_value": "99", "claim_unit": "mg"}
    )
    with pytest.raises(ValidationError, match="value is absent"):
        EvidenceProvenanceValidator().validate_slide(
            SlideMapper().to_domain(schema(references=[invented])),
            [resource()],
            require_claims=True,
        )


def test_conflicting_positions_must_both_remain_visible_and_traceable():
    positions = [
        reference(
            "source-a", "position-a", PASSAGE_A, claim_value="10", claim_unit="mg",
            conflict_group_id="response-conflict", source_position="Source A: no benefit",
        ),
        reference(
            "source-b", "position-b", PASSAGE_B, claim_value="12", claim_unit="mg",
            conflict_group_id="response-conflict", source_position="Source B: benefit",
        ),
    ]
    slide = SlideMapper().to_domain(schema(references=positions))
    EvidenceProvenanceValidator().validate_slide(
        slide, [resource(), resource("source-b", PASSAGE_B)], require_claims=True
    )
    assert {claim.source_position for claim in slide.claims} == {
        "Source A: no benefit", "Source B: benefit"
    }

    unmarked = [
        item.model_copy(update={"conflict_group_id": None, "source_position": None})
        for item in positions
    ]
    with pytest.raises(ValidationError, match="conflicting supplied values"):
        EvidenceProvenanceValidator().validate_slide(
            SlideMapper().to_domain(schema(references=unmarked)),
            [resource(), resource("source-b", PASSAGE_B)],
            require_claims=True,
        )

    with pytest.raises(ValidationError, match="hide a source conflict"):
        EvidenceProvenanceValidator().validate_slide(
            SlideMapper().to_domain(schema(references=positions[:1])),
            [resource()],
            require_claims=True,
        )


def test_provider_failure_preserves_completed_slide_across_restart_and_retry_resumes(
    tmp_path, monkeypatch
):
    project = presentation(outline_count=2)
    project.resources = [resource()]
    generated = {1: schema(1), 2: schema(2)}

    class Sufficient:
        is_sufficient = True

        @staticmethod
        def diagnostic():
            return {"synthetic": True}

    monkeypatch.setattr(
        "app.application.use_cases.generate_slides.ProductionEvidenceGate.generation_assessment",
        lambda *args, **kwargs: Sufficient(),
    )
    use_case = object.__new__(GenerateSlidesUseCase)
    use_case.mapper = SlideMapper()
    use_case.evidence_validator = EvidenceProvenanceValidator()

    class FailingChain:
        def invoke(self, presentation, outline, **kwargs):
            if outline.slide_number == 2:
                raise RuntimeError("synthetic provider outage")
            return generated[outline.slide_number]

    use_case.chain = FailingChain()
    with pytest.raises(RuntimeError, match="provider outage"):
        use_case.execute(project)
    assert [slide.slide_number for slide in project.slides] == [1]

    repository = UserSessionRepository(tmp_path / "slide-recovery.sqlite3")
    repository.save(
        "owner",
        "project",
        "thread",
        GraphState(
            prototype_declaration="synthetic",
            presentation=project,
            resource_library=project.resources,
        ),
    )
    restarted = UserSessionRepository(repository.database_path)
    _, restored = restarted.load("owner", "project")
    project = restored.presentation
    restored_resources = restored.resource_library

    class RecoveredChain:
        calls = []

        def invoke(self, presentation, outline, **kwargs):
            self.calls.append(outline.slide_number)
            return generated[outline.slide_number]

    recovered = RecoveredChain()
    use_case.chain = recovered
    result = use_case.execute(project, restored_resources)
    assert recovered.calls == [2]
    assert [slide.slide_number for slide in result.slides] == [1, 2]


def test_direct_slide_job_api_cannot_bypass_blueprint_approval(tmp_path, monkeypatch):
    repository = UserSessionRepository(tmp_path / "slide-bypass.sqlite3")
    repository.register_user("owner", "owner-safe-password")
    project = presentation()
    project.state.blueprint_validated = False
    repository.save(
        "owner",
        "project",
        "thread",
        GraphState(prototype_declaration="synthetic", presentation=project),
    )
    monkeypatch.setattr(api, "get_repository", lambda: repository)
    response = TestClient(api.app).post(
        "/api/v1/projects/owner/project/slides/jobs",
        headers={"Authorization": f"Bearer {repository.create_auth_token('owner')}"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "BLUEPRINT_NOT_VALIDATED"


def test_invalid_generated_evidence_blocks_only_its_slide(monkeypatch):
    project = presentation(outline_count=2)
    project.resources = [resource()]

    class Sufficient:
        is_sufficient = True

        @staticmethod
        def diagnostic():
            return {"synthetic": True}

    monkeypatch.setattr(
        "app.application.use_cases.generate_slides.ProductionEvidenceGate.generation_assessment",
        lambda *args, **kwargs: Sufficient(),
    )
    use_case = object.__new__(GenerateSlidesUseCase)
    use_case.mapper = SlideMapper()
    use_case.evidence_validator = EvidenceProvenanceValidator()
    use_case.chain = type(
        "Chain",
        (),
        {"invoke": lambda self, presentation, outline, **kwargs: schema(
            outline.slide_number,
            references=(
                [reference("source-a", "valid", PASSAGE_A)]
                if outline.slide_number == 1
                else [reference("source-a", "invalid", "Invented passage long enough")]
            ),
        )},
    )()

    result = use_case.execute(project)
    assert [slide.slide_number for slide in result.slides] == [1]
    assert [blocker.slide_number for blocker in result.state.slide_generation_blockers] == [2]
    assert result.state.workflow_status == WorkflowStatus.AWAITING_SLIDE_RESOLUTION
