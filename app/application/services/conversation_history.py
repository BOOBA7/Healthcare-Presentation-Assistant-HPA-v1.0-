"""Provider-independent conversation transcript used by the two user interfaces."""

from langchain_core.messages import AIMessage, HumanMessage

from app.ai.workflows.graph_state import GraphState
from app.domain.models.conversation_turn import ConversationTurn


def message_text(message: object) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ).strip()
    return ""


def ensure_history(state: GraphState) -> bool:
    """Migrate existing LangChain messages once, without duplicating new turns."""
    if state.conversation_history:
        return False
    for message in state.messages:
        text = message_text(message)
        if not text:
            continue
        if isinstance(message, HumanMessage):
            state.conversation_history.append(ConversationTurn(role="user", text=text))
        elif isinstance(message, AIMessage):
            state.conversation_history.append(ConversationTurn(role="assistant", text=text))
    return bool(state.conversation_history)


def add_turn(state: GraphState, role: str, text: str) -> None:
    """Append a presentation-assistant turn only."""
    normalized = text.strip()
    if not normalized:
        return
    state.conversation_history.append(ConversationTurn(role=role, text=normalized))


def add_resource_turn(state: GraphState, role: str, text: str) -> None:
    """Append a PDF-library exploration turn without changing agent history."""
    normalized = text.strip()
    if not normalized:
        return
    state.resource_conversation_history.append(ConversationTurn(role=role, text=normalized))
