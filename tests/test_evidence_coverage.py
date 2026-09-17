"""Behavioural coverage for the deterministic pre-Agenda evidence gate."""

import pytest

from app.ai.workflows.graph_state import GraphState
from app.application.services.evidence_coverage import EvidenceCoverageService
from app.application.use_cases.build_blueprint import BuildBlueprintUseCase
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.models.resource_chunk import ResourceChunk
from app.domain.value_objects.presentation_context import PresentationContext
from app.tests.source_fixtures import dated_resource
from app.interfaces.storage.user_session_repository import UserSessionRepository
from app.domain.exceptions.concurrent_modification_error import ConcurrentModificationError
from app.domain.exceptions.workflow_error import WorkflowError


def scenario():
    context = PresentationContext(topic="Asthma controller therapy", audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE, language=Language.ENGLISH, duration_minutes=20,
        objective="Compare controller therapy; Explain inhaler adherence", target_slide_count=9,
        special_instructions="Advanced detailed review", professional_scope="specialist teaching", is_multidisciplinary=False)
    presentation = CreatePresentationUseCase().execute(context.topic, context)
    resource = dated_resource(id="r1", filename="asthma.pdf", title="Asthma guideline", is_validated=True)
    chunks = [
        ResourceChunk(resource_id="r1", page=1, position=0, title="Asthma guideline", text="Advanced specialist guidance can compare asthma controller therapy options with detailed clinical recommendations for maintenance care."),
        ResourceChunk(resource_id="r1", page=2, position=0, title="Asthma guideline", text="Advanced specialist training should explain inhaler adherence using detailed assessment, education, monitoring, and shared decision methods."),
    ]
    return presentation, [resource], chunks


def test_positive_assessment_covers_five_dimensions_without_claiming_scientific_validity(monkeypatch):
    presentation, resources, chunks = scenario()
    assessment = EvidenceCoverageService().assess(presentation, resources, chunks)
    presentation.evidence_coverage = assessment

    assert assessment.sufficient
    assert {result.dimension for result in assessment.results} == {"topic", "objective", "audience", "depth", "slide_count"}
    assert len([r for r in assessment.results if r.dimension == "objective"]) == 2
    assert all(result.passages for result in assessment.results)
    assert assessment.scientific_validity_reviewed is False


def test_partial_passages_are_not_pooled_and_each_gap_requests_a_resource():
    presentation, resources, _ = scenario()
    chunks = [
        ResourceChunk(resource_id="r1", page=1, position=0, title="Asthma guideline", text="Asthma background is discussed in a long passage that deliberately contains no management recommendation or audience statement."),
        ResourceChunk(resource_id="r1", page=2, position=0, title="Asthma guideline", text="Controller therapy options appear separately in another sufficiently long passage without the requested disease anchor or teaching depth."),
    ]
    assessment = EvidenceCoverageService().assess(presentation, resources, chunks)

    assert not assessment.sufficient
    assert not next(r for r in assessment.results if r.dimension == "topic").sufficient
    assert all(r.requested_resource for r in assessment.results if not r.sufficient)


def test_short_ambiguous_passages_and_unrealistic_slide_count_fail():
    presentation, resources, _ = scenario()
    presentation.context.target_slide_count = 40
    chunks = [ResourceChunk(resource_id="r1", page=1, position=0, title="Asthma guideline", text="Asthma controller therapy.")]
    assessment = EvidenceCoverageService().assess(presentation, resources, chunks)
    assert not assessment.sufficient
    assert not next(r for r in assessment.results if r.dimension == "slide_count").sufficient
    assert all(not r.passages for r in assessment.results)


def test_context_or_passage_change_makes_persisted_assessment_obsolete():
    presentation, resources, chunks = scenario()
    service = EvidenceCoverageService()
    presentation.evidence_coverage = service.assess(presentation, resources, chunks)
    presentation.context.objective = "Evaluate biologic eligibility"
    with pytest.raises(ValueError, match="obsolete"):
        service.require_current(presentation, resources, chunks)
    presentation, resources, chunks = scenario()
    presentation.evidence_coverage = service.assess(presentation, resources, chunks)
    chunks[0].text += " changed"
    with pytest.raises(ValueError, match="obsolete"):
        service.require_current(presentation, resources, chunks)


def test_direct_blueprint_call_cannot_create_agenda_without_current_coverage(monkeypatch):
    presentation, resources, chunks = scenario()
    presentation.state.resources_validated = True
    with pytest.raises(ValueError, match="Assess evidence coverage"):
        BuildBlueprintUseCase().execute(presentation, resources, chunks)


def persisted_scenario(tmp_path):
    presentation, _, chunks = scenario()
    presentation.state.resources_validated = True
    resource = dated_resource(id="r1", filename="asthma.pdf", title="Asthma guideline", is_validated=True,
                              extracted_pages=[{"page": c.page, "text": c.text} for c in chunks])
    resources = [resource]
    presentation.resources = [resource.model_copy(deep=True)]
    state = GraphState(prototype_declaration="synthetic", resource_library=resources, presentation=presentation)
    repository = UserSessionRepository(tmp_path / "coverage.sqlite3")
    repository.save_with_event("owner", "project", "thread", state, "SETUP", "owner")
    return repository


def test_assessment_is_atomic_durable_owner_scoped_and_revisioned(tmp_path):
    repository = persisted_scenario(tmp_path)
    _, initial = repository.load("owner", "project")
    _, assessed = repository.assess_evidence_coverage("owner", "project", initial.project_revision, "owner")
    reopened = UserSessionRepository(repository.database_path).load("owner", "project")[1]
    assert assessed.presentation.evidence_coverage.sufficient
    assert reopened.presentation.evidence_coverage == assessed.presentation.evidence_coverage
    with pytest.raises(ConcurrentModificationError):
        repository.assess_evidence_coverage("owner", "project", initial.project_revision, "owner")
    with pytest.raises(WorkflowError, match="Project not found"):
        repository.assess_evidence_coverage("intruder", "project", assessed.project_revision, "intruder")


def test_generic_save_cannot_fabricate_coverage_and_context_change_invalidates_it(tmp_path):
    repository = persisted_scenario(tmp_path)
    _, state = repository.load("owner", "project")
    _, state = repository.assess_evidence_coverage("owner", "project", state.project_revision, "owner")
    fabricated = state.model_copy(deep=True)
    fabricated.presentation.evidence_coverage.sufficient = False
    with pytest.raises(WorkflowError, match="authenticated evidence-coverage"):
        repository.save("owner", "project", "thread", fabricated)
    state.presentation.context.objective = "Evaluate biologic eligibility"
    repository.save("owner", "project", "thread", state)
    assert repository.load("owner", "project")[1].presentation.evidence_coverage is None


def test_audit_failure_rolls_back_coverage_assessment(tmp_path, monkeypatch):
    repository = persisted_scenario(tmp_path)
    _, state = repository.load("owner", "project")
    monkeypatch.setattr(repository, "_insert_event", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit unavailable")))
    with pytest.raises(RuntimeError, match="audit unavailable"):
        repository.assess_evidence_coverage("owner", "project", state.project_revision, "owner")
    reopened = UserSessionRepository(repository.database_path).load("owner", "project")[1]
    assert reopened.presentation.evidence_coverage is None
