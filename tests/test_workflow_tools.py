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

    state = validate_slides.func(state, approved=True)
    state = validate_final_presentation.func(state, approved=True)

    assert state.presentation.state.slides_validated
    assert state.presentation.state.presentation_validated
