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
from app.application.use_cases.export_powerpoint import ExportPowerPointUseCase
from app.domain.enums.resource_type import ResourceType
from app.domain.models.resource import Resource
from pptx import Presentation as PowerPoint


def test_context_can_create_a_presentation_without_a_live_llm():
    state = collect_context.func(
        GraphState(),
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


def test_final_approval_requires_slide_approval_first():
    state = GraphState()
    state.presentation = type("Presentation", (), {"slides": [Slide(slide_number=1, title="Test")], "state": type("State", (), {"slides_validated": False, "presentation_validated": False})()})()

    state = ReviewSlideUseCase().execute(state, index=0, comments="Approved")
    state = validate_slides.func(state, approved=True)
    state = validate_final_presentation.func(state, approved=True)

    assert state.presentation.state.slides_validated
    assert state.presentation.state.presentation_validated


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

    path = ExportPowerPointUseCase().execute(presentation, tmp_path)
    deck = PowerPoint(path)
    last_slide_text = " ".join(shape.text for shape in deck.slides[-1].shapes if hasattr(shape, "text"))

    assert deck.slides[-1].shapes.title.text == "Ressources et validation"
    assert "guideline" in last_slide_text
    assert "validées par l’utilisateur" in last_slide_text
