from langchain_core.messages import AIMessage, HumanMessage

from app.ai.workflows.graph_state import GraphState
from app.application.services.conversation_memory import (
    MAX_RECENT_MODEL_MESSAGES,
    prepare_model_context,
    strip_transient_model_context,
)


def test_long_model_history_is_compacted_without_losing_durable_transcript():
    state = GraphState(
        messages=[
            HumanMessage(content=f"User turn {index}") if index % 2 == 0 else AIMessage(content=f"Assistant turn {index}")
            for index in range(MAX_RECENT_MODEL_MESSAGES + 6)
        ]
    )

    prepared = prepare_model_context(state)

    assert len(prepared.messages) == MAX_RECENT_MODEL_MESSAGES + 1
    assert "User turn 0" in prepared.conversation_memory_summary
    assert len(state.messages) == MAX_RECENT_MODEL_MESSAGES + 6

    stripped = strip_transient_model_context(prepared)

    assert len(stripped.messages) == MAX_RECENT_MODEL_MESSAGES
    assert stripped.conversation_memory_summary
