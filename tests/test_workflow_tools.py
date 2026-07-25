from app.ai.workflows.graph_state import GraphState
from app.ai.workflows.tools import collect_context, create_presentation, validate_context
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType


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
