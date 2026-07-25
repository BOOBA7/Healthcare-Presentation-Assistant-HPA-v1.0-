from typing import Annotated

from langchain.tools import tool
from langchain_core.tools import InjectedToolArg

from app.ai.workflows.graph_state import GraphState
from app.application.use_cases.build_blueprint import BuildBlueprintUseCase
from app.application.use_cases.create_presentation import CreatePresentationUseCase
from app.application.use_cases.generate_slides import GenerateSlidesUseCase
from app.application.validators.audience_validator import AudienceValidator
from app.domain.enums.audience_type import AudienceType
from app.domain.enums.language import Language
from app.domain.enums.presentation_type import PresentationType
from app.domain.models.conversation_context import ConversationContext
from app.domain.value_objects.presentation_context import PresentationContext


@tool
def collect_context(
    state: Annotated[GraphState, InjectedToolArg],
    topic: str | None = None,
    audience: AudienceType | None = None,
    presentation_type: PresentationType | None = None,
    language: Language | None = None,
    duration_minutes: int | None = None,
    objective: str | None = None,
) -> GraphState:
    """Save presentation details explicitly provided by the user."""
    updates = {
        key: value
        for key, value in {
            "topic": topic, "audience": audience, "presentation_type": presentation_type,
            "language": language, "duration_minutes": duration_minutes, "objective": objective,
        }.items() if value is not None
    }
    context = ConversationContext.model_validate(
        {**state.conversation_context.model_dump(), **updates}
    )
    return state.model_copy(update={"conversation_context": context})


@tool
def validate_context(state: Annotated[GraphState, InjectedToolArg]) -> GraphState:
    """Validate the collected context before creating a presentation."""
    context = state.conversation_context
    if not context.is_complete():
        raise ValueError(f"Missing context fields: {', '.join(context.missing_fields())}")
    is_valid, messages = AudienceValidator().validate(context.audience)
    if not is_valid:
        raise ValueError("; ".join(messages))
    return state.model_copy(update={"presentation_context": PresentationContext(**context.model_dump())})


@tool
def create_presentation(state: Annotated[GraphState, InjectedToolArg]) -> GraphState:
    """Create a presentation from a validated context."""
    if state.presentation is not None:
        return state
    if state.presentation_context is None:
        raise ValueError("Validate the context before creating the presentation.")
    presentation = CreatePresentationUseCase().execute(
        title=state.presentation_context.topic,
        context=state.presentation_context,
    )
    return state.model_copy(update={"presentation": presentation})


@tool
def build_blueprint(state: Annotated[GraphState, InjectedToolArg]) -> GraphState:
    """Generate the presentation blueprint from the current presentation."""
    if state.presentation is None:
        raise ValueError("Create the presentation before generating its blueprint.")
    return state.model_copy(update={"presentation": BuildBlueprintUseCase().execute(state.presentation)})


@tool
def generate_slides(state: Annotated[GraphState, InjectedToolArg]) -> GraphState:
    """Generate all slides from the current presentation blueprint."""
    if state.presentation is None:
        raise ValueError("Create the presentation before generating slides.")
    return state.model_copy(update={"presentation": GenerateSlidesUseCase().execute(state.presentation)})


TOOLS = (collect_context, validate_context, create_presentation, build_blueprint, generate_slides)
