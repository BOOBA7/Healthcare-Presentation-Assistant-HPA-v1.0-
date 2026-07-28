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
from app.domain.models.slide_outline import SlideOutline
from app.domain.models.blueprint import Blueprint
from app.application.use_cases.workflow_steps import EditBlueprintItemUseCase, EditSlideUseCase, ReviewSlideUseCase
from app.application.use_cases.workflow_steps import (
    BuildBlueprintWorkflowUseCase,
    RecordProfessionalScopeUseCase,
)
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.application.use_cases.remove_resource import RemoveResourceUseCase
from app.application.use_cases.add_resource import AddResourceUseCase
from app.application.services.workflow_policy import WorkflowPolicy
from app.ai.agents.healthcare_presentation_agent import HealthcarePresentationAgent
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


def test_scope_explanation_is_persisted_once_before_the_agent_can_reply_again():
    """A model omission must not force the user to repeat the same explanation."""
    state = collect_context.func(
        GraphState(user_profile=UserProfile(professional_role="veterinarian", preferred_language="en")),
        topic="Depression",
        audience=AudienceType.GENERAL_PRACTITIONER,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=20,
        objective="Review approved product evidence",
    )
    state = create_presentation.func(validate_context.func(state))
    state.presentation.state.workflow_status = WorkflowStatus.AWAITING_SCOPE_CLARIFICATION
    explanation = "I am a human medical representative with veterinary training presenting Zoloft evidence."

    clarified = HealthcarePresentationAgent._record_scope_clarification_if_supplied(state, explanation)
    repeated = HealthcarePresentationAgent._record_scope_clarification_if_supplied(clarified, explanation)

    assert clarified.presentation.professional_scope == explanation
    assert clarified.presentation.state.workflow_status == WorkflowStatus.BLUEPRINT_GENERATION
    assert repeated.presentation.professional_scope == explanation
    assert repeated.presentation.state.workflow_status == WorkflowStatus.BLUEPRINT_GENERATION
    assert HealthcarePresentationAgent._scope_clarification_message_if_needed(clarified) is None


def test_scope_clarification_prompt_is_deterministic_and_concise():
    state = GraphState(user_profile=UserProfile(professional_role="veterinarian", preferred_language="en"))
    state.presentation = type(
        "Presentation",
        (),
        {"state": type("State", (), {"workflow_status": WorkflowStatus.AWAITING_SCOPE_CLARIFICATION})()},
    )()

    prompt = HealthcarePresentationAgent._scope_clarification_message_if_needed(state)

    assert prompt is not None
    assert "medical representative" in prompt
    assert "clinical guidance for human patients" not in prompt


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


def test_adding_a_resource_is_allowed_late_and_resets_dependent_output():
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
    presentation.blueprint = Blueprint(
        title="Blueprint",
        learning_objective="Objective",
        target_number_of_slides=1,
        storytelling="Story",
        slides=[SlideOutline(slide_number=1, title="Evidence", objective="Review", key_message="Message")],
    )
    presentation.agenda = Agenda(items=["Evidence"], is_validated=True)
    presentation.slides = [Slide(slide_number=1, title="Generated slide")]
    presentation.state.resources_validated = True
    presentation.state.blueprint_validated = True
    presentation.state.slides_validated = True
    presentation.state.presentation_validated = True
    presentation.state.workflow_status = WorkflowStatus.READY_FOR_EXPORT

    AddResourceUseCase().execute(
        presentation,
        Resource(
            id="resource-new",
            filename="new-guideline.pdf",
            file_type=ResourceType.PDF,
            extracted_pages=[{"page": 1, "text": "New evidence."}],
            is_validated=True,
        ),
    )

    assert [resource.id for resource in presentation.resources] == ["resource-new"]
    assert presentation.blueprint is None
    assert presentation.agenda is None
    assert presentation.slides == []
    assert not presentation.state.resources_validated
    assert presentation.state.workflow_status == WorkflowStatus.AWAITING_RESOURCE_VALIDATION
    assert WorkflowPolicy.requires_resource_validation(presentation)


def test_blueprint_request_surfaces_human_resource_validation_only_when_needed():
    state = collect_context.func(
        GraphState(),
        topic="Depression",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.FRENCH,
        duration_minutes=20,
        objective="Review treatment guidelines",
    )
    state = create_presentation.func(validate_context.func(state))
    state.presentation.resources = [
        Resource(
            id="resource-1",
            filename="guideline.pdf",
            file_type=ResourceType.PDF,
            extracted_pages=[{"page": 1, "text": "Guideline evidence."}],
            is_validated=True,
        )
    ]
    state.presentation.state.workflow_status = WorkflowStatus.AWAITING_RESOURCE_VALIDATION

    assert HealthcarePresentationAgent._needs_resource_validation_for_blueprint(
        state, "Génère le blueprint de ma présentation"
    )
    assert not HealthcarePresentationAgent._needs_resource_validation_for_blueprint(
        state, "Résume les points clés de cette ressource"
    )

    state.presentation.state.resources_validated = True
    assert not HealthcarePresentationAgent._needs_resource_validation_for_blueprint(
        state, "Génère le blueprint de ma présentation"
    )


def test_user_blueprint_edit_is_traced_and_invalidates_dependent_workflow_steps():
    state = collect_context.func(
        GraphState(),
        topic="Depression",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.FRENCH,
        duration_minutes=20,
        objective="Review treatment guidelines",
    )
    state = create_presentation.func(validate_context.func(state))
    presentation = state.presentation
    presentation.blueprint = Blueprint(
        title="Blueprint",
        learning_objective="Objective",
        target_number_of_slides=1,
        storytelling="Story",
        slides=[SlideOutline(slide_number=1, title="AI title", objective="AI objective", key_message="AI message", is_validated=True)],
        is_validated=True,
    )
    presentation.agenda = Agenda(items=["AI title"], is_validated=True)
    presentation.slides = [Slide(slide_number=1, title="Old generated slide")]
    presentation.state.blueprint_validated = True
    presentation.state.slides_validated = True
    presentation.state.presentation_validated = True
    presentation.state.workflow_status = WorkflowStatus.AWAITING_BLUEPRINT_APPROVAL

    EditBlueprintItemUseCase().execute(
        state,
        0,
        title="User title",
        objective="User objective",
        key_message="User message",
        content_origin="user_authored",
    )

    item = presentation.blueprint.slides[0]
    assert item.content_origin == "user_authored"
    assert item.original_ai_snapshot["title"] == "AI title"
    assert not item.is_validated
    assert not presentation.agenda.is_validated
    assert presentation.agenda.items == ["User title"]
    assert presentation.slides == []
    assert presentation.state.workflow_status == WorkflowStatus.AWAITING_AGENDA_APPROVAL


def test_user_slide_edit_requires_new_human_approval_without_inheriting_ai_evidence():
    state = GraphState()
    state.presentation = type(
        "Presentation",
        (),
        {
            "slides": [
                Slide(
                    slide_number=1,
                    title="AI title",
                    key_messages=["AI message"],
                    content="AI content",
                    evidence_verified=True,
                    is_validated=True,
                )
            ],
            "state": type(
                "State",
                (),
                {
                    "slides_validated": True,
                    "presentation_validated": True,
                    "workflow_status": WorkflowStatus.AWAITING_SLIDE_APPROVAL,
                },
            )(),
        },
    )()

    EditSlideUseCase().execute(
        state,
        0,
        title="Human title",
        objective="",
        key_messages=["Human message"],
        content="Human content",
        speaker_notes="",
        content_origin="user_edited",
    )

    slide = state.presentation.slides[0]
    assert slide.content_origin == "user_edited"
    assert slide.original_ai_snapshot["content"] == "AI content"
    assert not slide.evidence_verified
    assert slide.evidence_review_required
    assert not slide.is_validated
    assert not state.presentation.state.slides_validated


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


def test_powerpoint_labels_user_authored_slide_without_claiming_verified_evidence(tmp_path):
    state = collect_context.func(
        GraphState(),
        topic="Depression",
        audience=AudienceType.SPECIALIST,
        presentation_type=PresentationType.LECTURE,
        language=Language.ENGLISH,
        duration_minutes=10,
        objective="Review treatment options",
    )
    presentation = create_presentation.func(validate_context.func(state)).presentation
    presentation.slides = [
        Slide(
            slide_number=1,
            title="Clinical reflection",
            key_messages=["Human-authored message"],
            content_origin="user_authored",
            is_validated=True,
        )
    ]
    presentation.resources = [
        Resource(
            id="resource-1",
            filename="guideline.pdf",
            file_type=ResourceType.PDF,
            extracted_pages=[{"page": 1, "text": "Evidence."}],
            is_validated=True,
        )
    ]
    presentation.agenda = Agenda(items=["Clinical reflection"], is_validated=True)
    presentation.state.resources_validated = True
    presentation.state.presentation_validated = True

    path = ExportPowerPointUseCase().execute(presentation, tmp_path)
    deck = PowerPoint(path)
    content_text = " ".join(shape.text for shape in deck.slides[2].shapes if hasattr(shape, "text"))
    resources_text = " ".join(shape.text for shape in deck.slides[-1].shapes if hasattr(shape, "text"))

    assert "User-authored content" in content_text
    assert "Human-approved" in content_text
    assert "1 user-authored" in resources_text
