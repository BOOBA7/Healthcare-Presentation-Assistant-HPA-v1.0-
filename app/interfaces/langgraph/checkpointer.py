from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


@lru_cache
def get_checkpointer() -> InMemorySaver:
    """
    Return the LangGraph checkpointer.

    For the first version of the application,
    an in-memory checkpointer is used.

    This implementation can later be replaced
    by a persistent PostgreSQL checkpointer
    without changing the workflow code.
    """
    serializer = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("app.ai.workflows.graph_state", "GraphState"),
            ("app.domain.models.conversation_context", "ConversationContext"),
            ("app.domain.value_objects.presentation_context", "PresentationContext"),
            ("app.domain.models.presentation", "Presentation"),
            ("app.domain.models.presentation_state", "PresentationState"),
            ("app.domain.value_objects.audience_profile", "AudienceProfile"),
            ("app.domain.models.blueprint", "Blueprint"),
            ("app.domain.models.slide_outline", "SlideOutline"),
            ("app.domain.models.slide", "Slide"),
            ("app.domain.models.resource", "Resource"),
            ("app.domain.enums.audience_type", "AudienceType"),
            ("app.domain.enums.language", "Language"),
            ("app.domain.enums.presentation_type", "PresentationType"),
            ("app.domain.enums.workflow_step", "WorkflowStep"),
            ("app.domain.enums.presentation_status", "PresentationStatus"),
            ("app.domain.enums.resource_type", "ResourceType"),
            ("app.domain.enums.slide_status", "SlideStatus"),
        ]
    )
    return InMemorySaver(serde=serializer)
