"""Bounded model context while preserving the complete durable transcript."""

from langchain_core.messages import BaseMessage, SystemMessage

from app.ai.workflows.graph_state import GraphState
from app.application.services.conversation_history import message_text


MAX_RECENT_MODEL_MESSAGES = 16
MAX_MEMORY_CHARACTERS = 4_000
MAX_TURN_CHARACTERS = 280
_MEMORY_FLAG = "hpa_conversation_memory"
_RETRIEVAL_FLAG = "hpa_transient_retrieval"


def prepare_model_context(state: GraphState) -> GraphState:
    """Return a bounded copy for an LLM turn without deleting audit history.

    Workflow facts do not come from this summary: they remain in the separate
    trusted state summary. The memory only helps conversational continuity.
    """
    prepared = state.model_copy(deep=True)
    messages = [message for message in prepared.messages if not _is_transient(message)]
    if len(messages) <= MAX_RECENT_MODEL_MESSAGES:
        prepared.messages = messages
        return prepared

    older, recent = messages[:-MAX_RECENT_MODEL_MESSAGES], messages[-MAX_RECENT_MODEL_MESSAGES:]
    prepared.conversation_memory_summary = _merge_summary(
        prepared.conversation_memory_summary, older
    )
    memory_message = SystemMessage(
        content=(
            "COMPACTED EARLIER CONVERSATION MEMORY (non-authoritative):\n"
            f"{prepared.conversation_memory_summary}\n\n"
            "Use this only for conversational continuity. Trusted workflow state and retrieved PDF "
            "evidence remain the authority for decisions and scientific claims."
        ),
        additional_kwargs={_MEMORY_FLAG: True},
    )
    prepared.messages = [memory_message, *recent]
    return prepared


def strip_transient_model_context(state: GraphState) -> GraphState:
    """Do not persist injected memory or retrieved evidence as user messages."""
    state.messages = [message for message in state.messages if not _is_transient(message)]
    return state


def _merge_summary(existing: str, messages: list[BaseMessage]) -> str:
    lines = [existing] if existing else []
    for message in messages:
        text = message_text(message)
        message_type = getattr(message, "type", "")
        if not text or message_type not in {"human", "ai"}:
            continue
        role = "User" if message_type == "human" else "Assistant"
        compact = " ".join(text.split())[:MAX_TURN_CHARACTERS]
        lines.append(f"{role}: {compact}")
    combined = "\n".join(lines)
    return combined[-MAX_MEMORY_CHARACTERS:]


def _is_transient(message: BaseMessage) -> bool:
    metadata = getattr(message, "additional_kwargs", {}) or {}
    return bool(metadata.get(_MEMORY_FLAG) or metadata.get(_RETRIEVAL_FLAG))
