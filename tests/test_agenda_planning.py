"""Focused provider-free coverage for phase 07.1 Agenda planning."""

import pytest

from app.ai.schemas.agenda_schema import AgendaSchema
from app.application.services.evidence_coverage import EvidenceCoverageService
from app.application.services.presentation_context_policy import PresentationContextPolicy
from app.application.services.workflow_view import WorkflowViewBuilder
from app.application.use_cases.build_agenda import BuildAgendaUseCase
from app.application.use_cases.build_blueprint import BuildBlueprintUseCase
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.models.agenda import Agenda
from app.domain.models.resource_chunk import ResourceChunk
from app.domain.models.professional_scope_declaration import ProfessionalScopeDeclaration
from app.domain.value_objects.presentation_context import PresentationContext
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.ai.workflows.graph_state import GraphState
from app.tests.source_fixtures import dated_resource


class FixedAgendaChain:
    def invoke(self, presentation, resources, chunks):
        return AgendaSchema(sections=["Evidence overview", "Clinical application"])


def scenario():
    context = PresentationContext(
        topic="Asthma controller therapy",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=20,
        objective="Compare controller therapy; Explain inhaler adherence",
        target_slide_count=9,
        special_instructions="Advanced detailed review",
        professional_scope="specialist teaching",
        is_multidisciplinary=False,
    )
    presentation = CreatePresentationUseCase().execute(context.topic, context)
    presentation.prototype_declaration = "synthetic"
    presentation.professional_scope_declaration = ProfessionalScopeDeclaration(
        actor_user_id="owner",
        context_digest=PresentationContextPolicy.digest(context),
        is_multidisciplinary=False,
        declared_role="Specialist educator",
        delivery_purpose="Teach specialists using synthetic evidence.",
        confirmed_within_scope=True,
    )
    presentation.state.resources_validated = True
    presentation.state.workflow_status = WorkflowStatus.BLUEPRINT_GENERATION
    resource = dated_resource(id="r1", filename="asthma.pdf", title="Asthma guideline", is_validated=True)
    chunks = [
        ResourceChunk(resource_id="r1", page=1, position=0, title="Asthma guideline", text="Advanced specialist guidance can compare asthma controller therapy options with detailed clinical recommendations for maintenance care."),
        ResourceChunk(resource_id="r1", page=2, position=0, title="Asthma guideline", text="Advanced specialist training should explain inhaler adherence using detailed assessment, education, monitoring, and shared decision methods."),
    ]
    presentation.resources = [resource]
    return presentation, [resource], chunks


def test_agenda_generation_requires_current_sufficient_coverage():
    presentation, resources, chunks = scenario()
    with pytest.raises(ValueError, match="Assess evidence coverage"):
        BuildAgendaUseCase(chain=FixedAgendaChain()).execute(presentation, resources, chunks)


def test_agenda_generation_creates_only_editable_high_level_sections():
    presentation, resources, chunks = scenario()
    presentation.evidence_coverage = EvidenceCoverageService().assess(presentation, resources, chunks)

    result = BuildAgendaUseCase(chain=FixedAgendaChain()).execute(presentation, resources, chunks)

    assert result.agenda == Agenda(items=["Evidence overview", "Clinical application"])
    assert result.blueprint is None
    assert result.state.workflow_status == WorkflowStatus.AWAITING_AGENDA_APPROVAL


def test_blueprint_generation_cannot_bypass_agenda_approval():
    presentation, resources, chunks = scenario()
    presentation.evidence_coverage = EvidenceCoverageService().assess(presentation, resources, chunks)
    presentation.agenda = Agenda(items=["Evidence overview"])

    with pytest.raises(Exception, match="approve the Agenda"):
        BuildBlueprintUseCase().execute(presentation, resources, chunks)


def test_workflow_exposes_agenda_then_blueprint_in_order():
    presentation, resources, chunks = scenario()
    presentation.evidence_coverage = EvidenceCoverageService().assess(presentation, resources, chunks)
    state = GraphState(presentation=presentation, resource_library=resources, resource_chunks=chunks)
    assert WorkflowViewBuilder.build(state)["allowed_actions"] == ["generate_agenda"]

    presentation.agenda = Agenda(items=["Evidence overview"], is_validated=True)
    assert WorkflowViewBuilder.build(state)["allowed_actions"] == ["generate_blueprint"]
