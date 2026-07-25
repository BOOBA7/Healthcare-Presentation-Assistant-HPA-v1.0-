from app.application.validators.audience_validator import AudienceValidator
from app.ai.workflows.graph_state import GraphState
from app.domain.value_objects.presentation_context import PresentationContext


class ValidatePresentationContextTool:
    """
    Validate the collected ConversationContext and convert it
    into a valid PresentationContext.
    """

    def __init__(self) -> None:
        self.audience_validator = AudienceValidator()

    def __call__(self, state: GraphState) -> GraphState:
        """
        Validate the collected conversation context and build
        the PresentationContext.
        """
        context = state.conversation_context

        if not context.is_complete():
            raise ValueError("PresentationContext is incomplete.")

        presentation_context = PresentationContext(
            topic=context.topic,
            audience=context.audience,
            presentation_type=context.presentation_type,
            language=context.language,
            duration_minutes=context.duration_minutes,
            objective=context.objective,
        )

        self.audience_validator.validate(presentation_context)
        state.presentation_context = presentation_context

        return state
