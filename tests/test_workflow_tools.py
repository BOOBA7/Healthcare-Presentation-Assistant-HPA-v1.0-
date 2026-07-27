import pytest

from app.ai.workflows.graph_state import GraphState
from app.ai.workflows.tools import (
    collect_context,
    create_presentation,
    validate_context,
    validate_final_presentation,
    validate_slides,
)
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.models.slide import Slide
from app.application.use_cases.workflow_steps import ReviewSlideUseCase
from app.application.use_cases.workflow_steps import (
    BuildBlueprintWorkflowUseCase,
    RecordProfessionalScopeUseCase,
)
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.application.use_cases.remove_resource import RemoveResourceUseCase
from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource
from app.domain.models.agenda import Agenda
from app.domain.models.user_profile import UserProfile
from app.domain.enums.workflow_status import WorkflowStatus
from app.domain.exceptions.workflow_error import WorkflowError
from pptx import Presentation as PowerPoint


def test_context_can_create_a_presentation_without_a_live_llm():
    state = collect_context.func(
        GraphState(user_profile=UserProfile(professional_role="biologist", preferred_language="ar")),
        topic="Depression",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.FRENCH,
        duration_minutes=20,
        objective="Review novel treatment strategies",
    )

    state = validate_context.func(state)
    state = create_presentation.func(state)

    assert state.presentation is not None
    assert state.presentation.title == "Depression"
    assert state.presentation.owner_profile.professional_role == "biologist"


def test_final_approval_requires_slide_approval_first():
    state = GraphState()
    state.presentation = type("Presentation", (), {"slides": [Slide(slide_number=1, title="Test")], "state": type("State", (), {"slides_validated": False, "presentation_validated": False, "workflow_status": WorkflowStatus.AWAITING_SLIDE_APPROVAL})()})()

    state = ReviewSlideUseCase().execute(state, index=0, comments="Approved")
    state = validate_slides.func(state, approved=True)
    state = validate_final_presentation.func(state, approved=True)

    assert state.presentation.state.slides_validated
    assert state.presentation.state.presentation_validated


def test_veterinarian_profile_requires_scope_clarification_before_blueprint_generation():
    state = collect_context.func(
        GraphState(user_profile=UserProfile(professional_role="veterinarian", preferred_language="fr")),
        topic="Depression",
        audience=AudienceType.GENERAL_PRACTITIONER,
        presentation_type=PresentationType.LECTURE,
        language=Language.FRENCH,
        duration_minutes=20,
        objective="Review treatment guidelines",
    )
    state = create_presentation.func(validate_context.func(state))
    state.presentation.resources = [
        Resource(
            id="apa-pdf",
            filename="apa-depression-guideline.pdf",
            file_type=ResourceType.PDF,
            extracted_pages=[{"page": 1, "text": "Depression treatment guideline for primary care."}],
            is_validated=True,
        )
    ]
    state.presentation.state.resources_validated = True
    state.presentation.state.workflow_status = WorkflowStatus.BLUEPRINT_GENERATION

    with pytest.raises(WorkflowError, match="human healthcare audience"):
        BuildBlueprintWorkflowUseCase().execute(state)

    assert state.presentation.state.workflow_status == WorkflowStatus.AWAITING_SCOPE_CLARIFICATION
    state = RecordProfessionalScopeUseCase().execute(
        state,
        "I am a medical representative with veterinary training and present human-health information.",
    )

    assert state.presentation.professional_scope is not None
    assert state.presentation.state.workflow_status == WorkflowStatus.BLUEPRINT_GENERATION


def test_scope_clarification_resumes_slide_generation_when_blueprint_was_already_approved():
    state = GraphState()
    state.presentation = type(
        "Presentation",
        (),
        {
            "state": type(
                "State",
                (),
                {
                    "workflow_status": WorkflowStatus.AWAITING_SCOPE_CLARIFICATION,
                    "blueprint_validated": True,
                },
            )(),
            "professional_scope": None,
        },
    )()

    state = RecordProfessionalScopeUseCase().execute(
        state,
        "I am a medical representative with veterinary training for this human-health topic.",
    )

    assert state.presentation.state.workflow_status == WorkflowStatus.SLIDE_GENERATION


def test_deleting_a_resource_resets_generated_content_and_approvals():
    state = collect_context.func(
        GraphState(),
        topic="Depression",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.FRENCH,
        duration_minutes=20,
        objective="Review treatment guidelines",
    )
    presentation = create_presentation.func(validate_context.func(state)).presentation
    presentation.resources = [
        Resource(
            id="resource-1",
            filename="guideline.pdf",
            file_type=ResourceType.PDF,
            extracted_pages=[{"page": 1, "text": "Guideline evidence."}],
            is_validated=True,
        )
    ]
    presentation.state.resources_validated = True
    presentation.state.blueprint_validated = True
    presentation.state.slides_validated = True
    presentation.state.presentation_validated = True
    presentation.slides = [Slide(slide_number=1, title="Evidence")]

    RemoveResourceUseCase().execute(presentation, "resource-1")

    assert presentation.resources == []
    assert presentation.blueprint is None
    assert presentation.slides == []
    assert not presentation.state.resources_validated
    assert presentation.state.workflow_status == WorkflowStatus.AWAITING_RESOURCE_UPLOAD


def test_powerpoint_always_ends_with_user_validated_resources(tmp_path):
    state = collect_context.func(
        GraphState(),
        topic="Depression",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.FRENCH,
        duration_minutes=20,
        objective="Review novel treatment strategies",
    )
    state = create_presentation.func(validate_context.func(state))
    presentation = state.presentation
    presentation.slides = [
        Slide(
            slide_number=1,
            title="Introduction",
            key_messages=["Message"],
            reference_details=[
                {
                    "title": "Clinical guideline",
                    "resource_id": "resource-1",
                    "page": 1,
                    "evidence_excerpt": "Evidence supporting clinical management.",
                }
            ],
        )
    ]
    presentation.resources = [
        Resource(
            id="resource-1",
            filename="guideline.pdf",
            title="Clinical guideline",
            source="WHO",
            file_type=ResourceType.PDF,
            extracted_text="Evidence",
            extracted_pages=[{"page": 1, "text": "Evidence supporting clinical management."}],
            is_validated=True,
        )
    ]
    presentation.state.resources_validated = True
    presentation.state.presentation_validated = True
    presentation.agenda = Agenda(items=["Introduction", "Treatment"], is_validated=True)

    custom_template = tmp_path / "custom-template.pptx"
    base_deck = PowerPoint()
    base_deck.slides.add_slide(base_deck.slide_layouts[0])
    base_deck.save(custom_template)

    path = ExportPowerPointUseCase().execute(presentation, tmp_path, custom_template)
    deck = PowerPoint(path)
    last_slide_text = " ".join(shape.text for shape in deck.slides[-1].shapes if hasattr(shape, "text"))

    assert len(deck.slides) == 4  # title, mandatory agenda, content, resources
    assert deck.slides[1].shapes[1].text == "Agenda"
    assert deck.slides[-1].shapes[1].text == "Ressources et validation"
    assert "guideline" in last_slide_text
    assert "validées par l’utilisateur" in last_slide_text
