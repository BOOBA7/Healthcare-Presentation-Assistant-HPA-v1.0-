from app.ai.workflows.graph_state import GraphState
from app.ai.workflows.tools import collect_context, create_presentation, validate_context
from app.application.services.resource_library import ensure_resource_library, resolve_presentation_resources
from app.application.use_cases.manage_project_resources import (
    AddProjectResourceUseCase,
    AttachResourceToPresentationUseCase,
    DetachResourceFromPresentationUseCase,
)
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.enums.resource_type import ResourceType
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.models.resource import Resource


def _resource() -> Resource:
    return Resource(
        id="pdf-1",
        filename="guideline.pdf",
        file_type=ResourceType.PDF,
        extracted_pages=[{"page": 1, "text": "Evidence text."}],
        is_validated=True,
    )


def _presentation_state() -> GraphState:
    state = collect_context.func(
        GraphState(),
        topic="Topic",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=10,
        objective="Review evidence",
    )
    return create_presentation.func(validate_context.func(state))


def test_project_library_is_independent_from_presentation_creation():
    state = GraphState()
    AddProjectResourceUseCase().execute(state, _resource())

    assert [resource.id for resource in state.resource_library] == ["pdf-1"]
    assert state.presentation is None


def test_explicit_attachment_and_detachment_reset_only_production_state():
    state = _presentation_state()
    AddProjectResourceUseCase().execute(state, _resource())

    AttachResourceToPresentationUseCase().execute(state, "pdf-1")

    assert [resource.id for resource in state.presentation.resources] == ["pdf-1"]
    assert state.presentation.resources[0].extracted_text is None
    assert state.presentation.resources[0].extracted_pages == []
    assert resolve_presentation_resources(state)[0].extracted_pages == [{"page": 1, "text": "Evidence text."}]
    assert state.presentation.state.workflow_status == WorkflowStatus.AWAITING_RESOURCE_VALIDATION
    DetachResourceFromPresentationUseCase().execute(state, "pdf-1")
    assert not state.presentation.resources
    assert [resource.id for resource in state.resource_library] == ["pdf-1"]


def test_legacy_presentation_resources_are_migrated_to_library_once():
    state = _presentation_state()
    state.presentation.resources = [_resource()]

    assert ensure_resource_library(state) is True
    assert [resource.id for resource in state.resource_library] == ["pdf-1"]
    assert state.presentation.resources[0].extracted_pages == []
    assert ensure_resource_library(state) is False
